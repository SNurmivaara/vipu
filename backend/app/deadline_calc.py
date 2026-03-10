"""Deadline calculation utilities for budget items.

Handles recurring and one-time payments/income with flexible frequencies.
"""

from calendar import monthrange
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
    """Get all dates this item occurs between window_start and window_end (inclusive).

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
        if window_start <= occurrence <= window_end:
            occurrences.append(occurrence)
        return occurrences

    # Recurring logic based on frequency_unit
    if frequency_unit == "months":
        # On due_day every N months
        current = date(window_start.year, window_start.month, 1)

        while current <= window_end:
            occurrence_day = normalize_day(due_day, current.year, current.month)
            occurrence = date(current.year, current.month, occurrence_day)

            if window_start <= occurrence <= window_end:
                if start_date is None or occurrence >= start_date:
                    if end_date is None or occurrence <= end_date:
                        occurrences.append(occurrence)

            # Move to next occurrence (N months later)
            month = current.month + frequency_value
            year = current.year
            while month > 12:
                month -= 12
                year += 1
            current = date(year, month, 1)

    elif frequency_unit == "years":
        # On due_day of same month every N years
        # Use start_date's month, or January if no start_date
        base_month = start_date.month if start_date else 1
        current_year = window_start.year

        while True:
            occurrence_day = normalize_day(due_day, current_year, base_month)
            occurrence = date(current_year, base_month, occurrence_day)

            if occurrence > window_end:
                break

            if window_start <= occurrence <= window_end:
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
            # Use due_day of current month as reference
            ref_day = normalize_day(due_day, window_start.year, window_start.month)
            reference = date(window_start.year, window_start.month, ref_day)

        # Find first occurrence at or after window_start
        if reference < window_start:
            days_diff = (window_start - reference).days
            periods_to_skip = (days_diff + interval - 1) // interval
            reference = reference + timedelta(days=periods_to_skip * interval)

        current = reference
        while current <= window_end:
            if window_start <= current <= window_end:
                if start_date is None or current >= start_date:
                    if end_date is None or current <= end_date:
                        occurrences.append(current)
            current = current + timedelta(days=interval)

    return occurrences


def calculate_income_before_payday(
    income_items: list["IncomeItem"],
    today: date,
    next_payday: date,
    default_tax_pct: Decimal,
) -> Decimal:
    """Calculate total net income arriving before next payday.

    Args:
        income_items: List of income items
        today: Current date
        next_payday: Next payday date
        default_tax_pct: Default tax percentage for taxed income

    Returns:
        Total net income due before next payday
    """
    total = Decimal("0")

    for item in income_items:
        occurrences = get_occurrences_in_window(
            due_day=item.due_day,
            frequency_value=item.frequency_value,
            frequency_unit=item.frequency_unit,
            start_date=item.start_date,
            end_date=item.end_date,
            is_ephemeral=item.is_ephemeral,
            archived_at=item.archived_at,
            window_start=today,
            window_end=next_payday,
        )

        if occurrences:
            net_per_occurrence = item.calculate_net(default_tax_pct)
            total += net_per_occurrence * len(occurrences)

    return total


def calculate_expenses_before_payday(
    expense_items: list["ExpenseItem"],
    today: date,
    next_payday: date,
    include_savings: bool = False,
) -> Decimal:
    """Calculate total expenses due before next payday.

    Args:
        expense_items: List of expense items
        today: Current date
        next_payday: Next payday date
        include_savings: If True, only include savings goals.
                        If False, only include regular expenses.

    Returns:
        Total expenses due before next payday
    """
    total = Decimal("0")

    for item in expense_items:
        # Filter by savings goal flag
        if item.is_savings_goal != include_savings:
            continue

        occurrences = get_occurrences_in_window(
            due_day=item.due_day,
            frequency_value=item.frequency_value,
            frequency_unit=item.frequency_unit,
            start_date=item.start_date,
            end_date=item.end_date,
            is_ephemeral=item.is_ephemeral,
            archived_at=item.archived_at,
            window_start=today,
            window_end=next_payday,
        )

        if occurrences:
            total += item.amount * len(occurrences)

    return total


def calculate_cc_payments_before_payday(
    accounts: list["Account"],
    today: date,
    next_payday: date,
) -> Decimal:
    """Calculate credit card payments due before next payday.

    Args:
        accounts: List of accounts
        today: Current date
        next_payday: Next payday date

    Returns:
        Total credit card payments due before next payday
    """
    total = Decimal("0")

    for account in accounts:
        if not account.is_credit:
            continue

        # If no payment_due_day set, include full balance
        if account.payment_due_day is None:
            total += abs(account.balance)
            continue

        # Check if payment_due_day falls in window
        # Check current month
        due_day = normalize_day(account.payment_due_day, today.year, today.month)
        due_date = date(today.year, today.month, due_day)

        if today <= due_date <= next_payday:
            total += abs(account.balance)
            continue

        # Check next month
        if today.month == 12:
            next_month, next_year = 1, today.year + 1
        else:
            next_month, next_year = today.month + 1, today.year

        due_day = normalize_day(account.payment_due_day, next_year, next_month)
        due_date = date(next_year, next_month, due_day)

        if today <= due_date <= next_payday:
            total += abs(account.balance)

    return total
