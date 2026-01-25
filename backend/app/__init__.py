from typing import Any

from apiflask import APIFlask
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config import get_config
from app.models import Base

engine: Any = None
Session: scoped_session[SQLAlchemySession] | None = None


def create_app(config_class: type | None = None) -> APIFlask:
    """Create and configure the Flask application."""
    global engine, Session

    app = APIFlask(
        __name__,
        title="Vipu API",
        version="0.1.0",
        docs_ui="redoc",
    )
    app.config["DESCRIPTION"] = "Personal finance tracker API"
    app.config["SERVERS"] = [
        {"name": "Local", "url": "http://localhost:5000"},
    ]

    if config_class is None:
        config_class = get_config()

    app.config.from_object(config_class)

    # Parse CORS origins from config (comma-separated string)
    cors_config = app.config.get("CORS_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_config.split(",") if o.strip()]
    CORS(app, origins=cors_origins or ["http://localhost:3000"])

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)

    # Use checkfirst=True to avoid race conditions with multiple workers
    Base.metadata.create_all(engine, checkfirst=True)

    from app.routes import (
        accounts,
        budget,
        expenses,
        goals,
        health,
        income,
        networth,
        seed,
        settings,
    )

    app.register_blueprint(health.bp)
    app.register_blueprint(budget.bp)
    app.register_blueprint(accounts.bp)
    app.register_blueprint(income.bp)
    app.register_blueprint(expenses.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(seed.bp)
    app.register_blueprint(networth.bp)
    app.register_blueprint(goals.bp)

    @app.teardown_appcontext
    def shutdown_session(exception: BaseException | None = None) -> None:
        if Session:
            Session.remove()

    return app


def get_session() -> SQLAlchemySession:
    """Get the current database session."""
    if Session is None:
        raise RuntimeError("Database session not initialized. Call create_app first.")
    return Session()
