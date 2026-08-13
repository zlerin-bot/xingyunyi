#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_PRODUCTION_CHANGE:-}" != "YES" ]]; then
  echo "Refusing to deploy without CONFIRM_PRODUCTION_CHANGE=YES." >&2
  exit 2
fi

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment_file="${AGENTPOST_ENV_FILE:-/opt/agentpost/shared/agentpost.env}"
compose_file="$repository_root/docker-compose.production.yml"

if [[ ! -f "$environment_file" ]]; then
  echo "Production environment file is missing: $environment_file" >&2
  exit 2
fi

compose=(docker compose --env-file "$environment_file" -f "$compose_file")

"${compose[@]}" config --quiet
"${compose[@]}" build --pull api
"${compose[@]}" up -d --remove-orphans

deadline=$((SECONDS + 180))
while (( SECONDS < deadline )); do
  if "${compose[@]}" exec -T caddy wget -q -O - http://api:8000/ready >/dev/null 2>&1; then
    "${compose[@]}" ps
    echo "AgentPost is ready."
    exit 0
  fi
  sleep 3
done

"${compose[@]}" ps >&2
"${compose[@]}" logs --tail=100 api db caddy >&2
echo "AgentPost did not become ready within 180 seconds." >&2
exit 1

