import logging
import os
from typing import Any
from urllib.parse import urlsplit

from apiflask import APIFlask
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config import get_config
from app.models import Base

engine: Any = None
Session: scoped_session[SQLAlchemySession] | None = None

# Recycle pooled connections before typical managed-Postgres/proxy idle
# timeouts (often ~5 min) so we never hand out a half-open connection.
POOL_RECYCLE_SECONDS = 280

logger = logging.getLogger(__name__)

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Fetch Metadata values a browser sends for the frontend's own /api calls,
# which always go through a same-origin proxy (Next.js rewrite or Traefik).
TRUSTED_FETCH_SITES = frozenset({"same-origin", "none"})

# Docker health checks call this by container address, whatever the Host
# allowlist says. It answers with a constant and changes nothing.
HOST_CHECK_EXEMPT_PATHS = frozenset({"/api/health"})


def build_engine_options(database_uri: str) -> dict[str, Any]:
    """SQLAlchemy engine options for a given database URI.

    For server databases (Postgres) we enable ``pool_pre_ping`` so a connection
    the server dropped while idle is transparently replaced instead of surfacing
    as an intermittent 500 until the pool recycles. SQLite (tests) uses its own
    pooling and needs neither option.
    """
    if database_uri.startswith("sqlite"):
        return {}
    return {"pool_pre_ping": True, "pool_recycle": POOL_RECYCLE_SECONDS}


