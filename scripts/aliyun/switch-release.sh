#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${CONFIRM_PRODUCTION_CHANGE:-}" != "YES" ]]; then
  echo "deploy_error code=confirmation_required" >&2
  exit 2
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "deploy_error code=root_required" >&2
  exit 2
fi
if [[ "$#" -ne 1 ]]; then
  echo "Usage: CONFIRM_PRODUCTION_CHANGE=YES sudo -n env CONFIRM_PRODUCTION_CHANGE=YES $0 /home/admin/manifest-VERSION.txt" >&2
  exit 2
fi

manifest="$(readlink -f "$1")"
manifest_dir="$(dirname "${manifest}")"
[[ -f "${manifest}" ]] || { echo "deploy_error code=manifest_missing" >&2; exit 2; }

manifest_value() {
  local key="$1"
  local count
  local value
  count="$(grep -Ec "^${key}=" "${manifest}" || true)"
  [[ "${count}" == "1" ]] || { echo "deploy_error code=manifest_key_invalid key=${key}" >&2; exit 2; }
  value="$(grep -E "^${key}=" "${manifest}" | cut -d= -f2-)"
  printf '%s' "${value}"
}

version="$(manifest_value version)"
release_id="$(manifest_value commit)"
commit_full="$(manifest_value commit_full)"
target_schema="$(manifest_value alembic_revision)"
source_name="$(manifest_value source_file)"
source_sha="$(manifest_value source_sha256)"
wheel_name="$(manifest_value wheel_file)"
wheel_sha="$(manifest_value wheel_sha256)"

[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "deploy_error code=version_invalid" >&2; exit 2; }
[[ "${release_id}" =~ ^[0-9a-f]{7,12}$ ]] || { echo "deploy_error code=release_id_invalid" >&2; exit 2; }
[[ "${commit_full}" =~ ^[0-9a-f]{40}$ ]] || { echo "deploy_error code=commit_invalid" >&2; exit 2; }
[[ "${commit_full}" == "${release_id}"* ]] || { echo "deploy_error code=commit_mismatch" >&2; exit 2; }
[[ "${target_schema}" =~ ^[0-9]{4}_[a-z0-9_]+$ ]] || { echo "deploy_error code=schema_invalid" >&2; exit 2; }
[[ "${source_name}" == "agentpost-${version}-source.tar.gz" ]] || { echo "deploy_error code=source_name_invalid" >&2; exit 2; }
[[ "${wheel_name}" == "agentpost-${version}-py3-none-any.whl" ]] || { echo "deploy_error code=wheel_name_invalid" >&2; exit 2; }
[[ "${source_sha}" =~ ^[0-9a-f]{64}$ && "${wheel_sha}" =~ ^[0-9a-f]{64}$ ]] || { echo "deploy_error code=sha_invalid" >&2; exit 2; }

source_artifact="${manifest_dir}/${source_name}"
wheel_artifact="${manifest_dir}/${wheel_name}"
sums="${manifest_dir}/SHA256SUMS"
release="/opt/agentpost/releases/${release_id}"
venv="/opt/agentpost/venvs/${release_id}"
env_file="/opt/agentpost/shared/agentpost.env"
unit_file="/etc/systemd/system/agentpost.service"
nginx_file="/etc/nginx/sites-available/agentpost"
public_wheel="/opt/agentpost/public/downloads/${wheel_name}"
current_release="$(readlink -f /opt/agentpost/current)"
prior_release_id="$(basename "${current_release}")"
prior_schema="$(sudo -u postgres psql -d agentpost -Atc 'select version_num from alembic_version')"
prior_version="$(python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
    print(json.load(response)["version"])
PY
)"
prior_wheel_name="agentpost-${prior_version}-py3-none-any.whl"
prior_public_wheel="/opt/agentpost/public/downloads/${prior_wheel_name}"
stamp="$(date +%Y%m%d-%H%M%S)"
patch_version="${version##*.}"
printf -v release_suffix '%03d' "$((10#${patch_version}))"
backup="/opt/agentpost/backups/${stamp}-${release_id}-pre-${release_suffix}"
rollback="${backup}/rollback-immediate-${version}.sh"
rehearsal_db="agentpost_rehearsal_${release_id}"
rehearsal_dump="/var/lib/postgresql/${rehearsal_db}.dump"
mutated=0
rehearsal_exists=0

