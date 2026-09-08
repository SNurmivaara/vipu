# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies. --no-dev keeps the vipu-backend path dependency out:
# it exists only so the tests can drive the real Flask app, and the running
# container talks to the backend over HTTP.
RUN uv sync --frozen --no-dev --no-install-project

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r vipu && useradd -r -g vipu vipu

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY vipu_mcp/ ./vipu_mcp/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=5100

# Change to non-root user
USER vipu

# Expose port
EXPOSE 5100

# Health check. /health is deliberately outside the bearer-token gate, so this
# needs no credentials.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5100/health')" || exit 1

# Run with uvicorn. Shell form so PORT is honoured.
CMD uvicorn vipu_mcp.server:create_app --factory --host 0.0.0.0 --port ${PORT:-5100}
