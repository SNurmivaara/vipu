"""Configuration, read once from the environment at import time.

Mirrors the posture backend/app/config.py takes with SECRET_KEY: a missing
secret is a startup failure in production and a warned-about default in
development, never a server that quietly listens without auth.
"""

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

# Where the REST API lives. In compose this is the backend service.
VIPU_API_URL = os.environ.get("VIPU_API_URL", "http://localhost:5000").rstrip("/")

# Optional legacy credential when OAuth is configured.
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

# Example values the repository has published. Anyone can read them, so they
# never authenticate anything. Compared case-insensitively.
PLACEHOLDER_TOKENS = frozenset({"your-mcp-token-here", "<token>", "<mcp_auth_token>"})

# Development tokens from the dev Compose file and README. Fine on a laptop,
# refused in production for the same reason.
DEVELOPMENT_TOKENS = frozenset({"dev-mcp-token-not-for-production", "dev-token"})

# openssl rand -hex 32 gives 64; a shorter token still starts, with a warning.
MIN_TOKEN_LENGTH = 32

# Partial OAuth configuration is an error, even with a legacy token present.
OAUTH_ENV = (
    "MCP_OAUTH_ISSUER",
    "MCP_OAUTH_RESOURCE_URL",
    "MCP_OAUTH_JWKS_URL",
    "MCP_OAUTH_ALLOWED_CLIENTS",
    "MCP_OAUTH_ALLOWED_USERS",
)


@dataclass(frozen=True)
class OAuthConfig:
    issuer: str
    resource_url: str
    jwks_url: str
    allowed_clients: frozenset[str]
    allowed_users: frozenset[str]

    def __post_init__(self) -> None:
        for name in ("issuer", "resource_url", "jwks_url"):
            url = getattr(self, name)
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or any(char.isspace() for char in url)
            ):
                raise ValueError(f"OAuth {name} must be an absolute HTTPS URL")
        if urlsplit(self.resource_url).path != "/mcp":
            raise ValueError(
                "MCP_OAUTH_RESOURCE_URL must end in /mcp (no trailing slash)"
            )
        if not self.allowed_clients or not self.allowed_users:
            raise ValueError("OAuth requires non-empty client and user allowlists")


def oauth_config() -> OAuthConfig | None:
    """Enable OAuth only with a complete, explicit trust configuration."""
    values = {key: os.environ.get(key, "").strip() for key in OAUTH_ENV}
    if not any(values.values()):
        return None
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError("Incomplete OAuth configuration: " + ", ".join(missing))

    def allowlist(key: str) -> frozenset[str]:
        return frozenset(
            item.strip() for item in values[key].split(",") if item.strip()
        )

    if MCP_AUTH_TOKEN:
        check_token(MCP_AUTH_TOKEN)
    return OAuthConfig(
        issuer=values["MCP_OAUTH_ISSUER"],
        resource_url=values["MCP_OAUTH_RESOURCE_URL"],
        jwks_url=values["MCP_OAUTH_JWKS_URL"],
        allowed_clients=allowlist("MCP_OAUTH_ALLOWED_CLIENTS"),
        allowed_users=allowlist("MCP_OAUTH_ALLOWED_USERS"),
    )


def check_token(token: str) -> None:
    """Refuse a published example token; warn about a short one."""
    normalized = token.strip().lower()
    if normalized in PLACEHOLDER_TOKENS:
        raise ValueError(
            "MCP_AUTH_TOKEN is still the example placeholder. "
            "Generate a token with: openssl rand -hex 32"
        )
    if ENV == "production" and normalized in DEVELOPMENT_TOKENS:
        raise ValueError(
            "MCP_AUTH_TOKEN is a published development token. "
            "Generate a token with: openssl rand -hex 32"
        )
    if len(token) < MIN_TOKEN_LENGTH:
        logger.warning(
            "MCP_AUTH_TOKEN is shorter than %d characters. "
            "Generate a stronger one with: openssl rand -hex 32",
            MIN_TOKEN_LENGTH,
        )


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
    check_token(MCP_AUTH_TOKEN)
    return MCP_AUTH_TOKEN
