from datetime import date, datetime, timedelta
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import (
    Account,
    BudgetBalanceEntry,
    BudgetSettings,
    BudgetSnapshot,
    ExpenseItem,
    Goal,
    IncomeItem,
    NetWorthCategory,
    NetWorthEntry,
    NetWorthGroup,
    NetWorthSnapshot,
)
from app.routes.goals import DATE_FORMAT_ERROR, VALID_GOAL_TYPES
from app.routes.networth import VALID_GROUP_TYPES
from app.validation import (
    InvalidInput,
    parse_amount,
    parse_int,
    parse_name,
    parse_percentage,
    register_validation,
)

bp = APIBlueprint("seed", __name__, tag="Data Management")
register_validation(bp)


@bp.post("/api/seed")
def seed_data() -> Response:
    """Seed example data for demos/testing.

    Clears all existing data and creates example accounts, income, and expenses.
    Includes various deadline configurations for comprehensive testing.
    """
    session = get_session()

    # Clear existing data
    session.query(BudgetBalanceEntry).delete()
    session.query(BudgetSnapshot).delete()
    session.query(Account).delete()
    session.query(IncomeItem).delete()
    session.query(ExpenseItem).delete()
    session.query(BudgetSettings).delete()

    # Create settings with payday on 25th
    settings = BudgetSettings(tax_percentage=Decimal("25.0"), payday_day=25)
    session.add(settings)

    # Create income items with various frequencies
    income_items = [
        # Monthly salary on payday
        IncomeItem(
            name="Salary",
            gross_amount=Decimal("5000.00"),
            is_taxed=True,
            due_day=25,
            frequency_value=1,
            frequency_unit="months",
        ),
        # Bi-weekly side gig
        IncomeItem(
            name="Freelance",
            gross_amount=Decimal("300.00"),
            is_taxed=True,
            due_day=15,
            frequency_value=2,
            frequency_unit="weeks",
        ),
        # Quarterly dividend
        IncomeItem(
            name="Dividends",
            gross_amount=Decimal("200.00"),
            is_taxed=False,
            due_day=1,
            frequency_value=3,
            frequency_unit="months",
        ),
        # One-time bonus (ephemeral)
        IncomeItem(
            name="Year-end bonus",
            gross_amount=Decimal("1000.00"),
            is_taxed=True,
            due_day=20,
            frequency_value=1,
            frequency_unit="months",
            is_ephemeral=True,
            start_date=date.today(),
        ),
        # Lunch benefit deduction
        IncomeItem(
            name="Lunch benefit",
            gross_amount=Decimal("200.00"),
            is_taxed=True,
            tax_percentage=Decimal("75.0"),
            is_deduction=True,
            due_day=25,
            frequency_value=1,
            frequency_unit="months",
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
            balance=Decimal("8000.00"),
            is_credit=False,
        ),
        # Credit card with payment due day
        Account(
            name="Visa",
            balance=Decimal("-750.00"),
            is_credit=True,
            payment_due_day=15,
        ),
        Account(
            name="Mastercard",
            balance=Decimal("-200.00"),
            is_credit=True,
            payment_due_day=5,
        ),
    ]
    for account in accounts:
        session.add(account)

    # Calculate some future dates for variety
    today = date.today()
    next_week = today + timedelta(days=7)
    in_3_months = today + timedelta(days=90)

    # Create expenses with various frequencies
    expenses = [
        # Monthly rent on 1st
        ExpenseItem(
            name="Rent",
            amount=Decimal("1200.00"),
            due_day=1,
            frequency_value=1,
            frequency_unit="months",
        ),
        # Weekly groceries (shows multiple occurrences per period)
        ExpenseItem(
            name="Groceries",
            amount=Decimal("100.00"),
            due_day=today.day,  # Use today's day so first occurrence is soon
            frequency_value=1,
            frequency_unit="weeks",
        ),
        # Monthly utilities
        ExpenseItem(
            name="Utilities",
            amount=Decimal("150.00"),
            due_day=15,
            frequency_value=1,
            frequency_unit="months",
        ),
        # Bi-weekly transport pass
        ExpenseItem(
            name="Transport",
            amount=Decimal("50.00"),
            due_day=today.day,
            frequency_value=2,
            frequency_unit="weeks",
        ),
        # Quarterly tax payment (shows in "Future" if not due soon)
        ExpenseItem(
            name="Quarterly taxes",
            amount=Decimal("500.00"),
            due_day=15,
            frequency_value=3,
            frequency_unit="months",
            start_date=in_3_months,  # Starts 3 months from now
        ),
        # Yearly insurance - starts 3 months out to show in "Future"
        ExpenseItem(
            name="Home insurance",
            amount=Decimal("1200.00"),
            due_day=10,
            frequency_value=1,
            frequency_unit="years",
            start_date=in_3_months,
        ),
        # Monthly subscriptions
        ExpenseItem(
            name="Subscriptions",
            amount=Decimal("50.00"),
            due_day=1,
            frequency_value=1,
            frequency_unit="months",
        ),
        # One-time expense coming up next week
        ExpenseItem(
            name="Concert tickets",
            amount=Decimal("150.00"),
            due_day=next_week.day,
            frequency_value=1,
            frequency_unit="months",
            is_ephemeral=True,
            start_date=next_week,
        ),
        # One-time expense in the future (shows in "Future" section)
        ExpenseItem(
            name="Vacation booking",
            amount=Decimal("800.00"),
            due_day=in_3_months.day,
            frequency_value=1,
            frequency_unit="months",
            is_ephemeral=True,
            start_date=in_3_months,
        ),
    ]
    for expense in expenses:
        session.add(expense)

    # Roadmap goals: a sequential plan funded by the monthly surplus
    session.query(Goal).filter(
        Goal.goal_type.in_(("savings_goal", "debt_payoff"))
    ).delete()
    roadmap_goals = [
        Goal(
            name="Pay off Visa",
            goal_type="debt_payoff",
            target_value=Decimal("750.00"),
            current_amount=Decimal("0"),
            priority=0,
        ),
        Goal(
            name="Emergency fund",
            goal_type="savings_goal",
            target_value=Decimal("6000.00"),
            current_amount=Decimal("2000.00"),
            priority=1,
        ),
        Goal(
            name="Travel fund",
            goal_type="savings_goal",
            target_value=Decimal("3000.00"),
            current_amount=Decimal("0"),
            priority=2,
        ),
    ]
    for goal in roadmap_goals:
        session.add(goal)

    session.commit()

    # Create budget history snapshots (simulating weekly tracking)
    # Work backwards from today: 6 weekly snapshots showing realistic
    # fluctuations (salary on 25th, spending in between)
    snapshot_data: list[tuple[int, dict[str, Decimal]]] = [
        # 5 weeks ago – just after payday, balances are high
        (
            35,
            {
                "checking": Decimal("4200.00"),
                "savings": Decimal("7500.00"),
                "visa": Decimal("-300.00"),
                "mastercard": Decimal("-100.00"),
            },
        ),
        # 4 weeks ago – spending has started
        (
            28,
            {
                "checking": Decimal("3400.00"),
                "savings": Decimal("7500.00"),
                "visa": Decimal("-550.00"),
                "mastercard": Decimal("-150.00"),
            },
        ),
        # 3 weeks ago – mid-period, more spending
        (
            21,
            {
                "checking": Decimal("2900.00"),
                "savings": Decimal("7500.00"),
                "visa": Decimal("-700.00"),
                "mastercard": Decimal("-180.00"),
            },
        ),
        # 2 weeks ago – payday hit, balances jump up
        (
            14,
            {
                "checking": Decimal("5100.00"),
                "savings": Decimal("8000.00"),
                "visa": Decimal("-400.00"),
                "mastercard": Decimal("-120.00"),
            },
        ),
        # 1 week ago – some spending after payday
        (
            7,
            {
                "checking": Decimal("4100.00"),
                "savings": Decimal("8000.00"),
                "visa": Decimal("-600.00"),
                "mastercard": Decimal("-180.00"),
            },
        ),
        # Today – current state (matches seeded account balances)
        (
            0,
            {
                "checking": Decimal("3500.00"),
                "savings": Decimal("8000.00"),
                "visa": Decimal("-750.00"),
                "mastercard": Decimal("-200.00"),
            },
        ),
    ]

    account_names = {
        "checking": ("Checking", False),
        "savings": ("Savings", False),
        "visa": ("Visa", True),
        "mastercard": ("Mastercard", True),
    }

    # Look up the account IDs we just created
    created_accounts = session.query(Account).all()
    account_id_map = {a.name: a.id for a in created_accounts}

    prev_balance: Decimal | None = None
    for days_ago, balances in snapshot_data:
        snap_date = today - timedelta(days=days_ago)
        balance = (
            balances["checking"]
            + balances["savings"]
            + balances["visa"]
            + balances["mastercard"]
        )
        change = balance - prev_balance if prev_balance is not None else Decimal("0")

        snapshot = BudgetSnapshot(
            date=snap_date,
            current_balance=balance,
            change_from_previous=change,
        )
        session.add(snapshot)
        session.flush()

        for key, (name, is_credit) in account_names.items():
            session.add(
                BudgetBalanceEntry(
                    snapshot_id=snapshot.id,
                    account_id=account_id_map.get(name),
                    account_name=name,
                    balance=balances[key],
                    is_credit=is_credit,
                )
            )

        prev_balance = balance

    session.commit()

    return jsonify(
        {
            "message": "Example data seeded successfully",
            "counts": {
                "settings": 1,
                "income_items": len(income_items),
                "accounts": len(accounts),
                "expenses": len(expenses),
                "goals": len(roadmap_goals),
                "budget_snapshots": len(snapshot_data),
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
    session.query(BudgetBalanceEntry).delete()
    session.query(BudgetSnapshot).delete()
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
                "priority": g.priority,
                "current_amount": (
                    float(g.current_amount) if g.current_amount is not None else None
                ),
            }
            for g in goals
        ],
    }

    return jsonify(export)


