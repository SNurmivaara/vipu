"""One plain-text markdown summary of the whole app state, for an LLM to read.

Budget and wealth live in a single document: they run on different cadences
(accounts are edited continuously, net worth is a monthly snapshot), and as two
separate pastes the same account read at two different times looks like a
contradiction. Here the As of section states the skew once, up front, and every
figure below is labelled with which source it came from.

Uses plain numbers (1234.56) instead of locale formatting so the text survives
copy/paste and stays unambiguous for the model.

Ported from the frontend's lib/aiSummary.ts, which assembled the same document
client-side from five API calls. Serving it from here gives the MCP server a
one-call entry point and leaves one implementation instead of two.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.routes.budget import build_budget_payload
from app.routes.forecasting import build_projection
from app.routes.goals import build_goal_progress, build_roadmap
from app.routes.networth import list_snapshot_dicts

# Bump when the shape changes enough that a model reading an old paste
# alongside a new one could be misled.
FORMAT_VERSION = "vipu-export/v1"

CENTS = Decimal("0.01")
TENTHS = Decimal("0.1")


def _dec(value: object) -> Decimal:
    """A payload number as a Decimal, so the arithmetic below is exact.

    Built from the float itself rather than its shortest repr, because that is
    the value the TypeScript original rounded. A change_percent of 4.05 is the
    double 4.04999...; via str() it would round up to 4.1 and via the double
    down to 4.0, and only the latter matches what the frontend printed.
    """
    if value is None:
        return Decimal(0)
    if isinstance(value, int | float):
        return Decimal(value)
    return Decimal(str(value))


def _quantize(value: Decimal, places: Decimal) -> str:
    """Fixed-point, rounding halves up the way the TypeScript toFixed did."""
    return str(value.quantize(places, rounding=ROUND_HALF_UP))


def eur(value: object) -> str:
    """Money, two decimals."""
    return f"{_quantize(_dec(value), CENTS)} €"


def pct(value: object) -> str:
    """A percentage, one decimal."""
    return f"{_quantize(_dec(value), TENTHS)}%"


def num(value: float | int | None) -> str:
    """A bare number, without the trailing .0 a whole float would print with.

    The TypeScript original interpolated JavaScript numbers directly, where
    25.0 renders as "25". Matching that keeps the two outputs identical.
    """
    if value is None:
        return "None"
    if isinstance(value, int):
        return str(value)
    if value == int(value):
        return str(int(value))
    return repr(value)


def iso_date(value: str) -> str:
    """The date half of an ISO timestamp."""
    return value.split("T")[0]


def month_label(snapshot: dict) -> str:
    """A snapshot's year and month, as 2026-08."""
    return f"{snapshot['year']}-{str(snapshot['month']).zfill(2)}"


def schedule(item: dict) -> str:
    """An item's cadence, in words."""
    if item["is_ephemeral"]:
        start = item.get("start_date")
        return f"one-time{f' on {start}' if start else ''}"
    value = item["frequency_value"]
    unit = item["frequency_unit"]
    if value == 1:
        cadence = "daily" if unit == "days" else unit.removesuffix("s") + "ly"
    else:
        cadence = f"every {value} {unit}"
    return f"{cadence}, lands on day {item['due_day']}"


def occurrence_override(item: dict) -> str:
    """One-off timing corrections the user has made.

    Worth stating explicitly: they are why a period figure can disagree with the
    item's own schedule, and they deliberately do not touch the monthly rates or
    anything projected from them.
    """
    if item.get("settled_occurrence"):
        return (
            f" [{item['settled_occurrence']} occurrence already settled ahead of "
            "its day, so it is in the balance and excluded from the period figures]"
        )
    if item.get("pending_occurrence"):
        return (
            f" [{item['pending_occurrence']} occurrence has not moved yet despite "
            "its day passing, so it still counts in the period figures]"
        )
    return ""


def net_income(item: dict, default_tax_pct: Decimal) -> Decimal:
    """What one occurrence of this income line is worth after tax."""
    gross = _dec(item["gross_amount"])
    if item["is_deduction"]:
        return -gross * _dec(item.get("tax_percentage") or 0) / 100
    if not item["is_taxed"]:
        return gross
    return gross * (1 - default_tax_pct / 100)


