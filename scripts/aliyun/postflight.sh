#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 /home/admin/manifest-VERSION.txt" >&2
  exit 2
fi

manifest="$(readlink -f "$1")"
manifest_dir="$(dirname "${manifest}")"

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
public_copy="$(mktemp)"
trap 'rm -f "${public_copy}"' EXIT
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
trap 'rm -f "${public_copy}" "${current_counts}"' EXIT
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
echo "postflight_status=ok release=${version} commit=${release_id} schema=${target_schema}"
