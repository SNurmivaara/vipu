"""Verify RFC 9068 access tokens from an external OAuth provider.

Authelia owns login, consent, PKCE, token issuance and refresh. Vipu accepts
only signed access tokens for this resource, an allowed client and an allowed
user. An ID token or a token for another homelab service is never sufficient.
"""

import hmac
import logging
import time
from collections.abc import Callable
from typing import Any

import anyio
import httpx
import jwt
from mcp.server.auth.provider import AccessToken

from vipu_mcp.config import OAuthConfig

logger = logging.getLogger(__name__)
REQUIRED_SCOPES = ["openid", "vipu"]
KEY_CACHE_SECONDS = 300
KEY_REFRESH_SECONDS = 30


def token_scopes(claims: dict[str, Any]) -> list[str] | None:
    """Accept RFC 9068's scope string or Authelia's scp array, never their union."""
    scopes: list[str] | None = None
    if "scope" in claims:
        scope = claims["scope"]
        if not isinstance(scope, str):
            return None
        scopes = scope.split()
        if "scp" not in claims:
            return scopes
    scp = claims.get("scp")
    if not isinstance(scp, list):
        return None
    items: list[str] = []
    for item in scp:
        if not isinstance(item, str) or not item or any(c.isspace() for c in item):
            return None
        items.append(item)
    if scopes is not None and set(scopes) != set(items):
        return None
    return items


class OAuthTokenVerifier:
    """A bounded JWKS cache and a fail-closed JWT verifier for the MCP SDK."""

    def __init__(
        self,
        settings: OAuthConfig,
        legacy_token: str = "",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings
        self.legacy_token = legacy_token
        self._transport = transport
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._expires_at = 0.0
        self._refresh_after = 0.0
        self._lock = anyio.Lock()

    async def _signing_key(self, kid: str) -> jwt.PyJWK | None:
        async with self._lock:
            now = self._clock()
            key = self._keys.get(kid)
            if key is not None and now < self._expires_at:
                return key
            if now < self._refresh_after:
                return None

            # Unknown kids and provider failures cannot force an HTTP request
            # on every unauthenticated call. Refreshes are serialized as well.
            self._refresh_after = now + KEY_REFRESH_SECONDS
            try:
                async with httpx.AsyncClient(
                    timeout=5.0, follow_redirects=False, transport=self._transport
                ) as http:
                    response = await http.get(self.settings.jwks_url)
                    response.raise_for_status()
                    document = response.json()
                    if not isinstance(document, dict):
                        raise ValueError("Invalid JWKS document")
                    jwks = jwt.PyJWKSet.from_dict(document)
                keys = {
                    key.key_id: key
                    for key in jwks.keys
                    if isinstance(key.key_id, str)
                    and key.algorithm_name == "RS256"
                    and key.public_key_use in (None, "sig")
                    and key.key_type == "RSA"
                }
                if not keys:
                    raise ValueError("No RS256 signing keys")
            except (httpx.HTTPError, jwt.PyJWTError, ValueError, TypeError):
                # Do not include exceptions, URLs, tokens or claims in logs.
                logger.warning("OAuth signing keys could not be refreshed")
                return None
            self._keys = keys
            self._expires_at = self._clock() + KEY_CACHE_SECONDS
            return keys.get(kid)

    async def verify_token(self, token: str) -> AccessToken | None:
        # Opt-in migration support. OAuth-only deployments leave this unset.
        if self.legacy_token and hmac.compare_digest(
            token.encode("utf-8"), self.legacy_token.encode("utf-8")
        ):
            return AccessToken(
                token=token,
                client_id="vipu-legacy-token",
                scopes=REQUIRED_SCOPES.copy(),
                resource=self.settings.resource_url,
            )

        if len(token) > 16384:
            return None
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or header.get("typ") not in (
                "at+jwt",
                "application/at+jwt",
            ):
                return None
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid or len(kid) > 128:
                return None
            key = await self._signing_key(kid)
            if key is None:
                return None
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.resource_url,
                options={
                    "require": ["iss", "aud", "exp", "iat", "sub", "client_id", "jti"],
                },
            )
            client_id = claims["client_id"]
            username = claims.get("preferred_username")
            scopes = token_scopes(claims)
            if (
                not isinstance(client_id, str)
                or client_id not in self.settings.allowed_clients
                or not isinstance(username, str)
                or username not in self.settings.allowed_users
                or scopes is None
                or not isinstance(claims["sub"], str)
                or not claims["sub"]
                or type(claims["exp"]) is not int
                or type(claims["iat"]) is not int
            ):
                return None
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=claims["exp"],
                resource=self.settings.resource_url,
                subject=claims["sub"],
                claims=claims,
            )
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return None