def accounts_updated_at(accounts: list[dict]) -> str | None:
    """Most recent edit across accounts: how fresh the budget cash figures are."""
    stamps = sorted(a["updated_at"] for a in accounts if a.get("updated_at"))
    return iso_date(stamps[-1]) if stamps else None


def occurrence_lines(items: list[dict]) -> list[str]:
    """One line per dated occurrence in a period.

    Settled occurrences stay on the list but are labelled, since they are
    excluded from the totals above them: without the label the lines would look
    like they should add up to the total and don't.
    """
    ordered = sorted(items, key=lambda i: i.get("next_occurrence_date") or "")
    return [
        f"  - {item.get('next_occurrence_date') or 'date unknown'}: {item['name']} "
        f"{eur(item['amount'])}"
        f"{' (already paid, not counted above)' if item['is_settled'] else ''}"
        for item in ordered
    ]


def _as_of_section(lines: list[str], accounts: list[dict], latest: dict | None) -> None:
    """Say once, up front, why the two halves disagree about the same account."""
    lines.append("## As of")
    updated = accounts_updated_at(accounts)
    lines.append(
        f"- Budget section: live account balances"
        f"{f', last edited {updated}' if updated else ''}."
        " Updated whenever the user edits them."
    )
    if latest:
        lines.append(
            f"- Wealth section: {month_label(latest)} net worth snapshot. Monthly "
            "cadence, so it can lag the budget section by weeks."
        )
        lines.append(
            "- The same account may therefore show different figures in the two "
            "sections. Both are correct as of their own date; prefer the budget "
            "section for current cash."
        )
    else:
        lines.append("- Wealth section: no net worth snapshots recorded yet.")
    lines.append("")


