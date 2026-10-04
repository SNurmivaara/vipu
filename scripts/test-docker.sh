#!/usr/bin/env bash
# Build and check an isolated, disposable copy of the production Compose stack.
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
test_dir=$(mktemp -d "${TMPDIR:-/tmp}/vipu-test-XXXXXXXX")
project=$(basename "$test_dir" | tr '[:upper:]' '[:lower:]')

# Never load the user's .env or inherited production authentication settings.
export SECRET_KEY=test-secret-key-for-ci
export POSTGRES_PASSWORD=test-password-for-ci
export MCP_AUTH_TOKEN=test-mcp-token-for-ci
export DOMAIN=localhost
export MCP_OAUTH_ISSUER= MCP_OAUTH_RESOURCE_URL= MCP_OAUTH_JWKS_URL=
export MCP_OAUTH_ALLOWED_CLIENTS= MCP_OAUTH_ALLOWED_USERS=

compose=(docker compose --env-file /dev/null --project-directory "$repo_root"
  --project-name "$project" -f "$test_dir/compose.json")

cleanup() {
  result=$?
  trap - EXIT
  if [[ -f "$test_dir/compose.json" ]]; then
    if [[ "$result" != 0 ]]; then
      "${compose[@]}" logs --no-color || true
    fi
    "${compose[@]}" down --volumes --remove-orphans || result=1
  fi
  rm -r -- "$test_dir"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Reuse the existing services and Dockerfiles, replacing only resource identity
# and published ports. A project name alone does not isolate fixed container_name.
docker compose --env-file /dev/null --project-directory "$repo_root" \
  -f "$repo_root/docker-compose.yml" config --format json > "$test_dir/base.json"
python3 - "$test_dir/base.json" "$test_dir/compose.json" "$project" <<'PY'
import json
import sys

with open(sys.argv[1]) as source:
    config = json.load(source)
config["name"] = sys.argv[3]
for name, service in config["services"].items():
    service.pop("container_name", None)
    service.pop("ports", None)
    service["restart"] = "no"
    if name in ("backend", "mcp", "frontend"):
        service["ports"] = [{
            "target": {"backend": 5000, "mcp": 5100, "frontend": 3000}[name],
            "published": "0",
            "host_ip": "127.0.0.1",
            "protocol": "tcp",
        }]
# docker compose config expands resource names; give every resource a fresh name.
for section in ("volumes", "networks"):
    for name, resource in config.get(section, {}).items():
        if resource.get("external"):
            raise SystemExit(f"Refusing external {section} resource: {name}")
        resource["name"] = f"{sys.argv[3]}_{name}"
with open(sys.argv[2], "w") as output:
    json.dump(config, output)
PY

echo "Starting disposable integration project: $project"
"${compose[@]}" up -d --build --wait --wait-timeout 120

backend_address=$("${compose[@]}" port backend 5000)
mcp_address=$("${compose[@]}" port mcp 5100)
curl --fail --silent --show-error "http://$backend_address/api/health" | grep -q 'ok'
curl --fail --silent --show-error "http://$mcp_address/health" | grep -q 'ok'
status=$(curl --silent --show-error -o /dev/null -w '%{http_code}' -X POST \
  "http://$mcp_address/mcp" -H 'Content-Type: application/json' -d '{}')
[[ "$status" == 401 ]]

"${compose[@]}" exec -T backend python < "$repo_root/scripts/check-migrations.py"

# Browser smoke tests against this stack. Needs `npm ci` in frontend/ first.
frontend_address=$("${compose[@]}" port frontend 3000)
(
  cd "$repo_root/frontend"
  # CI runners lack Chromium's system libraries; --with-deps installs them via apt.
  npx --no playwright install ${GITHUB_ACTIONS:+--with-deps} chromium
  E2E_BASE_URL="http://$frontend_address" E2E_API_URL="http://$backend_address" \
    npm run test:e2e
)
echo 'Docker health, MCP authentication, PostgreSQL migration, and Playwright checks passed'
