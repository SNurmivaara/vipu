"""Startup posture: no token, no server."""

import importlib

import pytest

from vipu_mcp import config


def reloaded(monkeypatch, **env):
    """Re-import config with a patched environment, since it reads once."""
    for key in (
        "MCP_AUTH_TOKEN",
        "FLASK_ENV",
        "VIPU_MCP_READ_ONLY",
        "VIPU_API_URL",
        *config.OAUTH_ENV,
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def restore_config():
    """Leave the module as the rest of the suite expects to find it."""
    yield
    importlib.reload(config)


def test_missing_token_fails_in_production(monkeypatch):
    """Same posture backend/app/config.py takes with SECRET_KEY."""
    module = reloaded(monkeypatch, FLASK_ENV="production")
    with pytest.raises(ValueError, match="must be set in production"):
        module.require_auth_token()


def test_missing_token_also_fails_in_development(monkeypatch):
    """A server that listens without auth is never the helpful default."""
    module = reloaded(monkeypatch)
    with pytest.raises(ValueError, match="would accept any caller"):
        module.require_auth_token()


def test_token_is_returned_when_set(monkeypatch):
    module = reloaded(monkeypatch, MCP_AUTH_TOKEN="abc123")
    assert module.require_auth_token() == "abc123"


STRONG = "0123456789abcdef" * 4


@pytest.mark.parametrize("env", ["production", "development"])
@pytest.mark.parametrize(
    "token", ["your-mcp-token-here", " Your-MCP-Token-Here ", "<token>"]
)
def test_example_placeholder_token_is_refused(monkeypatch, env, token):
    module = reloaded(monkeypatch, FLASK_ENV=env, MCP_AUTH_TOKEN=token)
    with pytest.raises(ValueError, match="placeholder"):
        module.require_auth_token()


@pytest.mark.parametrize("token", ["dev-mcp-token-not-for-production", "dev-token"])
def test_development_token_is_refused_in_production(monkeypatch, token):
    module = reloaded(monkeypatch, FLASK_ENV="production", MCP_AUTH_TOKEN=token)
    with pytest.raises(ValueError, match="development token"):
        module.require_auth_token()


def test_dev_compose_token_still_works_in_development(monkeypatch, caplog):
    token = "dev-mcp-token-not-for-production"
    module = reloaded(monkeypatch, FLASK_ENV="development", MCP_AUTH_TOKEN=token)
    with caplog.at_level("WARNING", logger="vipu_mcp.config"):
        assert module.require_auth_token() == token
    assert caplog.text == ""


def test_short_token_starts_with_a_warning(monkeypatch, caplog):
    """Existing deployments must keep starting."""
    module = reloaded(monkeypatch, FLASK_ENV="production", MCP_AUTH_TOKEN="abc123")
    with caplog.at_level("WARNING", logger="vipu_mcp.config"):
        assert module.require_auth_token() == "abc123"
    assert "shorter than 32 characters" in caplog.text


def test_strong_token_starts_without_a_warning(monkeypatch, caplog):
    module = reloaded(monkeypatch, FLASK_ENV="production", MCP_AUTH_TOKEN=STRONG)
    with caplog.at_level("WARNING", logger="vipu_mcp.config"):
        assert module.require_auth_token() == STRONG
    assert caplog.text == ""


OAUTH = {
    "MCP_OAUTH_ISSUER": "https://auth.example.com",
    "MCP_OAUTH_RESOURCE_URL": "https://mcp.example.com/mcp",
    "MCP_OAUTH_JWKS_URL": "https://auth.example.com/jwks.json",
    "MCP_OAUTH_ALLOWED_CLIENTS": "claude",
    "MCP_OAUTH_ALLOWED_USERS": "owner",
}


def test_placeholder_legacy_token_is_refused_alongside_oauth(monkeypatch):
    """The legacy token still authenticates under OAuth, so the same rule holds."""
    module = reloaded(monkeypatch, MCP_AUTH_TOKEN="your-mcp-token-here", **OAUTH)
    with pytest.raises(ValueError, match="placeholder"):
        module.oauth_config()


def test_oauth_with_a_strong_legacy_token_is_accepted(monkeypatch):
    module = reloaded(monkeypatch, MCP_AUTH_TOKEN=STRONG, **OAUTH)
    assert module.oauth_config() is not None


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
def test_read_only_flag_is_forgiving(monkeypatch, value):
    assert reloaded(monkeypatch, VIPU_MCP_READ_ONLY=value).VIPU_MCP_READ_ONLY is True


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_read_only_flag_defaults_off(monkeypatch, value):
    assert reloaded(monkeypatch, VIPU_MCP_READ_ONLY=value).VIPU_MCP_READ_ONLY is False


def test_api_url_loses_its_trailing_slash(monkeypatch):
    """Otherwise every request path would carry a double slash."""
    module = reloaded(monkeypatch, VIPU_API_URL="http://backend:5000/")
    assert module.VIPU_API_URL == "http://backend:5000"


def test_oauth_is_opt_in(monkeypatch):
    assert reloaded(monkeypatch).oauth_config() is None


@pytest.mark.parametrize("key", config.OAUTH_ENV)
def test_partial_oauth_never_falls_back_to_legacy_auth(monkeypatch, key):
    module = reloaded(monkeypatch, MCP_AUTH_TOKEN="legacy", **{key: "configured"})
    with pytest.raises(ValueError, match="Incomplete OAuth"):
        module.oauth_config()


def test_complete_oauth_does_not_need_a_static_token(monkeypatch):
    module = reloaded(
        monkeypatch,
        MCP_OAUTH_ISSUER="https://auth.example.com",
        MCP_OAUTH_RESOURCE_URL="https://mcp.example.com/mcp",
        MCP_OAUTH_JWKS_URL="https://auth.example.com/jwks.json",
        MCP_OAUTH_ALLOWED_CLIENTS="chatgpt, claude, ",
        MCP_OAUTH_ALLOWED_USERS="owner",
    )
    oauth = module.oauth_config()
    assert oauth is not None
    assert oauth.allowed_clients == frozenset({"chatgpt", "claude"})
    assert oauth.allowed_users == frozenset({"owner"})
    assert module.MCP_AUTH_TOKEN == ""
    monkeypatch.setenv("MCP_OAUTH_ALLOWED_USERS", " , ")
    with pytest.raises(ValueError, match="allowlists"):
        module.oauth_config()