step() {
  echo "deploy_step=$1"
}

rollback_on_error() {
  local status=$?
  trap - ERR
  if [[ "${rehearsal_exists}" -eq 1 ]]; then
    sudo -u postgres dropdb --if-exists "${rehearsal_db}" || true
  fi
  rm -f "${rehearsal_dump}"
  if [[ "${mutated}" -eq 1 && -x "${rollback}" ]]; then
    echo "deploy_step=automatic_rollback"
    "${rollback}" || true
  fi
  echo "deploy_error code=switch_failed status=${status}" >&2
  exit "${status}"
}
trap rollback_on_error ERR

step preflight
[[ "${current_release}" == "/opt/agentpost/releases/${prior_release_id}" ]]
[[ "${prior_release_id}" != "${release_id}" ]]
[[ "${prior_version}" != "${version}" ]]
[[ "$(systemctl is-active agentpost)" == "active" ]]
[[ "$(systemctl is-active nginx)" == "active" ]]
[[ "$(systemctl is-active postgresql)" == "active" ]]
[[ "$(stat -c '%a:%U:%G' "${env_file}")" == "600:root:root" ]]
[[ -f "${source_artifact}" && -f "${wheel_artifact}" && -f "${sums}" ]]
[[ "$(sha256sum "${source_artifact}" | awk '{print $1}')" == "${source_sha}" ]]
[[ "$(sha256sum "${wheel_artifact}" | awk '{print $1}')" == "${wheel_sha}" ]]
(cd "${manifest_dir}" && sha256sum -c "${sums}")
[[ -f "${prior_public_wheel}" ]]
if [[ -e "${release}" || -e "${venv}" ]]; then
  [[ -d "${release}" && -d "${venv}" ]]
  "${venv}/bin/python" -c "import agentpost, agentpost_sdk, agentpost_mcp; assert {agentpost.__version__, agentpost_sdk.__version__, agentpost_mcp.__version__} == {'${version}'}"
  (cd "${release}" && "${venv}/bin/python" -m alembic -c alembic.ini heads | grep -Fx "${target_schema} (head)")
fi

step backup
install -d -o root -g root -m 700 "${backup}"
printf '%s\n' "${current_release}" > "${backup}/prior-release.txt"
printf '%s\n' "${prior_version}" > "${backup}/prior-version.txt"
printf '%s\n' "${prior_schema}" > "${backup}/prior-schema.txt"
install -o root -g root -m 600 "${env_file}" "${backup}/agentpost.env"
install -o root -g root -m 644 "${unit_file}" "${backup}/agentpost.service"
install -o root -g root -m 644 "${nginx_file}" "${backup}/nginx-agentpost"
install -o root -g root -m 644 "${manifest}" "${backup}/RELEASE_MANIFEST.txt"
install -o root -g root -m 644 "${sums}" "${backup}/SHA256SUMS.release"
install -o root -g root -m 644 "${prior_public_wheel}" "${backup}/${prior_wheel_name}"
sudo -u postgres pg_dump -Fc -d agentpost > "${backup}/agentpost.dump"
chown root:root "${backup}/agentpost.dump"
chmod 600 "${backup}/agentpost.dump"
pg_restore --list "${backup}/agentpost.dump" > "${backup}/agentpost.dump.list"
tar -C /var/lib/agentpost -czf "${backup}/attachments.tar.gz" attachments
tar -tzf "${backup}/attachments.tar.gz" > "${backup}/attachments.list"
sudo -u postgres psql -d agentpost -Atc "select 'agents='||count(*) from agents; select 'messages='||count(*) from messages; select 'deliveries='||count(*) from deliveries; select 'attachments='||count(*) from attachments; select 'humans='||count(*) from human_users;" > "${backup}/row-counts.txt"
[[ -s "${backup}/agentpost.dump" && -s "${backup}/agentpost.dump.list" ]]
[[ -s "${backup}/attachments.tar.gz" && -s "${backup}/attachments.list" ]]
sha256sum "${backup}/agentpost.dump" "${backup}/attachments.tar.gz" "${backup}/agentpost.env" "${backup}/agentpost.service" "${backup}/nginx-agentpost" "${backup}/${prior_wheel_name}" > "${backup}/SHA256SUMS.backup"

