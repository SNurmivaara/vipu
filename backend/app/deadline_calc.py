"""Deadline calculation utilities for budget items.

Handles recurring and one-time payments/income with flexible frequencies.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Account, ExpenseItem, IncomeItem


def get_last_day_of_month(year: int, month: int) -> int:
    """Return last day of given month."""
    return monthrange(year, month)[1]


def normalize_day(day: int, year: int, month: int) -> int:
    """Normalize day to valid day in month.

    Handles cases like 31st in February -> 28th/29th.
    """
    last_day = get_last_day_of_month(year, month)
    return min(day, last_day)


def get_next_payday(today: date, payday_day: int) -> date:
    """Calculate next payday from today.

    Args:
        today: Current date
        payday_day: Day of month for payday (1-31)

    Returns:
        Next payday date (uses last day of month if payday_day > days in month)
    """
    normalized_day = normalize_day(payday_day, today.year, today.month)

    if today.day < normalized_day:
        # Payday is later this month
        return date(today.year, today.month, normalized_day)
    else:
        # Payday is next month
        if today.month == 12:
            next_month, next_year = 1, today.year + 1
        else:
            next_month, next_year = today.month + 1, today.year
        normalized_day = normalize_day(payday_day, next_year, next_month)
        return date(next_year, next_month, normalized_day)


def get_previous_payday(today: date, payday_day: int) -> date:
    """Calculate the payday that opened the pay period containing today.

    On payday itself the period is considered to start today, mirroring
    get_next_payday, which points at the following month once payday arrives.

    Args:
        today: Current date
        payday_day: Day of month for payday (1-31)

    Returns:
        The most recent payday at or before today
    """
    normalized_day = normalize_day(payday_day, today.year, today.month)

    if today.day >= normalized_day:
        return date(today.year, today.month, normalized_day)

    if today.month == 1:
        prev_month, prev_year = 12, today.year - 1
    else:
        prev_month, prev_year = today.month - 1, today.year
    normalized_day = normalize_day(payday_day, prev_year, prev_month)
    return date(prev_year, prev_month, normalized_day)


def get_payday_after(payday: date, payday_day: int) -> date:
    """Calculate the payday following a given payday.

    Args:
        payday: A payday date
        payday_day: Day of month for payday (1-31)

    Returns:
        The next payday after the given payday
    """
    if payday.month == 12:
        next_month, next_year = 1, payday.year + 1
    else:
        next_month, next_year = payday.month + 1, payday.year
    normalized_day = normalize_day(payday_day, next_year, next_month)
    return date(next_year, next_month, normalized_day)


def get_occurrences_in_window(
    due_day: int,
    frequency_value: int,
    frequency_unit: str,
    start_date: date | None,
    end_date: date | None,
    is_ephemeral: bool,
    archived_at: datetime | None,
    window_start: date,
    window_end: date,
) -> list[date]:
    """Get all dates this item occurs in [window_start, window_end) (end-exclusive).

    Handles:
    - "days": every N days from start_date (or due_day of current month)
    - "weeks": every N weeks (N*7 days)
    - "months": on due_day every N months
    - "years": on due_day every N years
    - Ephemeral: single occurrence on start_date

    Args:
        due_day: Day of month (1-31)
        frequency_value: Multiplier (e.g., 2 for "every 2 weeks")
        frequency_unit: "days", "weeks", "months", or "years"
        start_date: When this item starts (None = always existed)
        end_date: When this item ends (None = forever)
        is_ephemeral: True if one-time item
        archived_at: When item was archived (None = active)
        window_start: Start of calculation window
        window_end: End of calculation window

    Returns:
        List of dates when this item occurs in the window
    """
    occurrences: list[date] = []

    # Archived items don't occur
    if archived_at is not None:
        return []

    # Check if item is active in this window
    if end_date and end_date < window_start:
        return []
    if start_date and start_date > window_end:
        return []

    # Ephemeral: one-time on start_date (or due_day of current month if no start_date)
    if is_ephemeral:
        if start_date:
            occurrence = start_date
        else:
            # Fall back to due_day of window_start's month
            year, month = window_start.year, window_start.month
            occurrence_day = normalize_day(due_day, year, month)
            occurrence = date(year, month, occurrence_day)
        if window_start <= occurrence < window_end:
            occurrences.append(occurrence)
        return occurrences

    # Recurring logic based on frequency_unit
    if frequency_unit == "months":
        # On due_day every N months, phase-anchored to start_date's month so the
        # cadence stays stable regardless of which month a window happens to begin
        # in (a quarterly bill stays quarterly across every period). Without a
        # start_date there is no canonical phase, so fall back to window_start.
        anchor = start_date if start_date is not None else window_start
        anchor_total = anchor.year * 12 + (anchor.month - 1)
        window_start_total = window_start.year * 12 + (window_start.month - 1)

        # Jump to the in-phase month at or before window_start, then step forward.
        if window_start_total > anchor_total:
            steps = (window_start_total - anchor_total) // frequency_value
        else:
            steps = 0
        current_total = anchor_total + steps * frequency_value

        while True:
            year, month = current_total // 12, current_total % 12 + 1
            if date(year, month, 1) > window_end:
                break

            occurrence_day = normalize_day(due_day, year, month)
            occurrence = date(year, month, occurrence_day)

            if window_start <= occurrence < window_end:
                if start_date is None or occurrence >= start_date:
                    if end_date is None or occurrence <= end_date:
                        occurrences.append(occurrence)

            # Move to next occurrence (N months later)
            current_total += frequency_value

    elif frequency_unit == "years":
        # On due_day of start_date's month every N years, phase-anchored to
        # start_date's year (so "every 2 years" stays in phase). Without a
        # start_date, fall back to window_start's year and January.
        base_month = start_date.month if start_date else 1
        anchor_year = start_date.year if start_date else window_start.year

        # Jump to the in-phase year at or before window_start, then step forward.
        if window_start.year > anchor_year:
            steps = (window_start.year - anchor_year) // frequency_value
        else:
            steps = 0
        current_year = anchor_year + steps * frequency_value

        while True:
            occurrence_day = normalize_day(due_day, current_year, base_month)
            occurrence = date(current_year, base_month, occurrence_day)

            if occurrence > window_end:
                break

            if window_start <= occurrence < window_end:
                if start_date is None or occurrence >= start_date:
                    if end_date is None or occurrence <= end_date:
                        occurrences.append(occurrence)

            current_year += frequency_value

    elif frequency_unit in ("days", "weeks"):
        # Every N days or N*7 days
        interval = frequency_value if frequency_unit == "days" else frequency_value * 7

        # Need a reference point - use start_date or calculate from due_day
        if start_date:
            reference = start_date
        else:
            # Last-resort fallback for rows that predate the anchoring migration:
            # due_day of the window's own month, which makes the phase depend on
            # where the window happens to start. Anything created since is given
            # a start_date (see needs_anchor), so both windows agree.
            ref_day = normalize_day(due_day, window_start.year, window_start.month)
            reference = date(window_start.year, window_start.month, ref_day)

        # Find first occurrence at or after window_start
        if reference < window_start:
            days_diff = (window_start - reference).days
            periods_to_skip = (days_diff + interval - 1) // interval
            reference = reference + timedelta(days=periods_to_skip * interval)

        current = reference
        while current < window_end:
            if window_start <= current < window_end:
                if start_date is None or current >= start_date:
                    if end_date is None or current <= end_date:
                        occurrences.append(current)
            current = current + timedelta(days=interval)

    return occurrences


# How far ahead get_next_occurrence looks for the following occurrence. Long
# enough to catch multi-year schedules; the search is a cheap walk over dates.
OCCURRENCE_HORIZON_DAYS = 5 * 366


# Cadences that need an explicit anchor date. A "day 15, every 2 weeks" schedule
# says nothing about which day 15 the count starts from, so without a start_date
# the grid is generated relative to whichever window asks for it and the same
# item lands on different dates in different periods. Month and year cadences
# carry their own phase in due_day, so they don't need this.
ANCHORED_UNITS = ("days", "weeks")


def default_start_date(due_day: int, today: date) -> date:
    """Anchor for a day/week cadence created without a start_date.

    Pins the count to due_day of the current month, fixing the cadence once so
    every window afterwards agrees on it.
    """
    return date(
        today.year, today.month, normalize_day(due_day, today.year, today.month)
    )


def needs_anchor(
    frequency_unit: str, start_date: date | None, is_ephemeral: bool
) -> bool:
    """Whether this schedule would otherwise be left without a stable phase."""
    return frequency_unit in ANCHORED_UNITS and start_date is None and not is_ephemeral


def expense_window_start(today: date) -> date:
    """First day from which a bill still counts as due.

    Bills debit at the start of their due day and are then reflected in the
    account balance, so anything dated today or earlier has cleared.
    """
    return today + timedelta(days=1)


def income_window_start(today: date, payday_day: int | None) -> date:
    """First day from which income still counts as on its way.

    Unlike a bill, pay dated today is not assumed to have landed — except on
    payday itself, when it is taken to be in the balance already.
    """
    if payday_day is not None:
        normalized = normalize_day(payday_day, today.year, today.month)
        if today.day == normalized:
            return today + timedelta(days=1)
    return today


def get_item_occurrences(
    item: "ExpenseItem | IncomeItem", window_start: date, window_end: date
) -> list[date]:
    """Dates the item is scheduled to occur in [window_start, window_end).

    The raw schedule: settled/pending overrides are not applied here, since the
    display lists need the occurrence itself in order to show its state.
    """
    return get_occurrences_in_window(
        due_day=item.due_day,
        frequency_value=item.frequency_value,
        frequency_unit=item.frequency_unit,
        start_date=item.start_date,
        end_date=item.end_date,
        is_ephemeral=item.is_ephemeral,
        archived_at=item.archived_at,
        window_start=window_start,
        window_end=window_end,
    )


def get_next_occurrence(
    item: "ExpenseItem | IncomeItem", settled_before: date, period_start: date
) -> date | None:
    """The item's first occurrence still ahead of us, or None if it has none.

    "Ahead of us" is the window start the money totals use (expense_window_start
    or income_window_start), so the occurrence the user can tick off is exactly
    the one those totals are still counting.

    Searched from period_start rather than from that boundary, because a day or
    week cadence without a start_date takes its phase from where the window
    begins: a search starting elsewhere would put the item on a different set of
    dates than the period list the user is ticking off.
    """
    occurrences = get_item_occurrences(
        item,
        period_start,
        period_start + timedelta(days=OCCURRENCE_HORIZON_DAYS),
    )
    return next((o for o in occurrences if o >= settled_before), None)


def get_latest_due_occurrence(
    item: "ExpenseItem | IncomeItem", settled_before: date, period_start: date
) -> date | None:
    """The item's most recent occurrence already behind us this pay period."""
    occurrences = get_item_occurrences(item, period_start, settled_before)
    return occurrences[-1] if occurrences else None


