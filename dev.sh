#!/bin/bash
# Development server with hot reloading
# Usage: ./dev.sh [command]
#   ./dev.sh        - Start all services
#   ./dev.sh down   - Stop all services
#   ./dev.sh logs   - View logs
#   ./dev.sh build  - Rebuild containers
#   ./dev.sh reset  - Reset database (removes volumes)

set -e

case "${1:-up}" in
  up)
    echo "Starting development environment..."
    docker compose -f docker-compose.dev.yml up --build
    ;;
  down)
    echo "Stopping development environment..."
    docker compose -f docker-compose.dev.yml down
    ;;
  logs)
    docker compose -f docker-compose.dev.yml logs -f
    ;;
  build)
    echo "Rebuilding containers..."
    docker compose -f docker-compose.dev.yml build --no-cache
    ;;
  reset)
    echo "Resetting database (removing volumes)..."
    docker compose -f docker-compose.dev.yml down -v
    echo "Database reset. Run ./dev.sh to start fresh."
    ;;
  *)
    echo "Usage: ./dev.sh [up|down|logs|build|reset]"
    exit 1
    ;;
esac
