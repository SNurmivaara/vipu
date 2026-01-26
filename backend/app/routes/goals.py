from datetime import datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from sqlalchemy.orm import Session

from app import get_session
from app.forecasting import calculate_goal_forecast
from app.models import (
    BudgetSettings,
    Goal,
    IncomeItem,
    NetWorthCategory,
    NetWorthSnapshot,
)

bp = APIBlueprint("goals", __name__, tag="Goals")

MAX_NAME_LENGTH = 100
MAX_TARGET_VALUE = 1_000_000_000  # 1 billion
VALID_GOAL_TYPES = [
    "net_worth_target",
    "category_target",
    "category_monthly",
    "category_rate",
]
VALID_TRACKING_PERIODS = ["month", "quarter", "half_year", "year"]
TRACKING_PERIOD_MONTHS = {
    "month": 1,
    "quarter": 3,
    "half_year": 6,
    "year": 12,
}

RATE_ERROR = "category_rate target_value must be between 0 and 100"
DATE_FORMAT_ERROR = "target_date must be a valid ISO date string"
CATEGORY_REQUIRED_ERROR = "category_id is required for category-based goals"
PERIOD_REQUIRED_ERROR = "tracking_period is required for monthly/rate goals"


@bp.get("/api/goals")
def list_goals() -> Response:
    """List all goals."""
    session = get_session()
    goals = session.query(Goal).order_by(Goal.created_at.desc()).all()
    return jsonify([g.to_dict() for g in goals])


