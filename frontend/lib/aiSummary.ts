import {
  Account,
  BudgetData,
  ExpenseItem,
  ExpenseWithOccurrence,
  GoalProgress,
  IncomeItem,
  NetWorthSnapshot,
  RoadmapData,
} from "@/types";
import { ForecastingProjection } from "@/hooks/useForecastingProjection";

// One plain-text markdown summary of the whole app state, meant to be pasted
// into an LLM chat. Budget and wealth live in a single document: they run on
// different cadences (accounts are edited continuously, net worth is a monthly
// snapshot), and as two separate pastes the same account read at two different
// times looks like a contradiction. Here the As of section states the skew
// once, up front, and every figure below is labelled with which source it came
// from.
//
// Uses plain numbers (1234.56) instead of locale formatting so the text
// survives copy/paste and stays unambiguous for the model.

// Bump when the shape changes enough that a model reading an old paste
// alongside a new one could be misled.
const FORMAT_VERSION = "vipu-export/v1";

function eur(value: number): string {
  return `${value.toFixed(2)} €`;
}

function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

function today(): string {
  return new Date().toISOString().split("T")[0];
}

function isoDate(value: string): string {
  return value.split("T")[0];
}

function monthLabel(snapshot: { year: number; month: number }): string {
  return `${snapshot.year}-${String(snapshot.month).padStart(2, "0")}`;
}

function schedule(item: {
  frequency_value: number;
  frequency_unit: string;
  due_day: number;
  is_ephemeral: boolean;
  start_date: string | null;
}): string {
  if (item.is_ephemeral) {
    return `one-time${item.start_date ? ` on ${item.start_date}` : ""}`;
  }
  const { frequency_value: value, frequency_unit: unit, due_day } = item;
  let cadence: string;
  if (value === 1) {
    cadence = unit === "days" ? "daily" : unit.replace(/s$/, "ly");
  } else {
    cadence = `every ${value} ${unit}`;
  }
  return `${cadence}, lands on day ${due_day}`;
}

// One-off timing corrections the user has made. Worth stating explicitly: they
// are why a period figure can disagree with the item's own schedule, and they
// deliberately do not touch the monthly rates or anything projected from them.
function occurrenceOverride(item: IncomeItem | ExpenseItem): string {
  if (item.settled_occurrence) {
    return ` [${item.settled_occurrence} occurrence already settled ahead of its day, so it is in the balance and excluded from the period figures]`;
  }
  if (item.pending_occurrence) {
    return ` [${item.pending_occurrence} occurrence has not moved yet despite its day passing, so it still counts in the period figures]`;
  }
  return "";
}

function netIncome(item: IncomeItem, defaultTaxPct: number): number {
  if (item.is_deduction) {
    return (-item.gross_amount * (item.tax_percentage ?? 0)) / 100;
  }
  if (!item.is_taxed) {
    return item.gross_amount;
  }
  return item.gross_amount * (1 - defaultTaxPct / 100);
}

/** Most recent edit across accounts: how fresh the budget-side cash figures are. */
function accountsUpdatedAt(accounts: Account[]): string | null {
  const stamps = accounts
    .map((a) => a.updated_at)
    .filter((s): s is string => Boolean(s))
    .sort();
  return stamps.length > 0 ? isoDate(stamps[stamps.length - 1]) : null;
}

// Settled occurrences stay on the list but are labelled, since they are
// excluded from the totals above them: without the label the lines would look
// like they should add up to the total and don't.
function occurrenceLines(items: ExpenseWithOccurrence[]): string[] {
  return [...items]
    .sort((a, b) =>
      (a.next_occurrence_date ?? "").localeCompare(b.next_occurrence_date ?? "")
    )
    .map(
      (item) =>
        `  - ${item.next_occurrence_date ?? "date unknown"}: ${item.name} ${eur(item.amount)}${
          item.is_settled ? " (already paid, not counted above)" : ""
        }`
    );
}