cat > "${rollback}" <<ROLLBACK
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "\$(sudo -u postgres psql -d agentpost -Atc 'select version_num from alembic_version')" == '${target_schema}' ]]; then
  database_url="\$(python3 - '/opt/agentpost/shared/agentpost.env' <<'PY'
import sys
from pathlib import Path
for line in Path(sys.argv[1]).read_text().splitlines():
    if line.startswith('AGENTPOST_DATABASE_URL='):
        value = line.split('=', 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        print(value)
        break
else:
    raise SystemExit('AGENTPOST_DATABASE_URL is missing')
PY
)"
  cd '${release}'
  sudo -u agentpost env AGENTPOST_DATABASE_URL="\${database_url}" '${venv}/bin/python' -m alembic -c alembic.ini downgrade '${prior_schema}'
fi
install -o root -g root -m 600 '${backup}/agentpost.env' '/opt/agentpost/shared/agentpost.env'
install -o root -g root -m 644 '${backup}/agentpost.service' '/etc/systemd/system/agentpost.service'
install -o root -g root -m 644 '${backup}/nginx-agentpost' '/etc/nginx/sites-available/agentpost'
ln -sfn '${current_release}' '/opt/agentpost/current.next'
mv -Tf '/opt/agentpost/current.next' '/opt/agentpost/current'
systemctl daemon-reload
nginx -t
systemctl restart agentpost
systemctl reload nginx
health_response=''
for attempt in {1..30}; do
  health_response="\$(curl -fsS --max-time 5 http://127.0.0.1:8000/health || true)"
  [[ "\${health_response}" == '{"status":"ok","version":"${prior_version}"}' ]] && break
  sleep 1
done
[[ "\${health_response}" == '{"status":"ok","version":"${prior_version}"}' ]]
[[ "\$(sudo -u postgres psql -d agentpost -Atc 'select version_num from alembic_version')" == '${prior_schema}' ]]
echo 'rollback_status=ok release=${prior_version} schema=${prior_schema}'
ROLLBACK
chmod 700 "${rollback}"
sha256sum "${rollback}" >> "${backup}/SHA256SUMS.backup"
(cd "${backup}" && sha256sum -c SHA256SUMS.backup)

step prepare_release
if [[ ! -e "${release}" ]]; then
  install -d -o root -g root -m 755 "${release}"
  tar -xzf "${source_artifact}" -C "${release}"
  chown -R root:root "${release}"
fi
if [[ ! -e "${venv}" ]]; then
  python3 -m venv "${venv}"
  "${venv}/bin/pip" install --disable-pip-version-check "${wheel_artifact}"
fi
"${venv}/bin/pip" check
"${venv}/bin/python" -c "import agentpost, agentpost_sdk, agentpost_mcp; assert {agentpost.__version__, agentpost_sdk.__version__, agentpost_mcp.__version__} == {'${version}'}"
(cd "${release}" && "${venv}/bin/python" -m alembic -c alembic.ini heads | grep -Fx "${target_schema} (head)")
install -d -o root -g root -m 755 /opt/agentpost/public/downloads
install -o root -g root -m 644 "${wheel_artifact}" "${public_wheel}"
[[ "$(sha256sum "${public_wheel}" | awk '{print $1}')" == "${wheel_sha}" ]]

database_url="$(python3 - "${env_file}" <<'PY'
import sys
from pathlib import Path
for line in Path(sys.argv[1]).read_text().splitlines():
    if line.startswith("AGENTPOST_DATABASE_URL="):
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        print(value)
        break
else:
    raise SystemExit("AGENTPOST_DATABASE_URL is missing")
PY
)"

