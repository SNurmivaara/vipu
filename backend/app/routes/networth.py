from decimal import Decimal, InvalidOperation

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from sqlalchemy.orm import Session

from app import get_session
from app.models import NetWorthSnapshot

bp = APIBlueprint("networth", __name__, tag="Net Worth")

MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion

# Fields that can be provided in request body
INPUT_FIELDS = [
    "cash",
    "savings",
    "rent_account",
    "crypto",
    "house_worth",
    "personal_investments",
    "personal_bonds",
    "company_investments",
    "company_checkings",
    "student_loan",
    "credit_cards",
]


def _get_previous_net_worth(session: Session, year: int, month: int) -> Decimal | None:
    """Get the net worth from the previous month's snapshot."""
    # Calculate previous month
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

    # Validate numeric fields
    for field in INPUT_FIELDS:
        if field in data:
            try:
                value = Decimal(str(data[field]))
                if abs(value) > MAX_AMOUNT_VALUE:
                    return False, f"{field} exceeds maximum allowed value"
            except (ValueError, TypeError, InvalidOperation):
                return False, f"{field} must be a number"

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
    """Create a new net worth snapshot.

    Requires month and year. All asset/liability fields default to 0.
    Calculated fields (net_worth, totals, percentages) are computed automatically.
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

    # Create snapshot with input fields
    snapshot = NetWorthSnapshot(month=month, year=year)
    for field in INPUT_FIELDS:
        if field in data:
            setattr(snapshot, field, Decimal(str(data[field])))

    # Calculate derived fields
    previous_net_worth = _get_previous_net_worth(session, year, month)
    snapshot.calculate_derived_fields(previous_net_worth)

    session.add(snapshot)
    session.commit()

    return jsonify(snapshot.to_dict()), 201


@bp.put("/api/networth/<int:snapshot_id>")
def update_snapshot(snapshot_id: int) -> Response | tuple[Response, int]:
    """Update an existing net worth snapshot."""
    session = get_session()
    snapshot = session.query(NetWorthSnapshot).filter_by(id=snapshot_id).first()

    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate numeric fields
    for field in INPUT_FIELDS:
        if field in data:
            try:
                value = Decimal(str(data[field]))
                if abs(value) > MAX_AMOUNT_VALUE:
                    return (
                        jsonify({"error": f"{field} exceeds maximum allowed value"}),
                        400,
                    )
            except (ValueError, TypeError, InvalidOperation):
                return jsonify({"error": f"{field} must be a number"}), 400

    # Check if month/year is being changed and would create duplicate
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

        existing = (
            session.query(NetWorthSnapshot)
            .filter_by(year=new_year, month=new_month)
            .filter(NetWorthSnapshot.id != snapshot_id)
            .first()
        )
        if existing:
            msg = f"Snapshot for {new_year}-{new_month:02d} already exists"
            return jsonify({"error": msg}), 409
        snapshot.month = new_month
        snapshot.year = new_year

    # Update input fields
    for field in INPUT_FIELDS:
        if field in data:
            setattr(snapshot, field, Decimal(str(data[field])))

    # Recalculate derived fields
    previous_net_worth = _get_previous_net_worth(session, snapshot.year, snapshot.month)
    snapshot.calculate_derived_fields(previous_net_worth)

    session.commit()
    return jsonify(snapshot.to_dict())


@bp.delete("/api/networth/<int:snapshot_id>")
def delete_snapshot(snapshot_id: int) -> tuple[Response, int]:
    """Delete a net worth snapshot."""
    session = get_session()
    snapshot = session.query(NetWorthSnapshot).filter_by(id=snapshot_id).first()

    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    session.delete(snapshot)
    session.commit()
    return jsonify({"message": "Snapshot deleted"}), 200


@bp.post("/api/networth/seed")
def seed_networth() -> Response | tuple[Response, int]:
    """Seed example net worth data (12 months of fictional growth).

    Shows growth from ~50k to ~90k over 12 months.
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

    # Generate 12 months of example data with realistic growth
    # Starting from January 2024, ending December 2024
    # Base values grow roughly 3-5% per month
    base_data = [
        # (month, year, cash, savings, rent_account, crypto, house_worth,
        #  personal_investments, personal_bonds, company_investments, company_checkings,
        #  student_loan, credit_cards)
        (1, 2024, 3500, 8000, 1200, 2500, 0, 25000, 5000, 8000, 2000, -5000, -500),
        (2, 2024, 3200, 8500, 1300, 2800, 0, 26000, 5000, 8500, 2200, -4800, -300),
        (3, 2024, 4000, 9000, 1400, 3200, 0, 27500, 5000, 9000, 2500, -4600, -400),
        (4, 2024, 3800, 9500, 1500, 2900, 0, 28500, 5200, 9500, 2800, -4400, -200),
        (5, 2024, 4200, 10000, 1600, 3500, 0, 30000, 5200, 10000, 3000, -4200, -300),
        (6, 2024, 4500, 10500, 1700, 4000, 0, 31500, 5500, 10500, 3200, -4000, -250),
        (7, 2024, 4800, 11000, 1800, 4500, 0, 33000, 5500, 11000, 3500, -3800, -200),
        (8, 2024, 5000, 11500, 1900, 5000, 0, 34500, 5800, 11500, 3800, -3600, -150),
        (9, 2024, 5200, 12000, 2000, 4800, 0, 36000, 5800, 12000, 4000, -3400, -100),
        (10, 2024, 5500, 12500, 2100, 5500, 0, 38000, 6000, 12500, 4200, -3200, -80),
        (11, 2024, 5800, 13000, 2200, 6000, 0, 40000, 6000, 13000, 4500, -3000, -50),
        (12, 2024, 6000, 13500, 2300, 6500, 0, 42000, 6200, 13500, 4800, -2800, 0),
    ]

    previous_net_worth = None
    for row in base_data:
        snapshot = NetWorthSnapshot(
            month=row[0],
            year=row[1],
            cash=Decimal(str(row[2])),
            savings=Decimal(str(row[3])),
            rent_account=Decimal(str(row[4])),
            crypto=Decimal(str(row[5])),
            house_worth=Decimal(str(row[6])),
            personal_investments=Decimal(str(row[7])),
            personal_bonds=Decimal(str(row[8])),
            company_investments=Decimal(str(row[9])),
            company_checkings=Decimal(str(row[10])),
            student_loan=Decimal(str(row[11])),
            credit_cards=Decimal(str(row[12])),
        )
        snapshot.calculate_derived_fields(previous_net_worth)
        previous_net_worth = snapshot.net_worth
        session.add(snapshot)

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
