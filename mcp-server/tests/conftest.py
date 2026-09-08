"""Shared fixtures.

Tools run against the real Flask app over httpx.WSGITransport rather than
against mocked JSON. Flask is WSGI, so this works directly, and it means each
test exercises actual pay-period and occurrence semantics instead of a
fixture's idea of them. httpx.MockTransport is kept for the error paths a real
backend will not produce on demand: timeouts, 5xx, malformed bodies.
"""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from app import create_app
from app.config import TestingConfig

from vipu_mcp.client import VipuClient
from vipu_mcp.server import build_server


@pytest.fixture
def backend(tmp_path: Path) -> Iterator[httpx.BaseTransport]:
    """A transport speaking to a fresh Vipu backend on a throwaway database.

    A file rather than TestingConfig's sqlite:///:memory:. MCPServer runs sync
    tool functions in a worker thread, and an in-memory SQLite database belongs
    to the connection that opened it, so the tool would find an empty schema
    while the fixture that seeded it saw a full one.
    """

    class Config(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'vipu.db'}"

    yield httpx.WSGITransport(app=create_app(Config))


@pytest.fixture
def client(backend: httpx.BaseTransport) -> Iterator[VipuClient]:
    """A VipuClient wired to that backend."""
    vipu = VipuClient(base_url="http://backend", transport=backend)
    yield vipu
    vipu.close()


@pytest.fixture
def seeded(backend: httpx.BaseTransport, client: VipuClient) -> VipuClient:
    """The same client, against a backend carrying the demo data.

    Seeding goes through a raw httpx client rather than VipuClient, because the
    seed endpoints are deliberately not wrapped: nothing reachable over MCP is
    allowed to overwrite real data with demo data.
    """
    with httpx.Client(base_url="http://backend", transport=backend) as raw:
        for path in (
            "/api/seed",
            "/api/networth/categories/seed",
            "/api/networth/seed",
        ):
            assert raw.post(path).status_code < 400, path
    return client


@pytest.fixture
def server(client: VipuClient):
    """The MCP server, wired to that client."""
    return build_server(client)


@pytest.fixture
def seeded_server(seeded: VipuClient):
    """The MCP server, against a backend carrying the demo data."""
    return build_server(seeded)


@pytest.fixture
def anyio_backend() -> str:
    """anyio's parametrized backend fixture, pinned to asyncio."""
    return "asyncio"
