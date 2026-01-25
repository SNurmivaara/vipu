from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import IncomeItem

bp = APIBlueprint("income", __name__, tag="Income")

MAX_NAME_LENGTH = 100
MAX_AMOUNT_VALUE = 1_000_000_000  # 1 billion


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

    item = IncomeItem(
        name=name,
        gross_amount=gross_amount,
        is_taxed=bool(data.get("is_taxed", True)),
        tax_percentage=tax_pct,
        is_deduction=bool(data.get("is_deduction", False)),
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