def _budget_section(lines: list[str], budget: dict) -> None:
    """Current position, monthly rates, income, accounts and expenses."""
    totals = budget["totals"]
    settings = budget["settings"]

    lines.append("## Budget")
    lines.append("")
    lines.append(
        f"Default tax rate: {num(settings['tax_percentage'])}%. The budget month "
        f"rolls over on payday, day {num(settings['payday_day'])} of the month, so "
        "periods below run payday to payday rather than calendar months. "
        "Individual income and expense items land on their own days, which need "
        "not be the payday."
    )
    lines.append("")

    # The same two periods the summary card walks, off the same calculator, so a
    # paste can't disagree with what the user is looking at.
    current = totals["period_current"]
    following = totals["period_next"]
    cash_balance = _dec(totals["cash_balance"])
    at_payday = cash_balance + _dec(current["money_in"]) - _dec(current["money_out"])
    end_of_next = at_payday + _dec(following["money_in"]) - _dec(following["money_out"])
    current_balance = _dec(totals["current_balance"])
    low_point = totals["cash_low_point"]

    lines.append("### Current position")
    lines.append(f"- Cash across all non-credit accounts: {eur(cash_balance)}")
    lines.append(
        f"- Owed on credit cards: {eur(totals['card_debt'])}, leaving each card on "
        f"its own due day. Net of the two: {eur(current_balance)}"
        + (
            ", so the cards owe more than there is cash to cover them"
            if current_balance < 0
            else ""
        )
    )
    lines.append(f"- Next payday: {totals['next_payday']}")
    lines.append(
        f"- Still to happen before payday: +{eur(current['money_in'])} pay, "
        f"{eur(_dec(current['bills']) + _dec(current['savings']))} of bills, "
        f"{eur(current['card_payments'])} of card payments"
    )
    lines.extend(occurrence_lines(totals["expenses_before_payday_list"]))
    lines.append(
        f"- Lowest the cash gets between now and the end of next period: "
        f"{eur(low_point['balance'])} on {low_point['date']}"
        + (
            ". The account goes under before the pay that covers those bills "
            "arrives, so the projections below are reached through a shortfall "
            "rather than around it."
            if _dec(low_point["balance"]) < 0
            else ""
        )
    )
    lines.append(f"- Projected cash at payday: {eur(at_payday)}")
    lines.append(
        f"- Next period ({following['start']} to {following['end']}): "
        f"+{eur(following['money_in'])} pay, "
        f"{eur(_dec(following['bills']) + _dec(following['savings']))} of bills, "
        f"{eur(following['card_payments'])} of card payments"
    )
    lines.extend(occurrence_lines(totals["expenses_next_period_list"]))
    lines.append(f"- Projected cash at the end of it: {eur(end_of_next)}")
    lines.append(
        f"- Unallocated next period: {eur(following['net'])}. That is next "
        "period's own money less what next period needs, so it is the amount "
        "that can be swept to savings on payday without touching the balance "
        "already in the account."
    )
    lines.append(
        "- A card balance is charged once, on its first due day from today, not "
        "in every period."
    )
    lines.append("")

    lines.append("### Monthly rates")
    lines.append(
        "Recurring items normalized to a per-month rate (a quarterly bill counts "
        "as a third, a yearly one as a twelfth). One-time items are excluded here "
        "and listed separately below."
    )
    lines.append(f"- Net income: {eur(totals['monthly_net_income'])}/mo")
    lines.append(f"- Expenses: {eur(totals['monthly_expenses'])}/mo")
    lines.append(
        f"- Surplus: {eur(totals['monthly_surplus'])}/mo (net income minus "
        "expenses; this is what funds the roadmap)"
    )
    lines.append("")

    default_tax_pct = _dec(settings["tax_percentage"])
    income = [i for i in budget["income"] if not i["is_deduction"]]
    deductions = [i for i in budget["income"] if i["is_deduction"]]
    lines.append("### Income (gross -> net per occurrence)")
    if not income and not deductions:
        lines.append("- (none)")
    for item in income:
        if not item["is_taxed"]:
            tax = "untaxed"
        elif item.get("tax_percentage") is not None:
            tax = f"taxed at {num(item['tax_percentage'])}%"
        else:
            tax = f"taxed at default {num(settings['tax_percentage'])}%"
        lines.append(
            f"- {item['name']}: {eur(item['gross_amount'])} -> "
            f"{eur(net_income(item, default_tax_pct))} ({tax}; {schedule(item)})"
            f"{occurrence_override(item)}"
        )
    for item in deductions:
        lines.append(
            f"- {item['name']}: {eur(net_income(item, default_tax_pct))} (deduction "
            f"of {num(item.get('tax_percentage') or 0)}% of "
            f"{eur(item['gross_amount'])}, subtracted from net pay after tax; "
            f"{schedule(item)}){occurrence_override(item)}"
        )
    lines.append("")

    cash_accounts = [a for a in budget["accounts"] if not a["is_credit"]]
    credit_cards = [a for a in budget["accounts"] if a["is_credit"]]
    lines.append("### Accounts (live)")
    if not cash_accounts and not credit_cards:
        lines.append("- (none)")
    for account in cash_accounts:
        lines.append(f"- {account['name']}: {eur(account['balance'])}")
    if credit_cards:
        lines.append("Credit cards (negative balance = amount owed):")
        for card in credit_cards:
            due = (
                f", payment due day {num(card['payment_due_day'])}"
                if card.get("payment_due_day") is not None
                else ", no scheduled payment day"
            )
            lines.append(f"- {card['name']}: {eur(card['balance'])}{due}")
    lines.append("")

    recurring = [e for e in budget["expenses"] if not e["is_ephemeral"]]
    one_time = [e for e in budget["expenses"] if e["is_ephemeral"]]
    lines.append("### Expenses")
    if not budget["expenses"]:
        lines.append("- (none)")
    for expense in recurring:
        kind = " [savings transfer]" if expense["is_savings_goal"] else ""
        lines.append(
            f"- {expense['name']}: {eur(expense['amount'])}{kind} "
            f"({schedule(expense)}){occurrence_override(expense)}"
        )
    if one_time:
        lines.append("One-time (excluded from the monthly rates above):")
        for expense in one_time:
            lines.append(
                f"- {expense['name']}: {eur(expense['amount'])} "
                f"({schedule(expense)}){occurrence_override(expense)}"
            )
    lines.append("")


