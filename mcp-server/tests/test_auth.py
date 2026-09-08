"""The bearer-token gate in front of the MCP mount."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
import httpx
import pytest

from vipu_mcp.server import build_app, build_server

TOKEN = "s3cret-token"


@asynccontextmanager
async def running(app) -> AsyncIterator[httpx.AsyncClient]:
    """Drive the ASGI lifespan, then hand back a client speaking to the app.

    The streamable HTTP transport starts its session manager in lifespan
    startup, so a bare ASGITransport would reach a half-built app.
    """
    send: anyio.abc.ObjectSendStream
    receive: anyio.abc.ObjectReceiveStream
    send, receive = anyio.create_memory_object_stream(4)
    events: list[dict] = []

    async def receive_event():
        return await receive.receive()

    async def send_event(message):
        events.append(message)

    async with anyio.create_task_group() as tg:
        tg.start_soon(lambda: app({"type": "lifespan"}, receive_event, send_event))
        await send.send({"type": "lifespan.startup"})
        while not events:
            await anyio.sleep(0)
        assert events[0]["type"] == "lifespan.startup.complete", events
        try:
            async with httpx.AsyncClient(
                base_url="http://mcp", transport=httpx.ASGITransport(app=app)
            ) as http:
                yield http
        finally:
            await send.send({"type": "lifespan.shutdown"})
            await send.aclose()


@pytest.fixture
def app(client):
    return build_app(build_server(client), TOKEN)


async def initialize(http: httpx.AsyncClient, headers: dict[str, str] | None = None):
    """A minimal MCP initialize request, which is what a client sends first."""
    return await http.post(
        "/mcp",
        headers={"Accept": "application/json, text/event-stream", **(headers or {})},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
    )


@pytest.mark.anyio
async def test_health_needs_no_token(app):
    """The compose healthcheck has no token to present."""
    async with running(app) as http:
        response = await http.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_mcp_without_a_token_is_401(app):
    async with running(app) as http:
        response = await initialize(http)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.anyio
async def test_mcp_with_the_wrong_token_is_401(app):
    async with running(app) as http:
        response = await initialize(http, {"Authorization": f"Bearer not-{TOKEN}"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_a_token_prefix_is_not_enough(app):
    """compare_digest, not startswith."""
    async with running(app) as http:
        response = await initialize(http, {"Authorization": f"Bearer {TOKEN[:4]}"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_the_wrong_scheme_is_401(app):
    async with running(app) as http:
        response = await initialize(http, {"Authorization": f"Basic {TOKEN}"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_mcp_with_the_token_gets_through(app):
    async with running(app) as http:
        response = await initialize(http, {"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["result"]["serverInfo"]["name"] == "vipu"
