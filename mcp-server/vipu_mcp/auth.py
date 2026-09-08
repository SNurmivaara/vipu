"""Bearer-token gate in front of the MCP mount.

A deliberate simplification over the MCP spec's OAuth flow, sized to a
single-user homelab behind a Cloudflare tunnel: one static token, compared in
constant time. Recorded here as a decision rather than an oversight. If Vipu
ever grows a second user, this is the piece to replace.

Pure ASGI rather than Starlette middleware so it sits outside the session
manager and rejects before any MCP machinery runs.
"""

import hmac
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]

# The compose healthcheck has no token to present, and leaks nothing.
OPEN_PATHS = frozenset({"/health"})


class BearerTokenMiddleware:
    """Reject anything without the configured Authorization: Bearer <token>."""

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in OPEN_PATHS:
            await self.app(scope, receive, send)
            return

        if self._is_authorized(scope):
            await self.app(scope, receive, send)
            return

        await self._unauthorized(send)

    def _is_authorized(self, scope: Scope) -> bool:
        for name, value in scope.get("headers", []):
            if name.lower() != b"authorization":
                continue
            scheme, _, presented = value.decode("latin-1").partition(" ")
            if scheme.lower() != "bearer":
                return False
            return hmac.compare_digest(presented.strip(), self.token)
        return False

    @staticmethod
    async def _unauthorized(send: Send) -> None:
        body = b'{"error": "Missing or invalid bearer token"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    # Named realm, so mcp-remote and the inspector report the
                    # failure as an auth problem rather than a broken endpoint.
                    (b"www-authenticate", b'Bearer realm="vipu"'),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