def is_occurrence_settled(
    item: "ExpenseItem | IncomeItem", occurrence: date, settled_before: date
) -> bool:
    """Whether the money for this occurrence has already moved.

    By default an occurrence is assumed to have moved once its day is behind us:
    settled_before is the same boundary the money totals use, so an occurrence
    counts as settled exactly when those totals have stopped counting it. Either
    direction can be overridden for a single occurrence — settled_occurrence for
    one paid or received early, pending_occurrence for one whose day has passed
    without the money moving (a debit that waits for the next banking day).
    """
    if occurrence >= settled_before:
        return occurrence == item.settled_occurrence
    return occurrence != item.pending_occurrence


def get_checkpoint_occurrence(
    item: "ExpenseItem | IncomeItem", settled_before: date, period_start: date
) -> date | None:
    """The single occurrence whose settled state is currently in question.

    Used where an item is shown as one row rather than one row per occurrence
    (income). An override always wins, so the user can always undo it.
    Otherwise it is whichever of the last occurrence this pay period and the
    next one up is nearer: just after a due day the question is "did it actually
    land?", and as the next one approaches it becomes "has it come early?".
    """
    if item.pending_occurrence is not None:
        return item.pending_occurrence
    if item.settled_occurrence is not None:
        return item.settled_occurrence

    upcoming = get_next_occurrence(item, settled_before, period_start)
    latest = get_latest_due_occurrence(item, settled_before, period_start)

    if latest is None:
        return upcoming
    if upcoming is None:
        return latest
    return (
        latest if (settled_before - latest) <= (upcoming - settled_before) else upcoming
    )


