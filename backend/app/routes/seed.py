from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import Account, BudgetSettings, ExpenseItem, IncomeItem

bp = APIBlueprint("seed", __name__, tag="Data Management")


@bp.post("/api/seed")
def seed_data() -> Response:
    """Seed example data for demos/testing.

    Clears all existing data and creates example accounts, income, and expenses.
    """
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


@bp.post("/api/reset")
def reset_data() -> Response:
    """Reset all budget data.

    Clears all accounts, income, expenses, and resets settings to default.
    """
    session = get_session()

    # Clear existing data
    session.query(Account).delete()
    session.query(IncomeItem).delete()
    session.query(ExpenseItem).delete()
    session.query(BudgetSettings).delete()

    # Create default settings
    settings = BudgetSettings(tax_percentage=Decimal("25.0"))
    session.add(settings)

    session.commit()

    return jsonify({"message": "Budget data reset successfully"})


@bp.get("/api/export")
def export_data() -> Response:
    """Export all budget data as JSON.

    Returns all accounts, income items, expenses, and settings for backup/transfer.
    """
    session = get_session()

    settings = session.query(BudgetSettings).first()
    accounts = session.query(Account).all()
    income_items = session.query(IncomeItem).all()
    expenses = session.query(ExpenseItem).all()

    export = {
        "version": 1,
        "settings": {
            "tax_percentage": float(settings.tax_percentage) if settings else 25.0,
        },
        "accounts": [
            {
                "name": a.name,
                "balance": float(a.balance),
                "is_credit": a.is_credit,
            }
            for a in accounts
        ],
        "income": [
            {
                "name": i.name,
                "gross_amount": float(i.gross_amount),
                "is_taxed": i.is_taxed,
                "tax_percentage": (
                    float(i.tax_percentage) if i.tax_percentage is not None else None
                ),
            }
            for i in income_items
        ],
        "expenses": [
            {
                "name": e.name,
                "amount": float(e.amount),
                "is_savings_goal": e.is_savings_goal,
            }
            for e in expenses
        ],
    }

    return jsonify(export)


@bp.post("/api/import")
def import_data() -> Response | tuple[Response, int]:
    """Import budget data from JSON.

    Replaces all existing data with the imported data.
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate version
    version = data.get("version", 1)
    if version != 1:
        return jsonify({"error": f"Unsupported export version: {version}"}), 400

    # Clear existing data
    session.query(Account).delete()
    session.query(IncomeItem).delete()
    session.query(ExpenseItem).delete()
    session.query(BudgetSettings).delete()

    # Import settings
    settings_data = data.get("settings", {})
    settings = BudgetSettings(
        tax_percentage=Decimal(str(settings_data.get("tax_percentage", 25.0)))
    )
    session.add(settings)

    # Import accounts
    accounts_data = data.get("accounts", [])
    for a in accounts_data:
        account = Account(
            name=a["name"],
            balance=Decimal(str(a["balance"])),
            is_credit=a.get("is_credit", False),
        )
        session.add(account)

    # Import income
    income_data = data.get("income", [])
    for i in income_data:
        income = IncomeItem(
            name=i["name"],
            gross_amount=Decimal(str(i["gross_amount"])),
            is_taxed=i.get("is_taxed", True),
            tax_percentage=(
                Decimal(str(i["tax_percentage"]))
                if i.get("tax_percentage") is not None
                else None
            ),
        )
        session.add(income)

    # Import expenses
    expenses_data = data.get("expenses", [])
    for e in expenses_data:
        expense = ExpenseItem(
            name=e["name"],
            amount=Decimal(str(e["amount"])),
            is_savings_goal=e.get("is_savings_goal", False),
        )
        session.add(expense)

    session.commit()

    return jsonify(
        {
            "message": "Data imported successfully",
            "counts": {
                "accounts": len(accounts_data),
                "income": len(income_data),
                "expenses": len(expenses_data),
            },
        }
    )