def _import_list(data: dict, key: str) -> list[dict]:
    """The list of objects stored under key, or an empty list when absent."""
    items = data.get(key, [])
    if not isinstance(items, list):
        raise InvalidInput(f"{key} must be a list")
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise InvalidInput(f"{key}[{i}] must be an object")
    return items


def _require(item: dict, key: str, path: str) -> object:
    """The value under key, which must be present."""
    if key not in item:
        raise InvalidInput(f"{path}.{key} is required")
    return item[key]


def _non_negative_amount(value: object, field: str) -> Decimal:
    """A goal amount: between 0 and the maximum, as the goal routes accept."""
    amount = parse_amount(value, field)
    if amount < 0:
        raise InvalidInput(f"{field} must not be negative")
    return amount


def _validate_budget_import(data: dict) -> dict:
    """Check the budget part of an import and return model arguments.

    Applies the limits of the create routes, so an import cannot store a value
    they would refuse.
    """
    settings_data = data.get("settings", {})
    if not isinstance(settings_data, dict):
        raise InvalidInput("settings must be an object")

    accounts = []
    for i, a in enumerate(_import_list(data, "accounts")):
        path = f"accounts[{i}]"
        accounts.append(
            {
                "name": parse_name(_require(a, "name", path), f"{path}.name"),
                "balance": parse_amount(a.get("balance", 0), f"{path}.balance"),
                "is_credit": bool(a.get("is_credit", False)),
            }
        )

    income = []
    for i, item in enumerate(_import_list(data, "income")):
        path = f"income[{i}]"
        tax_pct = item.get("tax_percentage")
        income.append(
            {
                "name": parse_name(_require(item, "name", path), f"{path}.name"),
                "gross_amount": parse_amount(
                    _require(item, "gross_amount", path), f"{path}.gross_amount"
                ),
                "is_taxed": bool(item.get("is_taxed", True)),
                "tax_percentage": (
                    parse_percentage(tax_pct, f"{path}.tax_percentage")
                    if tax_pct is not None
                    else None
                ),
                "is_deduction": bool(item.get("is_deduction", False)),
            }
        )

    expenses = []
    for i, e in enumerate(_import_list(data, "expenses")):
        path = f"expenses[{i}]"
        expenses.append(
            {
                "name": parse_name(_require(e, "name", path), f"{path}.name"),
                "amount": parse_amount(_require(e, "amount", path), f"{path}.amount"),
                "is_savings_goal": bool(e.get("is_savings_goal", False)),
            }
        )

    return {
        "tax_percentage": parse_percentage(
            settings_data.get("tax_percentage", 25.0), "settings.tax_percentage"
        ),
        "accounts": accounts,
        "income": income,
        "expenses": expenses,
    }


