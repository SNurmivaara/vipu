from datetime import date, datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify
from sqlalchemy.orm import Session

from app import get_session
from app.deadline_calc import (
    calculate_cc_payments_in_window,
    calculate_expenses_before_payday,
    calculate_income_before_payday,
    expense_window_start,
    get_checkpoint_occurrence,
    get_item_occurrences,
    get_latest_due_occurrence,
    get_next_occurrence,
    get_next_payday,
    get_payday_after,
    get_previous_payday,
    income_window_start,
    is_occurrence_settled,
)
from app.models import (
    Account,
    BudgetSettings,
    ExpenseItem,
    IncomeItem,
)

bp = APIBlueprint("budget", __name__, tag="Budget")


def calculate_net_income(
    income_items: list[IncomeItem], default_tax_pct: Decimal
) -> Decimal:
    """Calculate total net income after taxes."""
    total = Decimal("0")
    for item in income_items:
        total += item.calculate_net(default_tax_pct)
    return total


# Average month length, for normalizing day/week frequencies to monthly rates
DAYS_PER_MONTH = Decimal("30.4375")


def monthly_occurrences(frequency_value: int, frequency_unit: str) -> Decimal:
    """How many times per month an item with this schedule occurs."""
    value = Decimal(frequency_value or 1)
    if frequency_unit == "years":
        return 1 / (value * 12)
    if frequency_unit == "weeks":
        return DAYS_PER_MONTH / (value * 7)
    if frequency_unit == "days":
        return DAYS_PER_MONTH / value
    return 1 / value  # months


def pending_one_time_items(session: Session, today: date) -> list[tuple[date, Decimal]]:
    """One-time items still ahead of us, as (due date, signed amount) pairs.

    monthly_net_income/monthly_expenses deliberately exclude ephemeral items so
    the monthly rate isn't distorted by a single bill. That means anything
    projecting forward at that rate has to charge the one-time items separately
    or it spends money that is already claimed.

    Positive is an inflow (a pending bonus), negative an outflow (a pending tax
    bill). Items dated in the past are treated as already settled, unless the
    user marked the occurrence as not yet moved. An ephemeral item with no
    start_date has no unambiguous due date, so it falls due immediately rather
    than being silently dropped.
    """
    tax_pct = _tax_percentage(session)
    items: list[tuple[date, Decimal]] = []

    def still_owed(item: IncomeItem | ExpenseItem, due: date) -> bool:
        """Whether this one-time item's money has yet to move."""
        if item.settled_occurrence == due:
            return False
        return due >= today or item.pending_occurrence == due

    for income in session.query(IncomeItem).all():
        if not income.is_ephemeral or income.archived_at is not None:
            continue
        due = income.start_date or today
        if not still_owed(income, due):
            continue
        # A pending item's own date is behind us; it falls due now.
        items.append((max(due, today), income.calculate_net(tax_pct)))

    for expense in session.query(ExpenseItem).all():
        if not expense.is_ephemeral or expense.archived_at is not None:
            continue
        due = expense.start_date or today
        if not still_owed(expense, due):
            continue
        items.append((max(due, today), -expense.amount))

    return sorted(items, key=lambda pair: pair[0])


def pending_one_time_net(session: Session, today: date) -> Decimal:
    """Net cash effect of all one-time items still ahead of us."""
    return sum(
        (amount for _, amount in pending_one_time_items(session, today)),
        Decimal("0"),
    )


def _tax_percentage(session: Session) -> Decimal:
    """Configured default tax rate, or the 25% fallback used elsewhere."""
    settings = session.query(BudgetSettings).first()
    return settings.tax_percentage if settings else Decimal("25.0")


def configured_payday_day(session: Session) -> int:
    """Configured payday day of month, or the 25th fallback used elsewhere."""
    settings = session.query(BudgetSettings).first()
    return settings.payday_day if settings else 25


