"""Typed httpx wrapper over the Vipu REST API.

One method per endpoint the tools use. The backend validates inline and answers
a bad request with ``{"error": ...}`` and a 400; VipuApiError carries that
message through to the tool result, so a validation failure reaches the model as
something it can act on rather than a bare status code.

Deliberately never wrapped, and deliberately unreachable over MCP:

    POST /api/reset
    POST /api/networth/reset
    POST /api/import
    POST /api/seed
    POST /api/networth/seed
    POST /api/networth/categories/seed

Those either drop every row or overwrite real data with demo data. There is no
undo and no confirmation step a model could be held to, so the safe surface is
one that cannot express them at all.
"""

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from vipu_mcp import config


class VipuApiError(ToolError):
    """The backend refused a call, with the reason it gave.

    ``message`` is the backend's own ``{"error": ...}`` text where there was
    one, since that wording already explains the domain rule that was broken.

    A ToolError rather than a plain exception, because that is the difference
    between the model reading "due_day must be between 1 and 31" and reading
    "Error executing tool add_expense". The SDK surfaces a ToolError's message
    as an is_error result and reduces anything else to the tool's name.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class VipuClient:
    """Everything the MCP tools are allowed to ask the backend for."""

    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url or config.VIPU_API_URL,
            transport=transport,
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )

    def close(self) -> None:
        self._http.close()

    # -- plumbing ---------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise VipuApiError(f"The Vipu API timed out on {method} {path}") from exc
        except httpx.HTTPError as exc:
            raise VipuApiError(f"Could not reach the Vipu API: {exc}") from exc

        if response.status_code >= 400:
            raise VipuApiError(self._error_message(response), response.status_code)

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise VipuApiError(
                f"The Vipu API returned a non-JSON body for {method} {path}"
            ) from exc

    @staticmethod
    def _error_message(response: httpx.Response) -> str:
        """The backend's own explanation, or the bare status if it gave none."""
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict):
            message = body.get("error") or body.get("message")
            if isinstance(message, str):
                details = body.get("details")
                return f"{message}: {details}" if details else message
        return f"The Vipu API returned {response.status_code}"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("POST", path, json=json or {})

    def _put(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("PUT", path, json=json or {})

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # -- read -------------------------------------------------------------

    def get_summary(self) -> dict:
        """GET /api/summary: the whole app state as one markdown digest."""
        result = self._get("/api/summary")
        return dict(result)

    def get_budget(self) -> dict:
        """GET /api/budget/current.

        Not a pure read: the handler clears occurrence overrides the calendar
        has caught up with and auto-archives past ephemeral items, then commits.
        """
        result = self._get("/api/budget/current")
        return dict(result)

    def list_net_worth(self) -> list[dict]:
        """GET /api/networth: every snapshot, newest first."""
        result = self._get("/api/networth")
        return list(result)

    def get_roadmap(self) -> dict:
        """GET /api/goals/roadmap: the sequential plan and its projections."""
        result = self._get("/api/goals/roadmap")
        return dict(result)

    def get_goal_progress(self) -> list[dict]:
        """GET /api/goals/progress: per-goal pace against target."""
        result = self._get("/api/goals/progress")
        return list(result)

    def get_projection(self) -> dict:
        """GET /api/forecasting/projection: FIRE from the persisted settings."""
        result = self._get("/api/forecasting/projection")
        return dict(result)

    def list_budget_snapshots(self, limit: int = 50, offset: int = 0) -> dict:
        """GET /api/budget/snapshots: cash history, newest first."""
        result = self._get(
            "/api/budget/snapshots", params={"limit": limit, "offset": offset}
        )
        return dict(result)

    def list_accounts(self) -> list[dict]:
        """GET /api/accounts."""
        return list(self._get("/api/accounts"))

    def list_expenses(self) -> list[dict]:
        """GET /api/expenses."""
        return list(self._get("/api/expenses"))

    def list_income(self) -> list[dict]:
        """GET /api/income."""
        return list(self._get("/api/income"))

    def list_net_worth_categories(self) -> list[dict]:
        """GET /api/networth/categories."""
        return list(self._get("/api/networth/categories"))

    def get_net_worth_month(self, year: int, month: int) -> dict | None:
        """GET /api/networth/<year>/<month>, or None when nothing is recorded."""
        try:
            return dict(self._get(f"/api/networth/{year}/{month}"))
        except VipuApiError as exc:
            if exc.status_code == 404:
                return None
            raise

    # -- write ------------------------------------------------------------

    def update_account(self, account_id: int, **fields: Any) -> dict:
        """PUT /api/accounts/<id>."""
        return dict(self._put(f"/api/accounts/{account_id}", fields))

    def create_budget_snapshot(self, notes: str | None = None) -> dict:
        """POST /api/budget/snapshots. Upserts on today's date."""
        return dict(self._post("/api/budget/snapshots", {"notes": notes}))

    def create_net_worth_snapshot(
        self, year: int, month: int, entries: list[dict]
    ) -> dict:
        """POST /api/networth. 409s when the month already has a snapshot."""
        return dict(
            self._post(
                "/api/networth", {"year": year, "month": month, "entries": entries}
            )
        )

    def update_net_worth_snapshot(self, snapshot_id: int, entries: list[dict]) -> dict:
        """PUT /api/networth/<id>. Entries replace the whole set."""
        return dict(self._put(f"/api/networth/{snapshot_id}", {"entries": entries}))

    def set_expense_occurrence(
        self, expense_id: int, occurrence_date: str, settled: bool
    ) -> dict:
        """PUT /api/expenses/<id>/occurrence."""
        return dict(
            self._put(
                f"/api/expenses/{expense_id}/occurrence",
                {"occurrence_date": occurrence_date, "settled": settled},
            )
        )

    def set_income_occurrence(
        self, income_id: int, occurrence_date: str, settled: bool
    ) -> dict:
        """PUT /api/income/<id>/occurrence."""
        return dict(
            self._put(
                f"/api/income/{income_id}/occurrence",
                {"occurrence_date": occurrence_date, "settled": settled},
            )
        )

    # -- plan -------------------------------------------------------------

    def get_forecasting_settings(self) -> dict:
        """GET /api/forecasting/settings."""
        return dict(self._get("/api/forecasting/settings"))

    def calculate_fire(self, inputs: dict[str, Any]) -> dict:
        """POST /api/forecasting/calculate.

        Computes from the posted body and stores nothing, which is what makes
        it usable as a what-if.
        """
        return dict(self._post("/api/forecasting/calculate", inputs))

    def forecast_net_worth(self, period: str, months_ahead: int) -> dict:
        """GET /api/networth/forecast."""
        return dict(
            self._get(
                "/api/networth/forecast",
                params={"period": period, "months_ahead": months_ahead},
            )
        )

    def update_forecasting_settings(self, fields: dict[str, Any]) -> dict:
        """PUT /api/forecasting/settings."""
        return dict(self._put("/api/forecasting/settings", fields))

    def get_budget_settings(self) -> dict:
        """GET /api/settings."""
        return dict(self._get("/api/settings"))

    def update_budget_settings(self, fields: dict[str, Any]) -> dict:
        """PUT /api/settings."""
        return dict(self._put("/api/settings", fields))