def _validate_snapshots_import(data: dict) -> list[dict]:
    """Check the net worth snapshots of an import."""
    snapshots = []
    seen_months: set[tuple[int, int]] = set()
    for i, snap in enumerate(_import_list(data, "networth_snapshots")):
        path = f"networth_snapshots[{i}]"
        month = parse_int(_require(snap, "month", path), f"{path}.month", 1, 12)
        year = parse_int(_require(snap, "year", path), f"{path}.year", 1900, 2100)
        if (year, month) in seen_months:
            raise InvalidInput(f"{path} repeats the snapshot for {year}-{month:02d}")
        seen_months.add((year, month))

        entries = []
        seen_categories: set[str] = set()
        for j, entry in enumerate(_import_list(snap, "entries")):
            entry_path = f"{path}.entries[{j}]"
            category_name = str(entry.get("category_name", ""))
            if category_name in seen_categories:
                raise InvalidInput(f"{entry_path} repeats category {category_name!r}")
            seen_categories.add(category_name)
            entries.append(
                {
                    "category_name": category_name,
                    "amount": parse_amount(
                        entry.get("amount", 0), f"{entry_path}.amount"
                    ),
                }
            )
        snapshots.append({"month": month, "year": year, "entries": entries})
    return snapshots


def _validate_goals_import(data: dict) -> list[dict]:
    """Check the goals of an import and return model arguments."""
    goals = []
    for i, g in enumerate(_import_list(data, "goals")):
        path = f"goals[{i}]"
        goal_type = str(_require(g, "goal_type", path)).strip()
        if goal_type not in VALID_GOAL_TYPES:
            types_str = ", ".join(VALID_GOAL_TYPES)
            raise InvalidInput(f"{path}.goal_type must be one of: {types_str}")

        target_date = None
        if g.get("target_date"):
            try:
                target_date = datetime.fromisoformat(
                    str(g["target_date"]).replace("Z", "+00:00")
                )
            except ValueError:
                raise InvalidInput(f"{path}.{DATE_FORMAT_ERROR}") from None

        priority = g.get("priority")
        current_amount = g.get("current_amount")
        category_name = g.get("category_name")
        goals.append(
            {
                "name": parse_name(_require(g, "name", path), f"{path}.name"),
                "goal_type": goal_type,
                "target_value": _non_negative_amount(
                    _require(g, "target_value", path), f"{path}.target_value"
                ),
                "category_name": str(category_name) if category_name else None,
                "target_date": target_date,
                "is_active": bool(g.get("is_active", True)),
                "priority": (
                    parse_int(priority, f"{path}.priority")
                    if priority is not None
                    else None
                ),
                "current_amount": (
                    _non_negative_amount(current_amount, f"{path}.current_amount")
                    if current_amount is not None
                    else None
                ),
            }
        )
    return goals