def _roadmap_section(lines: list[str], budget: dict, roadmap: dict) -> None:
    """The sequential plan, and what each step is projected to cost in time."""
    totals = budget["totals"]
    lines.append("### Financial roadmap")
    lines.append(
        "Sequential plan funded by whatever each pay period leaves over: "
        f"{eur(totals['unallocated_next_period'])} next period, against a smoothed "
        f"rate of {eur(roadmap['surplus_monthly'])}/mo. The whole of it fills the "
        "first unfinished goal, then cascades to the next. Projected dates walk "
        "real periods rather than that rate, so a yearly bill delays the step it "
        "lands on instead of being spread across every month, and steps complete "
        "on a payday, since that is when the money arrives."
    )
    if roadmap["starting_position"] < 0:
        lines.append(
            f"The plan starts {eur(-_dec(roadmap['starting_position']))} behind: net "
            "account balances with credit cards assumed paid in full, plus "
            f"{eur(-_dec(roadmap['pending_one_time_net']))} of pending one-time "
            f"items. That is about {num(roadmap['shortfall_months'])} months of "
            "surplus, cleared before any goal progresses."
        )
    for index, step in enumerate(roadmap["goals"], start=1):
        goal = step["goal"]
        kind = "pay off debt" if goal["goal_type"] == "debt_payoff" else "save up"
        progress = (
            f"{eur(step['current_value'])} / {eur(goal['target_value'])} "
            f"({_quantize(_dec(step['progress_percentage']), Decimal('1'))}%)"
        )
        if step["status"] == "completed":
            eta = ", completed"
        elif step["projected_completion_date"]:
            eta = (
                f", projected done {step['projected_completion_date']} "
                f"({num(step['months_to_complete'])} months from now)"
            )
        else:
            eta = ", no projection (no surplus)"
        lines.append(f"{index}. {goal['name']} ({kind}): {progress}{eta}")
    lines.append("")


def _wealth_section(lines: list[str], snapshots: list[dict], goals: list[dict]) -> None:
    """Net worth, its trend, and the goals measured against it."""
    latest = snapshots[0] if snapshots else None
    lines.append("## Wealth")
    lines.append("")

    if latest:
        lines.append(f"### Net worth ({month_label(latest)} snapshot)")
        lines.append(f"- Net worth: {eur(latest['net_worth'])}")
        lines.append(
            f"- Assets: {eur(latest['total_assets'])}, liabilities: "
            f"{eur(latest['total_liabilities'])}"
        )
        lines.append(
            f"- Personal: {eur(latest['personal_wealth'])}, company: "
            f"{eur(latest['company_wealth'])}"
        )

        groups = [(g, a) for g, a in latest["by_group"].items() if a != 0]
        if groups:
            lines.append("By group (assets only, percentages are of total assets):")
            for group, amount in groups:
                # The backend keys these as "<group>_pct", not by the bare name.
                share = latest["percentages"].get(f"{group}_pct")
                lines.append(
                    f"- {group}: {eur(amount)}"
                    f"{f' ({pct(share)})' if share is not None else ''}"
                )

        # Split so the two breakdowns aren't silently inconsistent: By group is
        # assets-only, so listing liability categories under it invites the
        # reader to add up columns that don't reconcile.
        entries = [e for e in latest["entries"] if e["amount"] != 0]
        asset_entries = [e for e in entries if e["amount"] > 0]
        liability_entries = [e for e in entries if e["amount"] < 0]
        if asset_entries:
            lines.append("Asset categories:")
            for entry in asset_entries:
                lines.append(f"- {entry['category']['name']}: {eur(entry['amount'])}")
        if liability_entries:
            lines.append("Liability categories (not included in By group above):")
            for entry in liability_entries:
                lines.append(f"- {entry['category']['name']}: {eur(entry['amount'])}")
        lines.append("")
    else:
        lines.append("No net worth snapshots recorded yet.")
        lines.append("")

    if len(snapshots) > 1:
        lines.append("### Trend (newest first)")
        for snapshot in snapshots[:12]:
            change = ""
            if snapshot["change_from_previous"] != 0:
                sign = "+" if snapshot["change_from_previous"] > 0 else ""
                change = (
                    f" ({sign}{eur(snapshot['change_from_previous'])}, "
                    f"{pct(snapshot['change_percent'])})"
                )
            lines.append(
                f"- {month_label(snapshot)}: {eur(snapshot['net_worth'])}{change}"
            )
        lines.append("")

    net_worth_goals = [g for g in goals if g["goal"]["goal_type"] == "net_worth"]
    if net_worth_goals:
        lines.append("### Net worth goals")
        lines.append(
            "Progress and required-monthly figures below are zero-growth linear: "
            "they assume no investment return. The FIRE section compounds "
            "instead, so the two can disagree about whether a target is reachable."
        )
        for progress in net_worth_goals:
            goal = progress["goal"]
            deadline = (
                f", deadline {iso_date(goal['target_date'])}"
                if goal["target_date"]
                else ""
            )
            if progress["status"]:
                label = "on track" if progress["status"] == "on_track" else "behind"
                status = f", {label} (linear)"
            else:
                status = ""
            required = progress["required_monthly"]
            needed = (
                f", needs {eur(required)}/mo at zero growth"
                if required is not None and required > 0
                else ""
            )
            lines.append(
                f"- {goal['name']}: {eur(progress['current_value'])} / "
                f"{eur(progress['target_value'])} "
                f"({pct(progress['progress_percentage'])})"
                f"{deadline}{status}{needed}"
            )
        lines.append("")


