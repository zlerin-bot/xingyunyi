#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  echo "Usage: $0 <git-commit> <version> <alembic-head>" >&2
  echo "Example: $0 8f9bc79 0.1.19 0023_human_usernames" >&2
}

if [[ "$#" -ne 3 ]]; then
  usage
  exit 2
fi

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
requested_commit="$1"
version="$2"
alembic_head="$3"
python_bin="${PYTHON_BIN:-${repository_root}/.venv/bin/python}"

[[ "${version}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid version: ${version}" >&2; exit 2; }
[[ "${alembic_head}" =~ ^[0-9]{4}_[a-z0-9_]+$ ]] || { echo "Invalid Alembic head: ${alembic_head}" >&2; exit 2; }
[[ -x "${python_bin}" ]] || { echo "Project Python is missing: ${python_bin}" >&2; exit 2; }

commit="$(git -C "${repository_root}" rev-parse --verify "${requested_commit}^{commit}")"
release_id="${commit:0:7}"
output_dir="${repository_root}/dist/${version}"
temporary_root="$(mktemp -d)"
snapshot="${temporary_root}/source"

cleanup() {
  rm -rf "${temporary_root}"
}
trap cleanup EXIT

mkdir -p "${snapshot}" "${output_dir}"
git -C "${repository_root}" archive --format=tar "${commit}" -o "${temporary_root}/source.tar"
tar -xf "${temporary_root}/source.tar" -C "${snapshot}"

snapshot_version="$("${python_bin}" - "${snapshot}/pyproject.toml" <<'PY'
import sys
import tomllib
from pathlib import Path

print(tomllib.loads(Path(sys.argv[1]).read_text())["project"]["version"])
PY
)"
[[ "${snapshot_version}" == "${version}" ]] || {
  echo "Snapshot version ${snapshot_version} does not match requested ${version}." >&2
  exit 2
}

source_name="agentpost-${version}-source.tar.gz"
wheel_name="agentpost-${version}-py3-none-any.whl"
manifest_name="manifest-${version}.txt"
upload_name="agentpost-${version}-aliyun-upload.tar.gz"
commands_name="workbench-commands-${version}.txt"
uv_cache_dir="${UV_CACHE_DIR:-${TMPDIR:-/tmp}/agentpost-uv-release-cache}"
mkdir -p "${uv_cache_dir}"

git -C "${repository_root}" archive --format=tar.gz "${commit}" -o "${output_dir}/${source_name}"
UV_CACHE_DIR="${uv_cache_dir}" uv build --wheel --out-dir "${output_dir}" "${snapshot}"
[[ -f "${output_dir}/${wheel_name}" ]] || { echo "Expected wheel was not built: ${wheel_name}" >&2; exit 1; }

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

source_sha="$(sha256_file "${output_dir}/${source_name}")"
wheel_sha="$(sha256_file "${output_dir}/${wheel_name}")"

cat > "${output_dir}/${manifest_name}" <<EOF
version=${version}
commit=${release_id}
commit_full=${commit}
alembic_revision=${alembic_head}
source_file=${source_name}
source_sha256=${source_sha}
wheel_file=${wheel_name}
wheel_sha256=${wheel_sha}
EOF

install -m 755 "${repository_root}/scripts/aliyun/switch-release.sh" "${output_dir}/aliyun-switch-release.sh"
install -m 755 "${repository_root}/scripts/aliyun/postflight.sh" "${output_dir}/aliyun-postflight.sh"

(
  cd "${output_dir}"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${source_name}" "${wheel_name}" "${manifest_name}" aliyun-switch-release.sh aliyun-postflight.sh > SHA256SUMS
  else
    shasum -a 256 "${source_name}" "${wheel_name}" "${manifest_name}" aliyun-switch-release.sh aliyun-postflight.sh > SHA256SUMS
  fi
)

bundle_root="${temporary_root}/upload"
mkdir -p "${bundle_root}"
install -m 644 \
  "${output_dir}/${source_name}" \
  "${output_dir}/${wheel_name}" \
  "${output_dir}/${manifest_name}" \
  "${output_dir}/SHA256SUMS" \
  "${bundle_root}/"
install -m 755 \
  "${output_dir}/aliyun-switch-release.sh" \
  "${output_dir}/aliyun-postflight.sh" \
  "${bundle_root}/"
tar -czf "${output_dir}/${upload_name}" -C "${bundle_root}" .
upload_sha="$(sha256_file "${output_dir}/${upload_name}")"

remote_upload="/home/admin/${upload_name}"
remote_stage="/home/admin/agentpost-release-${version}"
cat > "${output_dir}/${commands_name}" <<EOF
# Upload only this file in Workbench: ${output_dir}/${upload_name}
# Then run these commands in order. The first command creates the staging directory; do not create it in File Navigator.
if test -e '${remote_stage}'; then echo 'stage_error code=directory_exists path=${remote_stage}' >&2; false; else install -d -m 755 '${remote_stage}' && printf '%s  %s\n' '${upload_sha}' '${remote_upload}' | sha256sum -c - && tar -xzf '${remote_upload}' -C '${remote_stage}' && cd '${remote_stage}' && sha256sum -c SHA256SUMS && bash -n aliyun-switch-release.sh aliyun-postflight.sh && chmod 750 aliyun-switch-release.sh aliyun-postflight.sh && echo 'stage_status=ok release=${version}'; fi
sudo -n env CONFIRM_PRODUCTION_CHANGE=YES '${remote_stage}/aliyun-switch-release.sh' '${remote_stage}/${manifest_name}'
sudo -n '${remote_stage}/aliyun-postflight.sh' '${remote_stage}/${manifest_name}'
EOF

printf 'release_artifacts=%s\n' "${output_dir}"
printf 'release_version=%s commit=%s alembic=%s\n' "${version}" "${release_id}" "${alembic_head}"
printf 'source_sha256=%s\nwheel_sha256=%s\n' "${source_sha}" "${wheel_sha}"
printf 'workbench_upload=%s\nworkbench_upload_sha256=%s\n' "${output_dir}/${upload_name}" "${upload_sha}"
printf 'workbench_commands=%s\n' "${output_dir}/${commands_name}"