def apply_occurrence_override(
    item: "ExpenseItem | IncomeItem",
    occurrence: date,
    settled: bool,
    settled_before: date,
    period_start: date,
) -> bool:
    """Record whether the money for one occurrence has moved yet.

    Only two occurrences can be overridden, which is what keeps the correction a
    one-off: the next one ahead of us (paid or received early) and the last one
    to have come due this pay period (its day passed, the money didn't move).
    Everything after them keeps running on the item's own schedule, so the
    forecast is untouched.

    Returns False if the date is neither of those, leaving the item unchanged.
    """
    if occurrence == get_next_occurrence(item, settled_before, period_start):
        item.settled_occurrence = occurrence if settled else None
        return True

    if occurrence == get_latest_due_occurrence(item, settled_before, period_start):
        item.pending_occurrence = None if settled else occurrence
        # An occurrence that has come due no longer needs a settled mark: the
        # default assumption already says its money has moved.
        if item.settled_occurrence == occurrence:
            item.settled_occurrence = None
        return True

    return False


def calculate_income_before_payday(
    income_items: list["IncomeItem"],
    today: date,
    next_payday: date,
    default_tax_pct: Decimal,
    payday_day: int | None = None,
    include_pending: bool = False,
) -> Decimal:
    """Calculate total net income arriving through next payday.

    The window includes income arriving ON payday (inclusive end).
    On payday itself, today's income is assumed already in the account balance,
    so the window starts from tomorrow to avoid double-counting.

    Args:
        income_items: List of income items
        today: Current date
        next_payday: Next payday date
        default_tax_pct: Default tax percentage for taxed income
        payday_day: Day of month for payday (used to detect if today is payday)
        include_pending: Add back occurrences whose day has passed but which the
                         user marked as not received yet. Only for the current
                         period — a later window would count them twice.

    Returns:
        Total net income due through next payday
    """
    return sum(
        (
            movement.amount
            for movement in income_movements(
                income_items,
                today,
                next_payday,
                default_tax_pct,
                payday_day=payday_day,
                include_pending=include_pending,
            )
        ),
        Decimal("0"),
    )


