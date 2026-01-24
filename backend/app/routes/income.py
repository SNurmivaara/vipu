from decimal import Decimal

from flask import Blueprint, jsonify, request

from app import get_session
from app.models import IncomeItem

bp = Blueprint("income", __name__)


@bp.route("/api/income", methods=["GET"])
def list_income():
    """List all income items."""
    session = get_session()
    items = session.query(IncomeItem).order_by(IncomeItem.name).all()
    return jsonify([i.to_dict() for i in items])


@bp.route("/api/income", methods=["POST"])
def create_income():
    """Create a new income item."""
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" not in data:
        return jsonify({"error": "name is required"}), 400

    if "gross_amount" not in data:
        return jsonify({"error": "gross_amount is required"}), 400

    tax_pct = data.get("tax_percentage")
    if tax_pct is not None:
        tax_pct = Decimal(str(tax_pct))

    item = IncomeItem(
        name=data["name"],
        gross_amount=Decimal(str(data["gross_amount"])),
        is_taxed=data.get("is_taxed", True),
        tax_percentage=tax_pct,
    )
    session.add(item)
    session.commit()

    return jsonify(item.to_dict()), 201


@bp.route("/api/income/<int:income_id>", methods=["PUT"])
def update_income(income_id: int):
    """Update an existing income item."""
    session = get_session()
    item = session.query(IncomeItem).filter_by(id=income_id).first()

    if not item:
        return jsonify({"error": "Income item not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" in data:
        item.name = data["name"]
    if "gross_amount" in data:
        item.gross_amount = Decimal(str(data["gross_amount"]))
    if "is_taxed" in data:
        item.is_taxed = data["is_taxed"]
    if "tax_percentage" in data:
        tax_pct = data["tax_percentage"]
        item.tax_percentage = Decimal(str(tax_pct)) if tax_pct is not None else None

    session.commit()
    return jsonify(item.to_dict())


@bp.route("/api/income/<int:income_id>", methods=["DELETE"])
def delete_income(income_id: int):
    """Delete an income item."""
    session = get_session()
    item = session.query(IncomeItem).filter_by(id=income_id).first()

    if not item:
        return jsonify({"error": "Income item not found"}), 404

    session.delete(item)
    session.commit()
    return jsonify({"message": "Income item deleted"}), 200