@bp.post("/api/goals")
def create_goal() -> Response | tuple[Response, int]:
    """Create a new goal.

    Required fields: name, goal_type, target_value
    Optional fields: category_id, tracking_period, target_date, is_active

    For category_target, category_monthly, category_rate: category_id required
    For category_monthly, category_rate: tracking_period required
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate required fields
    if "name" not in data:
        return jsonify({"error": "name is required"}), 400
    if "goal_type" not in data:
        return jsonify({"error": "goal_type is required"}), 400
    if "target_value" not in data:
        return jsonify({"error": "target_value is required"}), 400

    # Validate name
    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}), 400

    # Validate goal_type
    goal_type = str(data["goal_type"]).strip()
    if goal_type not in VALID_GOAL_TYPES:
        types_str = ", ".join(VALID_GOAL_TYPES)
        return jsonify({"error": f"goal_type must be one of: {types_str}"}), 400

    # Validate target_value
    try:
        target_value = Decimal(str(data["target_value"]))
    except (ValueError, TypeError):
        return jsonify({"error": "target_value must be a valid number"}), 400

    if abs(target_value) > MAX_TARGET_VALUE:
        return jsonify({"error": "target_value exceeds maximum allowed value"}), 400

    # For category_rate, target_value should be a percentage (0-100)
    if goal_type == "category_rate" and (target_value < 0 or target_value > 100):
        return jsonify({"error": RATE_ERROR}), 400

    # Validate category_id for category-based goals
    category_id = None
    if goal_type in ["category_target", "category_monthly", "category_rate"]:
        if "category_id" not in data or data["category_id"] is None:
            return jsonify({"error": CATEGORY_REQUIRED_ERROR}), 400
        category_id = int(data["category_id"])
        # Verify category exists
        category = session.query(NetWorthCategory).filter_by(id=category_id).first()
        if not category:
            return jsonify({"error": "Category not found"}), 404

    # Validate tracking_period for monthly/rate goals
    tracking_period = None
    if goal_type in ["category_monthly", "category_rate"]:
        if "tracking_period" not in data or data["tracking_period"] is None:
            return jsonify({"error": PERIOD_REQUIRED_ERROR}), 400
        tracking_period = str(data["tracking_period"]).strip()
        if tracking_period not in VALID_TRACKING_PERIODS:
            periods_str = ", ".join(VALID_TRACKING_PERIODS)
            err = f"tracking_period must be one of: {periods_str}"
            return jsonify({"error": err}), 400

    # Parse optional target_date
    target_date = None
    if "target_date" in data and data["target_date"]:
        try:
            date_str = str(data["target_date"])
            target_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": DATE_FORMAT_ERROR}), 400

    # For category_target goals on liability categories, capture starting value
    starting_value = None
    if goal_type == "category_target" and category_id:
        category = session.query(NetWorthCategory).filter_by(id=category_id).first()
        if category and category.group and category.group.group_type == "liability":
            # Get current value from latest snapshot
            latest_snapshot = (
                session.query(NetWorthSnapshot)
                .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
                .first()
            )
            if latest_snapshot:
                for entry in latest_snapshot.entries:
                    if entry.category_id == category_id:
                        starting_value = entry.amount
                        break

    goal = Goal(
        name=name,
        goal_type=goal_type,
        target_value=target_value,
        category_id=category_id,
        tracking_period=tracking_period,
        target_date=target_date,
        starting_value=starting_value,
        is_active=bool(data.get("is_active", True)),
    )
    session.add(goal)
    session.commit()

    return jsonify(goal.to_dict()), 201


@bp.get("/api/goals/<int:goal_id>")
def get_goal(goal_id: int) -> Response | tuple[Response, int]:
    """Get a specific goal."""
    session = get_session()
    goal = session.query(Goal).filter_by(id=goal_id).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    return jsonify(goal.to_dict())


@bp.put("/api/goals/<int:goal_id>")
def update_goal(goal_id: int) -> Response | tuple[Response, int]:
    """Update an existing goal."""
    session = get_session()
    goal = session.query(Goal).filter_by(id=goal_id).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            err = f"name must be 1-{MAX_NAME_LENGTH} characters"
            return jsonify({"error": err}), 400
        goal.name = name

    if "goal_type" in data:
        goal_type = str(data["goal_type"]).strip()
        if goal_type not in VALID_GOAL_TYPES:
            types_str = ", ".join(VALID_GOAL_TYPES)
            return jsonify({"error": f"goal_type must be one of: {types_str}"}), 400
        goal.goal_type = goal_type

    if "target_value" in data:
        try:
            target_value = Decimal(str(data["target_value"]))
        except (ValueError, TypeError):
            return jsonify({"error": "target_value must be a valid number"}), 400

        if abs(target_value) > MAX_TARGET_VALUE:
            return jsonify({"error": "target_value exceeds maximum allowed value"}), 400

        current_type = data.get("goal_type", goal.goal_type)
        if current_type == "category_rate":
            if target_value < 0 or target_value > 100:
                return jsonify({"error": RATE_ERROR}), 400

        goal.target_value = target_value

    if "category_id" in data:
        if data["category_id"] is None:
            goal.category_id = None
        else:
            category_id = int(data["category_id"])
            category = session.query(NetWorthCategory).filter_by(id=category_id).first()
            if not category:
                return jsonify({"error": "Category not found"}), 404
            goal.category_id = category_id

    if "tracking_period" in data:
        if data["tracking_period"] is None:
            goal.tracking_period = None
        else:
            tracking_period = str(data["tracking_period"]).strip()
            if tracking_period not in VALID_TRACKING_PERIODS:
                periods_str = ", ".join(VALID_TRACKING_PERIODS)
                err = f"tracking_period must be one of: {periods_str}"
                return jsonify({"error": err}), 400
            goal.tracking_period = tracking_period

    if "target_date" in data:
        if data["target_date"] is None:
            goal.target_date = None
        else:
            try:
                date_str = str(data["target_date"])
                date_val = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                goal.target_date = date_val
            except ValueError:
                return jsonify({"error": DATE_FORMAT_ERROR}), 400

    if "is_active" in data:
        goal.is_active = bool(data["is_active"])

    session.commit()
    return jsonify(goal.to_dict())


@bp.delete("/api/goals/<int:goal_id>")
def delete_goal(goal_id: int) -> tuple[Response, int]:
    """Delete a goal."""
    session = get_session()
    goal = session.query(Goal).filter_by(id=goal_id).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    session.delete(goal)
    session.commit()
    return jsonify({"message": "Goal deleted"}), 200


def _get_snapshots_in_period(
    session: Session, num_months: int
) -> list[NetWorthSnapshot]:
    """Get snapshots for the tracking period, ordered newest first."""
    result: list[NetWorthSnapshot] = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .limit(num_months + 1)  # +1 to get the "before" snapshot for comparison
        .all()
    )
    return result


def _get_category_amount_in_snapshot(
    snapshot: NetWorthSnapshot, category_id: int
) -> Decimal:
    """Get the amount for a specific category in a snapshot."""
    for entry in snapshot.entries:
        if entry.category_id == category_id:
            return entry.amount if entry.amount is not None else Decimal("0")
    return Decimal("0")


def _calculate_net_income(
    income_items: list[IncomeItem], default_tax_pct: Decimal
) -> Decimal:
    """Calculate total net income after taxes."""
    total = Decimal("0")
    for item in income_items:
        total += item.calculate_net(default_tax_pct)
    return total


def _calculate_goal_progress(
    goal: Goal,
    snapshots: list[NetWorthSnapshot],
    net_income: Decimal,
) -> dict:
    """Calculate progress for a single goal.

    Returns a dict with:
    - goal: the goal data
    - current_value: current progress value
    - target_value: target value
    - progress_percentage: 0-100 percentage (capped at 100)
    - is_achieved: whether goal is met
    - details: additional context (varies by goal type)
    - forecast: projection information (for target-based goals)
      - forecast_date: when goal will be reached at current pace
      - months_until_target: months until goal reached
      - on_track: whether goal will be met by target_date
      - required_monthly_change: change needed to meet goal on time
      - current_monthly_change: current average monthly change
    """
    zero = Decimal("0")
    current_value = zero
    details: dict = {}
    latest = snapshots[0] if snapshots else None

    if goal.goal_type == "net_worth_target":
        # Overall net worth target
        if latest:
            current_value = Decimal(str(latest.net_worth))
            details["latest_month"] = f"{latest.year}-{latest.month:02d}"
        else:
            details["latest_month"] = None

    elif goal.goal_type == "category_target":
        # Target balance for a specific category
        is_liability = (
            goal.category
            and goal.category.group
            and goal.category.group.group_type == "liability"
        )
        details["is_liability"] = is_liability
        details["starting_value"] = (
            float(goal.starting_value) if goal.starting_value is not None else None
        )

        if latest and goal.category_id:
            current_value = _get_category_amount_in_snapshot(latest, goal.category_id)
            # For liabilities, use absolute value for display
            if is_liability:
                current_value = abs(current_value)
            details["latest_month"] = f"{latest.year}-{latest.month:02d}"
            details["category_name"] = goal.category.name if goal.category else None
        else:
            details["latest_month"] = None
            details["category_name"] = goal.category.name if goal.category else None

    elif goal.goal_type == "category_monthly":
        # Monthly contribution to a category (average over tracking period)
        if goal.category_id and goal.tracking_period:
            num_months = TRACKING_PERIOD_MONTHS.get(goal.tracking_period, 1)
            details["tracking_period"] = goal.tracking_period
            details["category_name"] = goal.category.name if goal.category else None

            if len(snapshots) >= 2:
                # Calculate average monthly change
                total_change = zero
                changes_count = 0

                for i in range(min(num_months, len(snapshots) - 1)):
                    current_snap = snapshots[i]
                    prev_snap = snapshots[i + 1]

                    curr_amt = _get_category_amount_in_snapshot(
                        current_snap, goal.category_id
                    )
                    prev_amt = _get_category_amount_in_snapshot(
                        prev_snap, goal.category_id
                    )
                    change = curr_amt - prev_amt

                    # For assets, positive change = savings (good)
                    # For liabilities (stored as negative), when debt decreases
                    # (e.g., -20000 to -19500), change is already positive (+500)
                    # No sign flip needed - both cases want positive for "good"

                    total_change += change
                    changes_count += 1

                if changes_count > 0:
                    current_value = total_change / changes_count
                    details["total_change"] = float(total_change)
                    details["months_tracked"] = changes_count
                else:
                    details["total_change"] = 0
                    details["months_tracked"] = 0
            else:
                details["total_change"] = 0
                details["months_tracked"] = 0

    elif goal.goal_type == "category_rate":
        # Percentage of income growth in a category
        if goal.category_id and goal.tracking_period and net_income > 0:
            num_months = TRACKING_PERIOD_MONTHS.get(goal.tracking_period, 1)
            details["tracking_period"] = goal.tracking_period
            details["category_name"] = goal.category.name if goal.category else None
            details["net_income"] = float(net_income)

            if len(snapshots) >= 2:
                # Calculate average monthly change
                total_change = zero
                changes_count = 0

                for i in range(min(num_months, len(snapshots) - 1)):
                    current_snap = snapshots[i]
                    prev_snap = snapshots[i + 1]

                    curr_amt = _get_category_amount_in_snapshot(
                        current_snap, goal.category_id
                    )
                    prev_amt = _get_category_amount_in_snapshot(
                        prev_snap, goal.category_id
                    )
                    change = curr_amt - prev_amt

                    # For assets, positive change = savings (good)
                    # For liabilities (stored as negative), when debt decreases
                    # (e.g., -20000 to -19500), change is already positive (+500)
                    # No sign flip needed - both cases want positive for "good"

                    total_change += change
                    changes_count += 1

                if changes_count > 0:
                    avg_change = total_change / changes_count
                    # Rate = (avg_monthly_change / net_income) * 100
                    current_value = (avg_change / net_income) * 100
                    details["avg_monthly_change"] = float(avg_change)
                    details["months_tracked"] = changes_count
                else:
                    details["avg_monthly_change"] = 0
                    details["months_tracked"] = 0
            else:
                details["avg_monthly_change"] = 0
                details["months_tracked"] = 0
        else:
            details["net_income"] = float(net_income)
            details["avg_monthly_change"] = 0
            details["months_tracked"] = 0

    # Calculate progress percentage
    target = goal.target_value
    is_liability_goal = (
        goal.goal_type == "category_target"
        and details.get("is_liability", False)
        and goal.starting_value is not None
    )

    if is_liability_goal:
        # For liability goals: progress = (starting - current) / (starting - target)
        # E.g., loan started at 26728, now 20000, target 0:
        # progress = (26728 - 20000) / (26728 - 0) = 6728 / 26728 = 25.2%
        starting = Decimal(str(goal.starting_value))
        if starting > target:
            progress_pct = float((starting - current_value) / (starting - target) * 100)
        elif starting == target:
            # Already at target
            progress_pct = 100.0
        else:
            progress_pct = 0.0
        # For liabilities, achieved when current <= target
        is_achieved = current_value <= target
    else:
        # Standard progress: current / target
        if target > 0:
            progress_pct = float((current_value / target) * 100)
        elif target == 0 and current_value >= 0:
            progress_pct = 100.0
        else:
            progress_pct = 0.0
        # Standard: achieved when current >= target
        is_achieved = current_value >= target

    # Cap at 100%
    progress_pct = min(progress_pct, 100.0)
    # Floor at 0%
    progress_pct = max(progress_pct, 0.0)

    # Calculate forecast for target-based goals
    forecast_info: dict | None = None
    if goal.goal_type in ("net_worth_target", "category_target"):
        forecast = calculate_goal_forecast(
            goal=goal,
            current_value=float(current_value),
            snapshots=snapshots,
            category_id=goal.category_id,
        )
        forecast_info = {
            "forecast_date": forecast.forecast_date,
            "months_until_target": forecast.months_until_target,
            "on_track": forecast.on_track,
            "required_monthly_change": forecast.required_monthly_change,
            "current_monthly_change": forecast.current_monthly_change,
        }

    return {
        "goal": goal.to_dict(),
        "current_value": float(current_value),
        "target_value": float(target),
        "progress_percentage": round(progress_pct, 2),
        "is_achieved": is_achieved,
        "details": details,
        "forecast": forecast_info,
    }


@bp.get("/api/goals/progress")
def get_goals_progress() -> Response:
    """Get progress for all active goals.

    Calculates current progress based on:
    - net_worth_target: Latest net worth snapshot value
    - category_target: Current balance in a specific category
    - category_monthly: Average monthly change in category over tracking period
    - category_rate: Percentage of income as category change over tracking period

    Returns a list of goal progress objects.
    """
    session = get_session()

    # Get all active goals
    goals = (
        session.query(Goal)
        .filter_by(is_active=True)
        .order_by(Goal.created_at.desc())
        .all()
    )

    if not goals:
        return jsonify([])

    # Get snapshots for the longest tracking period we might need (12 months + 1)
    snapshots = _get_snapshots_in_period(session, 12)

    # Calculate net income for rate-based goals
    settings = session.query(BudgetSettings).first()
    tax_pct = settings.tax_percentage if settings else Decimal("25.0")
    income_items = session.query(IncomeItem).all()
    net_income = _calculate_net_income(income_items, tax_pct)

    # Calculate progress for each goal
    progress_list = [
        _calculate_goal_progress(goal, snapshots, net_income) for goal in goals
    ]

    return jsonify(progress_list)
