from datetime import date, datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.deadline_calc import (
    apply_occurrence_override,
    expense_window_start,
    get_previous_payday,
)
from app.models import ExpenseItem
from app.routes.budget import configured_payday_day

bp = APIBlueprint("expenses", __name__, tag="Expenses")

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


@bp.get("/api/expenses")
def list_expenses() -> Response:
    """List all expense items."""
    session = get_session()
    items = session.query(ExpenseItem).order_by(ExpenseItem.name).all()
    return jsonify([e.to_dict() for e in items])


@bp.post("/api/expenses")
def create_expense() -> Response | tuple[Response, int]:
    """Create a new expense item.

    Requires name and amount.
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" not in data:
        return jsonify({"error": "name is required"}), 400

    if "amount" not in data:
        return jsonify({"error": "amount is required"}), 400

    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}), 400

    amount = Decimal(str(data["amount"]))
    if abs(amount) > MAX_AMOUNT_VALUE:
        return jsonify({"error": "amount exceeds maximum allowed value"}), 400

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

    item = ExpenseItem(
        name=name,
        amount=amount,
        is_savings_goal=bool(data.get("is_savings_goal", False)),
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


@bp.put("/api/expenses/<int:expense_id>")
def update_expense(expense_id: int) -> Response | tuple[Response, int]:
    """Update an existing expense item."""
    session = get_session()
    item = session.query(ExpenseItem).filter_by(id=expense_id).first()

    if not item:
        return jsonify({"error": "Expense item not found"}), 404

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
    if "amount" in data:
        amount = Decimal(str(data["amount"]))
        if abs(amount) > MAX_AMOUNT_VALUE:
            return jsonify({"error": "amount exceeds maximum allowed value"}), 400
        item.amount = amount
    if "is_savings_goal" in data:
        item.is_savings_goal = bool(data["is_savings_goal"])

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


@bp.put("/api/expenses/<int:expense_id>/occurrence")
def set_expense_occurrence(expense_id: int) -> Response | tuple[Response, int]:
    """Mark one occurrence of an expense as paid, or as not paid after all.

    Body: occurrence_date (YYYY-MM-DD) and settled (bool). Covers a bill paid
    ahead of its due day and one whose debit lands late, without moving the
    schedule: only that occurrence changes, later ones are unaffected.

    The date must be either the item's next occurrence or the most recent one
    that has come due in the current pay period.
    """
    session = get_session()
    item = session.query(ExpenseItem).filter_by(id=expense_id).first()

    if not item:
        return jsonify({"error": "Expense item not found"}), 404

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
    applied = apply_occurrence_override(
        item,
        occurrence,
        bool(data["settled"]),
        expense_window_start(today),
        get_previous_payday(today, configured_payday_day(session)),
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


@bp.delete("/api/expenses/<int:expense_id>")
def delete_expense(expense_id: int) -> tuple[Response, int]:
    """Delete an expense item."""
    session = get_session()
    item = session.query(ExpenseItem).filter_by(id=expense_id).first()

    if not item:
        return jsonify({"error": "Expense item not found"}), 404

    session.delete(item)
    session.commit()
    return jsonify({"message": "Expense item deleted"}), 200
