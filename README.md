# Vipu

[![CI](https://github.com/SNurmivaara/vipu/actions/workflows/ci.yml/badge.svg)](https://github.com/SNurmivaara/vipu/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Vipu** (Finnish for "lever") is a personal finance tracker designed for simplicity.

> **Note:** This app is built with Finnish personal finance in mind (tax percentages, payroll deductions, €). The core budgeting features work anywhere, but some features assume Finnish conventions.

## What Kind of Budgeting Is This?

Vipu uses **balance-based budgeting** - a middle ground between micro-management and no tracking at all.

| Style | Apps | Approach |
|----------|----------|------|
| **Micro** | YNAB, Mint | Tracks every transaction, allocates every euro |
| **Balance-based** | Vipu | Tracks balances and recurring obligations |
| **Macro** | Spreadsheets, net worth only | Just totals, no expense awareness |

**The core idea:** Know your recurring obligations, maintain enough balance to cover them, check in weekly. Don't sweat individual transactions.

This works well if you:
- Have relatively stable income and expenses
- Don't want to categorize every coffee purchase
- Care more about "am I on track?" than "where did 4,50€ go?"

For the full philosophy, see the [User Guide](https://snurmivaara.github.io/vipu/guide.html).

## Features

### Weekly Budget Tracking
- Set up expenses with flexible frequencies (weekly, monthly, yearly, etc.)
- Configure income sources with tax calculations and payroll deductions
- One-time items for things like bonuses or vacation bookings
- Track account balances and credit cards with payment due dates
- See your net position at a glance: `Current Balance - Monthly Expenses`

### Net Worth Tracking
- Track assets and liabilities over time with monthly snapshots
- User-defined groups and categories (cash, investments, crypto, property, loans, credit)
- Personal vs company wealth separation
- Automatic calculation of totals, percentages, and month-over-month changes
- Area chart for net worth trend over time
- Pie chart for asset allocation by group

### Forecasting & FIRE
- Net worth projections based on historical trends
- Configurable lookback period (month, quarter, half year, year)
- FIRE calculator: FIRE number, CoastFIRE, years to retirement
- Compound growth projections with inflation adjustment
- Chart comparing current trajectory vs. required pace

### Financial Goals
- Goal types: net worth target, savings rate, category savings
- On-track/behind status based on linear projection
- Goals shown as target lines on the net worth chart

### Data Management
- JSON export/import
- Seed data for demos
- Prefill snapshots from budget account balances

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, APIFlask, SQLAlchemy |
| Database | PostgreSQL |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Charts | Recharts |
| UI Components | Radix UI |
| State Management | React Query (TanStack) |
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

## Documentation

Full documentation is available at **[snurmivaara.github.io/vipu](https://snurmivaara.github.io/vipu/)**:

- **[User Guide](https://snurmivaara.github.io/vipu/guide.html)** - Learn how Vipu works and get started
- **[API Reference](https://snurmivaara.github.io/vipu/api.html)** - Technical API documentation

When running locally, interactive API docs are also available at `http://localhost:5000/docs`.

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

# View logs
./dev.sh logs

# Rebuild containers (after dependency changes)
./dev.sh build

# Reset database (removes volumes)
./dev.sh reset
```

### Frontend (without Docker)

```bash
cd frontend

# Install dependencies
npm install

# Set up environment (optional - no config needed for default setup)
cp .env.example .env.local

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

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`uv run pytest && uv run ruff check . && uv run black --check .`)
5. Commit with conventional commits (`feat:`, `fix:`, `docs:`, etc.)
6. Push and open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
