"""Startup posture: no token, no server."""

import importlib

import pytest

from vipu_mcp import config


def reloaded(monkeypatch, **env):
    """Re-import config with a patched environment, since it reads once."""
    for key in ("MCP_AUTH_TOKEN", "FLASK_ENV", "VIPU_MCP_READ_ONLY", "VIPU_API_URL"):
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
