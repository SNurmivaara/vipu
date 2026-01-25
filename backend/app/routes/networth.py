from datetime import datetime
from decimal import Decimal, InvalidOperation

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from sqlalchemy.orm import Session

from app import get_session
from app.models import NetWorthCategory, NetWorthEntry, NetWorthSnapshot

bp = APIBlueprint("networth", __name__, tag="Net Worth")

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion

# Valid category types and groups
VALID_CATEGORY_TYPES = {"asset", "liability"}
VALID_CATEGORY_GROUPS = {"cash", "investment", "crypto", "property", "loan", "credit"}


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
    if "category_type" not in data:
        return jsonify({"error": "category_type is required"}), 400
    if "category_group" not in data:
        return jsonify({"error": "category_group is required"}), 400

    # Validate name
    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return (
            jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
            400,
        )

    # Validate category_type
    category_type = str(data["category_type"]).lower()
    if category_type not in VALID_CATEGORY_TYPES:
        return (
            jsonify({"error": f"category_type must be one of: {VALID_CATEGORY_TYPES}"}),
            400,
        )

    # Validate category_group
    category_group = str(data["category_group"]).lower()
    if category_group not in VALID_CATEGORY_GROUPS:
        return (
            jsonify(
                {"error": f"category_group must be one of: {VALID_CATEGORY_GROUPS}"}
            ),
            400,
        )

    # Get optional fields
    is_personal = bool(data.get("is_personal", True))
    display_order = int(data.get("display_order", 0))

    category = NetWorthCategory(
        name=name,
        category_type=category_type,
        category_group=category_group,
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

    if "category_type" in data:
        category_type = str(data["category_type"]).lower()
        if category_type not in VALID_CATEGORY_TYPES:
            return (
                jsonify(
                    {"error": f"category_type must be one of: {VALID_CATEGORY_TYPES}"}
                ),
                400,
            )
        category.category_type = category_type

    if "category_group" in data:
        category_group = str(data["category_group"]).lower()
        if category_group not in VALID_CATEGORY_GROUPS:
            return (
                jsonify(
                    {"error": f"category_group must be one of: {VALID_CATEGORY_GROUPS}"}
                ),
                400,
            )
        category.category_group = category_group

    if "is_personal" in data:
        category.is_personal = bool(data["is_personal"])

    if "display_order" in data:
        category.display_order = int(data["display_order"])

    session.commit()
    return jsonify(category.to_dict())


@bp.delete("/api/networth/categories/<int:category_id>")
def delete_category(category_id: int) -> Response | tuple[Response, int]:
    """Delete a category. Fails if category is used in any snapshot entries."""
    session = get_session()
    category = session.query(NetWorthCategory).filter_by(id=category_id).first()

    if not category:
        return jsonify({"error": "Category not found"}), 404

    # Check if category is used in any entries
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
    """Seed default net worth categories."""
    session = get_session()

    # Check if categories already exist
    existing = session.query(NetWorthCategory).first()
    if existing:
        return (
            jsonify({"error": "Categories already exist. Delete first to reseed."}),
            409,
        )

    # Default categories matching the original column-based design
    default_categories = [
        # Personal Assets - Cash
        ("Cash", "asset", "cash", True, 1),
        ("Savings", "asset", "cash", True, 2),
        ("Rent Account", "asset", "cash", True, 3),
        # Personal Assets - Investments
        ("Personal Investments", "asset", "investment", True, 10),
        ("Personal Bonds", "asset", "investment", True, 11),
        # Personal Assets - Crypto
        ("Crypto", "asset", "crypto", True, 20),
        # Personal Assets - Property
        ("House/Apartment", "asset", "property", True, 30),
        # Company Assets
        ("Company Investments", "asset", "investment", False, 40),
        ("Company Checkings", "asset", "cash", False, 41),
        # Liabilities
        ("Student Loan", "liability", "loan", True, 50),
        ("Credit Cards", "liability", "credit", True, 51),
    ]

    for name, cat_type, cat_group, is_personal, order in default_categories:
        category = NetWorthCategory(
            name=name,
            category_type=cat_type,
            category_group=cat_group,
            is_personal=is_personal,
            display_order=order,
        )
        session.add(category)

    session.commit()

    categories = session.query(NetWorthCategory).all()
    return (
        jsonify({"message": "Seeded default categories", "count": len(categories)}),
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
        "Cash",
        "Savings",
        "Rent Account",
        "Crypto",
        "Personal Investments",
        "Personal Bonds",
        "Company Investments",
        "Company Checkings",
        "Student Loan",
        "Credit Cards",
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
                "Cash": 3500,
                "Savings": 8000,
                "Rent Account": 1200,
                "Crypto": 2500,
                "Personal Investments": 25000,
                "Personal Bonds": 5000,
                "Company Investments": 8000,
                "Company Checkings": 2000,
                "Student Loan": -5000,
                "Credit Cards": -500,
            },
        ),
        (
            2,
            {
                "Cash": 3200,
                "Savings": 8500,
                "Rent Account": 1300,
                "Crypto": 2800,
                "Personal Investments": 26000,
                "Personal Bonds": 5000,
                "Company Investments": 8500,
                "Company Checkings": 2200,
                "Student Loan": -4800,
                "Credit Cards": -300,
            },
        ),
        (
            3,
            {
                "Cash": 4000,
                "Savings": 9000,
                "Rent Account": 1400,
                "Crypto": 3200,
                "Personal Investments": 27500,
                "Personal Bonds": 5000,
                "Company Investments": 9000,
                "Company Checkings": 2500,
                "Student Loan": -4600,
                "Credit Cards": -400,
            },
        ),
        (
            4,
            {
                "Cash": 3800,
                "Savings": 9500,
                "Rent Account": 1500,
                "Crypto": 2900,
                "Personal Investments": 28500,
                "Personal Bonds": 5200,
                "Company Investments": 9500,
                "Company Checkings": 2800,
                "Student Loan": -4400,
                "Credit Cards": -200,
            },
        ),
        (
            5,
            {
                "Cash": 4200,
                "Savings": 10000,
                "Rent Account": 1600,
                "Crypto": 3500,
                "Personal Investments": 30000,
                "Personal Bonds": 5200,
                "Company Investments": 10000,
                "Company Checkings": 3000,
                "Student Loan": -4200,
                "Credit Cards": -300,
            },
        ),
        (
            6,
            {
                "Cash": 4500,
                "Savings": 10500,
                "Rent Account": 1700,
                "Crypto": 4000,
                "Personal Investments": 31500,
                "Personal Bonds": 5500,
                "Company Investments": 10500,
                "Company Checkings": 3200,
                "Student Loan": -4000,
                "Credit Cards": -250,
            },
        ),
        (
            7,
            {
                "Cash": 4800,
                "Savings": 11000,
                "Rent Account": 1800,
                "Crypto": 4500,
                "Personal Investments": 33000,
                "Personal Bonds": 5500,
                "Company Investments": 11000,
                "Company Checkings": 3500,
                "Student Loan": -3800,
                "Credit Cards": -200,
            },
        ),
        (
            8,
            {
                "Cash": 5000,
                "Savings": 11500,
                "Rent Account": 1900,
                "Crypto": 5000,
                "Personal Investments": 34500,
                "Personal Bonds": 5800,
                "Company Investments": 11500,
                "Company Checkings": 3800,
                "Student Loan": -3600,
                "Credit Cards": -150,
            },
        ),
        (
            9,
            {
                "Cash": 5200,
                "Savings": 12000,
                "Rent Account": 2000,
                "Crypto": 4800,
                "Personal Investments": 36000,
                "Personal Bonds": 5800,
                "Company Investments": 12000,
                "Company Checkings": 4000,
                "Student Loan": -3400,
                "Credit Cards": -100,
            },
        ),
        (
            10,
            {
                "Cash": 5500,
                "Savings": 12500,
                "Rent Account": 2100,
                "Crypto": 5500,
                "Personal Investments": 38000,
                "Personal Bonds": 6000,
                "Company Investments": 12500,
                "Company Checkings": 4200,
                "Student Loan": -3200,
                "Credit Cards": -80,
            },
        ),
        (
            11,
            {
                "Cash": 5800,
                "Savings": 13000,
                "Rent Account": 2200,
                "Crypto": 6000,
                "Personal Investments": 40000,
                "Personal Bonds": 6000,
                "Company Investments": 13000,
                "Company Checkings": 4500,
                "Student Loan": -3000,
                "Credit Cards": -50,
            },
        ),
        (
            12,
            {
                "Cash": 6000,
                "Savings": 13500,
                "Rent Account": 2300,
                "Crypto": 6500,
                "Personal Investments": 42000,
                "Personal Bonds": 6200,
                "Company Investments": 13500,
                "Company Checkings": 4800,
                "Student Loan": -2800,
                "Credit Cards": 0,
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