def income_movements(
    income_items: list["IncomeItem"],
    today: date,
    next_payday: date,
    default_tax_pct: Decimal,
    payday_day: int | None = None,
    include_pending: bool = False,
) -> list["CashMovement"]:
    """Each pay occurrence landing through next payday, on the day it lands."""
    movements: list[CashMovement] = []

    # Include income arriving ON payday (window_end is exclusive, so +1 day)
    inclusive_end = next_payday + timedelta(days=1)

    # If today is payday, that income is already reflected in the account
    # balance — start from tomorrow to avoid double-counting
    window_start = income_window_start(today, payday_day)

    for item in income_items:
        occurrences = [
            occurrence
            for occurrence in get_item_occurrences(item, window_start, inclusive_end)
            if occurrence != item.settled_occurrence
        ]

        # A payment marked "not received yet" sits before the window (its day has
        # passed), so it is added back rather than filtered in. It is dated to the
        # start of the window: it is owed now, not on a day behind us.
        if (
            include_pending
            and item.pending_occurrence is not None
            and item.pending_occurrence < window_start
        ):
            occurrences.append(window_start)

        amount = item.calculate_net(default_tax_pct)
        kind = "deduction" if item.is_deduction else "pay"
        movements.extend(
            CashMovement(occurrence, amount, item.name, kind)
            for occurrence in occurrences
        )

    return movements


