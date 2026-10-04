"""Cross-site write protection, the Host allowlist and security headers."""

import pytest

from app import create_app
from app.config import TestingConfig
from app.models import Account

ACCOUNT = {"name": "Guard test", "balance": 100}


def account_count(app) -> int:
    from app import get_session

    with app.app_context():
        return get_session().query(Account).count()


class TestCrossSiteWrites:
    """Browsers on other sites cannot change data; everything else still can."""

    @pytest.mark.parametrize("site", ["cross-site", "same-site"])
    def test_rejects_write_from_another_site(self, app, client, site):
        response = client.post(
            "/api/accounts", json=ACCOUNT, headers={"Sec-Fetch-Site": site}
        )
        assert response.status_code == 403
        assert response.get_json() == {
            "error": "Cross-site requests may not change data"
        }
        assert account_count(app) == 0

    def test_rejects_bodiless_destructive_post_from_another_site(self, client):
        client.post("/api/seed")
        response = client.post(
            "/api/reset",
            headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.test"},
        )
        assert response.status_code == 403
        assert client.get("/api/accounts").get_json()

    @pytest.mark.parametrize("method", ["put", "patch", "delete"])
    def test_rejects_every_unsafe_method(self, client, method):
        response = getattr(client, method)(
            "/api/accounts/1", headers={"Sec-Fetch-Site": "cross-site"}
        )
        assert response.status_code == 403

    def test_allows_cross_site_reads(self, client):
        response = client.get("/api/accounts", headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code == 200

    def test_allows_same_origin_browser_write(self, client):
        # What the frontend sends through the Next.js proxy: Host is the
        # backend, Origin and X-Forwarded-Host are the browser's.
        response = client.post(
            "/api/accounts",
            json=ACCOUNT,
            headers={
                "Sec-Fetch-Site": "same-origin",
                "Origin": "http://192.168.1.10:3000",
                "Host": "backend:5000",
                "X-Forwarded-Host": "192.168.1.10:3000",
            },
        )
        assert response.status_code == 201

    def test_allows_same_origin_bodiless_post(self, client):
        # Axios drops Content-Type when a POST has no body, as /api/seed has.
        response = client.post("/api/seed", headers={"Sec-Fetch-Site": "same-origin"})
        assert response.status_code == 200

    def test_allows_non_browser_clients(self, app, client):
        # The MCP server, scripts and e2e seeding send no browser headers.
        assert client.post("/api/accounts", json=ACCOUNT).status_code == 201
        assert client.delete("/api/accounts/1").status_code == 200
        assert account_count(app) == 0

    def test_allows_configured_cors_origin(self, client):
        response = client.post(
            "/api/accounts",
            json=ACCOUNT,
            headers={"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:3000"},
        )
        assert response.status_code == 201

    def test_legacy_browser_from_another_host_is_rejected(self, client):
        # No Sec-Fetch-Site: fall back to comparing Origin with the Host.
        response = client.post("/api/reset", headers={"Origin": "https://evil.test"})
        assert response.status_code == 403

    def test_legacy_browser_null_origin_is_rejected(self, client):
        response = client.post("/api/reset", headers={"Origin": "null"})
        assert response.status_code == 403

    def test_legacy_browser_same_host_is_allowed(self, client):
        response = client.post(
            "/api/accounts",
            json=ACCOUNT,
            headers={
                "Origin": "https://vipu.example.test",
                "Host": "backend:5000",
                "X-Forwarded-Host": "vipu.example.test",
            },
        )
        assert response.status_code == 201

    def test_wildcard_cors_origin_is_ignored(self):
        class WildcardConfig(TestingConfig):
            CORS_ORIGINS = "*"

        client = create_app(WildcardConfig).test_client()
        response = client.options(
            "/api/accounts",
            headers={
                "Origin": "https://evil.test",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "Access-Control-Allow-Origin" not in response.headers
        response = client.post(
            "/api/reset",
            headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.test"},
        )
        assert response.status_code == 403


class TestJsonBodies:
    """A write that carries a body must declare it as JSON."""

    @pytest.mark.parametrize(
        "content_type",
        ["text/plain", "application/x-www-form-urlencoded", "multipart/form-data"],
    )
    def test_rejects_non_json_body(self, app, client, content_type):
        response = client.post(
            "/api/accounts",
            data='{"name": "Guard test", "balance": 100}',
            content_type=content_type,
        )
        assert response.status_code == 415
        assert response.get_json() == {"error": "Content-Type must be application/json"}
        assert account_count(app) == 0

    def test_rejects_body_without_content_type(self, client):
        response = client.post("/api/import", data=b'{"accounts": []}')
        assert response.status_code == 415

    def test_rejects_non_json_content_type_without_body(self, client):
        response = client.post("/api/reset", content_type="text/plain")
        assert response.status_code == 415

    def test_accepts_json_with_charset(self, client):
        response = client.post(
            "/api/accounts",
            data='{"name": "Guard test", "balance": 100}',
            content_type="application/json; charset=utf-8",
        )
        assert response.status_code == 201

    def test_accepts_bodiless_write(self, client):
        assert client.post("/api/seed").status_code == 200


class TestAllowedHosts:
    """VIPU_ALLOWED_HOSTS is off by default and refuses other hosts when set."""

    @pytest.fixture
    def guarded_client(self):
        class HostsConfig(TestingConfig):
            VIPU_ALLOWED_HOSTS = "vipu.example.test, backend"

        return create_app(HostsConfig).test_client()

    def test_any_host_allowed_by_default(self, client):
        response = client.get("/api/accounts", headers={"Host": "rebound.test"})
        assert response.status_code == 200

    def test_allowed_host_with_any_port(self, guarded_client):
        for host in ["vipu.example.test", "backend:5000", "VIPU.example.test:443"]:
            response = guarded_client.get("/api/accounts", headers={"Host": host})
            assert response.status_code == 200, host

    def test_other_host_is_rejected(self, guarded_client):
        response = guarded_client.get("/api/accounts", headers={"Host": "rebound.test"})
        assert response.status_code == 400
        assert response.get_json() == {"error": "Host not allowed"}

    def test_forwarded_host_must_be_allowed_too(self, guarded_client):
        response = guarded_client.get(
            "/api/accounts",
            headers={"Host": "backend:5000", "X-Forwarded-Host": "rebound.test:3000"},
        )
        assert response.status_code == 400

    def test_health_check_is_exempt(self, guarded_client):
        response = guarded_client.get("/api/health", headers={"Host": "localhost"})
        assert response.status_code == 200


class TestSecurityHeaders:
    """Every response forbids framing and MIME sniffing."""

    @pytest.mark.parametrize("path", ["/api/health", "/api/budget/current", "/docs"])
    def test_headers_on_success(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_headers_on_rejected_request(self, client):
        response = client.post("/api/reset", headers={"Sec-Fetch-Site": "cross-site"})
        assert response.status_code == 403
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_headers_on_not_found(self, client):
        response = client.get("/api/does-not-exist")
        assert response.status_code == 404
        assert response.headers["X-Frame-Options"] == "DENY"
