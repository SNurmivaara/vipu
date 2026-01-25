from datetime import datetime
from decimal import Decimal, InvalidOperation

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from sqlalchemy.orm import Session

from app import get_session
from app.forecasting import generate_net_worth_forecast
from app.models import NetWorthCategory, NetWorthEntry, NetWorthGroup, NetWorthSnapshot

bp = APIBlueprint("networth", __name__, tag="Net Worth")

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion

# Valid group types
VALID_GROUP_TYPES = {"asset", "liability"}


# =============================================================================
# Group Endpoints
# =============================================================================


@bp.get("/api/networth/groups")
def list_groups() -> Response:
    """List all net worth groups, sorted by display order then name."""
    session = get_session()
    groups = (
        session.query(NetWorthGroup)
        .order_by(NetWorthGroup.display_order, NetWorthGroup.name)
        .all()
    )
    return jsonify([g.to_dict() for g in groups])


@bp.post("/api/networth/groups")
def create_group() -> Response | tuple[Response, int]:
    """Create a new net worth group."""
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate required fields
    if "name" not in data:
        return jsonify({"error": "name is required"}), 400
    if "group_type" not in data:
        return jsonify({"error": "group_type is required"}), 400

    # Validate name
    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return (
            jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
            400,
        )

    # Validate group_type
    group_type = str(data["group_type"]).lower()
    if group_type not in VALID_GROUP_TYPES:
        return (
            jsonify({"error": f"group_type must be one of: {VALID_GROUP_TYPES}"}),
            400,
        )

    # Get optional fields
    color = str(data.get("color", "#6b7280"))
    if not color.startswith("#") or len(color) != 7:
        return (
            jsonify({"error": "color must be a valid hex color (e.g., #6b7280)"}),
            400,
        )

    try:
        display_order = int(data.get("display_order", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "display_order must be an integer"}), 400

    group = NetWorthGroup(
        name=name,
        group_type=group_type,
        color=color,
        display_order=display_order,
    )
    session.add(group)
    session.commit()

    return jsonify(group.to_dict()), 201


