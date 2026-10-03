#!/bin/bash
set -e

echo "=== Backend Checks ==="
cd backend

echo ">> Black (formatting)"
uv run --locked black --check .

echo ">> Ruff (linting)"
uv run --locked ruff check .

echo ">> Mypy (type checking)"
uv run --locked mypy .

echo ">> Pytest (tests)"
uv run --locked pytest

cd ..

echo ""
echo "=== MCP Server Checks ==="
cd mcp-server

echo ">> Black (formatting)"
uv run --locked black --check .

echo ">> Ruff (linting)"
uv run --locked ruff check .

echo ">> Mypy (type checking)"
uv run --locked mypy .

echo ">> Pytest (tests)"
uv run --locked pytest

cd ..

echo ""
echo "=== Frontend Checks ==="
cd frontend

echo ">> ESLint"
npm run lint

echo ">> TypeScript"
npm run typecheck

echo ">> Build"
npm run build

cd ..

echo ""
echo "=== All checks passed ==="
