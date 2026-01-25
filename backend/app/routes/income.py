from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import IncomeItem

bp = APIBlueprint("income", __name__, tag="Income")


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
