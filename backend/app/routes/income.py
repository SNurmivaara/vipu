from datetime import date, datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.deadline_calc import (
    apply_occurrence_override,
    get_previous_payday,
    income_window_start,
)
from app.models import IncomeItem
from app.routes.budget import configured_payday_day

bp = APIBlueprint("income", __name__, tag="Income")

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion
VALID_FREQUENCY_UNITS = ("days", "weeks", "months", "years")


def parse_date(value: str | None) -> date | None:
    """Parse ISO date string to date object."""
    if not value:
        return None
    return date.fromisoformat(value)


def parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    return datetime.fromisoformat(value)


@bp.get("/api/income")
def list_income() -> Response:
    """List all income items."""
    session = get_session()
    items = session.query(IncomeItem).order_by(IncomeItem.name).all()
    return jsonify([i.to_dict() for i in items])


@bp.post("/api/income")
def create_income() -> Response | tuple[Response, int]:
    """Create a new income item.

    Requires name and gross_amount. Optional: is_taxed (default true), tax_percentage.
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" not in data:
        return jsonify({"error": "name is required"}), 400

    if "gross_amount" not in data:
        return jsonify({"error": "gross_amount is required"}), 400

    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}), 400

    gross_amount = Decimal(str(data["gross_amount"]))
    if abs(gross_amount) > MAX_AMOUNT_VALUE:
        return jsonify({"error": "gross_amount exceeds maximum allowed value"}), 400

    tax_pct = data.get("tax_percentage")
    if tax_pct is not None:
        tax_pct = Decimal(str(tax_pct))
        if tax_pct < 0 or tax_pct > 100:
            return jsonify({"error": "tax_percentage must be between 0 and 100"}), 400

    # Validate deadline fields
    due_day = int(data.get("due_day", 1))
    if due_day < 1 or due_day > 31:
        return jsonify({"error": "due_day must be between 1 and 31"}), 400

    frequency_value = int(data.get("frequency_value", 1))
    if frequency_value < 1:
        return jsonify({"error": "frequency_value must be at least 1"}), 400

    frequency_unit = data.get("frequency_unit", "months")
    if frequency_unit not in VALID_FREQUENCY_UNITS:
        return jsonify({"error": f"Invalid frequency_unit: {frequency_unit}"}), 400

    try:
        start_date = parse_date(data.get("start_date"))
        end_date = parse_date(data.get("end_date"))
    except ValueError:
        return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

    item = IncomeItem(
        name=name,
        gross_amount=gross_amount,
        is_taxed=bool(data.get("is_taxed", True)),
        tax_percentage=tax_pct,
        is_deduction=bool(data.get("is_deduction", False)),
        due_day=due_day,
        frequency_value=frequency_value,
        frequency_unit=frequency_unit,
        start_date=start_date,
        end_date=end_date,
        is_ephemeral=bool(data.get("is_ephemeral", False)),
    )
    session.add(item)
    session.commit()

    return jsonify(item.to_dict()), 201


@bp.put("/api/income/<int:income_id>")
def update_income(income_id: int) -> Response | tuple[Response, int]:
    """Update an existing income item."""
    session = get_session()
    item = session.query(IncomeItem).filter_by(id=income_id).first()

    if not item:
        return jsonify({"error": "Income item not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            return (
                jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
                400,
            )
        item.name = name
    if "gross_amount" in data:
        gross_amount = Decimal(str(data["gross_amount"]))
        if abs(gross_amount) > MAX_AMOUNT_VALUE:
            return jsonify({"error": "gross_amount exceeds maximum allowed value"}), 400
        item.gross_amount = gross_amount
    if "is_taxed" in data:
        item.is_taxed = bool(data["is_taxed"])
    if "tax_percentage" in data:
        tax_pct = data["tax_percentage"]
        if tax_pct is not None:
            tax_pct = Decimal(str(tax_pct))
            if tax_pct < 0 or tax_pct > 100:
                return (
                    jsonify({"error": "tax_percentage must be between 0 and 100"}),
                    400,
                )
        item.tax_percentage = tax_pct
    if "is_deduction" in data:
        item.is_deduction = bool(data["is_deduction"])

    # Deadline fields
    if "due_day" in data:
        due_day = int(data["due_day"])
        if due_day < 1 or due_day > 31:
            return jsonify({"error": "due_day must be between 1 and 31"}), 400
        item.due_day = due_day

    if "frequency_value" in data:
        frequency_value = int(data["frequency_value"])
        if frequency_value < 1:
            return jsonify({"error": "frequency_value must be at least 1"}), 400
        item.frequency_value = frequency_value

    if "frequency_unit" in data:
        frequency_unit = data["frequency_unit"]
        if frequency_unit not in VALID_FREQUENCY_UNITS:
            return jsonify({"error": f"Invalid frequency_unit: {frequency_unit}"}), 400
        item.frequency_unit = frequency_unit

    if "start_date" in data:
        try:
            item.start_date = parse_date(data["start_date"])
        except ValueError:
            return jsonify({"error": "Invalid start_date (use YYYY-MM-DD)"}), 400

    if "end_date" in data:
        try:
            item.end_date = parse_date(data["end_date"])
        except ValueError:
            return jsonify({"error": "Invalid end_date (use YYYY-MM-DD)"}), 400

    if "is_ephemeral" in data:
        item.is_ephemeral = bool(data["is_ephemeral"])

    if "archived_at" in data:
        try:
            item.archived_at = parse_datetime(data["archived_at"])
        except ValueError:
            return jsonify({"error": "Invalid archived_at format. Use ISO format"}), 400

    session.commit()
    return jsonify(item.to_dict())


@bp.put("/api/income/<int:income_id>/occurrence")
def set_income_occurrence(income_id: int) -> Response | tuple[Response, int]:
    """Mark one occurrence of an income item as received, or as still expected.

    Body: occurrence_date (YYYY-MM-DD) and settled (bool). Covers pay that
    arrives early (a banking holiday moving payday forward) and pay that hasn't
    landed on time, without moving the schedule: only that occurrence changes.

    The date must be either the item's next occurrence or the most recent one
    that has come due in the current pay period.
    """
    session = get_session()
    item = session.query(IncomeItem).filter_by(id=income_id).first()

    if not item:
        return jsonify({"error": "Income item not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "occurrence_date" not in data:
        return jsonify({"error": "occurrence_date is required"}), 400
    if "settled" not in data:
        return jsonify({"error": "settled is required"}), 400

    try:
        occurrence = parse_date(str(data["occurrence_date"]))
    except ValueError:
        return jsonify({"error": "Invalid occurrence_date (use YYYY-MM-DD)"}), 400
    if occurrence is None:
        return jsonify({"error": "occurrence_date is required"}), 400

    today = date.today()
    payday_day = configured_payday_day(session)
    applied = apply_occurrence_override(
        item,
        occurrence,
        bool(data["settled"]),
        income_window_start(today, payday_day),
        get_previous_payday(today, payday_day),
    )
    if not applied:
        return (
            jsonify(
                {
                    "error": "occurrence_date must be this item's next occurrence "
                    "or its most recent one this pay period"
                }
            ),
            400,
        )

    session.commit()
    return jsonify(item.to_dict())


@bp.delete("/api/income/<int:income_id>")
def delete_income(income_id: int) -> tuple[Response, int]:
    """Delete an income item."""
    session = get_session()
    item = session.query(IncomeItem).filter_by(id=income_id).first()

    if not item:
        return jsonify({"error": "Income item not found"}), 404

    session.delete(item)
    session.commit()
    return jsonify({"message": "Income item deleted"}), 200
