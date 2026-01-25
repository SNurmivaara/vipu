from typing import Any

from flask import Flask
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config import get_config
from app.models import Base

engine: Any = None
Session: scoped_session[SQLAlchemySession] | None = None


def create_app(config_class: type | None = None) -> Flask:
    """Create and configure the Flask application."""
    global engine, Session

    app = Flask(__name__)

    if config_class is None:
        config_class = get_config()

    app.config.from_object(config_class)

    CORS(app, origins=["http://localhost:3000"])

    engine = create_engine(app.config["SQLALCHEMY_DATABASE_URI"])
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)

    # Use checkfirst=True to avoid race conditions with multiple workers
    Base.metadata.create_all(engine, checkfirst=True)

    from app.routes import accounts, budget, expenses, health, income, seed, settings

    app.register_blueprint(health.bp)
    app.register_blueprint(budget.bp)
    app.register_blueprint(accounts.bp)
    app.register_blueprint(income.bp)
    app.register_blueprint(expenses.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(seed.bp)

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