def _validate_networth_import(data: dict) -> dict:
    """Check the net worth and goal part of a version 2 import."""
    groups = []
    for i, g in enumerate(_import_list(data, "networth_groups")):
        path = f"networth_groups[{i}]"
        group_type = str(_require(g, "group_type", path)).lower()
        if group_type not in VALID_GROUP_TYPES:
            types_str = ", ".join(VALID_GROUP_TYPES)
            raise InvalidInput(f"{path}.group_type must be one of: {types_str}")
        color = str(g.get("color", "#6b7280"))
        if not color.startswith("#") or len(color) != 7:
            raise InvalidInput(
                f"{path}.color must be a valid hex color (e.g., #6b7280)"
            )
        groups.append(
            {
                "name": parse_name(_require(g, "name", path), f"{path}.name"),
                "group_type": group_type,
                "color": color,
                "display_order": parse_int(
                    g.get("display_order", 0), f"{path}.display_order"
                ),
            }
        )

    categories = []
    for i, c in enumerate(_import_list(data, "networth_categories")):
        path = f"networth_categories[{i}]"
        categories.append(
            {
                "name": parse_name(_require(c, "name", path), f"{path}.name"),
                "group_name": str(c.get("group_name", "")),
                "is_personal": bool(c.get("is_personal", True)),
                "display_order": parse_int(
                    c.get("display_order", 0), f"{path}.display_order"
                ),
            }
        )

    return {
        "groups": groups,
        "categories": categories,
        "snapshots": _validate_snapshots_import(data),
        "goals": _validate_goals_import(data),
    }


