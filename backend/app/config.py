import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000")

    @staticmethod
    def get_database_url() -> str:
        """Get database URL from environment."""
        return os.environ.get(
            "DATABASE_URL", "postgresql://vipu:vipu@localhost:5432/vipu"
        )


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = Config.get_database_url()


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def _require_env(name: str) -> str:
    """Get required environment variable or raise error."""
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} environment variable must be set in production")
    return value


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False
    _is_prod = os.environ.get("FLASK_ENV") == "production"
    SECRET_KEY = _require_env("SECRET_KEY") if _is_prod else Config.SECRET_KEY
    SQLALCHEMY_DATABASE_URI = (
        _require_env("DATABASE_URL") if _is_prod else Config.get_database_url()
    )


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config() -> type[Config]:
    """Get configuration based on FLASK_ENV environment variable."""
    env = os.environ.get("FLASK_ENV", "development")
    return config.get(env, DevelopmentConfig)