def calculate_expenses_before_payday(
    expense_items: list["ExpenseItem"],
    today: date,
    next_payday: date,
    include_savings: bool = False,
    include_pending: bool = False,
) -> Decimal:
    """Calculate total expenses due before next payday.

    Args:
        expense_items: List of expense items
        today: Current date
        next_payday: Next payday date
        include_savings: If True, only include savings goals.
                        If False, only include regular expenses.
        include_pending: Add back occurrences whose due day has passed but which
                         the user marked as not debited yet. Only for the current
                         period — a later window would count them twice.

    Returns:
        Total expenses due before next payday
    """
    kind = "savings" if include_savings else "bill"
    return -sum(
        (
            movement.amount
            for movement in expense_movements(
                expense_items, today, next_payday, include_pending=include_pending
            )
            if movement.kind == kind
        ),
        Decimal("0"),
    )


def expense_movements(
    expense_items: list["ExpenseItem"],
    window_start: date,
    window_end: date,
    include_pending: bool = False,
) -> list["CashMovement"]:
    """Each bill and savings transfer due in the window, on the day it debits."""
    movements: list[CashMovement] = []

    for item in expense_items:
        occurrences = [
            occurrence
            for occurrence in get_item_occurrences(item, window_start, window_end)
            if occurrence != item.settled_occurrence
        ]

        # A bill marked "not paid yet" sits before the window (its due day has
        # passed), so it is added back rather than filtered in. It is dated to
        # the start of the window: it is owed now, not on a day behind us.
        if (
            include_pending
            and item.pending_occurrence is not None
            and item.pending_occurrence < window_start
        ):
            occurrences.append(window_start)

        kind = "savings" if item.is_savings_goal else "bill"
        movements.extend(
            CashMovement(occurrence, -item.amount, item.name, kind)
            for occurrence in occurrences
        )

    return movements


@dataclass(frozen=True)
class CashMovement:
    """One dated movement of money, signed: positive in, negative out.

    The primitive the period totals are built from. A total is the sum of the
    movements behind it, so a figure on the page and the day-by-day walk that
    finds the low point can't describe different money.
    """

    date: date
    amount: Decimal
    label: str
    #: "pay", "deduction", "bill", "savings" or "card"
    kind: str


def find_low_point(
    opening_balance: Decimal, movements: list[CashMovement], start: date
) -> tuple[date, Decimal]:
    """The lowest the balance gets while these movements play out.

    A period that ends comfortably can still go through the floor in the middle
    of itself: bills land on their own days and pay usually lands on one. Only
    walking it day by day shows that.

    A day is taken as a whole rather than ordered within itself: pay generally
    clears before the debits here, and a payment that does bounce in the morning
    can simply be retried once the day's money has landed. So a bill sharing a
    day with the pay that covers it is not a shortfall.

    Never worse than the balance you start with, so an account that is already
    overdrawn reports today rather than some later date.
    """
    by_day: dict[date, Decimal] = {}
    for movement in movements:
        by_day[movement.date] = (
            by_day.get(movement.date, Decimal("0")) + movement.amount
        )

    balance = opening_balance
    low_date = start
    low_balance = balance

    for day in sorted(by_day):
        balance += by_day[day]
        if balance < low_balance:
            low_balance = balance
            low_date = day

    return low_date, low_balance


