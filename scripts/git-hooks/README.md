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
- `npm run test` (Vitest)

## Installation

To install the git hooks, run this from the repository root (run it, do not
`source` it):

```bash
./scripts/install-git-hooks.sh
```

The script installs into the hooks directory git actually uses, so it also works
from a worktree. Running it again is safe: an identical hook is left alone and a
different existing `pre-commit` hook is first moved to `pre-commit.backup.<timestamp>`.
If `core.hooksPath` is set, the script warns, and it installs nothing when that
directory is outside the repository, because other repositories may share it.

Or manually:

```bash
hooks_dir="$(git rev-parse --git-path hooks)"
mkdir -p "$hooks_dir"
cp scripts/git-hooks/pre-commit "$hooks_dir/"
chmod +x "$hooks_dir/pre-commit"
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
