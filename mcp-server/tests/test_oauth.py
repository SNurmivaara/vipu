"""Real signed access tokens across the HTTP authentication boundary."""

import time
from dataclasses import replace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from tests.test_auth import initialize, running
from vipu_mcp import config
from vipu_mcp import server as server_module
from vipu_mcp.config import OAuthConfig
from vipu_mcp.oauth import KEY_CACHE_SECONDS, KEY_REFRESH_SECONDS, OAuthTokenVerifier
from vipu_mcp.server import build_app, build_server

ISSUER = "https://auth.example.com"
RESOURCE = "https://vipu-mcp.example.com/mcp"
JWKS_URL = f"{ISSUER}/jwks.json"
SETTINGS = OAuthConfig(
    issuer=ISSUER,
    resource_url=RESOURCE,
    jwks_url=JWKS_URL,
    allowed_clients=frozenset({"vipu-chatgpt", "vipu-claude"}),
    allowed_users=frozenset({"owner"}),
)


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwks(signing_key):
    return {
        "keys": [
            {
                **jwt.algorithms.RSAAlgorithm.to_jwk(
                    signing_key.public_key(), as_dict=True
                ),
                "kid": "key-1",
                "alg": "RS256",
                "use": "sig",
            }
        ]
    }


@pytest.fixture
def mint(signing_key):
    def token(*, headers=None, remove=(), **overrides):
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": [RESOURCE],
            "exp": now + 600,
            "iat": now,
            "sub": "user-uuid",
            "jti": "token-uuid",
            "client_id": "vipu-chatgpt",
            "preferred_username": "owner",
            "scope": "openid vipu offline_access",
            **overrides,
        }
        for name in remove:
            claims.pop(name)
        return jwt.encode(
            claims,
            signing_key,
            algorithm="RS256",
            headers={"kid": "key-1", "typ": "at+jwt", **(headers or {})},
        )

    return token


@pytest.fixture
def verifier(jwks):
    def respond(request):
        assert str(request.url) == JWKS_URL
        assert "authorization" not in request.headers
        return httpx.Response(200, json=jwks)

    return OAuthTokenVerifier(SETTINGS, transport=httpx.MockTransport(respond))


@pytest.fixture
def oauth_app(client, verifier):
    return build_app(build_server(client, oauth=SETTINGS, token_verifier=verifier))


