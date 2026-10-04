# Working on Vipu

This is the authoritative repository guidance for coding assistants. `CLAUDE.md`
imports it. Inspect the relevant implementation and tests before changing behavior.

## Architecture and navigation

Vipu tracks account balances, recurring obligations, and snapshots; it is not a
transaction ledger. The Next.js frontend calls the APIFlask REST API, which owns
the PostgreSQL data. The separate Python MCP server calls that same API over HTTP
and has no database of its own.

| Location | Purpose |
| --- | --- |
| `backend/app/routes/` | API endpoints and request handling |
| `backend/app/models.py` | SQLAlchemy models and serialization |
| `backend/app/deadline_calc.py` | Recurrences, pay periods, and cash movements |
| `backend/app/fire.py`, `forecasting.py`, `summary.py` | Projections and financial summaries |
| `backend/app/migrations.py` | Ordered startup migrations |
| `backend/tests/` | Backend regression tests, mostly using SQLite |
| `frontend/app/`, `components/` | Next.js pages and UI |
| `frontend/hooks/`, `lib/api.ts`, `types/` | React Query, API access, and types |
| `mcp-server/vipu_mcp/`, `mcp-server/tests/` | MCP tools, authentication, and tests against the real Flask app |
| `docs/` | Existing user guide, API reference, and generated OpenAPI specification |
| `deploy/`, `.github/workflows/` | Production Compose configuration and automation |

Read `mcp-server/README.md` and `mcp-server/OAUTH.md` for MCP design and authentication.
For example, `GET /api/budget/current` can archive expired items and clear stale
overrides; do not assume every GET or MCP read tool is free of writes.

## Lightweight change workflow

1. Inspect relevant code, tests, and documentation.
2. Use the [change request](.github/ISSUE_TEMPLATE/change-request.md) to record the
   problem, scope, and observable acceptance criteria. Refine the approach in the
   issue after investigation; an issue need not prescribe the implementation.
   In Claude Code, the `/new-issue` skill drafts issues (or an epic with PR-sized
   children) in this format and files them after the maintainer approves.
3. Implement on a branch. Keep changes focused and add regression coverage for
   changed behavior, especially financial calculations and migrations.
4. Run the relevant checks below, then the full suite when appropriate. Report
   exact commands, outcomes, and limitations; do not claim checks you did not run.
5. Open a PR using the [PR template](.github/pull_request_template.md), linking the
   issue and showing how the acceptance criteria were met. Tiny fixes may start
   directly with a PR. Use conventional commit subjects (`feat:`, `fix:`, `docs:`, etc.).

A refactoring never changes observable behavior, the API, the MCP surface or the
schema, and never shares a PR with a behavior change. The `/refactor` skill plans one
as an epic of PR-sized steps and executes them with a Definition of Done per step; its
guide lives in `.claude/skills/refactor/`.

In GitHub, `@claude implement this` on an issue runs the `/implement-issue` skill from
step 3 in Actions, on Opus 5.5 with the CI toolchain and Docker. It runs
`./scripts/test-docker.sh` and `./scripts/test-migrations-postgres.sh` when the change
needs them, and opens the PR itself, as a draft when a criterion lacks evidence. Its
tool allow-list does not match commands that start with an environment variable
(`VAR=value uv run ...`), so wrap such checks in a script under `scripts/`. Claude Code
also refuses `cd dir && ...` and `(cd dir && ...)` there; use `git -C`,
`uv --directory`, `npm --prefix` or paths instead, and write scratch files such as a
PR body under `/tmp`.
Open every PR against `main`: CI and the automatic review run only there, so a PR
stacked on another branch gets neither. Open a dependent PR after its base merges,
branched from the updated `main`. Every PR gets one advisory Claude review; only
**CI Status** is required to merge. The review waits for CI on the PR head, then
checks each acceptance criterion of the linked issue for evidence. Its summary comment
starts with `REVIEW: APPROVE` or `REVIEW: REQUEST CHANGES`, and so does any review
requested with `@claude review`; neither is a GitHub approval. When CI fails on a
`claude/` branch, `claude-ci-fix.yml` lets Claude fix it, at most twice per PR, and
comments when it gives up. Claude workflows run on Opus 5.5. The maintainer triages
review notes and asks
`@claude` to fix the accepted ones, comments `@claude review` after large changes,
and alone decides merges, releases, and deployments. The one exception is Dependabot
minor and patch PRs, which merge themselves once **CI Status** passes; majors stay
manual. The `@claude` app cannot push changes under `.github/workflows/`, so the
maintainer commits workflow changes. `@claude` runs only for users with write access
and refuses PRs from forks, because it runs their code next to its tokens. Text that
other people wrote in issues, PRs or comments reaches Claude when you tag it there,
so read it before tagging.

Keep task progress and handoffs in issue/PR comments when available and authorized;
otherwise include the handoff in the final response. Keep lasting knowledge in
relevant existing documentation and code comments, and update this file when shared
conventions change. Preserve `docs/plans/98-forecast-returns.md` as historical context;
new task-plan files are not required. Do not include credentials or personal financial
data in issues, PRs, logs, fixtures, or handoffs.

