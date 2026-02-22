from datetime import datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import (
    Account,
    BudgetSettings,
    ExpenseItem,
    Goal,
    IncomeItem,
    NetWorthCategory,
    NetWorthEntry,
    NetWorthGroup,
    NetWorthSnapshot,
)

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
            tax_percentage=Decimal("75.0"),  # 75% deduction rate
            is_deduction=True,
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
    """Export all data as JSON.

    Returns all budget data, net worth data, and goals for backup/transfer.
    Version 2 includes net worth groups, categories, snapshots, and goals.
    """
    session = get_session()

    # Budget data
    settings = session.query(BudgetSettings).first()
    accounts = session.query(Account).all()
    income_items = session.query(IncomeItem).all()
    expenses = session.query(ExpenseItem).all()

    # Net worth data
    groups = session.query(NetWorthGroup).order_by(NetWorthGroup.display_order).all()
    categories = (
        session.query(NetWorthCategory).order_by(NetWorthCategory.display_order).all()
    )
    snapshots = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year, NetWorthSnapshot.month)
        .all()
    )
    goals = session.query(Goal).all()

    # Build group name lookup for categories
    group_lookup = {g.id: g.name for g in groups}
    # Build category name lookup for snapshots and goals
    category_lookup = {c.id: c.name for c in categories}

    export = {
        "version": 2,
        # Budget data
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
                "is_deduction": i.is_deduction,
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
        # Net worth data
        "networth_groups": [
            {
                "name": g.name,
                "group_type": g.group_type,
                "color": g.color,
                "display_order": g.display_order,
            }
            for g in groups
        ],
        "networth_categories": [
            {
                "name": c.name,
                "group_name": group_lookup.get(c.group_id, ""),
                "is_personal": c.is_personal,
                "display_order": c.display_order,
            }
            for c in categories
        ],
        "networth_snapshots": [
            {
                "month": s.month,
                "year": s.year,
                "entries": [
                    {
                        "category_name": category_lookup.get(e.category_id, ""),
                        "amount": float(e.amount) if e.amount else 0,
                    }
                    for e in s.entries
                ],
            }
            for s in snapshots
        ],
        "goals": [
            {
                "name": g.name,
                "goal_type": g.goal_type,
                "target_value": float(g.target_value),
                "category_name": (
                    category_lookup.get(g.category_id, "") if g.category_id else None
                ),
                "target_date": g.target_date.isoformat() if g.target_date else None,
                "is_active": g.is_active,
            }
            for g in goals
        ],
    }

    return jsonify(export)


@bp.post("/api/import")
def import_data() -> Response | tuple[Response, int]:
    """Import data from JSON.

    Replaces all existing data with the imported data.
    Supports version 1 (budget only) and version 2 (full data with net worth).
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate version
    version = data.get("version", 1)
    if version not in (1, 2):
        return jsonify({"error": f"Unsupported export version: {version}"}), 400

    # Clear existing budget data
    session.query(Account).delete()
    session.query(IncomeItem).delete()
    session.query(ExpenseItem).delete()
    session.query(BudgetSettings).delete()

    # Clear net worth data if version 2
    if version == 2:
        session.query(Goal).delete()
        session.query(NetWorthEntry).delete()
        session.query(NetWorthSnapshot).delete()
        session.query(NetWorthCategory).delete()
        session.query(NetWorthGroup).delete()

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
            is_deduction=i.get("is_deduction", False),
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

    counts: dict = {
        "accounts": len(accounts_data),
        "income": len(income_data),
        "expenses": len(expenses_data),
    }

    # Import net worth data if version 2
    if version == 2:
        # Import groups first
        groups_data = data.get("networth_groups", [])
        group_name_to_id: dict[str, int] = {}

        for g in groups_data:
            group = NetWorthGroup(
                name=g["name"],
                group_type=g["group_type"],
                color=g.get("color", "#6b7280"),
                display_order=g.get("display_order", 0),
            )
            session.add(group)
            session.flush()  # Get the ID
            group_name_to_id[g["name"]] = group.id

        # Import categories
        categories_data = data.get("networth_categories", [])
        category_name_to_id: dict[str, int] = {}

        for c in categories_data:
            group_id = group_name_to_id.get(c.get("group_name", ""))
            if not group_id:
                continue  # Skip if group not found

            category = NetWorthCategory(
                name=c["name"],
                group_id=group_id,
                is_personal=c.get("is_personal", True),
                display_order=c.get("display_order", 0),
            )
            session.add(category)
            session.flush()  # Get the ID
            category_name_to_id[c["name"]] = category.id

        # Import snapshots with entries
        # Sort by date to ensure correct change_from_previous calculation
        snapshots_data = data.get("networth_snapshots", [])
        snapshots_data_sorted = sorted(
            snapshots_data, key=lambda s: (s["year"], s["month"])
        )

        previous_net_worth: Decimal | None = None
        for s in snapshots_data_sorted:
            snapshot = NetWorthSnapshot(
                month=s["month"],
                year=s["year"],
            )
            session.add(snapshot)
            session.flush()  # Get the ID

            # Add entries
            for entry_data in s.get("entries", []):
                category_id = category_name_to_id.get(entry_data.get("category_name"))
                if not category_id:
                    continue  # Skip if category not found

                entry = NetWorthEntry(
                    snapshot_id=snapshot.id,
                    category_id=category_id,
                    amount=Decimal(str(entry_data.get("amount", 0))),
                )
                session.add(entry)

            # Calculate snapshot totals with previous month's net worth
            snapshot.calculate_totals(previous_net_worth)
            previous_net_worth = snapshot.net_worth

        # Import goals
        goals_data = data.get("goals", [])
        for g in goals_data:
            category_id = None
            if g.get("category_name"):
                category_id = category_name_to_id.get(g["category_name"])

            target_date = None
            if g.get("target_date"):
                target_date = datetime.fromisoformat(
                    g["target_date"].replace("Z", "+00:00")
                )

            goal = Goal(
                name=g["name"],
                goal_type=g["goal_type"],
                target_value=Decimal(str(g["target_value"])),
                category_id=category_id,
                target_date=target_date,
                is_active=g.get("is_active", True),
            )
            session.add(goal)

        counts["networth_groups"] = len(groups_data)
        counts["networth_categories"] = len(categories_data)
        counts["networth_snapshots"] = len(snapshots_data)
        counts["goals"] = len(goals_data)

    session.commit()

    return jsonify({"message": "Data imported successfully", "counts": counts})


@bp.get("/api/budget/snapshot-prefill")
def get_snapshot_prefill() -> Response:
    """Get budget account balances formatted for snapshot prefill.

    Returns accounts with their balances, suitable for pre-filling a net worth
    snapshot form. Credit cards are returned as liabilities (positive amounts).
    """
    session = get_session()

    accounts = session.query(Account).all()

    prefill_items = [
        {
            "name": a.name,
            "amount": abs(float(a.balance)),
            "is_liability": a.is_credit,
        }
        for a in accounts
    ]

    return jsonify(prefill_items)
