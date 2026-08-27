#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 /home/admin/manifest-VERSION.txt" >&2
  exit 2
fi

manifest="$(readlink -f "$1")"
manifest_dir="$(dirname "${manifest}")"
postflight_started_epoch="$(date +%s)"

manifest_value() {
  local key="$1"
  local count
  count="$(grep -Ec "^${key}=" "${manifest}" || true)"
  [[ "${count}" == "1" ]] || { echo "postflight_error code=manifest_key_invalid key=${key}" >&2; exit 2; }
  grep -E "^${key}=" "${manifest}" | cut -d= -f2-
}

version="$(manifest_value version)"
release_id="$(manifest_value commit)"
target_schema="$(manifest_value alembic_revision)"
wheel_name="$(manifest_value wheel_file)"
wheel_sha="$(manifest_value wheel_sha256)"
release="/opt/agentpost/releases/${release_id}"
public_wheel="/opt/agentpost/public/downloads/${wheel_name}"

[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ "${release_id}" =~ ^[0-9a-f]{7,12}$ ]]
[[ "${target_schema}" =~ ^[0-9]{4}_[a-z0-9_]+$ ]]
[[ "${wheel_name}" == "agentpost-${version}-py3-none-any.whl" ]]
[[ "${wheel_sha}" =~ ^[0-9a-f]{64}$ ]]
[[ -f "${manifest_dir}/SHA256SUMS" ]]
(cd "${manifest_dir}" && sha256sum -c SHA256SUMS)

[[ "$(readlink -f /opt/agentpost/current)" == "${release}" ]]
[[ "$(systemctl is-active agentpost)" == "active" ]]
[[ "$(systemctl is-active nginx)" == "active" ]]
[[ "$(systemctl is-active postgresql)" == "active" ]]
[[ "$(stat -c '%a:%U:%G' /opt/agentpost/shared/agentpost.env)" == "600:root:root" ]]
[[ "$(sudo -u postgres psql -d agentpost -Atc 'select version_num from alembic_version')" == "${target_schema}" ]]
[[ "$(sha256sum "${public_wheel}" | awk '{print $1}')" == "${wheel_sha}" ]]
[[ "$(systemctl cat agentpost --no-pager | grep -Fc "/opt/agentpost/venvs/${release_id}")" == "2" ]]
nginx -t

expected_health="{\"status\":\"ok\",\"version\":\"${version}\"}"
expected_ready="{\"status\":\"ready\",\"version\":\"${version}\"}"
[[ "$(curl -fsS http://127.0.0.1:8000/health)" == "${expected_health}" ]]
[[ "$(curl -fsS http://127.0.0.1:8000/ready)" == "${expected_ready}" ]]
[[ "$(curl -fsS https://agentpost.me/health)" == "${expected_health}" ]]
[[ "$(curl -fsS https://agentpost.me/ready)" == "${expected_ready}" ]]
auth_config="$(mktemp)"
protocol_contract="$(mktemp)"
public_copy="$(mktemp)"
trap 'rm -f "${auth_config}" "${protocol_contract}" "${public_copy}"' EXIT
curl -fsS https://agentpost.me/api/v1/auth/config -o "${auth_config}"
python3 - "${auth_config}" "${version}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
expected = ["mac", "linux", "windows"]
hosts = ("codex", "workbuddy", "doubao_work", "openclaw", "hermes", "manus")
if payload.get("connector_release", {}).get("version") != sys.argv[2]:
    raise SystemExit("public auth config version mismatch")
published = payload.get("host_setup_platforms", {})
incorrect = {host: published.get(host) for host in hosts if published.get(host) != expected}
if incorrect:
    raise SystemExit(f"public host platform contract mismatch: {incorrect}")
PY
curl -fsS https://agentpost.me/api/v1/protocol/contract -o "${protocol_contract}"
python3 - "${protocol_contract}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
if payload.get("contract") != "AGENTPOST_AGENT_INTEGRATION":
    raise SystemExit("public protocol contract name mismatch")
