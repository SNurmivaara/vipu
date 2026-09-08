# Vipu MCP server

An [MCP](https://modelcontextprotocol.io) server that puts Vipu in a
conversation: recording a budget, recording net worth, talking through the
current position and planning ahead, without a form. It speaks streamable HTTP
and calls the existing REST API; it holds no database of its own.

The directory is `mcp-server` rather than `mcp_server` on purpose. The hyphen
keeps it non-importable, so it can never shadow the `mcp` PyPI package.

## Running it

```bash
uv sync --extra dev
MCP_AUTH_TOKEN=$(openssl rand -hex 32) \
  VIPU_API_URL=http://localhost:5000 \
  uv run uvicorn vipu_mcp.server:create_app --factory --host 0.0.0.0 --port 5100
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `VIPU_API_URL` | `http://localhost:5000` | Where the REST API lives |
| `MCP_AUTH_TOKEN` | *(required)* | Static bearer token for `/mcp` |
| `VIPU_MCP_READ_ONLY` | off | Unregister every write tool |
| `PORT` | `5100` | Port the container listens on |

Check it:

```bash
curl -s localhost:5100/health                 # {"status": "ok"}
curl -si -X POST localhost:5100/mcp | head -1 # HTTP/1.1 401 Unauthorized
```

## Authentication is one static token, on purpose

`/mcp` requires `Authorization: Bearer <MCP_AUTH_TOKEN>`, compared with
`hmac.compare_digest`. `/health` stays open so the compose healthcheck can
reach it.

That is a deliberate simplification over the MCP specification's OAuth flow,
sized to a single-user homelab behind a Cloudflare tunnel. It is recorded here
as a decision rather than left as an oversight: if Vipu ever grows a second
user, this is the piece to replace.

DNS rebinding protection is off, also deliberately. The tunnel forwards the
public hostname as `Host` and the container has no way to enumerate it, so the
check would reject every real request. The bearer token is the gate.

## Transport

`streamable_http_app(stateless_http=True, json_response=True)`. Stateless
removes session affinity concerns behind the tunnel, and JSON responses avoid
streaming SSE through Cloudflare entirely.

The MCP Python SDK renamed `FastMCP` to `MCPServer` in 2.x, and moved
`stateless_http` / `json_response` from the constructor onto
`streamable_http_app()`. This server targets 2.x.

## Design rules

What makes this AI-first rather than an API wrapper.

1. **Name-based resolution.** No tool takes a database id. `resolve.py` matches
   exactly, then case-insensitively, and on ambiguity raises an error listing
   the candidates so the model asks rather than guesses.
2. **Write tools return the consequence.** A write answers with the recomputed
   state the user cares about, so the model can narrate the effect without a
   second read.
3. **Tool annotations are honest.** In particular `get_budget` is *not*
   read-only: `GET /api/budget/current` clears stale occurrence overrides and
   auto-archives past ephemeral items, then commits.

Plus `VIPU_MCP_READ_ONLY=1`, which unregisters every write tool, as insurance
when testing against live data.

## Tools

**Read and talk**

| Tool | Backing call |
| --- | --- |
| `get_financial_summary` | `GET /api/summary`. The entry point for any open-ended question. |
| `get_budget` | `GET /api/budget/current` |
| `get_net_worth` | `GET /api/networth` |
| `get_goals` | `GET /api/goals/roadmap` + `GET /api/goals/progress`, merged |
| `get_fire_projection` | `GET /api/forecasting/projection` |
| `list_budget_snapshots` | `GET /api/budget/snapshots` |

**Record**

| Tool | Backing call |
| --- | --- |
| `set_account_balance` | `PUT /api/accounts/<id>`, resolved by name |
| `record_budget_snapshot` | `POST /api/budget/snapshots` |
| `record_net_worth` | `POST`/`PUT /api/networth`, taking `{category_name: amount}` |
| `settle_expense` / `settle_income` | `PUT /api/{expenses,income}/<id>/occurrence` |

**Manage**

| Tool | Backing call |
| --- | --- |
| `add_expense` / `update_expense` / `archive_expense` | `POST`/`PUT /api/expenses` |
| `add_income` / `update_income` / `archive_income` | `POST`/`PUT /api/income` |
| `add_account` | `POST /api/accounts` |
| `set_goal` / `update_goal` / `reorder_goals` | `POST`/`PUT /api/goals`, `PUT /api/goals/reorder` |

The `archive_*` tools set `archived_at` through `PUT`, which retires an item
and can be undone with `restore=true`. `DELETE /api/{expenses,income}/<id>`
removes the row outright with no undo, so it is not wrapped.

**Plan**

| Tool | Backing call |
| --- | --- |
| `project_fire` | `POST /api/forecasting/calculate`. The what-if tool. |
| `forecast_net_worth` | `GET /api/networth/forecast` |
| `update_forecasting_settings` | `PUT /api/forecasting/settings` |
| `update_budget_settings` | `PUT /api/settings` |

`project_fire` computes and stores nothing, so it stays available in read-only
mode alongside `forecast_net_worth`. It reports its result as a delta against a
baseline run of the same endpoint rather than against `get_fire_projection`:
the stored projection compounds each asset group at its own rate and amortises
debt separately, so the two models disagree on levels for identical inputs and
a cross-model comparison would credit the difference to the change being tested.

## What is deliberately not exposed

`POST /api/reset`, `/api/networth/reset`, `/api/import`, `/api/seed`,
`/api/networth/seed` and `/api/networth/categories/seed` are never wrapped.
They either drop every row or overwrite real data with demo data, with no undo
and no confirmation step a model could be held to. The omission is recorded in
`client.py` as well, so it survives someone reading only that file.

## Tests

```bash
uv run pytest
uv run black --check . && uv run ruff check . && uv run mypy .
```

Tools run against the real Flask app over `httpx.WSGITransport`, with
`vipu-backend` as a uv path dependency in the dev extras. That exercises actual
pay-period and occurrence semantics rather than a fixture's idea of them.
`httpx.MockTransport` is kept for the error paths a real backend will not
produce on demand: timeouts, 5xx, malformed bodies.
