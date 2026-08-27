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

printf 'release_artifacts=%s\n' "${output_dir}"
printf 'release_version=%s commit=%s alembic=%s\n' "${version}" "${release_id}" "${alembic_head}"
printf 'source_sha256=%s\nwheel_sha256=%s\n' "${source_sha}" "${wheel_sha}"