if payload.get("version") != "0.1":
    raise SystemExit("public protocol contract version mismatch")
if payload.get("content", {}).get("native_formats") != ["text", "markdown", "json"]:
    raise SystemExit("public protocol native formats mismatch")
if payload.get("states", {}).get("ack_means_received_not_completed") is not True:
    raise SystemExit("public protocol ACK semantics mismatch")
if payload.get("synchronization", {}).get("human_view_changes_agent_delivery_state") is not False:
    raise SystemExit("public protocol Human view semantics mismatch")
interoperability = payload.get("interoperability", {})
if interoperability.get("a2a") != "mapping_design_only":
    raise SystemExit("public protocol A2A status mismatch")
if interoperability.get("a2a_runtime_endpoint") is not None:
    raise SystemExit("public protocol unexpectedly publishes an A2A runtime")
PY
curl -fsS "https://agentpost.me/downloads/${wheel_name}" -o "${public_copy}"
[[ "$(sha256sum "${public_copy}" | awk '{print $1}')" == "${wheel_sha}" ]]
unknown_status="$(curl -sS -o /dev/null -w '%{http_code}' "https://agentpost.me/downloads/agentpost-${version}-NOTFOUND.whl")"
[[ "${unknown_status}" == "404" ]]
[[ "$(sudo -u postgres psql -Atc "select count(*) from pg_database where datname='agentpost_rehearsal_${release_id}'")" == "0" ]]
[[ ! -e "/var/lib/postgresql/agentpost_rehearsal_${release_id}.dump" ]]
[[ -s /opt/agentpost/shared/DEPLOYED_AT ]]
warning_output="$(journalctl -u agentpost --since "$(cat /opt/agentpost/shared/DEPLOYED_AT)" --no-pager -p warning -o cat)"
[[ -z "${warning_output}" ]]

backup="$(cat /opt/agentpost/shared/DEPLOYED_BACKUP)"
[[ "${backup}" =~ ^/opt/agentpost/backups/[0-9]{8}-[0-9]{6}-[0-9a-f]{7,12}-pre-[0-9]{3}$ ]]
[[ "$(stat -c '%a:%U:%G' "${backup}")" == "700:root:root" ]]
[[ "$(stat -c '%a:%U:%G' "${backup}/agentpost.dump")" == "600:root:root" ]]
(cd "${backup}" && sha256sum -c SHA256SUMS.backup)
bash -n "${backup}/rollback-immediate-${version}.sh"

current_counts="$(mktemp)"
trap 'rm -f "${auth_config}" "${protocol_contract}" "${public_copy}" "${current_counts}"' EXIT
sudo -u postgres psql -d agentpost -Atc "select 'agents='||count(*) from agents; select 'messages='||count(*) from messages; select 'deliveries='||count(*) from deliveries; select 'attachments='||count(*) from attachments; select 'humans='||count(*) from human_users;" > "${current_counts}"
python3 - "${backup}/row-counts.txt" "${current_counts}" <<'PY'
import sys
from pathlib import Path

def load(path: str) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in (
            line.split("=", 1)
            for line in Path(path).read_text().splitlines()
            if "=" in line
        )
    }

before = load(sys.argv[1])
after = load(sys.argv[2])
decreased = sorted(key for key, value in before.items() if after.get(key, -1) < value)
if decreased:
    raise SystemExit(f"production counts decreased: {decreased}")
PY

cat "${current_counts}"
printf 'agentpost_pid=%s\n' "$(systemctl show -p MainPID --value agentpost)"
printf 'nginx_pid=%s\n' "$(systemctl show -p MainPID --value nginx)"
printf 'postgres_pid=%s\n' "$(pgrep -o postgres)"
echo "postflight_status=ok release=${version} commit=${release_id} schema=${target_schema} duration_seconds=$(($(date +%s) - postflight_started_epoch))"