export function buildFinancialSummary(
  data: BudgetData,
  roadmap: RoadmapData | undefined,
  snapshots: NetWorthSnapshot[],
  goals: GoalProgress[],
  projection: ForecastingProjection | null
): string {
  const t = data.totals;
  const s = data.settings;
  const lines: string[] = [];
  const latest = snapshots[0] ?? null;

  lines.push(`# Vipu financial snapshot (${today()})`);
  lines.push("");
  lines.push(`Format: ${FORMAT_VERSION}. Currency: EUR.`);
  lines.push("");

  // ---- As of -------------------------------------------------------------
  // The whole point of the combined export: say once, up front, why the two
  // halves disagree about the same account.
  lines.push("## As of");
  const updated = accountsUpdatedAt(data.accounts);
  lines.push(
    `- Budget section: live account balances${updated ? `, last edited ${updated}` : ""}. Updated whenever the user edits them.`
  );
  if (latest) {
    lines.push(
      `- Wealth section: ${monthLabel(latest)} net worth snapshot. Monthly cadence, so it can lag the budget section by weeks.`
    );
    lines.push(
      "- The same account may therefore show different figures in the two sections. Both are correct as of their own date; prefer the budget section for current cash."
    );
  } else {
    lines.push("- Wealth section: no net worth snapshots recorded yet.");
  }
  lines.push("");

  // ---- Budget ------------------------------------------------------------
  lines.push("## Budget");
  lines.push("");
  lines.push(
    `Default tax rate: ${s.tax_percentage}%. The budget month rolls over on payday, day ${s.payday_day} of the month, so periods below run payday to payday rather than calendar months. Individual income and expense items land on their own days, which need not be the payday.`
  );
  lines.push("");

  // The same two periods the summary card walks, off the same calculator, so a
  // paste can't disagree with what the user is looking at.
  const current = t.period_current;
  const next = t.period_next;
  const atPayday = t.cash_balance + current.money_in - current.money_out;
  const endOfNextPeriod = atPayday + next.money_in - next.money_out;

  lines.push("### Current position");
  lines.push(
    `- Cash across all non-credit accounts: ${eur(t.cash_balance)}`
  );
  lines.push(
    `- Owed on credit cards: ${eur(t.card_debt)}, leaving each card on its own due day. Net of the two: ${eur(t.current_balance)}${t.current_balance < 0 ? ", so the cards owe more than there is cash to cover them" : ""}`
  );
  lines.push(`- Next payday: ${t.next_payday}`);
  lines.push(
    `- Still to happen before payday: +${eur(current.money_in)} pay, ${eur(current.bills + current.savings)} of bills, ${eur(current.card_payments)} of card payments`
  );
  lines.push(...occurrenceLines(t.expenses_before_payday_list));
  lines.push(
    `- Lowest the cash gets between now and the end of next period: ${eur(t.cash_low_point.balance)} on ${t.cash_low_point.date}${
      t.cash_low_point.balance < 0
        ? ". The account goes under before the pay that covers those bills arrives, so the projections below are reached through a shortfall rather than around it."
        : ""
    }`
  );
  lines.push(`- Projected cash at payday: ${eur(atPayday)}`);
  lines.push(
    `- Next period (${next.start} to ${next.end}): +${eur(next.money_in)} pay, ${eur(next.bills + next.savings)} of bills, ${eur(next.card_payments)} of card payments`
  );
  lines.push(...occurrenceLines(t.expenses_next_period_list));
  lines.push(`- Projected cash at the end of it: ${eur(endOfNextPeriod)}`);
  lines.push(
    `- Unallocated next period: ${eur(next.net)}. That is next period's own money less what next period needs, so it is the amount that can be swept to savings on payday without touching the balance already in the account.`
  );
  lines.push(
    "- A card balance is charged once, on its first due day from today, not in every period."
  );
  lines.push("");

  lines.push("### Monthly rates");
  lines.push(
    "Recurring items normalized to a per-month rate (a quarterly bill counts as a third, a yearly one as a twelfth). One-time items are excluded here and listed separately below."
  );
  lines.push(`- Net income: ${eur(t.monthly_net_income)}/mo`);
  lines.push(`- Expenses: ${eur(t.monthly_expenses)}/mo`);
  lines.push(
    `- Surplus: ${eur(t.monthly_surplus)}/mo (net income minus expenses; this is what funds the roadmap)`
  );
  lines.push("");

  const income = data.income.filter((i) => !i.is_deduction);
  const deductions = data.income.filter((i) => i.is_deduction);
  lines.push("### Income (gross -> net per occurrence)");
  if (income.length === 0 && deductions.length === 0) {
    lines.push("- (none)");
  }
  for (const item of income) {
    const tax = item.is_taxed
      ? item.tax_percentage != null
        ? `taxed at ${item.tax_percentage}%`
        : `taxed at default ${s.tax_percentage}%`
      : "untaxed";
    lines.push(
      `- ${item.name}: ${eur(item.gross_amount)} -> ${eur(netIncome(item, s.tax_percentage))} (${tax}; ${schedule(item)})${occurrenceOverride(item)}`
    );
  }
  for (const item of deductions) {
    lines.push(
      `- ${item.name}: ${eur(netIncome(item, s.tax_percentage))} (deduction of ${item.tax_percentage ?? 0}% of ${eur(item.gross_amount)}, subtracted from net pay after tax; ${schedule(item)})${occurrenceOverride(item)}`
    );
  }
  lines.push("");

  const cashAccounts = data.accounts.filter((a) => !a.is_credit);
  const creditCards = data.accounts.filter((a) => a.is_credit);
  lines.push("### Accounts (live)");
  if (cashAccounts.length === 0 && creditCards.length === 0) {
    lines.push("- (none)");
  }
  for (const account of cashAccounts) {
    lines.push(`- ${account.name}: ${eur(account.balance)}`);
  }
  if (creditCards.length > 0) {
    lines.push("Credit cards (negative balance = amount owed):");
    for (const card of creditCards) {
      const due =
        card.payment_due_day != null
          ? `, payment due day ${card.payment_due_day}`
          : ", no scheduled payment day";
      lines.push(`- ${card.name}: ${eur(card.balance)}${due}`);
    }
  }
  lines.push("");

  const recurring = data.expenses.filter((e: ExpenseItem) => !e.is_ephemeral);
  const oneTime = data.expenses.filter((e: ExpenseItem) => e.is_ephemeral);
  lines.push("### Expenses");
  if (data.expenses.length === 0) {
    lines.push("- (none)");
  }
  for (const expense of recurring) {
    const kind = expense.is_savings_goal ? " [savings transfer]" : "";
    lines.push(
      `- ${expense.name}: ${eur(expense.amount)}${kind} (${schedule(expense)})${occurrenceOverride(expense)}`
    );
  }
  if (oneTime.length > 0) {
    lines.push("One-time (excluded from the monthly rates above):");
    for (const expense of oneTime) {
      lines.push(
        `- ${expense.name}: ${eur(expense.amount)} (${schedule(expense)})${occurrenceOverride(expense)}`
      );
    }
  }
  lines.push("");

  // ---- Roadmap -----------------------------------------------------------
  if (roadmap) {
    lines.push("### Financial roadmap");
    lines.push(
      `Sequential plan funded by whatever each pay period leaves over: ${eur(t.unallocated_next_period)} next period, against a smoothed rate of ${eur(roadmap.surplus_monthly)}/mo. The whole of it fills the first unfinished goal, then cascades to the next. Projected dates walk real periods rather than that rate, so a yearly bill delays the step it lands on instead of being spread across every month, and steps complete on a payday, since that is when the money arrives.`
    );
    if (roadmap.starting_position < 0) {
      lines.push(
        `The plan starts ${eur(-roadmap.starting_position)} behind: net account balances with credit cards assumed paid in full, plus ${eur(-roadmap.pending_one_time_net)} of pending one-time items. That is about ${roadmap.shortfall_months} months of surplus, cleared before any goal progresses.`
      );
    }
    roadmap.goals.forEach((step, index) => {
      const goal = step.goal;
      const kind = goal.goal_type === "debt_payoff" ? "pay off debt" : "save up";
      const progress = `${eur(step.current_value)} / ${eur(goal.target_value)} (${step.progress_percentage.toFixed(0)}%)`;
      let eta: string;
      if (step.status === "completed") {
        eta = ", completed";
      } else if (step.projected_completion_date) {
        eta = `, projected done ${step.projected_completion_date} (${step.months_to_complete} months from now)`;
      } else {
        eta = ", no projection (no surplus)";
      }
      lines.push(`${index + 1}. ${goal.name} (${kind}): ${progress}${eta}`);
    });
    lines.push("");
  }

  // ---- Wealth ------------------------------------------------------------
  lines.push("## Wealth");
  lines.push("");

  if (latest) {
    lines.push(`### Net worth (${monthLabel(latest)} snapshot)`);
    lines.push(`- Net worth: ${eur(latest.net_worth)}`);
    lines.push(
      `- Assets: ${eur(latest.total_assets)}, liabilities: ${eur(latest.total_liabilities)}`
    );
    lines.push(
      `- Personal: ${eur(latest.personal_wealth)}, company: ${eur(latest.company_wealth)}`
    );

    const groups = Object.entries(latest.by_group).filter(
      ([, amount]) => amount !== 0
    );
    if (groups.length > 0) {
      lines.push("By group (assets only, percentages are of total assets):");
      for (const [group, amount] of groups) {
        // The backend keys these as "<group>_pct", not by the bare group name.
        const share = latest.percentages[`${group}_pct`];
        lines.push(
          `- ${group}: ${eur(amount)}${share != null ? ` (${pct(share)})` : ""}`
        );
      }
    }

    // Split so the two breakdowns aren't silently inconsistent: By group is
    // assets-only, so listing liability categories under it invites the reader
    // to add up columns that don't reconcile.
    const entries = latest.entries.filter((e) => e.amount !== 0);
    const assetEntries = entries.filter((e) => e.amount > 0);
    const liabilityEntries = entries.filter((e) => e.amount < 0);
    if (assetEntries.length > 0) {
      lines.push("Asset categories:");
      for (const entry of assetEntries) {
        lines.push(`- ${entry.category.name}: ${eur(entry.amount)}`);
      }
    }
    if (liabilityEntries.length > 0) {
      lines.push("Liability categories (not included in By group above):");
      for (const entry of liabilityEntries) {
        lines.push(`- ${entry.category.name}: ${eur(entry.amount)}`);
      }
    }
    lines.push("");
  } else {
    lines.push("No net worth snapshots recorded yet.");
    lines.push("");
  }

  if (snapshots.length > 1) {
    lines.push("### Trend (newest first)");
    for (const snapshot of snapshots.slice(0, 12)) {
      const change =
        snapshot.change_from_previous !== 0
          ? ` (${snapshot.change_from_previous > 0 ? "+" : ""}${eur(snapshot.change_from_previous)}, ${pct(snapshot.change_percent)})`
          : "";
      lines.push(
        `- ${monthLabel(snapshot)}: ${eur(snapshot.net_worth)}${change}`
      );
    }
    lines.push("");
  }

  const netWorthGoals = goals.filter((g) => g.goal.goal_type === "net_worth");
  if (netWorthGoals.length > 0) {
    lines.push("### Net worth goals");
    lines.push(
      "Progress and required-monthly figures below are zero-growth linear: they assume no investment return. The FIRE section compounds instead, so the two can disagree about whether a target is reachable."
    );
    for (const gp of netWorthGoals) {
      const deadline = gp.goal.target_date
        ? `, deadline ${isoDate(gp.goal.target_date)}`
        : "";
      const status = gp.status
        ? `, ${gp.status === "on_track" ? "on track" : "behind"} (linear)`
        : "";
      const needed =
        gp.required_monthly != null && gp.required_monthly > 0
          ? `, needs ${eur(gp.required_monthly)}/mo at zero growth`
          : "";
      lines.push(
        `- ${gp.goal.name}: ${eur(gp.current_value)} / ${eur(gp.target_value)} (${pct(gp.progress_percentage)})${deadline}${status}${needed}`
      );
    }
    lines.push("");
  }

  // ---- FIRE --------------------------------------------------------------
  if (projection) {
    const d = projection.derived;
    lines.push("## FIRE projection");
    lines.push(
      `Compounding at the weighted expected return below. Target retirement age is ${d.targetRetirementAge}.`
    );
    lines.push(
      `- Monthly savings input: ${eur(d.monthlySavings)}/mo ${
        d.monthlySavingsIsOverride
          ? `(manual override; the budget's own surplus is ${eur(t.monthly_surplus)}/mo)`
          : "(the budget's monthly surplus)"
      }`
    );
    lines.push(
      `- Annual expenses input: ${eur(d.annualExpenses)}/yr ${
        d.annualExpensesIsOverride
          ? "(manual override)"
          : "(monthly expenses x 12)"
      }`
    );
    lines.push(
      `- Weighted expected return: ${pct(d.weightedReturnPct)}/yr, from the allocation and per-group assumptions:`
    );
    for (const [group, rate] of Object.entries(d.groupReturnRates)) {
      const amount = d.byGroup[group];
      lines.push(
        `  - ${group}: ${pct(rate)}/yr${amount != null ? ` on ${eur(amount)}` : ""}`
      );
    }
    lines.push(
      `- FIRE number (at target retirement age ${d.targetRetirementAge}): ${eur(projection.fireNumber)}`
    );
    lines.push(`- FIRE number if retiring now: ${eur(projection.fireNumberNow)}`);
    lines.push(
      `- Coast FIRE number: ${eur(projection.coastFireNumber)} (${projection.coastFireReached ? "reached" : "not reached"})`
    );
    if (projection.yearsToFire != null) {
      lines.push(
        `- Years until the portfolio covers expenses: ${projection.yearsToFire}${
          projection.fireAge != null
            ? ` (at age ${projection.fireAge}; this is when work becomes optional, not the planned retirement age of ${d.targetRetirementAge})`
            : ""
        }`
      );
    } else {
      lines.push(
        "- Years until the portfolio covers expenses: not reachable with current inputs"
      );
    }
    if (projection.pension) {
      const p = projection.pension;
      lines.push(
        `- Pension mode active: projected pension ${eur(p.projectedMonthlyPension)}/mo` +
          (p.guaranteeActive
            ? ` (guarantee pension ${eur(p.guaranteeAmount)}/mo applies)`
            : "")
      );
      for (const scenario of p.scenarios) {
        lines.push(
          `  - ${scenario.label} retirement at ${scenario.pensionStartAge}: pension ${eur(scenario.monthlyPension)}/mo, FIRE number ${eur(scenario.pensionFireNumber)}`
        );
      }
    }
    lines.push("");
  }

  return lines.join("\n");
}