@dataclass(frozen=True)
class PeriodFlow:
    """What one pay period does to the account, broken down by where it goes.

    The single answer to "what happens in this period". Every surface that talks
    about a period reads it from here: the summary card, the section headers and
    the roadmap projection. Two of them computing their own version is how they
    ended up disagreeing about the same period.
    """

    start: date
    end: date
    #: Every dated movement in the period, the totals below summed from them
    movements: tuple[CashMovement, ...]

    def _by_kind(self, kind: str) -> Decimal:
        return sum((m.amount for m in self.movements if m.kind == kind), Decimal("0"))

    @property
    def income(self) -> Decimal:
        """Net pay arriving in the period, before payroll deductions."""
        return self._by_kind("pay")

    @property
    def deductions(self) -> Decimal:
        """Payroll deductions, negative, taken out of that pay."""
        return self._by_kind("deduction")

    @property
    def bills(self) -> Decimal:
        return -self._by_kind("bill")

    @property
    def savings(self) -> Decimal:
        return -self._by_kind("savings")

    @property
    def card_payments(self) -> Decimal:
        return -self._by_kind("card")

    @property
    def money_in(self) -> Decimal:
        """Pay actually landing in the account, deductions already taken off."""
        return self.income + self.deductions

    @property
    def money_out(self) -> Decimal:
        """Everything leaving the account in the period."""
        return self.bills + self.savings + self.card_payments

    @property
    def net(self) -> Decimal:
        """What the period leaves over: the amount free to be swept out."""
        return self.money_in - self.money_out


def calculate_period_flow(
    income_items: list["IncomeItem"],
    expense_items: list["ExpenseItem"],
    accounts: list["Account"],
    default_tax_pct: Decimal,
    payday_day: int,
    today: date,
    start: date,
    end: date,
) -> PeriodFlow:
    """Money in and out over [start, end), by category.

    The part-period we are standing in is treated differently in one respect:
    only it has occurrences behind us, which the user may have flagged as paid
    early or not paid yet. Later periods are entirely ahead, so no override can
    apply to them.
    """
    is_current = start == today

    # Bills clear on their due day, so the current period only still owes what
    # falls after today; a later period owes everything in it.
    expense_start = expense_window_start(today) if is_current else start

    movements = [
        *income_movements(
            income_items,
            start,
            end,
            default_tax_pct,
            payday_day=payday_day,
            include_pending=is_current,
        ),
        *expense_movements(
            expense_items, expense_start, end, include_pending=is_current
        ),
        *card_movements(accounts, today, start, end),
    ]

    return PeriodFlow(start=start, end=end, movements=tuple(movements))


def get_card_payment_date(account: "Account", today: date) -> date:
    """When this card's balance comes off the account.

    A balance is paid off once, on the first due day at or after today, not on
    every due day: the model has no notion of the card being spent on again, so
    charging it in each period would take the same debt out repeatedly. A card
    with no due day set has no schedule to place it on, so it falls due now.
    """
    if account.payment_due_day is None:
        return today

    due_day = normalize_day(account.payment_due_day, today.year, today.month)
    due_date = date(today.year, today.month, due_day)
    if due_date >= today:
        return due_date

    if today.month == 12:
        next_month, next_year = 1, today.year + 1
    else:
        next_month, next_year = today.month + 1, today.year
    due_day = normalize_day(account.payment_due_day, next_year, next_month)
    return date(next_year, next_month, due_day)


def calculate_cc_payments_in_window(
    accounts: list["Account"],
    today: date,
    window_start: date,
    window_end: date,
) -> Decimal:
    """Total credit card debt coming off the account in [start, end).

    Each card is charged in exactly one window, whichever contains its next
    payment date, so consecutive periods can be added up without the same
    balance being subtracted twice.
    """
    return -sum(
        (
            movement.amount
            for movement in card_movements(accounts, today, window_start, window_end)
        ),
        Decimal("0"),
    )


def card_movements(
    accounts: list["Account"],
    today: date,
    window_start: date,
    window_end: date,
) -> list["CashMovement"]:
    """Each card balance coming off the account, on the day it is paid."""
    movements: list[CashMovement] = []

    for account in accounts:
        if not account.is_credit or account.balance == 0:
            continue

        payment_date = get_card_payment_date(account, today)
        if window_start <= payment_date < window_end:
            movements.append(
                CashMovement(payment_date, -abs(account.balance), account.name, "card")
            )

    return movements