@pytest.mark.anyio
async def test_discovery_is_public_and_challenge_points_to_it(oauth_app):
    async with running(oauth_app) as http:
        response = await initialize(http)
        assert response.status_code == 401
        assert (
            'resource_metadata="https://vipu-mcp.example.com/'
            '.well-known/oauth-protected-resource/mcp"'
        ) in response.headers["www-authenticate"]
        metadata = await http.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json()["resource"] == RESOURCE
        assert metadata.json()["authorization_servers"] == [ISSUER]
        assert metadata.json()["scopes_supported"] == ["openid", "vipu"]
        assert metadata.json()["bearer_methods_supported"] == ["header"]
        assert (await http.get("/health")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("client_id", ["vipu-chatgpt", "vipu-claude"])
@pytest.mark.parametrize("scope_format", ["scope", "scp"])
async def test_both_clients_can_initialize_and_list_tools(
    oauth_app, mint, client_id, scope_format
):
    extra = (
        {"remove": ("scope",), "scp": ["openid", "vipu", "offline_access"]}
        if scope_format == "scp"
        else {}
    )
    headers = {"Authorization": f"Bearer {mint(client_id=client_id, **extra)}"}
    async with running(oauth_app) as http:
        response = await initialize(http, headers)
        assert response.status_code == 200
        assert response.json()["result"]["serverInfo"]["name"] == "vipu"
        response = await http.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream", **headers},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        assert response.status_code == 200
        assert len(response.json()["result"]["tools"]) == 25


@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://other.example.com"},
        {"iss": ISSUER + "/"},
        {"aud": "other-service"},
        {"aud": "vipu-chatgpt"},
        {"aud": RESOURCE + "/"},
        {"exp": 1},
        {"exp": str(int(time.time()) + 600)},
        {"iat": int(time.time()) + 600},
        {"nbf": int(time.time()) + 600},
        {"client_id": "unregistered"},
        {"client_id": ["vipu-chatgpt"]},
        {"preferred_username": "other-user"},
        {"preferred_username": ["owner"]},
        {"preferred_username": None},
        {"sub": ""},
        {"scope": ["openid", "vipu"]},
        {"remove": ("scope",), "scp": "openid vipu"},
        {"remove": ("scope",), "scp": ["openid vipu"]},
        {"remove": ("scope",), "scp": ["openid", 123]},
        {"remove": ("scope",), "scp": ["openid", ""]},
        {"scope": "openid", "scp": ["openid", "vipu"]},
        {"scope": None, "scp": ["openid", "vipu"]},
        {"remove": ("scope",)},
        {"headers": {"typ": "JWT"}},
        {"headers": {"kid": "not-a-signing-key"}},
        {"remove": ("exp",)},
        {"remove": ("iat",)},
        {"remove": ("jti",)},
        {"remove": ("sub",)},
        {"remove": ("client_id",)},
    ],
)
async def test_invalid_tokens_cannot_initialize(oauth_app, mint, overrides):
    async with running(oauth_app) as http:
        response = await initialize(
            http, {"Authorization": f"Bearer {mint(**overrides)}"}
        )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_scope_is_enforced_on_every_mcp_method(oauth_app, mint):
    async with running(oauth_app) as http:
        response = await initialize(
            http, {"Authorization": f"Bearer {mint(scope='openid profile')}"}
        )
        assert response.status_code == 403
        assert response.json()["error"] == "insufficient_scope"
        for method in ("tools/list", "resources/list", "prompts/list", "tools/call"):
            response = await http.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": method},
            )
            assert response.status_code == 401


@pytest.mark.anyio
async def test_matching_scope_claims_and_missing_authelia_scope(oauth_app, mint):
    async with running(oauth_app) as http:
        for claims, status in [
            ({"scp": ["openid", "vipu", "offline_access"]}, 200),
            ({"remove": ("scope",), "scp": ["openid"]}, 403),
            ({"remove": ("scope",), "scp": []}, 403),
        ]:
            response = await initialize(
                http, {"Authorization": f"Bearer {mint(**claims)}"}
            )
            assert response.status_code == status


@pytest.mark.anyio
async def test_forged_and_symmetric_tokens_are_rejected(verifier, mint):
    valid = mint()
    claims = jwt.decode(valid, options={"verify_signature": False})
    forged = jwt.encode(
        claims,
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        algorithm="RS256",
        headers={"kid": "key-1", "typ": "at+jwt"},
    )
    symmetric = jwt.encode(
        claims,
        "a-secret-an-attacker-controls-long-enough",
        algorithm="HS256",
        headers={"kid": "key-1", "typ": "at+jwt"},
    )
    for token in (forged, symmetric, "not-a-jwt", "x" * 17000):
        assert await verifier.verify_token(token) is None


@pytest.mark.anyio
async def test_legacy_transition_is_explicit(client, verifier, mint):
    verifier.legacy_token = "existing-secret"
    app = build_app(build_server(client, oauth=SETTINGS, token_verifier=verifier))
    async with running(app) as http:
        for token in ("existing-secret", mint()):
            assert (
                await initialize(http, {"Authorization": f"Bearer {token}"})
            ).status_code == 200
        for token in ("existing", "wrong-secret"):
            assert (
                await initialize(http, {"Authorization": f"Bearer {token}"})
            ).status_code == 401
        verifier.legacy_token = ""
        assert (
            await initialize(http, {"Authorization": "Bearer existing-secret"})
        ).status_code == 401


