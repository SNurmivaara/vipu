import pytest

from app import create_app
from app.config import TestingConfig


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app(TestingConfig)
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def seeded_client(client):
    """Create test client with seeded data."""
    client.post("/api/seed")
    return client
