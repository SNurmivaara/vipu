# Vipu

[![Backend CI](https://github.com/SNurmivaara/vipu/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/SNurmivaara/vipu/actions/workflows/backend-ci.yml)
[![Frontend CI](https://github.com/SNurmivaara/vipu/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/SNurmivaara/vipu/actions/workflows/frontend-ci.yml)
[![Docker Build](https://github.com/SNurmivaara/vipu/actions/workflows/docker-build.yml/badge.svg)](https://github.com/SNurmivaara/vipu/actions/workflows/docker-build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Vipu** (Finnish for "lever") is a personal finance tracker designed to answer one simple question: *"Do I have enough money to cover next month's expenses?"*

## Features

### Weekly Budget Tracking
- Set up monthly expenses (rent, utilities, subscriptions)
- Configure income sources with tax calculations
- Update account balances weekly
- See your net position at a glance: `Current Balance - Monthly Expenses`

### Monthly Net Worth *(Coming Soon)*
- Track assets and liabilities over time
- Visualize wealth growth with charts
- Monitor investment allocation

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
│   │   └── budget/          # Budget-specific components
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
- [ ] Net Worth tracking backend
- [ ] Net Worth frontend with charts
- [ ] Goals and targets

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
