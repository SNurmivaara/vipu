from decimal import Decimal

from flask import Blueprint, Response, jsonify

from app import get_session
from app.models import Account, BudgetSettings, ExpenseItem, IncomeItem

bp = Blueprint("budget", __name__)


def calculate_net_income(
    income_items: list[IncomeItem], default_tax_pct: Decimal
) -> Decimal:
    """Calculate total net income after taxes."""
    total = Decimal("0")
    for item in income_items:
        total += item.calculate_net(default_tax_pct)
    return total


@bp.route("/api/budget/current", methods=["GET"])
def get_current_budget() -> Response:
    """Get current budget state with calculated totals."""
    session = get_session()

    # Get or create settings
    settings = session.query(BudgetSettings).first()
    if not settings:
        settings = BudgetSettings(tax_percentage=Decimal("25.0"))
        session.add(settings)
        session.commit()

    # Get all data
    income_items = session.query(IncomeItem).order_by(IncomeItem.name).all()
    accounts = session.query(Account).order_by(Account.name).all()
    expenses = session.query(ExpenseItem).order_by(ExpenseItem.name).all()

    # Calculate totals
    gross_income = sum((i.gross_amount for i in income_items), Decimal("0"))
    net_income = calculate_net_income(income_items, settings.tax_percentage)
    current_balance = sum((a.balance for a in accounts), Decimal("0"))
    total_expenses = sum((e.amount for e in expenses), Decimal("0"))
    net_position = current_balance - total_expenses

    return jsonify(
        {
            "settings": settings.to_dict(),
            "income": [i.to_dict() for i in income_items],
            "accounts": [a.to_dict() for a in accounts],
            "expenses": [e.to_dict() for e in expenses],
            "totals": {
                "gross_income": float(gross_income),
                "net_income": float(net_income),
                "current_balance": float(current_balance),
                "total_expenses": float(total_expenses),
                "net_position": float(net_position),
            },
        }
    )
