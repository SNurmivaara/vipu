from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import BudgetSettings

bp = APIBlueprint("settings", __name__, tag="Settings")


def get_or_create_settings() -> BudgetSettings:
    """Get settings or create default if not exists."""
    session = get_session()
    settings = session.query(BudgetSettings).first()
    if not settings:
        settings = BudgetSettings(tax_percentage=Decimal("25.0"))
        session.add(settings)
        session.commit()
    return settings


@bp.get("/api/settings")
def get_settings() -> Response:
    """Get current budget settings."""
    settings = get_or_create_settings()
    return jsonify(settings.to_dict())


@bp.put("/api/settings")
def update_settings() -> Response | tuple[Response, int]:
    """Update budget settings.

    Accepts tax_percentage (0-100).
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    settings = get_or_create_settings()

    if "tax_percentage" in data:
        tax_pct = data["tax_percentage"]
        if not isinstance(tax_pct, (int, float)) or tax_pct < 0 or tax_pct > 100:
            return jsonify({"error": "tax_percentage must be between 0 and 100"}), 400
        settings.tax_percentage = Decimal(str(tax_pct))

    session.commit()
    return jsonify(settings.to_dict())