@bp.post("/api/import")
def import_data() -> Response | tuple[Response, int]:
    """Import data from JSON.

    Replaces all existing data with the imported data.
    Supports version 1 (budget only) and version 2 (full data with net worth).
    The whole file is checked first against the limits of the create routes;
    an invalid value rejects the import with a 400 and changes nothing.
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400
    if not isinstance(data, dict):
        return jsonify({"error": "Import data must be an object"}), 400

    # Validate version
    version = data.get("version", 1)
    if isinstance(version, bool) or version not in (1, 2):
        return jsonify({"error": f"Unsupported export version: {version}"}), 400

    budget = _validate_budget_import(data)
    networth = _validate_networth_import(data) if version == 2 else None

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

    session.add(BudgetSettings(tax_percentage=budget["tax_percentage"]))
    session.add_all(Account(**a) for a in budget["accounts"])
    session.add_all(IncomeItem(**i) for i in budget["income"])
    session.add_all(ExpenseItem(**e) for e in budget["expenses"])

    counts: dict = {
        "accounts": len(budget["accounts"]),
        "income": len(budget["income"]),
        "expenses": len(budget["expenses"]),
    }

    # Import net worth data if version 2
    if networth is not None:
        # Import groups first
        group_name_to_id: dict[str, int] = {}

        for g in networth["groups"]:
            group = NetWorthGroup(**g)
            session.add(group)
            session.flush()  # Get the ID
            group_name_to_id[g["name"]] = group.id

        # Import categories
        category_name_to_id: dict[str, int] = {}

        for c in networth["categories"]:
            group_id = group_name_to_id.get(c["group_name"])
            if not group_id:
                continue  # Skip if group not found

            category = NetWorthCategory(
                name=c["name"],
                group_id=group_id,
                is_personal=c["is_personal"],
                display_order=c["display_order"],
            )
            session.add(category)
            session.flush()  # Get the ID
            category_name_to_id[c["name"]] = category.id

        # Import snapshots with entries
        # Sort by date to ensure correct change_from_previous calculation
        snapshots_sorted = sorted(
            networth["snapshots"], key=lambda s: (s["year"], s["month"])
        )

        previous_net_worth: Decimal | None = None
        for s in snapshots_sorted:
            snapshot = NetWorthSnapshot(month=s["month"], year=s["year"])
            session.add(snapshot)
            session.flush()  # Get the ID

            # Add entries
            for entry_data in s["entries"]:
                category_id = category_name_to_id.get(entry_data["category_name"])
                if not category_id:
                    continue  # Skip if category not found

                entry = NetWorthEntry(
                    snapshot_id=snapshot.id,
                    category_id=category_id,
                    amount=entry_data["amount"],
                )
                session.add(entry)

            # Calculate snapshot totals with previous month's net worth
            snapshot.calculate_totals(previous_net_worth)
            previous_net_worth = snapshot.net_worth

        # Import goals
        for g in networth["goals"]:
            category_name = g.pop("category_name")
            category_id = (
                category_name_to_id.get(category_name) if category_name else None
            )
            session.add(Goal(**g, category_id=category_id))

        counts["networth_groups"] = len(networth["groups"])
        counts["networth_categories"] = len(networth["categories"])
        counts["networth_snapshots"] = len(networth["snapshots"])
        counts["goals"] = len(networth["goals"])

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