step rehearse_migration
database_owner="$(sudo -u postgres psql -d agentpost -Atc "select pg_get_userbyid(datdba) from pg_database where datname='agentpost'")"
sudo -u postgres dropdb --if-exists "${rehearsal_db}"
sudo -u postgres createdb -O "${database_owner}" "${rehearsal_db}"
rehearsal_exists=1
install -o postgres -g postgres -m 600 "${backup}/agentpost.dump" "${rehearsal_dump}"
sudo -u postgres pg_restore -d "${rehearsal_db}" "${rehearsal_dump}"
rehearsal_database_url="$(AGENTPOST_DEPLOY_DB_URL="${database_url}" AGENTPOST_DEPLOY_DB_NAME="${rehearsal_db}" python3 - <<'PY'
import os
from urllib.parse import urlsplit, urlunsplit
parts = urlsplit(os.environ["AGENTPOST_DEPLOY_DB_URL"])
print(urlunsplit((parts.scheme, parts.netloc, "/" + os.environ["AGENTPOST_DEPLOY_DB_NAME"], parts.query, parts.fragment)))
PY
)"
(cd "${release}" && sudo -u agentpost env AGENTPOST_DATABASE_URL="${rehearsal_database_url}" "${venv}/bin/python" -m alembic -c alembic.ini upgrade head)
[[ "$(sudo -u postgres psql -d "${rehearsal_db}" -Atc 'select version_num from alembic_version')" == "${target_schema}" ]]
(cd "${release}" && sudo -u agentpost env AGENTPOST_DATABASE_URL="${rehearsal_database_url}" "${venv}/bin/python" -m alembic -c alembic.ini downgrade "${prior_schema}")
[[ "$(sudo -u postgres psql -d "${rehearsal_db}" -Atc 'select version_num from alembic_version')" == "${prior_schema}" ]]
(cd "${release}" && sudo -u agentpost env AGENTPOST_DATABASE_URL="${rehearsal_database_url}" "${venv}/bin/python" -m alembic -c alembic.ini upgrade head)
[[ "$(sudo -u postgres psql -d "${rehearsal_db}" -Atc 'select version_num from alembic_version')" == "${target_schema}" ]]
sudo -u postgres dropdb "${rehearsal_db}"
rehearsal_exists=0
rm -f "${rehearsal_dump}"

step prepare_configuration
mutated=1
AGENTPOST_DEPLOY_VERSION="${version}" AGENTPOST_DEPLOY_WHEEL="${wheel_name}" AGENTPOST_DEPLOY_SHA="${wheel_sha}" python3 - "${env_file}" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = os.environ["AGENTPOST_DEPLOY_VERSION"]
updates = {
    "AGENTPOST_CONNECTOR_RELEASE_VERSION": version,
    "AGENTPOST_CONNECTOR_WHEEL_URL": f"https://agentpost.me/downloads/{os.environ['AGENTPOST_DEPLOY_WHEEL']}",
    "AGENTPOST_CONNECTOR_WHEEL_SHA256": os.environ["AGENTPOST_DEPLOY_SHA"],
}
lines = path.read_text().splitlines()
seen = {key: 0 for key in updates}
result = []
for line in lines:
    key = line.split("=", 1)[0] if "=" in line else ""
    if key in updates:
        seen[key] += 1
        result.append(f"{key}={updates[key]}")
    else:
        result.append(line)
if any(count > 1 for count in seen.values()):
    raise SystemExit("duplicate release setting")
for key, count in seen.items():
    if count == 0:
        result.append(f"{key}={updates[key]}")
temporary = path.with_name(f".{path.name}.{version}.tmp")
temporary.write_text("\n".join(result) + "\n")
os.chmod(temporary, 0o600)
os.replace(temporary, path)
PY

AGENTPOST_DEPLOY_PRIOR="${prior_release_id}" AGENTPOST_DEPLOY_TARGET="${release_id}" python3 - "${unit_file}" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
old = f"/opt/agentpost/venvs/{os.environ['AGENTPOST_DEPLOY_PRIOR']}"
new = f"/opt/agentpost/venvs/{os.environ['AGENTPOST_DEPLOY_TARGET']}"
if text.count(old) != 2:
    raise SystemExit("unexpected systemd runtime references")
