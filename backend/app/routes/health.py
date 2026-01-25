from flask import Blueprint, Response, jsonify

bp = Blueprint("health", __name__)


@bp.route("/api/health", methods=["GET"])
def health_check() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "ok"})
