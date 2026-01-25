from datetime import datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.models import (
    BudgetSettings,
    ExpenseItem,
    Goal,
    IncomeItem,
    NetWorthSnapshot,
)

bp = APIBlueprint("goals", __name__, tag="Goals")

MAX_NAME_LENGTH = 100
MAX_TARGET_VALUE = 1_000_000_000  # 1 billion
VALID_GOAL_TYPES = ["net_worth", "savings_rate", "monthly_savings"]

SAVINGS_RATE_ERROR = "savings_rate target_value must be between 0 and 100"
DATE_FORMAT_ERROR = "target_date must be a valid ISO date string"


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
    Optional fields: target_date, is_active
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

    # For savings_rate, target_value should be a percentage (0-100)
    if goal_type == "savings_rate" and (target_value < 0 or target_value > 100):
        return jsonify({"error": SAVINGS_RATE_ERROR}), 400

    # Parse optional target_date
    target_date = None
    if "target_date" in data and data["target_date"]:
        try:
            # Accept ISO format date string
            date_str = str(data["target_date"])
            target_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": DATE_FORMAT_ERROR}), 400

    goal = Goal(
        name=name,
        goal_type=goal_type,
        target_value=target_value,
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
            return (
                jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}),
                400,
            )
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

        # For savings_rate, target_value should be a percentage (0-100)
        current_type = data.get("goal_type", goal.goal_type)
        if current_type == "savings_rate":
            if target_value < 0 or target_value > 100:
                return jsonify({"error": SAVINGS_RATE_ERROR}), 400

        goal.target_value = target_value

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
    latest_snapshot: NetWorthSnapshot | None,
    net_income: Decimal,
    savings_goal_expenses: Decimal,
) -> dict:
    """Calculate progress for a single goal.

    Returns a dict with:
    - goal: the goal data
    - current_value: current progress value
    - target_value: target value
    - progress_percentage: 0-100 percentage (capped at 100)
    - is_achieved: whether goal is met
    - details: additional context (varies by goal type)
    """
    zero = Decimal("0")
    current_value = zero
    details: dict = {}

    if goal.goal_type == "net_worth":
        # Net worth target - compare latest net worth to target
        if latest_snapshot:
            current_value = Decimal(str(latest_snapshot.net_worth))
            year = latest_snapshot.year
            month = latest_snapshot.month
            details["latest_month"] = f"{year}-{month:02d}"
        else:
            details["latest_month"] = None

    elif goal.goal_type == "savings_rate":
        # Savings rate - calculate actual savings rate percentage
        # savings_rate = (savings_goal_expenses / net_income) * 100
        if net_income > 0:
            actual_rate = (savings_goal_expenses / net_income) * 100
            current_value = actual_rate
            details["net_income"] = float(net_income)
            details["savings_amount"] = float(savings_goal_expenses)
        else:
            current_value = zero
            details["net_income"] = 0
            details["savings_amount"] = float(savings_goal_expenses)

    elif goal.goal_type == "monthly_savings":
        # Monthly savings target - compare savings goal expenses to target
        current_value = savings_goal_expenses
        details["net_income"] = float(net_income)

    # Calculate progress percentage
    target = goal.target_value
    if target > 0:
        progress_pct = float((current_value / target) * 100)
    elif target == 0 and current_value >= 0:
        progress_pct = 100.0
    else:
        progress_pct = 0.0

    # Cap at 100%
    progress_pct = min(progress_pct, 100.0)

    # Check if goal is achieved
    is_achieved = current_value >= target

    return {
        "goal": goal.to_dict(),
        "current_value": float(current_value),
        "target_value": float(target),
        "progress_percentage": round(progress_pct, 2),
        "is_achieved": is_achieved,
        "details": details,
    }


@bp.get("/api/goals/progress")
def get_goals_progress() -> Response:
    """Get progress for all active goals.

    Calculates current progress based on:
    - Net worth goals: latest net worth snapshot value
    - Savings rate goals: savings_goal expenses / net_income * 100
    - Monthly savings goals: sum of savings_goal expenses

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

    # Get latest net worth snapshot
    latest_snapshot = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .first()
    )

    # Calculate net income and savings goal expenses
    settings = session.query(BudgetSettings).first()
    tax_pct = settings.tax_percentage if settings else Decimal("25.0")

    income_items = session.query(IncomeItem).all()
    net_income = _calculate_net_income(income_items, tax_pct)

    # Sum up savings goal expenses
    savings_goals = session.query(ExpenseItem).filter_by(is_savings_goal=True).all()
    savings_goal_expenses = sum(
        (e.amount for e in savings_goals),
        Decimal("0"),
    )

    # Calculate progress for each goal
    progress_list = [
        _calculate_goal_progress(
            goal, latest_snapshot, net_income, savings_goal_expenses
        )
        for goal in goals
    ]

    return jsonify(progress_list)
