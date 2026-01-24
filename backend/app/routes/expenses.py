from decimal import Decimal

from flask import Blueprint, jsonify, request

from app import get_session
from app.models import ExpenseItem

bp = Blueprint("expenses", __name__)


@bp.route("/api/expenses", methods=["GET"])
def list_expenses():
    """List all expense items."""
    session = get_session()
    items = session.query(ExpenseItem).order_by(ExpenseItem.name).all()
    return jsonify([e.to_dict() for e in items])


@bp.route("/api/expenses", methods=["POST"])
def create_expense():
    """Create a new expense item."""
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
    )
    session.add(item)
    session.commit()

    return jsonify(item.to_dict()), 201


@bp.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def update_expense(expense_id: int):
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

    session.commit()
    return jsonify(item.to_dict())


@bp.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id: int):
    """Delete an expense item."""
    session = get_session()
    item = session.query(ExpenseItem).filter_by(id=expense_id).first()

    if not item:
        return jsonify({"error": "Expense item not found"}), 404

    session.delete(item)
    session.commit()
    return jsonify({"message": "Expense item deleted"}), 200