def create_app(config_class: type | None = None) -> APIFlask:
    """Create and configure the Flask application."""
    global engine, Session

    app = APIFlask(
        __name__,
        title="Vipu API",
        version="0.1.0",
        docs_ui="redoc",
    )
    app.config["DESCRIPTION"] = (
        "Personal finance tracker API.\n\n"
        "Requests that change data (POST, PUT, PATCH, DELETE) must send any body "
        "as `application/json` (415 otherwise). A browser may send them only "
        "from the same origin or an origin listed in `CORS_ORIGINS` (403 "
        "otherwise)."
    )
    app.config["SERVERS"] = [
        {"name": "Local", "url": "http://localhost:5000"},
    ]

    if config_class is None:
        config_class = get_config()

    app.config.from_object(config_class)

    # Parse CORS origins from config (comma-separated string). A wildcard would
    # let any web page pass a CORS preflight, so it is dropped.
    cors_config = app.config.get("CORS_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_config.split(",") if o.strip()]
    if "*" in cors_origins:
        logger.warning("Ignoring '*' in CORS_ORIGINS; list explicit origins instead")
        cors_origins = [o for o in cors_origins if o != "*"]
    cors_origins = cors_origins or ["http://localhost:3000"]
    CORS(app, origins=cors_origins)

    app.config.setdefault(
        "VIPU_ALLOWED_HOSTS", os.environ.get("VIPU_ALLOWED_HOSTS", "")
    )
    register_request_guards(app, cors_origins)

    database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    engine = create_engine(database_uri, **build_engine_options(database_uri))
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)

    # Use checkfirst=True to avoid race conditions with multiple workers
    Base.metadata.create_all(engine, checkfirst=True)

    # Run database migrations
    from app.migrations import run_migrations

    with Session() as session:
        run_migrations(session)

    # Gunicorn's --preload forks workers after this point. Close the pooled
    # connection startup used so workers never share one Postgres socket.
    # In-memory SQLite (tests) would lose its database, so it keeps its pool.
    if not database_uri.startswith("sqlite"):
        engine.dispose()

    from app.routes import (
        accounts,
        budget,
        budget_snapshots,
        expenses,
        forecasting,
        goals,
        health,
        income,
        networth,
        seed,
        settings,
        summary,
    )

    app.register_blueprint(health.bp)
    app.register_blueprint(budget.bp)
    app.register_blueprint(budget_snapshots.bp)
    app.register_blueprint(accounts.bp)
    app.register_blueprint(income.bp)
    app.register_blueprint(expenses.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(seed.bp)
    app.register_blueprint(networth.bp)
    app.register_blueprint(goals.bp)
    app.register_blueprint(forecasting.bp)
    app.register_blueprint(summary.bp)

    @app.teardown_appcontext
    def shutdown_session(exception: BaseException | None = None) -> None:
        if Session:
            Session.remove()

    return app


def _hostname(netloc: str) -> str | None:
    """Lowercased hostname of ``host[:port]``, or None when it does not parse."""
    try:
        return urlsplit(f"//{netloc.strip()}").hostname
    except ValueError:
        return None


def _forwarded_hosts() -> list[str]:
    """Every value of X-Forwarded-Host, which the Next.js proxy sets."""
    header = request.headers.get("X-Forwarded-Host", "")
    return [h.strip() for h in header.split(",") if h.strip()]


def _error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": message}), status


def _is_cross_site(trusted_origins: set[str]) -> bool:
    """Whether a browser sent this request from another site.

    The API has no login of its own, so a page on any site could otherwise
    make a visitor's browser change data on a localhost or LAN instance.
    Browsers send Sec-Fetch-Site on every request, and it reaches us unchanged
    through the Next.js and Traefik proxies, unlike Host. Browsers too old to
    send it still send Origin on unsafe requests, so compare its hostname with
    the one the browser addressed; ports are ignored because a proxy may change
    them. Clients that are not browsers (the MCP server, scripts, the e2e
    seeding) send neither header and are not affected.
    """
    origin = request.headers.get("Origin")
    if origin and origin.lower() in trusted_origins:
        return False

    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site is not None:
        return fetch_site.lower() not in TRUSTED_FETCH_SITES

    if origin is None:
        return False
    try:
        origin_host = urlsplit(origin).hostname
    except ValueError:
        origin_host = None
    if origin_host is None:  # includes "Origin: null"
        return True
    addressed = [request.host, *_forwarded_hosts()]
    return origin_host not in {_hostname(h) for h in addressed}


def _host_allowed(allowed_hosts: set[str]) -> bool:
    """Whether Host and every X-Forwarded-Host name an allowed hostname."""
    names = [request.host, *_forwarded_hosts()]
    return all(_hostname(name) in allowed_hosts for name in names)


def register_request_guards(app: Flask, cors_origins: list[str]) -> None:
    """Refuse cross-site writes and unexpected hosts; add security headers."""
    trusted_origins = {o.lower() for o in cors_origins}
    allowed_hosts = {
        h.strip().lower()
        for h in app.config.get("VIPU_ALLOWED_HOSTS", "").split(",")
        if h.strip()
    }

    @app.before_request
    def guard_request() -> tuple[Response, int] | None:
        # Opt-in DNS rebinding protection: off unless VIPU_ALLOWED_HOSTS is set.
        if (
            allowed_hosts
            and request.path not in HOST_CHECK_EXEMPT_PATHS
            and not _host_allowed(allowed_hosts)
        ):
            return _error("Host not allowed", 400)

        if request.method not in UNSAFE_METHODS:
            return None
        if not request.path.startswith("/api/"):
            return None

        if _is_cross_site(trusted_origins):
            return _error("Cross-site requests may not change data", 403)

        # Every endpoint reads JSON. Requiring it for any body means a browser
        # can only send one cross-origin after a CORS preflight, which only
        # origins in CORS_ORIGINS pass.
        chunked = "chunked" in request.headers.get("Transfer-Encoding", "").lower()
        has_body = bool(request.content_length) or chunked
        if (has_body or request.content_type) and not request.is_json:
            return _error("Content-Type must be application/json", 415)
        return None

    @app.after_request
    def set_security_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        return response


def get_session() -> SQLAlchemySession:
    """Get the current database session."""
    if Session is None:
        raise RuntimeError("Database session not initialized. Call create_app first.")
    return Session()
