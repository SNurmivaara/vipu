from datetime import date

from apiflask import APIBlueprint
from flask import Response, jsonify

from app import get_session
from app.summary import FORMAT_VERSION, build_financial_summary

bp = APIBlueprint("summary", __name__, tag="Summary")


@bp.get("/api/summary")
def get_summary() -> Response:
    """The whole app state as one markdown digest, meant for an LLM to read.

    Budget and wealth in a single document, with the caveats a model would
    otherwise get wrong: the budget-vs-snapshot date skew, settled occurrences
    being excluded from period totals, a card charged once rather than every
    period, and linear goal math against compounding FIRE math.

    Composes the same payloads GET /api/budget/current, /api/goals/roadmap,
    /api/goals/progress, /api/networth and /api/forecasting/projection return,
    so it can never disagree with them.
    """
    today = date.today()
    return jsonify(
        {
            "format_version": FORMAT_VERSION,
            "generated_at": today.isoformat(),
            "markdown": build_financial_summary(get_session(), today),
        }
    )
