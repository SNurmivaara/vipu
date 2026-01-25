from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import ExpenseItem

bp = APIBlueprint("expenses", __name__, tag="Expenses")


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

    item = ExpenseItem(
        name=data["name"],
        amount=Decimal(str(data["amount"])),
        is_savings_goal=data.get("is_savings_goal", False),
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
        item.name = data["name"]
    if "amount" in data:
        item.amount = Decimal(str(data["amount"]))
    if "is_savings_goal" in data:
        item.is_savings_goal = data["is_savings_goal"]

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
