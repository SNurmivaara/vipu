from dataclasses import asdict
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from marshmallow import Schema, ValidationError, fields, post_load, validate

from app import get_session
from app.fire import (
    FireInputs,
    build_portfolio,
    calculate_fire,
    real_return_from_nominal,
    resolve_group_return_rates,
    weighted_return,
)
from app.models import ForecastingSettings, NetWorthSnapshot
from app.routes.budget import compute_budget_totals

bp = APIBlueprint("forecasting", __name__, tag="Forecasting")


# ---------------------------------------------------------------------------
# Input validation schema
# ---------------------------------------------------------------------------


class FireCalculateInputSchema(Schema):
    """Schema for FIRE calculation input validation."""

    current_net_worth = fields.Float(required=True)
    monthly_contribution = fields.Float(required=True)
    annual_expenses = fields.Float(required=True, validate=validate.Range(min=0))
    annual_return_pct = fields.Float(
        required=True, validate=validate.Range(min=-50, max=100)
    )
    inflation_pct = fields.Float(
        required=True, validate=validate.Range(min=-10, max=50)
    )
    current_age = fields.Integer(required=True, validate=validate.Range(min=0, max=120))
    target_retirement_age = fields.Integer(
        required=True, validate=validate.Range(min=0, max=120)
    )
    safe_withdrawal_rate = fields.Float(
        required=True, validate=validate.Range(min=0.1, max=20)
    )

    # Optional pension fields
    pension_accrued_monthly = fields.Float(
        allow_none=True, load_default=None, validate=validate.Range(min=0)
    )
    pension_monthly_salary = fields.Float(
        allow_none=True, load_default=None, validate=validate.Range(min=0)
    )
    pension_accrual_rate = fields.Float(
        load_default=1.5, validate=validate.Range(min=0, max=10)
    )
    pension_full_age = fields.Integer(
        load_default=68, validate=validate.Range(min=50, max=80)
    )
    pension_guarantee_enabled = fields.Boolean(load_default=False)
    pension_guarantee_amount = fields.Float(
        load_default=990.0, validate=validate.Range(min=0, max=5000)
    )
    life_expectancy = fields.Integer(
        load_default=95, validate=validate.Range(min=60, max=120)
    )

    @post_load
    def make_fire_inputs(self, data: dict, **kwargs: object) -> FireInputs:
        """Convert validated data to FireInputs dataclass."""
        return FireInputs(
            current_net_worth=Decimal(str(data["current_net_worth"])),
            monthly_contribution=Decimal(str(data["monthly_contribution"])),
            annual_expenses=Decimal(str(data["annual_expenses"])),
            annual_return_pct=Decimal(str(data["annual_return_pct"])),
            inflation_pct=Decimal(str(data["inflation_pct"])),
            current_age=data["current_age"],
            target_retirement_age=data["target_retirement_age"],
            safe_withdrawal_rate=Decimal(str(data["safe_withdrawal_rate"])),
            pension_accrued_monthly=(
                Decimal(str(data["pension_accrued_monthly"]))
                if data["pension_accrued_monthly"] is not None
                else None
            ),
            pension_monthly_salary=(
                Decimal(str(data["pension_monthly_salary"]))
                if data["pension_monthly_salary"] is not None
                else None
            ),
            pension_accrual_rate=Decimal(str(data["pension_accrual_rate"])),
            pension_full_age=data["pension_full_age"],
            pension_guarantee_enabled=data["pension_guarantee_enabled"],
            pension_guarantee_amount=Decimal(str(data["pension_guarantee_amount"])),
            life_expectancy=data["life_expectancy"],
        )


fire_calculate_schema = FireCalculateInputSchema()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


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


def decimal_to_float(obj: object) -> object:
    """Recursively convert Decimal values to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decimal_to_float(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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
        "pension_guarantee_amount": (0, 5000),
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

    # Boolean fields
    if "pension_guarantee_enabled" in data:
        val = data["pension_guarantee_enabled"]
        if not isinstance(val, bool):
            return (
                jsonify({"error": "pension_guarantee_enabled must be a boolean"}),
                400,
            )
        settings.pension_guarantee_enabled = val

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

    # Contribution destination (null routes contributions across the mix)
    if "contribution_group" in data:
        val = data["contribution_group"]
        if val is not None and not isinstance(val, str):
            return (
                jsonify({"error": "contribution_group must be a string or null"}),
                400,
            )
        settings.contribution_group = val or None

    session.commit()
    return jsonify(settings.to_dict())


@bp.post("/api/forecasting/calculate")
def calculate_fire_projection() -> Response | tuple[Response, int]:
    """Calculate FIRE projections based on provided inputs.

    Expects JSON body with:
    - current_net_worth: float
    - monthly_contribution: float
    - annual_expenses: float (>= 0)
    - annual_return_pct: float (-50 to 100, weighted return, e.g. 7 for 7%)
    - inflation_pct: float (-10 to 50, e.g. 2 for 2%)
    - current_age: int (0-120)
    - target_retirement_age: int (0-120)
    - safe_withdrawal_rate: float (0.1-20, e.g. 4 for 4%)
    - pension_accrued_monthly: float | null (activates pension mode if provided)
    - pension_monthly_salary: float | null
    - pension_accrual_rate: float (default 1.5, range 0-10)
    - pension_full_age: int (default 68, range 50-80)
    - pension_guarantee_enabled: bool (default false)
    - pension_guarantee_amount: float (default 990, range 0-5000)
    - life_expectancy: int (default 95, range 60-120)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    try:
        inputs: FireInputs = fire_calculate_schema.load(data)
    except ValidationError as err:
        return jsonify({"error": "Validation error", "details": err.messages}), 400

    result = calculate_fire(inputs)

    # Convert dataclass to dict and handle Decimal serialization
    result_dict = decimal_to_float(asdict(result))

    return jsonify(result_dict)