@bp.put("/api/networth/groups/<int:group_id>")
def update_group(group_id: int) -> Response | tuple[Response, int]:
    """Update an existing group."""
    session = get_session()
    group = session.query(NetWorthGroup).filter_by(id=group_id).first()

    if not group:
        return jsonify({"error": "Group not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Update fields if provided
    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            return (
                jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
                400,
            )
        group.name = name

    if "group_type" in data:
        group_type = str(data["group_type"]).lower()
        if group_type not in VALID_GROUP_TYPES:
            return (
                jsonify({"error": f"group_type must be one of: {VALID_GROUP_TYPES}"}),
                400,
            )
        group.group_type = group_type

    if "color" in data:
        color = str(data["color"])
        if not color.startswith("#") or len(color) != 7:
            return (
                jsonify({"error": "color must be a valid hex color (e.g., #6b7280)"}),
                400,
            )
        group.color = color

    if "display_order" in data:
        try:
            group.display_order = int(data["display_order"])
        except (ValueError, TypeError):
            return jsonify({"error": "display_order must be an integer"}), 400

    session.commit()
    return jsonify(group.to_dict())


@bp.delete("/api/networth/groups/<int:group_id>")
def delete_group(group_id: int) -> Response | tuple[Response, int]:
    """Delete a group. Fails if group has categories."""
    session = get_session()

    # Lock the group row to prevent race conditions
    group = (
        session.query(NetWorthGroup).filter_by(id=group_id).with_for_update().first()
    )

    if not group:
        return jsonify({"error": "Group not found"}), 404

    # Check if group has categories
    category_count = (
        session.query(NetWorthCategory).filter_by(group_id=group_id).count()
    )
    if category_count > 0:
        msg = f"Cannot delete group: has {category_count} categories"
        return jsonify({"error": msg}), 409

    session.delete(group)
    session.commit()
    return jsonify({"message": "Group deleted"})


# =============================================================================
# Category Endpoints
# =============================================================================


@bp.get("/api/networth/categories")
def list_categories() -> Response:
    """List all net worth categories, sorted by display order then name."""
    session = get_session()
    categories = (
        session.query(NetWorthCategory)
        .order_by(NetWorthCategory.display_order, NetWorthCategory.name)
        .all()
    )
    return jsonify([c.to_dict() for c in categories])


@bp.post("/api/networth/categories")
def create_category() -> Response | tuple[Response, int]:
    """Create a new net worth category."""
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate required fields
    if "name" not in data:
        return jsonify({"error": "name is required"}), 400
    if "group_id" not in data:
        return jsonify({"error": "group_id is required"}), 400

    # Validate name
    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return (
            jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
            400,
        )

    # Validate group exists
    try:
        group_id = int(data["group_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "group_id must be an integer"}), 400

    group = session.query(NetWorthGroup).filter_by(id=group_id).first()
    if not group:
        return jsonify({"error": f"Group {group_id} not found"}), 400

    # Get optional fields
    is_personal = bool(data.get("is_personal", True))
    try:
        display_order = int(data.get("display_order", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "display_order must be an integer"}), 400

    category = NetWorthCategory(
        name=name,
        group_id=group_id,
        is_personal=is_personal,
        display_order=display_order,
    )
    session.add(category)
    session.commit()

    return jsonify(category.to_dict()), 201


@bp.put("/api/networth/categories/<int:category_id>")
def update_category(category_id: int) -> Response | tuple[Response, int]:
    """Update an existing category."""
    session = get_session()
    category = session.query(NetWorthCategory).filter_by(id=category_id).first()

    if not category:
        return jsonify({"error": "Category not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Update fields if provided
    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            return (
                jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
                400,
            )
        category.name = name

    if "group_id" in data:
        try:
            group_id = int(data["group_id"])
        except (ValueError, TypeError):
            return jsonify({"error": "group_id must be an integer"}), 400

        group = session.query(NetWorthGroup).filter_by(id=group_id).first()
        if not group:
            return jsonify({"error": f"Group {group_id} not found"}), 400
        category.group_id = group_id

    if "is_personal" in data:
        category.is_personal = bool(data["is_personal"])

    if "display_order" in data:
        try:
            category.display_order = int(data["display_order"])
        except (ValueError, TypeError):
            return jsonify({"error": "display_order must be an integer"}), 400

    session.commit()
    return jsonify(category.to_dict())


@bp.delete("/api/networth/categories/<int:category_id>")
def delete_category(category_id: int) -> Response | tuple[Response, int]:
    """Delete a category. Fails if category is used in any snapshot entries."""
    session = get_session()

    # Lock the category row to prevent race conditions
    category = (
        session.query(NetWorthCategory)
        .filter_by(id=category_id)
        .with_for_update()
        .first()
    )

    if not category:
        return jsonify({"error": "Category not found"}), 404

    # Check if category is used in any entries (also locked by FK relationship)
    entry_count = (
        session.query(NetWorthEntry).filter_by(category_id=category_id).count()
    )
    if entry_count > 0:
        msg = f"Cannot delete category: used in {entry_count} snapshot entries"
        return jsonify({"error": msg}), 409

    session.delete(category)
    session.commit()
    return jsonify({"message": "Category deleted"})


@bp.post("/api/networth/categories/seed")
def seed_categories() -> Response | tuple[Response, int]:
    """Seed default net worth groups and categories."""
    session = get_session()

    # Check if groups or categories already exist
    existing_group = session.query(NetWorthGroup).first()
    existing_category = session.query(NetWorthCategory).first()
    if existing_group or existing_category:
        return (
            jsonify(
                {"error": "Groups or categories already exist. Delete first to reseed."}
            ),
            409,
        )

    # Default groups with colors
    default_groups = [
        # (name, group_type, color, display_order)
        ("Cash", "asset", "#22c55e", 1),  # green
        ("Investments", "asset", "#3b82f6", 2),  # blue
        ("Crypto", "asset", "#f59e0b", 3),  # amber
        ("Property", "asset", "#8b5cf6", 4),  # purple
        ("Loans", "liability", "#ef4444", 10),  # red
        ("Credit Card", "liability", "#f97316", 11),  # orange
    ]

    group_by_name: dict[str, NetWorthGroup] = {}
    for name, group_type, color, order in default_groups:
        group = NetWorthGroup(
            name=name,
            group_type=group_type,
            color=color,
            display_order=order,
        )
        session.add(group)
        session.flush()  # Get the ID
        group_by_name[name] = group

    # Default categories (name, group_name, is_personal, display_order)
    default_categories = [
        # Cash group
        ("Checking", "Cash", True, 1),
        ("Savings", "Cash", True, 2),
        ("Rent Account", "Cash", True, 3),
        ("Company Checkings", "Cash", False, 4),
        # Investments group
        ("Personal Investments", "Investments", True, 10),
        ("Personal Bonds", "Investments", True, 11),
        ("Company Investments", "Investments", False, 12),
        # Crypto group
        ("Crypto", "Crypto", True, 20),
        # Property group
        ("House/Apartment", "Property", True, 30),
        # Loans group
        ("Student Loan", "Loans", True, 50),
        # Credit Card group
        ("Credit Card", "Credit Card", True, 60),
    ]

    for name, group_name, is_personal, order in default_categories:
        category = NetWorthCategory(
            name=name,
            group_id=group_by_name[group_name].id,
            is_personal=is_personal,
            display_order=order,
        )
        session.add(category)

    session.commit()

    categories = session.query(NetWorthCategory).all()
    groups = session.query(NetWorthGroup).all()
    return (
        jsonify(
            {
                "message": "Seeded default groups and categories",
                "groups": len(groups),
                "categories": len(categories),
            }
        ),
        201,
    )


# =============================================================================
# Snapshot Endpoints
# =============================================================================


def _get_previous_net_worth(session: Session, year: int, month: int) -> Decimal | None:
    """Get the net worth from the previous month's snapshot."""
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1

    previous = (
        session.query(NetWorthSnapshot)
        .filter_by(year=prev_year, month=prev_month)
        .first()
    )
    return previous.net_worth if previous else None


def _recalculate_next_month(session: Session, year: int, month: int) -> None:
    """Recalculate the next month's change_from_previous if it exists."""
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    next_snapshot = (
        session.query(NetWorthSnapshot)
        .filter_by(year=next_year, month=next_month)
        .first()
    )

    if next_snapshot:
        # Get the current month's net worth (which was just updated)
        current = (
            session.query(NetWorthSnapshot).filter_by(year=year, month=month).first()
        )
        previous_net_worth = current.net_worth if current else None
        next_snapshot.calculate_totals(previous_net_worth)


def _validate_snapshot_data(data: dict) -> tuple[bool, str | None]:
    """Validate snapshot input data. Returns (is_valid, error_message)."""
    if "month" not in data:
        return False, "month is required"
    if "year" not in data:
        return False, "year is required"

    try:
        month = int(data["month"])
        if month < 1 or month > 12:
            return False, "month must be between 1 and 12"
    except (ValueError, TypeError):
        return False, "month must be an integer"

    try:
        year = int(data["year"])
        if year < 1900 or year > 2100:
            return False, "year must be between 1900 and 2100"
    except (ValueError, TypeError):
        return False, "year must be an integer"

    # Validate entries if provided
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        return False, "entries must be a list"

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return False, f"entries[{i}] must be an object"
        if "category_id" not in entry:
            return False, f"entries[{i}].category_id is required"
        if "amount" in entry:
            try:
                value = Decimal(str(entry["amount"]))
                if abs(value) > MAX_AMOUNT_VALUE:
                    return False, f"entries[{i}].amount exceeds maximum allowed value"
            except (ValueError, TypeError, InvalidOperation):
                return False, f"entries[{i}].amount must be a number"

    return True, None


@bp.get("/api/networth")
def list_snapshots() -> Response:
    """List all net worth snapshots, sorted by date descending."""
    session = get_session()
    snapshots = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .all()
    )
    return jsonify([s.to_dict() for s in snapshots])


@bp.get("/api/networth/<int:year>/<int:month>")
def get_snapshot(year: int, month: int) -> Response | tuple[Response, int]:
    """Get a specific snapshot by year and month."""
    if month < 1 or month > 12:
        return jsonify({"error": "month must be between 1 and 12"}), 400

    session = get_session()
    snapshot = session.query(NetWorthSnapshot).filter_by(year=year, month=month).first()

    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    return jsonify(snapshot.to_dict())


@bp.post("/api/networth")
def create_snapshot() -> Response | tuple[Response, int]:
    """Create a new net worth snapshot with entries.

    Requires month and year. Entries should be a list of {category_id, amount}.
    Calculated totals are computed automatically from entries.
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    is_valid, error = _validate_snapshot_data(data)
    if not is_valid:
        return jsonify({"error": error}), 400

    month = int(data["month"])
    year = int(data["year"])

    # Check for duplicate
    existing = session.query(NetWorthSnapshot).filter_by(year=year, month=month).first()
    if existing:
        return (
            jsonify({"error": f"Snapshot for {year}-{month:02d} already exists"}),
            409,
        )

    # Create snapshot
    snapshot = NetWorthSnapshot(month=month, year=year)
    session.add(snapshot)
    session.flush()  # Get the snapshot ID

    # Create entries
    entries_data = data.get("entries", [])
    for entry_data in entries_data:
        category_id = int(entry_data["category_id"])

        # Validate category exists
        category = session.query(NetWorthCategory).filter_by(id=category_id).first()
        if not category:
            session.rollback()
            return jsonify({"error": f"Category {category_id} not found"}), 400

        amount = Decimal(str(entry_data.get("amount", 0)))
        entry = NetWorthEntry(
            snapshot_id=snapshot.id,
            category_id=category_id,
            amount=amount,
        )
        session.add(entry)

    # Refresh to load entries relationship
    session.flush()
    session.refresh(snapshot)

    # Calculate totals
    previous_net_worth = _get_previous_net_worth(session, year, month)
    snapshot.calculate_totals(previous_net_worth)

    session.commit()
    return jsonify(snapshot.to_dict()), 201


@bp.put("/api/networth/<int:snapshot_id>")
def update_snapshot(snapshot_id: int) -> Response | tuple[Response, int]:
    """Update an existing net worth snapshot.

    Can update month/year or entries. If entries are provided, they replace
    all existing entries for this snapshot.
    """
    session = get_session()
    snapshot = session.query(NetWorthSnapshot).filter_by(id=snapshot_id).first()

    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Check if month/year is being changed
    new_month = data.get("month", snapshot.month)
    new_year = data.get("year", snapshot.year)

    if new_month != snapshot.month or new_year != snapshot.year:
        try:
            new_month = int(new_month)
            new_year = int(new_year)
            if new_month < 1 or new_month > 12:
                return jsonify({"error": "month must be between 1 and 12"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "month and year must be integers"}), 400

        # Check for duplicate
        existing = (
            session.query(NetWorthSnapshot)
            .filter_by(year=new_year, month=new_month)
            .filter(NetWorthSnapshot.id != snapshot_id)
            .first()
        )
        if existing:
            return (
                jsonify(
                    {"error": f"Snapshot for {new_year}-{new_month:02d} already exists"}
                ),
                409,
            )
        snapshot.month = new_month
        snapshot.year = new_year

    # Update entries if provided
    if "entries" in data:
        entries_data = data["entries"]
        if not isinstance(entries_data, list):
            return jsonify({"error": "entries must be a list"}), 400

        # Validate entries
        for i, entry_data in enumerate(entries_data):
            if not isinstance(entry_data, dict):
                return jsonify({"error": f"entries[{i}] must be an object"}), 400
            if "category_id" not in entry_data:
                return jsonify({"error": f"entries[{i}].category_id is required"}), 400
            if "amount" in entry_data:
                try:
                    value = Decimal(str(entry_data["amount"]))
                    if abs(value) > MAX_AMOUNT_VALUE:
                        msg = f"entries[{i}].amount exceeds maximum allowed value"
                        return jsonify({"error": msg}), 400
                except (ValueError, TypeError, InvalidOperation):
                    return (
                        jsonify({"error": f"entries[{i}].amount must be a number"}),
                        400,
                    )

        # Delete existing entries
        session.query(NetWorthEntry).filter_by(snapshot_id=snapshot_id).delete()

        # Create new entries
        for entry_data in entries_data:
            category_id = int(entry_data["category_id"])

            # Validate category exists
            category = session.query(NetWorthCategory).filter_by(id=category_id).first()
            if not category:
                session.rollback()
                return jsonify({"error": f"Category {category_id} not found"}), 400

            amount = Decimal(str(entry_data.get("amount", 0)))
            entry = NetWorthEntry(
                snapshot_id=snapshot.id,
                category_id=category_id,
                amount=amount,
            )
            session.add(entry)

        # Refresh to load new entries
        session.flush()
        session.refresh(snapshot)

    # Recalculate totals
    previous_net_worth = _get_previous_net_worth(session, snapshot.year, snapshot.month)
    snapshot.calculate_totals(previous_net_worth)

    # Recalculate next month's change_from_previous if it exists
    _recalculate_next_month(session, snapshot.year, snapshot.month)

    session.commit()
    return jsonify(snapshot.to_dict())


@bp.delete("/api/networth/<int:snapshot_id>")
def delete_snapshot(snapshot_id: int) -> Response | tuple[Response, int]:
    """Delete a net worth snapshot."""
    session = get_session()
    snapshot = session.query(NetWorthSnapshot).filter_by(id=snapshot_id).first()

    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    session.delete(snapshot)
    session.commit()
    return jsonify({"message": "Snapshot deleted"})


@bp.post("/api/networth/reset")
def reset_networth() -> Response:
    """Reset all net worth data.

    Clears all snapshots, entries, categories, and groups.
    """
    session = get_session()

    # Delete in FK order: entries -> snapshots -> categories -> groups
    session.query(NetWorthEntry).delete()
    session.query(NetWorthSnapshot).delete()
    session.query(NetWorthCategory).delete()
    session.query(NetWorthGroup).delete()

    session.commit()

    return jsonify({"message": "Net worth data reset successfully"})


@bp.post("/api/networth/seed")
def seed_networth() -> Response | tuple[Response, int]:
    """Seed example net worth data (12 months of fictional growth).

    Requires categories to be seeded first.
    Uses previous year for realistic demo data.
    """
    session = get_session()

    # Check if data already exists
    existing = session.query(NetWorthSnapshot).first()
    if existing:
        return (
            jsonify(
                {"error": "Net worth data already exists. Delete first to reseed."}
            ),
            409,
        )

    # Get categories (required)
    categories = session.query(NetWorthCategory).all()
    if not categories:
        return (
            jsonify({"error": "No categories found. Seed categories first."}),
            400,
        )

    # Build category lookup by name
    cat_by_name = {c.name: c for c in categories}

    # Required categories for seed data
    required_cats = [
        "Checking",
        "Savings",
        "Rent Account",
        "Crypto",
        "Personal Investments",
        "Personal Bonds",
        "Company Investments",
        "Company Checkings",
        "Student Loan",
        "Credit Card",
    ]
    missing = [name for name in required_cats if name not in cat_by_name]
    if missing:
        return (
            jsonify({"error": f"Missing required categories: {missing}"}),
            400,
        )

    # Use previous year for seed data (more realistic)
    seed_year = datetime.now().year - 1

    # 12 months of example data with realistic growth
    # Format: (month, {category_name: amount, ...})
    base_data = [
        (
            1,
            {
                "Checking": 3500,
                "Savings": 8000,
                "Rent Account": 1200,
                "Crypto": 2500,
                "Personal Investments": 25000,
                "Personal Bonds": 5000,
                "Company Investments": 8000,
                "Company Checkings": 2000,
                "Student Loan": -5000,
                "Credit Card": -500,
            },
        ),
        (
            2,
            {
                "Checking": 3200,
                "Savings": 8500,
                "Rent Account": 1300,
                "Crypto": 2800,
                "Personal Investments": 26000,
                "Personal Bonds": 5000,
                "Company Investments": 8500,
                "Company Checkings": 2200,
                "Student Loan": -4800,
                "Credit Card": -300,
            },
        ),
        (
            3,
            {
                "Checking": 4000,
                "Savings": 9000,
                "Rent Account": 1400,
                "Crypto": 3200,
                "Personal Investments": 27500,
                "Personal Bonds": 5000,
                "Company Investments": 9000,
                "Company Checkings": 2500,
                "Student Loan": -4600,
                "Credit Card": -400,
            },
        ),
        (
            4,
            {
                "Checking": 3800,
                "Savings": 9500,
                "Rent Account": 1500,
                "Crypto": 2900,
                "Personal Investments": 28500,
                "Personal Bonds": 5200,
                "Company Investments": 9500,
                "Company Checkings": 2800,
                "Student Loan": -4400,
                "Credit Card": -200,
            },
        ),
        (
            5,
            {
                "Checking": 4200,
                "Savings": 10000,
                "Rent Account": 1600,
                "Crypto": 3500,
                "Personal Investments": 30000,
                "Personal Bonds": 5200,
                "Company Investments": 10000,
                "Company Checkings": 3000,
                "Student Loan": -4200,
                "Credit Card": -300,
            },
        ),
        (
            6,
            {
                "Checking": 4500,
                "Savings": 10500,
                "Rent Account": 1700,
                "Crypto": 4000,
                "Personal Investments": 31500,
                "Personal Bonds": 5500,
                "Company Investments": 10500,
                "Company Checkings": 3200,
                "Student Loan": -4000,
                "Credit Card": -250,
            },
        ),
        (
            7,
            {
                "Checking": 4800,
                "Savings": 11000,
                "Rent Account": 1800,
                "Crypto": 4500,
                "Personal Investments": 33000,
                "Personal Bonds": 5500,
                "Company Investments": 11000,
                "Company Checkings": 3500,
                "Student Loan": -3800,
                "Credit Card": -200,
            },
        ),
        (
            8,
            {
                "Checking": 5000,
                "Savings": 11500,
                "Rent Account": 1900,
                "Crypto": 5000,
                "Personal Investments": 34500,
                "Personal Bonds": 5800,
                "Company Investments": 11500,
                "Company Checkings": 3800,
                "Student Loan": -3600,
                "Credit Card": -150,
            },
        ),
        (
            9,
            {
                "Checking": 5200,
                "Savings": 12000,
                "Rent Account": 2000,
                "Crypto": 4800,
                "Personal Investments": 36000,
                "Personal Bonds": 5800,
                "Company Investments": 12000,
                "Company Checkings": 4000,
                "Student Loan": -3400,
                "Credit Card": -100,
            },
        ),
        (
            10,
            {
                "Checking": 5500,
                "Savings": 12500,
                "Rent Account": 2100,
                "Crypto": 5500,
                "Personal Investments": 38000,
                "Personal Bonds": 6000,
                "Company Investments": 12500,
                "Company Checkings": 4200,
                "Student Loan": -3200,
                "Credit Card": -80,
            },
        ),
        (
            11,
            {
                "Checking": 5800,
                "Savings": 13000,
                "Rent Account": 2200,
                "Crypto": 6000,
                "Personal Investments": 40000,
                "Personal Bonds": 6000,
                "Company Investments": 13000,
                "Company Checkings": 4500,
                "Student Loan": -3000,
                "Credit Card": -50,
            },
        ),
        (
            12,
            {
                "Checking": 6000,
                "Savings": 13500,
                "Rent Account": 2300,
                "Crypto": 6500,
                "Personal Investments": 42000,
                "Personal Bonds": 6200,
                "Company Investments": 13500,
                "Company Checkings": 4800,
                "Student Loan": -2800,
                "Credit Card": 0,
            },
        ),
    ]

    previous_net_worth = None
    for month, amounts in base_data:
        snapshot = NetWorthSnapshot(month=month, year=seed_year)
        session.add(snapshot)
        session.flush()

        # Create entries for this snapshot
        for cat_name, amount in amounts.items():
            category = cat_by_name[cat_name]
            entry = NetWorthEntry(
                snapshot_id=snapshot.id,
                category_id=category.id,
                amount=Decimal(str(amount)),
            )
            session.add(entry)

        session.flush()
        session.refresh(snapshot)
        snapshot.calculate_totals(previous_net_worth)
        previous_net_worth = snapshot.net_worth

    session.commit()

    snapshots = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year, NetWorthSnapshot.month)
        .all()
    )
    return (
        jsonify(
            {"message": "Seeded 12 months of net worth data", "count": len(snapshots)}
        ),
        201,
    )


# =============================================================================
# Forecast Endpoints
# =============================================================================


VALID_FORECAST_PERIODS = {"month", "quarter", "half_year", "year"}


@bp.get("/api/networth/forecast")
def get_forecast() -> Response | tuple[Response, int]:
    """Get net worth forecast based on historical trend.

    Query parameters:
    - period: Time period to base projection on (month, quarter, half_year, year)
              Default: quarter
    - months_ahead: Number of months to project (1-36). Default: 12

    Returns projected net worth values and the monthly change rate used.
    """
    session = get_session()

    # Parse and validate query parameters
    period = request.args.get("period", "quarter")
    if period not in VALID_FORECAST_PERIODS:
        return (
            jsonify({"error": f"period must be one of: {VALID_FORECAST_PERIODS}"}),
            400,
        )

    try:
        months_ahead = int(request.args.get("months_ahead", 12))
        if months_ahead < 1 or months_ahead > 36:
            return jsonify({"error": "months_ahead must be between 1 and 36"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "months_ahead must be an integer"}), 400

    # Get snapshots ordered newest first
    snapshots = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .all()
    )

    # Generate forecast
    forecast = generate_net_worth_forecast(
        snapshots=snapshots,
        period=period,  # type: ignore[arg-type]
        months_ahead=months_ahead,
    )

    return jsonify(
        {
            "period": forecast.period,
            "months_ahead": forecast.months_ahead,
            "monthly_change_rate": forecast.monthly_change_rate,
            "data_points_used": forecast.data_points_used,
            "projections": [
                {
                    "month": p.month,
                    "year": p.year,
                    "projected_net_worth": p.projected_net_worth,
                }
                for p in forecast.projections
            ],
        }
    )
