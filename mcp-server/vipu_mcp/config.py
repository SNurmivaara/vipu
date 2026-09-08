"""Configuration, read once from the environment at import time.

Mirrors the posture backend/app/config.py takes with SECRET_KEY: a missing
secret is a startup failure in production and a warned-about default in
development, never a server that quietly listens without auth.
"""

import os

# Where the REST API lives. In compose this is the backend service.
VIPU_API_URL = os.environ.get("VIPU_API_URL", "http://localhost:5000").rstrip("/")

# Static bearer token every /mcp request must present.
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")

# Unregister every write tool. Insurance when pointing a client at live data.
VIPU_MCP_READ_ONLY = os.environ.get("VIPU_MCP_READ_ONLY", "").lower() in (
    "1",
    "true",
    "yes",
)

PORT = int(os.environ.get("PORT", "5100"))

# Matches FLASK_ENV on the backend, so one value describes the whole stack.
ENV = os.environ.get("FLASK_ENV", "development")

# How long to wait on the backend. Generous: /api/forecasting/projection walks
# a month-by-month portfolio simulation to life expectancy.
REQUEST_TIMEOUT_SECONDS = 30.0


def require_auth_token() -> str:
    """The configured bearer token, or a startup failure if there is none.

    Called from the app factory rather than at import, so tests and the
    inspector can build a server without one.
    """
    if not MCP_AUTH_TOKEN:
        if ENV == "production":
            raise ValueError(
                "MCP_AUTH_TOKEN environment variable must be set in production"
            )
        raise ValueError(
            "MCP_AUTH_TOKEN is not set. The MCP endpoint would accept any "
            "caller. Set it, or run the tools directly through the test harness."
        )
    return MCP_AUTH_TOKEN