@bp.get("/api/forecasting/projection")
def get_forecasting_projection() -> Response:
    """Compute FIRE projections from persisted settings, snapshots and budget.

    All FIRE inputs (weighted return, monthly savings, annual expenses, pension
    salary) are derived on the backend from the persisted forecasting settings,
    the latest net worth snapshot and the current budget — so the result is the
    same in every browser instead of being assembled client-side. Computed on
    demand; nothing is stored.

    Returns the same shape as POST /api/forecasting/calculate, plus a "derived"
    block exposing the inputs used (and the resolved per-group return rates).
    """
    session = get_session()
    settings = get_or_create_forecasting_settings()

    # Latest net worth snapshot -> current net worth + asset allocation
    latest = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .first()
    )
    current_net_worth = Decimal(str(latest.net_worth)) if latest else Decimal("0")
    by_group: dict = latest.to_dict()["by_group"] if latest else {}

    # Budget-derived figures (shared helper), frequency-normalized to monthly
    # rates so a quarterly or yearly bill isn't counted as a monthly one
    budget_totals = compute_budget_totals(session)
    monthly_expenses = budget_totals["monthly_expenses"]
    gross_income = budget_totals["gross_income"]

    group_rates = settings.group_return_rates or {}

    # Derive FIRE inputs, mirroring the former frontend logic
    monthly_savings = (
        settings.monthly_savings_override
        if settings.monthly_savings_override is not None
        else budget_totals["monthly_surplus"]
    )
    annual_expenses = (
        settings.annual_expenses_override
        if settings.annual_expenses_override is not None
        else monthly_expenses * 12
    )
    pension_monthly_salary = (
        settings.pension_monthly_salary_override
        if settings.pension_monthly_salary_override is not None
        else gross_income
    )
    weighted_return_pct = weighted_return(by_group, group_rates)
    real_return_pct = real_return_from_nominal(
        weighted_return_pct, settings.inflation_pct
    )
    pension_active = settings.pension_accrued_monthly is not None

    inputs = FireInputs(
        current_net_worth=current_net_worth,
        monthly_contribution=monthly_savings,
        annual_expenses=annual_expenses,
        annual_return_pct=weighted_return_pct,
        inflation_pct=settings.inflation_pct,
        current_age=settings.current_age,
        target_retirement_age=settings.target_retirement_age,
        safe_withdrawal_rate=settings.safe_withdrawal_rate,
        pension_accrued_monthly=(
            settings.pension_accrued_monthly if pension_active else None
        ),
        pension_monthly_salary=pension_monthly_salary if pension_active else None,
        pension_accrual_rate=settings.pension_accrual_rate,
        pension_full_age=settings.pension_full_age,
        pension_guarantee_enabled=settings.pension_guarantee_enabled,
        pension_guarantee_amount=settings.pension_guarantee_amount,
        life_expectancy=settings.life_expectancy,
    )

    # Each group compounds at its own rate, so the mix drifts toward the
    # faster groups and the blended return rises over the projection.
    portfolio = build_portfolio(
        current_net_worth,
        by_group,
        group_rates,
        settings.inflation_pct,
        contribution_group=settings.contribution_group,
    )

    result = calculate_fire(inputs, portfolio)
    result_dict = asdict(result)
    result_dict["derived"] = {
        "current_net_worth": current_net_worth,
        "monthly_savings": monthly_savings,
        "annual_expenses": annual_expenses,
        "weighted_return_pct": weighted_return_pct,
        # Fisher-converted real return, so the displayed figure is the one the
        # projection actually compounds at. Deriving it in the frontend as
        # "weighted - inflation" made the two disagree.
        "real_return_pct": real_return_pct,
        # Where monthly savings land. None spreads them across the mix.
        "contribution_group": portfolio.contribution_group,
        # Whether the figure above is a manual override or the budget-derived
        # default. Without this, "monthly savings" and the budget's "surplus"
        # look like contradictory answers to the same question.
        "monthly_savings_is_override": settings.monthly_savings_override is not None,
        "annual_expenses_is_override": settings.annual_expenses_override is not None,
        # The configured retirement age, so "years to FIRE" can be read against
        # the plan rather than mistaken for a projected retirement age.
        "target_retirement_age": settings.target_retirement_age,
        # Always exposed (used as the salary input placeholder) even when
        # pension mode is off; only fed into the FIRE inputs when active.
        "pension_monthly_salary": pension_monthly_salary,
        "pension_active": pension_active,
        "by_group": by_group,
        "group_return_rates": resolve_group_return_rates(by_group, group_rates),
    }

    # Convert all Decimals (result + derived) to float in one pass.
    return jsonify(decimal_to_float(result_dict))