```text
Issue:
Branch / current commit:
Completed work and key decisions:
Verification commands and results:
Remaining work and blockers:
```

## Setup and development

Use Python 3.11+ and Node.js 24 (the CI versions), uv, npm, and Docker Compose.
`frontend/.nvmrc` sets the Node major for CI; a Node upgrade changes it, the `FROM`
lines of both frontend Dockerfiles and `@types/node` together.
Run these commands from the repository root to install the committed dependencies:

```sh
(cd backend && uv sync --locked --extra dev)
(cd mcp-server && uv sync --locked --extra dev)
(cd frontend && npm ci)
```

Use `--locked` for Python verification so stale lockfiles fail instead of being
rewritten. Change dependencies and regenerate lockfiles only as an intentional task.
The MCP development extra includes the backend through a local path dependency.

For the complete development stack, run `./dev.sh` at the repository root. It uses
`docker-compose.dev.yml` with reloads and development credentials: frontend on 3000,
backend on 5000, MCP on 5100, PostgreSQL on 5433. `./dev.sh down` stops it,
`./dev.sh logs` follows logs, and `./dev.sh build` rebuilds images.
**`./dev.sh reset` is destructive: it removes the development database volume.**
Never use reset or `docker compose down -v` against existing user data as a test step.

Standalone processes (each in its own terminal):

```sh
# backend/: copy .env.example to .env and configure DATABASE_URL for a development
# PostgreSQL database. The example uses 5432; the dev Compose database uses 5433
# and its configured devpassword. Set FLASK_ENV=development and a local SECRET_KEY.
cd backend
uv run --locked flask --app app:create_app run --debug --port 5000

# frontend/: no environment file needed for the default local API on port 5000.
# Set BACKEND_URL if the backend is elsewhere; Next.js rewrites /api requests.
cd frontend
npm run dev

# mcp-server/: export MCP_AUTH_TOKEN with a development-only token before starting.
# VIPU_API_URL defaults to http://localhost:5000; export it to use another backend.
# Complete OAuth configuration is an alternative; see mcp-server/OAUTH.md.
cd mcp-server
uv run --locked uvicorn vipu_mcp.server:create_app --factory \
  --host 127.0.0.1 --port 5100 --reload
```

The backend loads `backend/.env`; the MCP process needs its configuration in the
environment. Production requires `DATABASE_URL` and `SECRET_KEY`, and MCP needs a
bearer token or complete OAuth configuration. Use disposable data for development.

## Verification

After installing dependencies, run `./test.sh` from the repository root. It runs
Black, Ruff, mypy, and pytest in both Python packages, then frontend lint, types,
unit tests, and build. Individual commands, in **each** of `backend/` and
`mcp-server/`:

```sh
uv run --locked black --check .
uv run --locked ruff check .
uv run --locked mypy .
uv run --locked pytest
```

In `frontend/`:

```sh
npm run lint
npm run typecheck
npm run test
npm run build
```

Frontend unit and component tests use Vitest with Testing Library and live next to
the code as `*.test.ts(x)`. They run in jsdom with `TZ=UTC`; `npx vitest run
--coverage` reports coverage.

The Playwright smoke tests (`frontend/e2e/`) are not part of `./test.sh`: they need a
running stack. Against `./dev.sh`, run `npm run test:e2e` in `frontend/` (first time:
`npx playwright install chromium`). They seed synthetic data through the REST API,
clean it up afterwards, and read `E2E_BASE_URL` (default `http://localhost:3000`) and
`E2E_API_URL` (default `http://localhost:5000`). `./scripts/test-docker.sh` and the CI
`docker` job run them against the disposable Compose stack.

`./scripts/snapshot-interfaces.sh <dir>` writes the public interfaces (the OpenAPI
spec and the MCP instructions, tools, prompts and resources) to `<dir>`. Snapshot
before and after a change and compare them with `git diff --no-index` to prove an
interface is unchanged.

Run `./scripts/test-docker.sh` from the repository root for disposable Docker
integration checks. It uses the existing production Dockerfiles with an isolated
Compose project, generated container names, ephemeral loopback ports, and its own
database volume; cleanup removes only that project's resources. It checks health,
MCP authentication, and migration registration/rerun behavior. Do not substitute
existing application containers or databases. CI performs these checks on its
disposable runner and always requires Docker success, including for docs-only PRs.

Shared Claude settings, skills, and agents belong in `.claude/` and are committed;
personal Claude permissions go in the untracked `.claude/settings.local.json`.
`.claude/settings.json` allows the routine checks, denies destructive database
resets and reading `.env` files and `.private/`, and runs a hook that formats edited
Python files with Ruff and Black. The `/implement-issue` skill walks the workflow above.
Local Codex permissions belong in an untracked `.codex/config.toml`. Keep workspace
filesystem isolation and approval on request; grant package cache writes and network
access for routine development as needed. Configuration changes require a refreshed
session and verification of effective permissions. An approved script runs the code
it calls too; do not treat its filename as an isolation boundary. Keep host Docker
access separately approved or use a dedicated development daemon/VM.