temporary = path.with_name(f".{path.name}.{os.environ['AGENTPOST_DEPLOY_TARGET']}.tmp")
temporary.write_text(text.replace(old, new))
os.chmod(temporary, 0o644)
os.replace(temporary, path)
PY

AGENTPOST_DEPLOY_WHEEL="${wheel_name}" python3 - "${nginx_file}" <<'PY'
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
wheel = os.environ["AGENTPOST_DEPLOY_WHEEL"]
location = f'''    location = /downloads/{wheel} {{
        root /opt/agentpost/public;
        default_type application/octet-stream;
        add_header Content-Disposition "attachment";
        add_header Cache-Control "public, max-age=300";
    }}
'''
marker = "    location /downloads/ { return 404; }"
if location not in text:
    if text.count(marker) != 1:
        raise SystemExit("unexpected downloads catch-all")
    text = text.replace(marker, f"{location}\n{marker}")
temporary = path.with_name(f".{path.name}.{wheel}.tmp")
temporary.write_text(text)
os.chmod(temporary, 0o644)
os.replace(temporary, path)
PY

step switch
cutover_started_at="$(date --iso-8601=seconds)"
(cd "${release}" && sudo -u agentpost env AGENTPOST_DATABASE_URL="${database_url}" "${venv}/bin/python" -m alembic -c alembic.ini upgrade head)
ln -sfn "${release}" /opt/agentpost/current.next
mv -Tf /opt/agentpost/current.next /opt/agentpost/current
systemctl daemon-reload
nginx -t
systemctl restart agentpost
systemctl reload nginx

step verify_local
health_response=''
ready_response=''
for attempt in {1..30}; do
  health_response="$(curl -fsS --max-time 5 http://127.0.0.1:8000/health || true)"
  ready_response="$(curl -fsS --max-time 5 http://127.0.0.1:8000/ready || true)"
  if [[ "${health_response}" == "{\"status\":\"ok\",\"version\":\"${version}\"}" && "${ready_response}" == "{\"status\":\"ready\",\"version\":\"${version}\"}" ]]; then
    break
  fi
  sleep 1
done
[[ "${health_response}" == "{\"status\":\"ok\",\"version\":\"${version}\"}" ]]
[[ "${ready_response}" == "{\"status\":\"ready\",\"version\":\"${version}\"}" ]]
[[ "$(readlink -f /opt/agentpost/current)" == "${release}" ]]
[[ "$(systemctl is-active nginx)" == "active" ]]
[[ "$(systemctl is-active postgresql)" == "active" ]]
[[ "$(sudo -u postgres psql -d agentpost -Atc 'select version_num from alembic_version')" == "${target_schema}" ]]
sudo -u postgres psql -d agentpost -Atc "select 'agents='||count(*) from agents; select 'messages='||count(*) from messages; select 'deliveries='||count(*) from deliveries; select 'attachments='||count(*) from attachments; select 'humans='||count(*) from human_users;" > "${backup}/row-counts.after.txt"
python3 - "${backup}/row-counts.txt" "${backup}/row-counts.after.txt" <<'PY'
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
missing = sorted(set(before) - set(after))
decreased = sorted(key for key, value in before.items() if after.get(key, -1) < value)
if missing or decreased:
    raise SystemExit(f"production counts invalid: missing={missing} decreased={decreased}")
PY
printf '%s %s\n' "${release_id}" "${version}" > /opt/agentpost/shared/DEPLOYED_RELEASE
chmod 644 /opt/agentpost/shared/DEPLOYED_RELEASE
printf '%s\n' "${cutover_started_at}" > /opt/agentpost/shared/DEPLOYED_AT
chmod 644 /opt/agentpost/shared/DEPLOYED_AT
printf '%s\n' "${backup}" > /opt/agentpost/shared/DEPLOYED_BACKUP
chmod 644 /opt/agentpost/shared/DEPLOYED_BACKUP
mutated=0
trap - ERR

echo "deploy_status=ok release=${version} commit=${release_id} backup=${backup}"
