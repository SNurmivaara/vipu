# Vipu

[![CI](https://github.com/SNurmivaara/vipu/actions/workflows/ci.yml/badge.svg)](https://github.com/SNurmivaara/vipu/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Vipu** (Finnish for "lever") is a personal finance tracker designed to answer one simple question: *"Do I have enough money to cover next month's expenses?"*

> **Note:** This app is built with Finnish personal finance in mind (tax percentages, payroll deductions, €). The core budgeting features work anywhere, but some features assume Finnish conventions.

## Features

### Weekly Budget Tracking
- Set up monthly expenses (rent, utilities, subscriptions)
- Configure income sources with tax calculations
- Update account balances weekly
- See your net position at a glance: `Current Balance - Monthly Expenses`

### Monthly Net Worth
- Track assets and liabilities over time
- User-defined groups and categories (cash, investments, crypto, property, loans, credit)
- Personal vs company wealth separation
- Automatic calculation of totals, percentages, and month-over-month changes
- Area chart for net worth trend over time
- Pie chart for asset allocation by group

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, APIFlask, SQLAlchemy |
| Database | PostgreSQL |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Deployment | Docker Compose |

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Run with Docker

```bash
# Clone the repository
git clone https://github.com/SNurmivaara/vipu.git
cd vipu

# Create environment file
cp .env.example .env
# Edit .env with your own SECRET_KEY and POSTGRES_PASSWORD

# Start all services
docker compose up

# Frontend: http://localhost:3000
# Backend API: http://localhost:5000
```

### Verify it works

```bash
# Health check
curl http://localhost:5000/api/health
# {"status": "ok"}

# Seed example data
curl -X POST http://localhost:5000/api/seed
# {"message": "Example data seeded successfully", "counts": {...}}

# Get current budget
curl http://localhost:5000/api/budget/current
```

## Production Deployment

For homelab or production deployments, pre-built images are published to GitHub Container Registry (GHCR) via the release workflow.

- GHCR images (built on tag push):
	- `ghcr.io/snurmivaara/vipu-backend:TAG` and `ghcr.io/snurmivaara/vipu-backend:latest`
	- `ghcr.io/snurmivaara/vipu-frontend:TAG` and `ghcr.io/snurmivaara/vipu-frontend:latest`

- Quick tag to create a release (triggers the GHCR build):

```bash
git tag v1.0.0
git push origin v1.0.0
```

## API Documentation

Full API documentation is available at **[snurmivaara.github.io/vipu](https://snurmivaara.github.io/vipu/)**.

When running locally, interactive docs are also available at `http://localhost:5000/docs`.

## Development Setup

### Quick Start (Recommended)

The easiest way to develop is using Docker Compose with hot reloading:

```bash
# Start everything with hot reloading
./dev.sh

# Or manually:
docker compose -f docker-compose.dev.yml up --build

# Frontend: http://localhost:3000 (hot reload enabled)
# Backend API: http://localhost:5000 (hot reload enabled)
# API Docs: http://localhost:5000/docs
```

Changes to frontend (`app/`, `components/`, `lib/`, `hooks/`, `types/`) and backend (`app/`) directories will automatically reload.

```bash
# Stop development environment
./dev.sh down

# Rebuild containers (after dependency changes)
./dev.sh build
```

### Frontend (without Docker)

```bash
cd frontend

# Install dependencies
npm install

# Set up environment
cp .env.example .env.local
# Edit .env.local with your backend URL (default: http://localhost:5000)

# Run development server
npm run dev

# Linting and type checking
npm run lint
npm run typecheck
```

### Backend (without Docker)

```bash
cd backend

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --extra dev

# Set up environment
cp .env.example .env
# Edit .env with your database connection

# Run development server
uv run flask run --debug

# Run tests
uv run pytest

# Linting and formatting
uv run ruff check .
uv run black --check .
uv run mypy .
```

### Database

The project uses PostgreSQL. With Docker Compose, it runs on port 5433 (to avoid conflicts with local PostgreSQL).

```bash
# Connect to the database (when using Docker)
docker compose exec postgres psql -U vipu -d vipu
```

## Project Structure

```
vipu/
├── backend/
│   ├── app/
│   │   ├── __init__.py      # Flask app factory
│   │   ├── config.py        # Configuration
│   │   ├── models.py        # SQLAlchemy models
│   │   └── routes/          # API endpoints
│   ├── tests/               # pytest tests
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── app/                 # Next.js app router pages
│   ├── components/          # React components
│   │   ├── budget/          # Budget-specific components
│   │   └── networth/        # Net worth components (charts, forms)
│   ├── hooks/               # React Query hooks
│   ├── lib/                 # API client, utilities
│   ├── types/               # TypeScript interfaces
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`uv run pytest && uv run ruff check . && uv run black --check .`)
5. Commit with conventional commits (`feat:`, `fix:`, `docs:`, etc.)
6. Push and open a Pull Request

## Roadmap

- [x] Backend API (Weekly Budget)
- [x] CI/CD with GitHub Actions
- [x] Frontend (Weekly Budget)
- [x] Net Worth tracking backend
- [x] Net Worth frontend with charts
- [x] Goals and targets
- [x] Data import/export
- [x] Release 1.0 to GHCR

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
