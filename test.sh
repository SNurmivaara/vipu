#!/bin/bash
set -e

echo "=== Backend Checks ==="
cd backend

echo ">> Black (formatting)"
uv run black --check .

echo ">> Ruff (linting)"
uv run ruff check .

echo ">> Mypy (type checking)"
uv run mypy .

echo ">> Pytest (tests)"
uv run pytest

cd ..

echo ""
echo "=== Frontend Checks ==="
cd frontend

echo ">> ESLint"
npm run lint

echo ">> TypeScript"
npx tsc --noEmit

echo ">> Build"
npm run build

cd ..

echo ""
echo "=== All checks passed ==="
