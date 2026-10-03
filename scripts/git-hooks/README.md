# Git Hooks for Vipu Project

This directory contains git hooks that are used to validate code before commits.

## Available Hooks

### pre-commit
Mirrors `./test.sh` for the components with staged changes, minus the slow
frontend production build. Commits touching only docs, workflows, etc. skip the
component checks. Python checks use `uv run --locked`.

**Backend (Python)** - when `backend/` files are staged:
- `black --check`, `ruff check`, `mypy`, `pytest`

**MCP server (Python)** - when `mcp-server/` or `backend/` files are staged
(MCP tests run against the real Flask app):
- `black --check`, `ruff check`, `mypy`, `pytest`

**Frontend (TypeScript)** - when `frontend/` files are staged:
- `npm run lint` (ESLint)
- `npm run typecheck`

## Installation

To install the git hooks, run:

```bash
./scripts/install-git-hooks.sh
```

Or manually:

```bash
# Copy the hook to .git/hooks/
mkdir -p .git/hooks
cp scripts/git-hooks/pre-commit .git/hooks/
chmod +x .git/hooks/pre-commit
```

## Bypassing Hooks

If you need to bypass the hooks (e.g., for a quick fix), use:

```bash
git commit --no-verify -m "Your message"
```

However, it's recommended to fix any issues the hooks identify.

## Auto-fixing Issues

For common formatting issues, you can auto-fix them:

**Backend:**
```bash
uv run --locked black .
uv run --locked ruff check . --fix
```

**Frontend:**
```bash
npm run lint -- --fix
```
