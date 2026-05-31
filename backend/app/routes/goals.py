from datetime import datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from sqlalchemy.orm import Session

from app import get_session
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
VALID_GOAL_TYPES = ["net_worth", "savings_rate", "savings_goal"]

RATE_ERROR = "savings_rate target_value must be between 0 and 100"
DATE_FORMAT_ERROR = "target_date must be a valid ISO date string"
CATEGORY_REQUIRED_ERROR = "category_id is required for savings_goal type"


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
    Optional fields: category_id (required for savings_goal), target_date, is_active
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

    if target_value < 0:
        return jsonify({"error": "target_value must be positive"}), 400

    if target_value > MAX_TARGET_VALUE:
        return jsonify({"error": "target_value exceeds maximum allowed value"}), 400

    # For savings_rate, target_value should be a percentage (0-100)
    if goal_type == "savings_rate" and target_value > 100:
        return jsonify({"error": RATE_ERROR}), 400

    # Only one savings_rate goal allowed
    if goal_type == "savings_rate":
        existing = session.query(Goal).filter_by(goal_type="savings_rate").first()
        if existing:
            return jsonify({"error": "Only one savings rate goal allowed"}), 400

    # Validate category_id for savings_goal
    category_id = None
    if goal_type == "savings_goal":
        if "category_id" not in data or data["category_id"] is None:
            return jsonify({"error": CATEGORY_REQUIRED_ERROR}), 400
        category_id = int(data["category_id"])
        # Verify category exists
        category = session.query(NetWorthCategory).filter_by(id=category_id).first()
        if not category:
            return jsonify({"error": "Category not found"}), 404

    # Parse optional target_date
    target_date = None
    if "target_date" in data and data["target_date"]:
        try:
            date_str = str(data["target_date"])
            target_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": DATE_FORMAT_ERROR}), 400

    goal = Goal(
        name=name,
        goal_type=goal_type,
        target_value=target_value,
        category_id=category_id,
        target_date=target_date,
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

        # Only one savings_rate goal allowed (check if changing to savings_rate)
        if goal_type == "savings_rate" and goal.goal_type != "savings_rate":
            existing = session.query(Goal).filter_by(goal_type="savings_rate").first()
            if existing:
                return jsonify({"error": "Only one savings rate goal allowed"}), 400

        goal.goal_type = goal_type

    if "target_value" in data:
        try:
            target_value = Decimal(str(data["target_value"]))
        except (ValueError, TypeError):
            return jsonify({"error": "target_value must be a valid number"}), 400

        if target_value < 0:
            return jsonify({"error": "target_value must be positive"}), 400

        if target_value > MAX_TARGET_VALUE:
            return jsonify({"error": "target_value exceeds maximum allowed value"}), 400

        current_type = data.get("goal_type", goal.goal_type)
        if current_type == "savings_rate" and target_value > 100:
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


def _get_snapshots(session: Session, num_months: int) -> list[NetWorthSnapshot]:
    """Get snapshots ordered newest first."""
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


# Minimum snapshots before we trust a measured saving pace.
MIN_MONTHS_FOR_PACE = 3


def _months_between(later: NetWorthSnapshot, earlier: NetWorthSnapshot) -> int:
    """Whole months from the earlier snapshot to the later one."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def _tracked_value_in_snapshot(snapshot: NetWorthSnapshot, goal: Goal) -> Decimal:
    """The value this goal tracks within a single snapshot."""
    if goal.goal_type in ("net_worth", "net_worth_target"):
        return Decimal(str(snapshot.net_worth))
    if goal.goal_type in ("savings_goal", "category_target") and goal.category_id:
        return abs(_get_category_amount_in_snapshot(snapshot, goal.category_id))
    return Decimal("0")


def _recent_monthly_change(
    goal: Goal, snapshots: list[NetWorthSnapshot]
) -> Decimal | None:
    """Average monthly change in the tracked value across the snapshot window.

    This is the *actual* recent saving pace: how much the tracked balance has
    moved per month over the available history. The previous implementation
    divided the whole current balance by the number of months of data, which
    treated a long-standing balance as if it had all been saved since tracking
    began and badly overstated progress.

    Returns None when there aren't at least two snapshots spanning a positive
    number of months, so no pace can be derived.
    """
    if len(snapshots) < 2:
        return None

    latest, oldest = snapshots[0], snapshots[-1]
    months = _months_between(latest, oldest)
    if months <= 0:
        return None

    change = _tracked_value_in_snapshot(latest, goal) - _tracked_value_in_snapshot(
        oldest, goal
    )
    return change / Decimal(months)


def _empty_pace() -> dict:
    """A pace analysis with no verdict (used for rate goals and as a base)."""
    return {
        "status": None,
        "status_reason": None,
        "required_monthly": None,
        "recent_monthly": None,
        "projected_value": None,
        "months_remaining": None,
    }


def _calculate_rate_status(
    current_value: Decimal, target_value: Decimal, data_months: int
) -> str | None:
    """On-track status for savings_rate goals: compare current vs target rate."""
    if data_months < 2:
        return None  # Not enough data
    return "on_track" if current_value >= target_value else "behind"


def _analyze_pace(
    goal: Goal,
    current_value: Decimal,
    target_value: Decimal,
    recent_monthly: Decimal | None,
    data_months: int,
) -> dict:
    """Assess whether a net_worth / savings_goal is on track for its target.

    Compares the *required* monthly pace (the gap to target spread over the
    time remaining) against the *actual* recent monthly pace measured from
    snapshots, and explains the verdict so the UI can say why.

    Returns a dict with: status, status_reason, required_monthly,
    recent_monthly, projected_value, months_remaining.
    """
    pace = _empty_pace()

    # Already there.
    if current_value >= target_value:
        pace["status"] = "on_track"
        pace["status_reason"] = "Target reached"
        return pace

    # Without a deadline there is no pace to be on track for.
    if not goal.target_date:
        pace["status_reason"] = "Set a target date to track your pace"
        return pace

    now = datetime.now(tz=goal.target_date.tzinfo)
    months_remaining = (goal.target_date.year - now.year) * 12 + (
        goal.target_date.month - now.month
    )
    pace["months_remaining"] = months_remaining

    if goal.target_date <= now or months_remaining <= 0:
        pace["status"] = "behind"
        pace["status_reason"] = "Target date has passed"
        return pace

    remaining = target_value - current_value
    required_monthly = remaining / Decimal(months_remaining)
    pace["required_monthly"] = float(required_monthly)

    # Need enough history to measure a trustworthy pace.
    if recent_monthly is None or data_months < MIN_MONTHS_FOR_PACE:
        pace["status_reason"] = "Add more monthly snapshots to track your pace"
        return pace

    pace["recent_monthly"] = float(recent_monthly)
    projected = current_value + recent_monthly * months_remaining
    pace["projected_value"] = float(projected)

    if recent_monthly >= required_monthly:
        pace["status"] = "on_track"
        pace["status_reason"] = "Saving fast enough to reach the target on time"
    elif recent_monthly <= 0:
        pace["status"] = "behind"
        pace["status_reason"] = "Balance isn't growing toward the target"
    else:
        pace["status"] = "behind"
        pace["status_reason"] = "Saving too slowly to reach the target on time"
    return pace


def calculate_goal_progress(
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
    - status: 'on_track', 'behind', or None (if no target_date or <3 months data)
    - status_reason: short human-readable explanation of the status
    - required_monthly: monthly amount needed to hit the target by target_date
    - recent_monthly: actual recent monthly saving pace (from snapshots)
    - projected_value: value at target_date if the recent pace continues
    - months_remaining: whole months until target_date
    - data_months: number of months of snapshot data available
    - category_name: category name (for savings_goal type)
    """
    zero = Decimal("0")
    current_value = zero
    category_name: str | None = None
    data_months = len(snapshots)
    latest = snapshots[0] if snapshots else None

    # Support both old types (net_worth_target, category_target) and new types
    if goal.goal_type in ("net_worth", "net_worth_target"):
        # Overall net worth target
        if latest:
            current_value = Decimal(str(latest.net_worth))

    elif goal.goal_type in ("savings_rate", "category_rate"):
        # Savings rate: YTD average ((current - start of year) / months / income) * 100
        category_name = None
        if len(snapshots) >= 2 and net_income > 0:
            current_nw = Decimal(str(snapshots[0].net_worth))
            current_year = snapshots[0].year

            # Find the start of year snapshot (Jan) or earliest snapshot in this year
            # Snapshots are ordered newest first
            start_snapshot = None
            for s in snapshots:
                if s.year == current_year:
                    start_snapshot = s  # Keep updating to get the oldest in this year
                elif s.year < current_year:
                    # Use last year's December as baseline if available
                    start_snapshot = s
                    break

            if start_snapshot and start_snapshot != snapshots[0]:
                start_nw = Decimal(str(start_snapshot.net_worth))
                # Calculate months elapsed
                months_elapsed = (
                    (snapshots[0].year - start_snapshot.year) * 12
                    + snapshots[0].month
                    - start_snapshot.month
                )
                if months_elapsed > 0:
                    total_change = current_nw - start_nw
                    avg_monthly_change = total_change / months_elapsed
                    current_value = (avg_monthly_change / net_income) * 100
                else:
                    current_value = zero
            else:
                current_value = zero
        else:
            current_value = zero

    elif goal.goal_type in ("savings_goal", "category_target"):
        # Target balance for a specific category
        if latest and goal.category_id:
            current_value = _get_category_amount_in_snapshot(latest, goal.category_id)
            # Use absolute value for display
            current_value = abs(current_value)
            category_name = goal.category.name if goal.category else None
        else:
            category_name = goal.category.name if goal.category else None

    # Calculate progress percentage
    target = goal.target_value

    if target > 0:
        progress_pct = float((current_value / target) * 100)
    elif target == 0 and current_value >= 0:
        progress_pct = 100.0
    else:
        progress_pct = 0.0

    # Standard: achieved when current >= target
    is_achieved = current_value >= target

    # Cap at 100%, floor at 0%
    progress_pct = max(0.0, min(progress_pct, 100.0))

    # Calculate on-track status and the pace details behind it
    if goal.goal_type in ("savings_rate", "category_rate"):
        pace = _empty_pace()
        pace["status"] = _calculate_rate_status(current_value, target, data_months)
    else:
        recent_monthly = _recent_monthly_change(goal, snapshots)
        pace = _analyze_pace(goal, current_value, target, recent_monthly, data_months)

    return {
        "goal": goal.to_dict(),
        "current_value": float(current_value),
        "target_value": float(target),
        "progress_percentage": round(progress_pct, 2),
        "is_achieved": is_achieved,
        "status": pace["status"],
        "status_reason": pace["status_reason"],
        "required_monthly": pace["required_monthly"],
        "recent_monthly": pace["recent_monthly"],
        "projected_value": pace["projected_value"],
        "months_remaining": pace["months_remaining"],
        "data_months": data_months,
        "category_name": category_name,
    }


@bp.get("/api/goals/progress")
def get_goals_progress() -> Response:
    """Get progress for all active goals.

    Calculates current progress based on:
    - net_worth: Latest net worth snapshot value
    - savings_rate: (monthly net worth change / net income) * 100
    - savings_goal: Current balance in a specific category

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

    # Get snapshots (enough for calculating monthly changes)
    snapshots = _get_snapshots(session, 12)

    # Calculate net income for savings_rate goals
    settings = session.query(BudgetSettings).first()
    tax_pct = settings.tax_percentage if settings else Decimal("25.0")
    income_items = session.query(IncomeItem).all()
    net_income = _calculate_net_income(income_items, tax_pct)

    # Calculate progress for each goal
    progress_list = [
        calculate_goal_progress(goal, snapshots, net_income) for goal in goals
    ]

    return jsonify(progress_list)