def compute_budget_totals(session: Session) -> dict[str, Decimal]:
    """Compute headline budget totals from active (non-archived) items.

    Returns gross_income, net_income, current_balance, total_expenses and
    net_position as Decimals. Shared by the budget and forecasting endpoints so
    the same numbers are derived in one place.

    total_expenses/net_income sum every active line at face value (what the
    list sections display). monthly_expenses/monthly_net_income normalize each
    recurring line to a per-month rate (a quarterly bill counts at a third,
    a yearly one at a twelfth, a weekly one at ~4.35x) and exclude one-time
    ephemeral items, giving the true monthly rate that the roadmap surplus and
    FIRE projections are based on.
    """
    settings = session.query(BudgetSettings).first()
    tax_pct = settings.tax_percentage if settings else Decimal("25.0")

    active_income = [
        i for i in session.query(IncomeItem).all() if i.archived_at is None
    ]
    active_expenses = [
        e for e in session.query(ExpenseItem).all() if e.archived_at is None
    ]
    accounts = session.query(Account).all()

    # Gross income excludes deductions
    gross_income = sum(
        (i.gross_amount for i in active_income if not i.is_deduction),
        Decimal("0"),
    )
    net_income = calculate_net_income(active_income, tax_pct)
    current_balance = sum((a.balance for a in accounts), Decimal("0"))
    total_expenses = sum((e.amount for e in active_expenses), Decimal("0"))

    monthly_expenses = sum(
        (
            e.amount * monthly_occurrences(e.frequency_value, e.frequency_unit)
            for e in active_expenses
            if not e.is_ephemeral
        ),
        Decimal("0"),
    )
    monthly_net_income = sum(
        (
            i.calculate_net(tax_pct)
            * monthly_occurrences(i.frequency_value, i.frequency_unit)
            for i in active_income
            if not i.is_ephemeral
        ),
        Decimal("0"),
    )

    return {
        "gross_income": gross_income,
        "net_income": net_income,
        "current_balance": current_balance,
        "total_expenses": total_expenses,
        "net_position": current_balance - total_expenses,
        "monthly_expenses": monthly_expenses,
        "monthly_net_income": monthly_net_income,
        "monthly_surplus": monthly_net_income - monthly_expenses,
    }


def clear_stale_overrides(
    item: IncomeItem | ExpenseItem,
    today: date,
    settled_before: date,
    period_start: date,
) -> None:
    """Drop occurrence overrides that no longer describe anything.

    A settled mark expires once its day arrives: from then on the default
    assumption (money moves on its due day) says the same thing, and keeping the
    mark would block the user from flagging that day as pending after all.

    A pending mark deliberately outlives its own due day — that is the point —
    but only while it is still the last occurrence to have come due this pay
    period. Once a newer one falls due, or the period rolls over, the mark
    refers to closed history and would silently inflate what is still owed.
    """
    if item.settled_occurrence is not None and item.settled_occurrence < today:
        item.settled_occurrence = None
    if item.pending_occurrence is not None:
        if item.pending_occurrence != get_latest_due_occurrence(
            item, settled_before, period_start
        ):
            item.pending_occurrence = None


def occurrence_entry(
    item: ExpenseItem,
    occurrence: date,
    settled_before: date,
    settleable: tuple[date | None, ...],
) -> dict:
    """One row of a period list: the item, dated, with its settled state."""
    entry = item.to_dict()
    entry["next_occurrence_date"] = occurrence.isoformat()
    entry["is_settled"] = is_occurrence_settled(item, occurrence, settled_before)
    entry["can_settle"] = occurrence in settleable
    return entry


