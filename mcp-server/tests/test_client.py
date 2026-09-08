"""VipuClient error paths.

A real backend will not produce a timeout or a malformed body on demand, so
these use httpx.MockTransport. Everything else in the suite runs against the
real Flask app.
"""

import httpx
import pytest

from vipu_mcp.client import VipuApiError, VipuClient


def mocked(handler) -> VipuClient:
    return VipuClient(base_url="http://backend", transport=httpx.MockTransport(handler))


def test_surfaces_the_backends_own_error_message():
    """A validation failure has to reach the model as something it can act on."""

    def handler(_request):
        return httpx.Response(400, json={"error": "due_day must be between 1 and 31"})

    with pytest.raises(VipuApiError) as excinfo:
        mocked(handler).get_summary()
    assert excinfo.value.message == "due_day must be between 1 and 31"
    assert excinfo.value.status_code == 400


def test_appends_validation_details_when_present():
    """Marshmallow errors arrive as a message plus a per-field breakdown."""

    def handler(_request):
        return httpx.Response(
            400,
            json={"error": "Validation error", "details": {"current_age": ["Bad."]}},
        )

    with pytest.raises(VipuApiError) as excinfo:
        mocked(handler).get_summary()
    assert "Validation error" in excinfo.value.message
    assert "current_age" in excinfo.value.message


def test_reports_a_server_error_without_a_body():
    """A 500 with an HTML body still has to say something useful."""

    def handler(_request):
        return httpx.Response(500, text="<html>nope</html>")

    with pytest.raises(VipuApiError) as excinfo:
        mocked(handler).get_summary()
    assert "500" in excinfo.value.message
    assert excinfo.value.status_code == 500


def test_reports_a_timeout_as_a_timeout():
    def handler(request):
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(VipuApiError, match="timed out"):
        mocked(handler).get_summary()


def test_reports_an_unreachable_backend():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(VipuApiError, match="Could not reach the Vipu API"):
        mocked(handler).get_summary()


def test_rejects_a_malformed_body():
    """A 200 that is not JSON is a broken backend, not an empty result."""

    def handler(_request):
        return httpx.Response(200, text="not json at all")

    with pytest.raises(VipuApiError, match="non-JSON body"):
        mocked(handler).get_summary()
