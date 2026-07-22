# Git Hooks for Vipu Project

This directory contains git hooks that are used to validate code before commits.

## Available Hooks

### pre-commit
Validates code formatting and runs tests for both backend and frontend:

**Backend (Python):**
- `black --check` - Code formatting
- `ruff check` - Linting
- `mypy` - Type checking
- `pytest` - Unit tests

**Frontend (TypeScript):**
- `tsc --noEmit` - TypeScript type checking
- `eslint` - Linting (if config exists)
- `prettier --check` - Formatting (if config exists)

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
uv run black .
uv run ruff check . --fix
```

**Frontend:**
```bash
npx prettier --write .
npx eslint . --fix
```