@bp.get("/api/budget/current")
def get_current_budget() -> Response:
    """Get current budget state with calculated totals.

    Returns all income, accounts, expenses, settings, and computed totals.
    Includes deadline-aware calculations for amounts due before next payday.
    """
    session = get_session()

    # Get or create settings
    settings = session.query(BudgetSettings).first()
    if not settings:
        settings = BudgetSettings(tax_percentage=Decimal("25.0"), payday_day=25)
        session.add(settings)
        session.commit()

    # Get all data
    income_items = session.query(IncomeItem).order_by(IncomeItem.name).all()
    accounts = session.query(Account).order_by(Account.name).all()
    expenses = session.query(ExpenseItem).order_by(ExpenseItem.name).all()

    today = date.today()
    now = datetime.now()
    period_start = get_previous_payday(today, settings.payday_day)

    # The day from which money still counts as unmoved. Bills clear on their due
    # day; pay only does so on payday itself, so the two boundaries differ by a
    # day and each item type has to be judged against its own.
    expenses_settled_before = expense_window_start(today)
    income_settled_before = income_window_start(today, settings.payday_day)

    # Retire occurrence overrides the calendar has caught up with, then
    # auto-archive past ephemeral items. A one-time item still marked pending is
    # left alone: its money hasn't actually moved, so it isn't history yet.
    for income_item in income_items:
        if income_item.archived_at is None:
            clear_stale_overrides(
                income_item, today, income_settled_before, period_start
            )
        if income_item.archived_at is None and income_item.is_ephemeral:
            if (
                income_item.start_date
                and income_item.start_date < today
                and income_item.pending_occurrence is None
            ):
                income_item.archived_at = now
    for expense_item in expenses:
        if expense_item.archived_at is None:
            clear_stale_overrides(
                expense_item, today, expenses_settled_before, period_start
            )
        if expense_item.archived_at is None and expense_item.is_ephemeral:
            if (
                expense_item.start_date
                and expense_item.start_date < today
                and expense_item.pending_occurrence is None
            ):
                expense_item.archived_at = now
    session.commit()

    # Split active vs archived items
    active_income = [i for i in income_items if i.archived_at is None]
    archived_income = [i for i in income_items if i.archived_at is not None]
    active_expenses = [e for e in expenses if e.archived_at is None]
    archived_expenses = [e for e in expenses if e.archived_at is not None]

    # Calculate headline totals (active items only) via the shared helper
    totals = compute_budget_totals(session)
    gross_income = totals["gross_income"]
    net_income = totals["net_income"]
    current_balance = totals["current_balance"]
    total_expenses = totals["total_expenses"]
    net_position = totals["net_position"]

    # Calculate deadline-aware totals
    next_payday = get_next_payday(today, settings.payday_day)
    next_period_end = get_payday_after(next_payday, settings.payday_day)

    # A bill is assumed paid once its due day arrives — bills usually debit at the
    # start of the day and are then reflected in current_balance. So the current
    # period starts the day AFTER today: anything due today (or earlier) has cleared
    # and no longer counts as still-due (mirrors the income-on-payday handling in
    # calculate_income_before_payday). A bill the user has flagged as not debited
    # yet is added back by include_pending.
    current_period_start = expenses_settled_before

    expenses_before_payday = calculate_expenses_before_payday(
        active_expenses,
        current_period_start,
        next_payday,
        include_savings=False,
        include_pending=True,
    )
    savings_before_payday = calculate_expenses_before_payday(
        active_expenses,
        current_period_start,
        next_payday,
        include_savings=True,
        include_pending=True,
    )
    income_before_payday = calculate_income_before_payday(
        active_income,
        today,
        next_payday,
        settings.tax_percentage,
        payday_day=settings.payday_day,
        include_pending=True,
    )
    cc_payments_before_payday = calculate_cc_payments_in_window(
        accounts, today, today, next_payday
    )

    # Calculate next period totals (payday to following payday)
    expenses_next_period = calculate_expenses_before_payday(
        active_expenses, next_payday, next_period_end, include_savings=False
    )
    savings_next_period = calculate_expenses_before_payday(
        active_expenses, next_payday, next_period_end, include_savings=True
    )
    cc_payments_next_period = calculate_cc_payments_in_window(
        accounts, today, next_payday, next_period_end
    )
    income_next_period = calculate_income_before_payday(
        active_income,
        next_payday,
        next_period_end,
        settings.tax_percentage,
        payday_day=settings.payday_day,
    )

    # What next period's own money leaves once that period's obligations are
    # met: the amount that can be swept out to savings on payday without
    # touching the balance already in the account.
    unallocated_next_period = (
        income_next_period
        - expenses_next_period
        - savings_next_period
        - cc_payments_next_period
    )

    # Cash and card debt separately: the projection spends actual cash, and card
    # debt leaves it on the card's own due day rather than being netted off up
    # front. current_balance keeps the netted view for everything else.
    cash_balance = sum((a.balance for a in accounts if not a.is_credit), Decimal("0"))
    card_debt = sum((a.balance for a in accounts if a.is_credit), Decimal("0"))

    # Calculate expense occurrences for each period (for frontend display)
    # Returns expense dicts with next_occurrence_date for each period
    expenses_before_payday_list: list[dict] = []
    expenses_next_period_list: list[dict] = []
    expenses_future_list: list[dict] = []

    # Also keep ID lists for backward compatibility
    expenses_before_payday_ids: list[int] = []
    expenses_next_period_ids: list[int] = []
    expenses_future_ids: list[int] = []

    # Look further ahead for "future" expenses (13 months to catch yearly expenses)
    future_window_end = get_payday_after(next_period_end, settings.payday_day)
    for _ in range(12):  # 13 months total
        future_window_end = get_payday_after(future_window_end, settings.payday_day)

    for expense in active_expenses:
        if expense.is_savings_goal:
            continue

        # The current period runs from the payday that opened it, not from today:
        # bills that already came due stay visible (ticked off) so a debit that
        # hasn't actually landed can be flagged as still pending.
        occurrences_before_payday = get_item_occurrences(
            expense, period_start, next_payday
        )
        occurrences_next_period = get_item_occurrences(
            expense, next_payday, next_period_end
        )

        # The two occurrences whose state the user can still change: the next one
        # ahead of us and the last one to have come due this period. Anything
        # further out is a schedule edit, not a one-off timing correction.
        settleable = (
            get_next_occurrence(expense, expenses_settled_before, period_start),
            get_latest_due_occurrence(expense, expenses_settled_before, period_start),
        )

        # Older occurrences of the period are closed history — listing them would
        # only be noise, since nothing about them can be changed any more.
        rows_before_payday = [
            occurrence
            for occurrence in occurrences_before_payday
            if occurrence >= expenses_settled_before or occurrence in settleable
        ]

        # Add one entry per occurrence in "this month" and "next month"
        if rows_before_payday:
            expenses_before_payday_ids.append(expense.id)
            for occurrence in rows_before_payday:
                expenses_before_payday_list.append(
                    occurrence_entry(
                        expense, occurrence, expenses_settled_before, settleable
                    )
                )

        if occurrences_next_period:
            expenses_next_period_ids.append(expense.id)
            for occurrence in occurrences_next_period:
                expenses_next_period_list.append(
                    occurrence_entry(
                        expense, occurrence, expenses_settled_before, settleable
                    )
                )

        if not occurrences_before_payday and not occurrences_next_period:
            # Expense doesn't occur in either period - show only first future occurrence
            expenses_future_ids.append(expense.id)
            occurrences_future = get_item_occurrences(
                expense, next_period_end, future_window_end
            )
            if occurrences_future:
                # Only first occurrence for "future" (open-ended window)
                expense_dict = occurrence_entry(
                    expense, occurrences_future[0], expenses_settled_before, settleable
                )
            else:
                expense_dict = expense.to_dict()
                expense_dict["next_occurrence_date"] = None
                expense_dict["is_settled"] = False
                expense_dict["can_settle"] = False
            expenses_future_list.append(expense_dict)

    # Income is listed one row per item rather than one per occurrence, so each
    # row carries the single occurrence whose state is currently in question.
    income_list: list[dict] = []
    for income_item in active_income:
        entry = income_item.to_dict()
        checkpoint = get_checkpoint_occurrence(
            income_item, income_settled_before, period_start
        )
        entry["next_occurrence_date"] = checkpoint.isoformat() if checkpoint else None
        entry["is_settled"] = (
            is_occurrence_settled(income_item, checkpoint, income_settled_before)
            if checkpoint
            else False
        )
        entry["can_settle"] = checkpoint is not None
        income_list.append(entry)

    return jsonify(
        {
            "settings": settings.to_dict(),
            "income": income_list,
            "accounts": [a.to_dict() for a in accounts],
            "expenses": [e.to_dict() for e in active_expenses],
            "archived_income": [i.to_dict() for i in archived_income],
            "archived_expenses": [e.to_dict() for e in archived_expenses],
            "totals": {
                # Existing totals (backward compat)
                "gross_income": float(gross_income),
                "net_income": float(net_income),
                "current_balance": float(current_balance),
                # Split view: cash in hand, and what the cards owe against it
                "cash_balance": float(cash_balance),
                "card_debt": float(card_debt),
                "total_expenses": float(total_expenses),
                "net_position": float(net_position),
                # Frequency-normalized monthly rates (one-time items excluded)
                "monthly_expenses": float(totals["monthly_expenses"]),
                "monthly_net_income": float(totals["monthly_net_income"]),
                "monthly_surplus": float(totals["monthly_surplus"]),
                # Deadline-aware totals
                "next_payday": next_payday.isoformat(),
                "expenses_before_payday": float(expenses_before_payday),
                "income_before_payday": float(income_before_payday),
                "savings_before_payday": float(savings_before_payday),
                "cc_payments_before_payday": float(cc_payments_before_payday),
                # Next period totals (payday to following payday)
                "next_period_end": next_period_end.isoformat(),
                "expenses_next_period": float(expenses_next_period),
                "savings_next_period": float(savings_next_period),
                "cc_payments_next_period": float(cc_payments_next_period),
                "income_next_period": float(income_next_period),
                # Next period's own money, less next period's obligations
                "unallocated_next_period": float(unallocated_next_period),
                # Expense IDs for each period (for frontend filtering) - backward compat
                "expenses_before_payday_ids": expenses_before_payday_ids,
                "expenses_next_period_ids": expenses_next_period_ids,
                "expenses_future_ids": expenses_future_ids,
                # Expenses with occurrence dates for each period
                "expenses_before_payday_list": expenses_before_payday_list,
                "expenses_next_period_list": expenses_next_period_list,
                "expenses_future_list": expenses_future_list,
            },
        }
    )
