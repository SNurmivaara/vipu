from datetime import date, datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify

from app import get_session
from app.deadline_calc import (
    calculate_cc_payments_before_payday,
    calculate_expenses_before_payday,
    calculate_income_before_payday,
    get_next_payday,
    get_payday_after,
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

    # Auto-archive past ephemeral items
    today = date.today()
    now = datetime.now()
    for income_item in income_items:
        if income_item.archived_at is None and income_item.is_ephemeral:
            if income_item.start_date and income_item.start_date < today:
                income_item.archived_at = now
    for expense_item in expenses:
        if expense_item.archived_at is None and expense_item.is_ephemeral:
            if expense_item.start_date and expense_item.start_date < today:
                expense_item.archived_at = now
    session.commit()

    # Split active vs archived items
    active_income = [i for i in income_items if i.archived_at is None]
    archived_income = [i for i in income_items if i.archived_at is not None]
    active_expenses = [e for e in expenses if e.archived_at is None]
    archived_expenses = [e for e in expenses if e.archived_at is not None]

    # Calculate totals (using active items only)
    # Gross income excludes deductions
    gross_income = sum(
        (i.gross_amount for i in active_income if not i.is_deduction),
        Decimal("0"),
    )
    net_income = calculate_net_income(active_income, settings.tax_percentage)
    current_balance = sum((a.balance for a in accounts), Decimal("0"))
    total_expenses = sum((e.amount for e in active_expenses), Decimal("0"))
    net_position = current_balance - total_expenses

    # Calculate deadline-aware totals
    next_payday = get_next_payday(today, settings.payday_day)
    next_period_end = get_payday_after(next_payday, settings.payday_day)

    expenses_before_payday = calculate_expenses_before_payday(
        active_expenses, today, next_payday, include_savings=False
    )
    savings_before_payday = calculate_expenses_before_payday(
        active_expenses, today, next_payday, include_savings=True
    )
    income_before_payday = calculate_income_before_payday(
        active_income,
        today,
        next_payday,
        settings.tax_percentage,
        payday_day=settings.payday_day,
    )
    cc_payments_before_payday = calculate_cc_payments_before_payday(
        accounts, today, next_payday
    )

    # Calculate next period totals (payday to following payday)
    expenses_next_period = calculate_expenses_before_payday(
        active_expenses, next_payday, next_period_end, include_savings=False
    )
    savings_next_period = calculate_expenses_before_payday(
        active_expenses, next_payday, next_period_end, include_savings=True
    )
    cc_payments_next_period = calculate_cc_payments_before_payday(
        accounts, next_payday, next_period_end, include_unscheduled=False
    )
    income_next_period = calculate_income_before_payday(
        active_income,
        next_payday,
        next_period_end,
        settings.tax_percentage,
        payday_day=settings.payday_day,
    )

    return jsonify(
        {
            "settings": settings.to_dict(),
            "income": [i.to_dict() for i in active_income],
            "accounts": [a.to_dict() for a in accounts],
            "expenses": [e.to_dict() for e in active_expenses],
            "archived_income": [i.to_dict() for i in archived_income],
            "archived_expenses": [e.to_dict() for e in archived_expenses],
            "totals": {
                # Existing totals (backward compat)
                "gross_income": float(gross_income),
                "net_income": float(net_income),
                "current_balance": float(current_balance),
                "total_expenses": float(total_expenses),
                "net_position": float(net_position),
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
            },
        }
    )