## Financial conventions to preserve

- Monetary model columns use Python `Decimal` and SQLAlchemy `Numeric(12, 2)`;
  percentage columns commonly use `Numeric(5, 2)`. Existing JSON serializers emit
  numbers using `float(...)`, not decimal strings. Preserve the API contract.
- Balances are signed. Credit-card debt and net-worth liability entries are negative;
  `net_worth = total_assets + total_liabilities`. Some projection inputs expose debt
  as positive magnitudes (`liabilities_by_group` / `liabilities_by_category`). Check
  the specific boundary rather than applying `abs()` to all balances.
- `compute_budget_totals()` in `backend/app/routes/budget.py` sums active lines at
  face value for `net_income` and `total_expenses`, including active one-time items.
  `net_position` is `current_balance - total_expenses`. `monthly_net_income` and
  `monthly_expenses` normalize recurring frequencies and exclude ephemeral items;
  their difference is the monthly surplus used by the roadmap and projections.
- In `deadline_calc.py`, legacy `is_savings_goal` expense lines produce `savings`
  movements rather than `bill` movements. Savings transfers still reduce available
  cash and are included in period money-out. Migration 009 archives existing legacy
  savings-goal expense lines as part of the roadmap transition. Do not equate those
  lines with roadmap goals or introduce double counting.
- Rounding is currently context-specific: summary formatting uses explicit
  `ROUND_HALF_UP`; FIRE's `_decimal_round` uses Decimal context rounding, with
  explicit `ROUND_CEILING` in some payment calculations; other projections and
  percentages use Python `round` on floats. There is no universal rounding policy.
  Preserve existing behavior unless a change deliberately specifies and tests it.

## Migrations and recovery

`create_app()` first calls SQLAlchemy `create_all`, then `run_migrations()`.
Append migrations to `MIGRATIONS` with a new unique, ordered ID. Never edit or reuse
released IDs or rewrite historical migration SQL to implement a new change.
Each migration's SQL and `_migrations` record commit in the same transaction;
failure rolls back that migration, not earlier successful migrations.

Migration SQL runs only on PostgreSQL. SQLite tests skip it and cannot prove
PostgreSQL DDL or data transformations. The Docker check proves startup on a fresh
database records every registered migration and a repeat applies zero migrations
without changing those records.

`backend/tests/test_migrations_postgres.py` covers populated upgrades: it builds a
legacy schema in a throwaway PostgreSQL schema, migrates to a historical point,
inserts synthetic rows, runs the next migrations and asserts the transformed data
(currently 009, 011 and 015). It runs only when `TEST_POSTGRES_URL` names a
disposable PostgreSQL database and skips otherwise. From the repository root,
`./scripts/test-migrations-postgres.sh` starts a throwaway `postgres:16` container on
an ephemeral loopback port, runs the file and removes the container; extra arguments
go to pytest. With `TEST_POSTGRES_URL` already set it uses that database instead:

```sh
./scripts/test-migrations-postgres.sh -v
TEST_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  ./scripts/test-migrations-postgres.sh
```

Add a test there for every new data-transforming migration. The legacy schema
contains only the columns migrations touch, not full historical DDL.

There is no automatic downgrade mechanism. For schema/data changes, describe backup,
compatibility, and recovery in the PR: a tested forward fix or restoration of a
pre-change backup may be necessary. Reverting an image alone does not undo a migration.

## API documentation and deployment

For API changes, regenerate and inspect `docs/openapi.json` from `backend/`:

```sh
uv run --locked python scripts/export_openapi.py
```

The exporter uses the testing configuration and in-memory SQLite; no external
database is needed. `./test.sh`, the pre-commit hook and CI regenerate it and fail
when the committed file differs. Keep `docs/api.html` and `docs/guide.html` current where relevant.
The Pages workflow deploys docs on qualifying pushes to `main` or manual dispatch.

The release workflow publishes GHCR images when a GitHub release is published, or
through manual dispatch with a tag (and optional forced builds). An ordinary push
does not publish release images. In Claude Code, the `/release` skill lists the
changes since the last release, chooses the semver bump against the public contract
it defines, and drafts the notes; it publishes only after the maintainer approves.
Production uses `deploy/docker-compose.yml` and `deploy/.env` (or copies of these on
the server); `VERSION` selects an image tag and defaults to `latest`. Existing
commands, from that deployment directory:

```sh
docker compose pull
docker compose up -d
docker compose ps
docker compose logs --tail=100
```

Deploy only when requested. Check database compatibility before selecting an older
image for recovery. Do not merge, release, deploy, or change repository settings as
an implicit part of implementing a feature.

## Follow-ups

- Extend the populated PostgreSQL migration tests to the remaining migrations and
  to full historical DDL snapshots rather than minimal legacy tables.
- Improve production dependency reproducibility further by pinning the moving
  base-image and uv tags. The backend image installs from its committed lockfile.
- Agree and test a rounding policy before attempting consistency changes.
