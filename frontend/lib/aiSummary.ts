import {
  BudgetData,
  ExpenseItem,
  GoalProgress,
  IncomeItem,
  NetWorthSnapshot,
  RoadmapData,
} from "@/types";
import { ForecastingProjection } from "@/hooks/useForecastingProjection";

// Plain-text markdown summaries of the app state, meant to be pasted into an
// LLM chat. Uses plain numbers (1234.56) instead of locale formatting so the
// text survives copy/paste and stays unambiguous for the model.

function eur(value: number): string {
  return `${value.toFixed(2)} €`;
}

function today(): string {
  return new Date().toISOString().split("T")[0];
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
  return `${cadence}, day ${due_day}`;
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

export function buildBudgetSummary(
  data: BudgetData,
  roadmap?: RoadmapData
): string {
  const t = data.totals;
  const s = data.settings;
  const lines: string[] = [];

  lines.push(`# Vipu budget snapshot (${today()})`);
  lines.push("");
  lines.push(`Currency: EUR. Default tax rate: ${s.tax_percentage}%.`);
  lines.push("");

  // Mirror BudgetSummary's three projected balances
  const obligations = t.expenses_before_payday + t.savings_before_payday;
  const beforePayday = t.current_balance - obligations;
  const afterPayday = beforePayday + t.income_before_payday;
  const nextPeriodBills = t.expenses_next_period + t.savings_next_period;
  const endOfNextPeriod = afterPayday - nextPeriodBills;

  lines.push("## Current position");
  lines.push(`- Cash across accounts now: ${eur(t.current_balance)}`);
  lines.push(
    `- Next payday: ${t.next_payday} (payday is day ${s.payday_day} of the month)`
  );
  lines.push(`- Bills still due before payday: ${eur(obligations)}`);
  lines.push(`- Projected balance before payday: ${eur(beforePayday)}`);
  lines.push(
    `- Projected after payday (+${eur(t.income_before_payday)} pay): ${eur(afterPayday)}`
  );
  lines.push(
    `- Projected end of next period ${t.next_period_end} (-${eur(nextPeriodBills)} bills): ${eur(endOfNextPeriod)}`
  );
  lines.push("");

  lines.push(
    "## Monthly rates (recurring items normalized per month, one-time items excluded)"
  );
  lines.push(`- Net income: ${eur(t.monthly_net_income)}/mo`);
  lines.push(`- Expenses: ${eur(t.monthly_expenses)}/mo`);
  lines.push(`- Surplus: ${eur(t.monthly_surplus)}/mo`);
  lines.push("");

  const income = data.income.filter((i) => !i.is_deduction);
  const deductions = data.income.filter((i) => i.is_deduction);
  lines.push("## Income (gross -> net per occurrence)");
  for (const item of income) {
    const tax = item.is_taxed
      ? item.tax_percentage != null
        ? `taxed at ${item.tax_percentage}%`
        : `taxed at default ${s.tax_percentage}%`
      : "untaxed";
    lines.push(
      `- ${item.name}: ${eur(item.gross_amount)} -> ${eur(netIncome(item, s.tax_percentage))} (${tax}; ${schedule(item)})`
    );
  }
  for (const item of deductions) {
    lines.push(
      `- ${item.name} (deduction): ${eur(netIncome(item, s.tax_percentage))} (${schedule(item)})`
    );
  }
  lines.push("");

  const cashAccounts = data.accounts.filter((a) => !a.is_credit);
  const creditCards = data.accounts.filter((a) => a.is_credit);
  lines.push("## Accounts");
  if (cashAccounts.length === 0 && creditCards.length === 0) {
    lines.push("- (none)");
  }
  for (const account of cashAccounts) {
    lines.push(`- ${account.name}: ${eur(account.balance)}`);
  }
  if (creditCards.length > 0) {
    lines.push("Credit cards:");
    for (const card of creditCards) {
      const due =
        card.payment_due_day != null
          ? `, payment due day ${card.payment_due_day}`
          : "";
      lines.push(`- ${card.name}: ${eur(card.balance)}${due}`);
    }
  }
  lines.push("");

  const recurring = data.expenses.filter((e: ExpenseItem) => !e.is_ephemeral);
  const oneTime = data.expenses.filter((e: ExpenseItem) => e.is_ephemeral);
  lines.push("## Expenses");
  if (data.expenses.length === 0) {
    lines.push("- (none)");
  }
  for (const expense of recurring) {
    lines.push(`- ${expense.name}: ${eur(expense.amount)} (${schedule(expense)})`);
  }
  if (oneTime.length > 0) {
    lines.push("One-time:");
    for (const expense of oneTime) {
      lines.push(
        `- ${expense.name}: ${eur(expense.amount)} (${schedule(expense)})`
      );
    }
  }
  lines.push("");

  if (roadmap) {
    lines.push(
      "## Financial roadmap (sequential goals funded by the monthly surplus)"
    );
    lines.push(
      `Surplus flowing into the plan: ${eur(roadmap.surplus_monthly)}/mo. The whole surplus fills the first unfinished goal, then cascades to the next.`
    );
    roadmap.goals.forEach((step, index) => {
      const goal = step.goal;
      const kind = goal.goal_type === "debt_payoff" ? "pay off debt" : "save up";
      const progress = `${eur(step.current_value)} / ${eur(goal.target_value)} (${step.progress_percentage.toFixed(0)}%)`;
      let eta = "";
      if (step.status === "completed") {
        eta = " — completed";
      } else if (step.projected_completion_date) {
        eta = ` — projected done ${step.projected_completion_date} (${step.months_to_complete} months from now)`;
      } else {
        eta = " — no projection (no surplus)";
      }
      lines.push(`${index + 1}. ${goal.name} (${kind}): ${progress}${eta}`);
    });
    lines.push("");
  }

  return lines.join("\n");
}

export function buildWealthSummary(
  snapshots: NetWorthSnapshot[],
  goals: GoalProgress[],
  projection: ForecastingProjection
): string {
  const lines: string[] = [];
  const latest = snapshots[0] ?? null;

  lines.push(`# Vipu wealth snapshot (${today()})`);
  lines.push("");
  lines.push("Currency: EUR.");
  lines.push("");

  if (latest) {
    lines.push(`## Net worth (latest snapshot: ${latest.year}-${String(latest.month).padStart(2, "0")})`);
    lines.push(`- Net worth: ${eur(latest.net_worth)}`);
    lines.push(
      `- Assets: ${eur(latest.total_assets)}, liabilities: ${eur(latest.total_liabilities)}`
    );
    lines.push(
      `- Personal: ${eur(latest.personal_wealth)}, company: ${eur(latest.company_wealth)}`
    );
    lines.push("By group:");
    for (const [group, amount] of Object.entries(latest.by_group)) {
      const pct = latest.percentages[group];
      lines.push(
        `- ${group}: ${eur(amount)}${pct != null ? ` (${pct.toFixed(1)}% of assets)` : ""}`
      );
    }
    lines.push("By category:");
    for (const entry of latest.entries) {
      lines.push(`- ${entry.category.name}: ${eur(entry.amount)}`);
    }
    lines.push("");
  } else {
    lines.push("No net worth snapshots recorded yet.");
    lines.push("");
  }

  if (snapshots.length > 1) {
    lines.push("## Trend (newest first)");
    for (const snapshot of snapshots.slice(0, 12)) {
      const month = `${snapshot.year}-${String(snapshot.month).padStart(2, "0")}`;
      const change =
        snapshot.change_from_previous !== 0
          ? ` (${snapshot.change_from_previous > 0 ? "+" : ""}${eur(snapshot.change_from_previous)}, ${snapshot.change_percent.toFixed(1)}%)`
          : "";
      lines.push(`- ${month}: ${eur(snapshot.net_worth)}${change}`);
    }
    lines.push("");
  }

  const netWorthGoals = goals.filter((g) => g.goal.goal_type === "net_worth");
  if (netWorthGoals.length > 0) {
    lines.push("## Net worth goals");
    for (const gp of netWorthGoals) {
      const deadline = gp.goal.target_date
        ? `, deadline ${gp.goal.target_date.split("T")[0]}`
        : "";
      const status = gp.status
        ? `, ${gp.status === "on_track" ? "on track" : "behind"}`
        : "";
      const needed =
        gp.required_monthly != null && gp.required_monthly > 0
          ? `, needs ${eur(gp.required_monthly)}/mo`
          : "";
      lines.push(
        `- ${gp.goal.name}: ${eur(gp.current_value)} / ${eur(gp.target_value)} (${gp.progress_percentage.toFixed(1)}%)${deadline}${status}${needed}`
      );
    }
    lines.push("");
  }

  const d = projection.derived;
  lines.push("## FIRE projection (backend-derived)");
  lines.push(`- Monthly savings: ${eur(d.monthlySavings)}/mo`);
  lines.push(`- Annual expenses: ${eur(d.annualExpenses)}/yr`);
  lines.push(
    `- Weighted expected return: ${d.weightedReturnPct.toFixed(1)}%/yr (from asset allocation and per-group return assumptions)`
  );
  lines.push(`- FIRE number (at target retirement age): ${eur(projection.fireNumber)}`);
  lines.push(`- FIRE number if retiring now: ${eur(projection.fireNumberNow)}`);
  lines.push(
    `- Coast FIRE number: ${eur(projection.coastFireNumber)} (${projection.coastFireReached ? "reached" : "not reached"})`
  );
  if (projection.yearsToFire != null) {
    lines.push(
      `- Years to FIRE: ${projection.yearsToFire}${projection.fireAge != null ? ` (age ${projection.fireAge})` : ""}`
    );
  } else {
    lines.push("- Years to FIRE: not reachable with current inputs");
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

  return lines.join("\n");
}
