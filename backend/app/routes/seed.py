from decimal import Decimal

from flask import Blueprint, Response, jsonify

from app import get_session
from app.models import Account, BudgetSettings, ExpenseItem, IncomeItem

bp = Blueprint("seed", __name__)


@bp.route("/api/seed", methods=["POST"])
def seed_data() -> Response:
    """Seed example data for demos/testing."""
    session = get_session()

    # Clear existing data
    session.query(Account).delete()
    session.query(IncomeItem).delete()
    session.query(ExpenseItem).delete()
    session.query(BudgetSettings).delete()

    # Create settings
    settings = BudgetSettings(tax_percentage=Decimal("25.0"))
    session.add(settings)

    # Create income items
    income_items = [
        IncomeItem(
            name="Salary",
            gross_amount=Decimal("5000.00"),
            is_taxed=True,
        ),
        IncomeItem(
            name="Side income",
            gross_amount=Decimal("500.00"),
            is_taxed=True,
        ),
        IncomeItem(
            name="Lunch benefit",
            gross_amount=Decimal("200.00"),
            is_taxed=True,
            tax_percentage=Decimal("75.0"),  # 75% taxable portion
        ),
    ]
    for item in income_items:
        session.add(item)

    # Create accounts
    accounts = [
        Account(
            name="Checking",
            balance=Decimal("3500.00"),
            is_credit=False,
        ),
        Account(
            name="Savings",
            balance=Decimal("2000.00"),
            is_credit=False,
        ),
        Account(
            name="Credit Card",
            balance=Decimal("-500.00"),
            is_credit=True,
        ),
    ]
    for account in accounts:
        session.add(account)

    # Create expenses
    expenses = [
        ExpenseItem(name="Rent", amount=Decimal("1200.00")),
        ExpenseItem(name="Groceries", amount=Decimal("400.00")),
        ExpenseItem(name="Utilities", amount=Decimal("150.00")),
        ExpenseItem(name="Transport", amount=Decimal("100.00")),
        ExpenseItem(name="Subscriptions", amount=Decimal("50.00")),
        ExpenseItem(name="Savings", amount=Decimal("500.00")),
    ]
    for expense in expenses:
        session.add(expense)

    session.commit()

    return jsonify(
        {
            "message": "Example data seeded successfully",
            "counts": {
                "settings": 1,
                "income_items": len(income_items),
                "accounts": len(accounts),
                "expenses": len(expenses),
            },
        }
    )