def _fire_section(lines: list[str], budget: dict, projection: dict) -> None:
    """The compounding half of the picture, and the inputs behind it."""
    derived = projection["derived"]
    totals = budget["totals"]
    target_age = num(derived["target_retirement_age"])

    lines.append("## FIRE projection")
    lines.append(
        "Compounding at the weighted expected return below. Target retirement "
        f"age is {target_age}."
    )
    lines.append(
        f"- Monthly savings input: {eur(derived['monthly_savings'])}/mo "
        + (
            "(manual override; the budget's own surplus is "
            f"{eur(totals['monthly_surplus'])}/mo)"
            if derived["monthly_savings_is_override"]
            else "(the budget's monthly surplus)"
        )
    )
    lines.append(
        f"- Annual expenses input: {eur(derived['annual_expenses'])}/yr "
        + (
            "(manual override)"
            if derived["annual_expenses_is_override"]
            else "(monthly expenses x 12)"
        )
    )
    lines.append(
        f"- Weighted expected return: {pct(derived['weighted_return_pct'])}/yr, "
        "from the allocation and per-group assumptions:"
    )
    for group, rate in derived["group_return_rates"].items():
        amount = derived["by_group"].get(group)
        lines.append(
            f"  - {group}: {pct(rate)}/yr"
            f"{f' on {eur(amount)}' if amount is not None else ''}"
        )
    lines.append(
        f"- FIRE number (at target retirement age {target_age}): "
        f"{eur(projection['fire_number'])}"
    )
    lines.append(f"- FIRE number if retiring now: {eur(projection['fire_number_now'])}")
    reached = "reached" if projection["coast_fire_reached"] else "not reached"
    lines.append(
        f"- Coast FIRE number: {eur(projection['coast_fire_number'])} ({reached})"
    )
    if projection["years_to_fire"] is not None:
        at_age = (
            f" (at age {num(projection['fire_age'])}; this is when work becomes "
            f"optional, not the planned retirement age of {target_age})"
            if projection["fire_age"] is not None
            else ""
        )
        lines.append(
            "- Years until the portfolio covers expenses: "
            f"{num(projection['years_to_fire'])}{at_age}"
        )
    else:
        lines.append(
            "- Years until the portfolio covers expenses: not reachable with "
            "current inputs"
        )
    pension = projection.get("pension")
    if pension:
        guarantee = (
            f" (guarantee pension {eur(pension['guarantee_amount'])}/mo applies)"
            if pension["guarantee_active"]
            else ""
        )
        lines.append(
            "- Pension mode active: projected pension "
            f"{eur(pension['projected_monthly_pension'])}/mo{guarantee}"
        )
        for scenario in pension["scenarios"]:
            lines.append(
                f"  - {scenario['label']} retirement at "
                f"{num(scenario['pension_start_age'])}: pension "
                f"{eur(scenario['monthly_pension'])}/mo, FIRE number "
                f"{eur(scenario['pension_fire_number'])}"
            )
    lines.append("")


def build_financial_summary(session: Session, today: date) -> str:
    """The whole app state as one markdown document, for an LLM to read."""
    budget = build_budget_payload(session, today)
    roadmap = build_roadmap(session, today)
    snapshots = list_snapshot_dicts(session)
    goals = build_goal_progress(session)
    projection = build_projection(session)

    lines: list[str] = []
    latest: dict[str, Any] | None = snapshots[0] if snapshots else None

    lines.append(f"# Vipu financial snapshot ({today.isoformat()})")
    lines.append("")
    lines.append(f"Format: {FORMAT_VERSION}. Currency: EUR.")
    lines.append("")

    _as_of_section(lines, budget["accounts"], latest)
    _budget_section(lines, budget)
    _roadmap_section(lines, budget, roadmap)
    _wealth_section(lines, snapshots, goals)
    _fire_section(lines, budget, projection)

    return "\n".join(lines)
