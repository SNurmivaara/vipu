from apiflask import APIBlueprint
from flask import Response, jsonify

bp = APIBlueprint("health", __name__, tag="Health")


@bp.get("/api/health")
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "ok"})
