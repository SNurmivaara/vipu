from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import ExpenseItem

bp = APIBlueprint("expenses", __name__, tag="Expenses")

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion


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

    item = ExpenseItem(
        name=name,
        amount=amount,
        is_savings_goal=bool(data.get("is_savings_goal", False)),
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
