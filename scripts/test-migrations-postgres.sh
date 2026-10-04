#!/usr/bin/env bash
# Run the populated PostgreSQL migration tests (backend/tests/test_migrations_postgres.py).
#
# Uses TEST_POSTGRES_URL when it is set. Otherwise starts a throwaway postgres:16
# container on an ephemeral loopback port and removes it, with its anonymous
# volume, on exit. Extra arguments go to pytest, e.g. -v or -k 015.
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
container=""

cleanup() {
  result=$?
  trap - EXIT
  if [[ -n "$container" ]]; then
    if [[ "$result" != 0 ]]; then
      docker logs --tail 50 "$container" || true
    fi
    docker rm --force --volumes "$container" > /dev/null || result=1
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -z "${TEST_POSTGRES_URL:-}" ]]; then
  container=$(docker run --detach --name "vipu-migration-test-$$-$RANDOM" \
    --env POSTGRES_PASSWORD=postgres --publish 127.0.0.1::5432 \
    postgres:16@sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54)
  echo "Started disposable PostgreSQL container: ${container:0:12}"

  # Probe over TCP: the image's init phase runs a socket-only temporary server
  # that would pass a plain pg_isready before the real server starts.
  ready=0
  for _ in $(seq 60); do
    if docker exec "$container" pg_isready --quiet -h 127.0.0.1 -U postgres; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" != 1 ]]; then
    echo "PostgreSQL did not become ready within 60 seconds" >&2
    exit 1
  fi

  port=$(docker port "$container" 5432/tcp | head -n 1)
  port=${port##*:}
  export TEST_POSTGRES_URL="postgresql://postgres:postgres@127.0.0.1:$port/postgres"
fi

cd "$repo_root/backend"
uv run --locked pytest tests/test_migrations_postgres.py "$@"
