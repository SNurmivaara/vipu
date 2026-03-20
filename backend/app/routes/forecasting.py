from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import ForecastingSettings

bp = APIBlueprint("forecasting", __name__, tag="Forecasting")


def get_or_create_forecasting_settings() -> ForecastingSettings:
    """Get forecasting settings or create defaults if not exists."""
    session = get_session()
    settings = session.query(ForecastingSettings).first()
    if settings:
        return settings
    new_settings = ForecastingSettings()
    session.add(new_settings)
    try:
        session.commit()
        return new_settings
    except Exception:
        session.rollback()
        # Another request inserted concurrently — fetch the row it created
        existing = session.query(ForecastingSettings).first()
        assert existing is not None
        return existing


@bp.get("/api/forecasting/settings")
def get_forecasting_settings() -> Response:
    """Get FIRE forecasting settings."""
    settings = get_or_create_forecasting_settings()
    return jsonify(settings.to_dict())


@bp.put("/api/forecasting/settings")
def update_forecasting_settings() -> Response | tuple[Response, int]:
    """Update FIRE forecasting settings."""
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    settings = get_or_create_forecasting_settings()

    # Numeric fields with ranges
    numeric_fields = {
        "inflation_pct": (0, 20),
        "safe_withdrawal_rate": (1, 10),
        "pension_accrual_rate": (0, 10),
    }
    for field, (lo, hi) in numeric_fields.items():
        if field in data:
            val = data[field]
            if not isinstance(val, (int, float)) or val < lo or val > hi:
                return jsonify({"error": f"{field} must be between {lo} and {hi}"}), 400
            setattr(settings, field, Decimal(str(val)))

    # Integer fields with ranges
    int_fields = {
        "current_age": (0, 120),
        "target_retirement_age": (0, 120),
        "pension_full_age": (50, 80),
        "life_expectancy": (60, 120),
    }
    for field, (lo, hi) in int_fields.items():
        if field in data:
            val = data[field]
            if not isinstance(val, (int, float)) or val < lo or val > hi:
                return jsonify({"error": f"{field} must be between {lo} and {hi}"}), 400
            setattr(settings, field, int(val))

    # Nullable decimal fields (null to clear)
    nullable_fields = [
        "monthly_savings_override",
        "annual_expenses_override",
        "pension_accrued_monthly",
        "pension_monthly_salary_override",
    ]
    for field in nullable_fields:
        if field in data:
            val = data[field]
            if val is None:
                setattr(settings, field, None)
            elif isinstance(val, (int, float)):
                setattr(settings, field, Decimal(str(val)))
            else:
                return jsonify({"error": f"{field} must be a number or null"}), 400

    # Group return rates (JSON object: group_name -> return %)
    if "group_return_rates" in data:
        val = data["group_return_rates"]
        if not isinstance(val, dict):
            return jsonify({"error": "group_return_rates must be an object"}), 400
        # Validate all values are numbers between -10 and 30
        for k, v in val.items():
            if not isinstance(v, (int, float)) or v < -10 or v > 30:
                msg = f"Return rate for {k} must be between -10 and 30"
                return jsonify({"error": msg}), 400
        settings.group_return_rates = val

    session.commit()
    return jsonify(settings.to_dict())