@pytest.mark.anyio
async def test_jwks_rotation_and_unknown_kids_are_rate_limited(jwks, mint):
    calls = []
    now = [1000.0]

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=jwks)

    verifier = OAuthTokenVerifier(
        SETTINGS, transport=httpx.MockTransport(respond), clock=lambda: now[0]
    )
    assert await verifier.verify_token(mint()) is not None
    for _ in range(3):
        assert await verifier.verify_token(mint()) is not None
        assert await verifier.verify_token(mint(headers={"kid": "key-2"})) is None
    assert len(calls) == 1
    jwks["keys"][0]["kid"] = "key-2"
    now[0] += KEY_REFRESH_SECONDS
    assert await verifier.verify_token(mint(headers={"kid": "key-2"})) is not None
    assert len(calls) == 2
    assert await verifier.verify_token(mint()) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure", ["offline", "redirect", "invalid-json", "empty", "list"]
)
async def test_jwks_failure_expires_cache_and_recovers(jwks, mint, failure):
    now = [1000.0]
    healthy = [True]
    calls = []

    def respond(request):
        calls.append(request)
        if healthy[0]:
            return httpx.Response(200, json=jwks)
        if failure == "offline":
            raise httpx.ConnectError("provider unavailable", request=request)
        if failure == "redirect":
            return httpx.Response(
                302, headers={"location": "https://other.example.com"}
            )
        if failure == "invalid-json":
            return httpx.Response(200, text="not-json")
        return httpx.Response(200, json={"keys": []} if failure == "empty" else [])

    verifier = OAuthTokenVerifier(
        SETTINGS, transport=httpx.MockTransport(respond), clock=lambda: now[0]
    )
    assert await verifier.verify_token(mint()) is not None
    healthy[0] = False
    assert await verifier.verify_token(mint()) is not None
    now[0] += KEY_CACHE_SECONDS
    for _ in range(3):
        assert await verifier.verify_token(mint()) is None
    assert len(calls) == 2
    healthy[0] = True
    now[0] += KEY_REFRESH_SECONDS
    assert await verifier.verify_token(mint()) is not None


@pytest.mark.anyio
async def test_token_key_urls_are_ignored(verifier, mint):
    assert (
        await verifier.verify_token(
            mint(headers={"jku": "https://attacker.example.com/jwks"})
        )
        is not None
    )


def test_app_cannot_accidentally_start_without_auth(client):
    with pytest.raises(ValueError, match="Configure OAuth"):
        build_app(build_server(client))


@pytest.mark.anyio
async def test_production_factory_enables_oauth_without_legacy_token(
    client, monkeypatch, verifier, mint
):
    monkeypatch.setattr(config, "oauth_config", lambda: SETTINGS)
    monkeypatch.setattr(config, "MCP_AUTH_TOKEN", "")
    monkeypatch.setattr(server_module, "VipuClient", lambda: client)
    monkeypatch.setattr(server_module, "OAuthTokenVerifier", lambda *a, **kw: verifier)
    async with running(server_module.create_app()) as http:
        assert (await initialize(http)).status_code == 401
        assert (
            await initialize(http, {"Authorization": f"Bearer {mint()}"})
        ).status_code == 200


@pytest.mark.anyio
async def test_production_factory_preserves_legacy_config(client, monkeypatch):
    monkeypatch.setattr(config, "oauth_config", lambda: None)
    monkeypatch.setattr(config, "MCP_AUTH_TOKEN", "existing-secret")
    monkeypatch.setattr(server_module, "VipuClient", lambda: client)
    async with running(server_module.create_app()) as http:
        assert (await initialize(http)).status_code == 401
        assert (
            await initialize(http, {"Authorization": "Bearer existing-secret"})
        ).status_code == 200


@pytest.mark.parametrize("field", ["issuer", "resource_url", "jwks_url"])
@pytest.mark.parametrize(
    "url", ["http://example.com/mcp", "https://user:pass@example.com/mcp", "not-a-url"]
)
def test_oauth_trust_urls_must_be_https(field, url):
    with pytest.raises(ValueError, match="HTTPS"):
        replace(SETTINGS, **{field: url})


@pytest.mark.parametrize("path", ["/", "/mcp/", "/other", "/mcp?token=secret"])
def test_resource_url_must_match_the_actual_mcp_mount(path):
    with pytest.raises(ValueError):
        replace(SETTINGS, resource_url=f"https://mcp.example.com{path}")
