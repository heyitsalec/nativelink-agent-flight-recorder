#!/usr/bin/env bash
# Regenerate the committed REAPI protobuf message stubs (dev-only tooling).
#
# NLFR's optional CAS probe (issue #81 part B, `pip install
# nativelink-agent-flight-recorder[reapi]`) uses protobuf message classes
# generated from the vendored proto subset under third_party/reapi/. The
# generated modules are COMMITTED under src/nlfr/reapi/_gen/ so that:
#
#   * a reviewer can read exactly what ships (no build-time codegen);
#   * the wheel build stays hatchling-only (no protoc in the build path);
#   * the runtime keeps zero build-time codegen dependencies.
#
# This script is the only place codegen happens. It is NOT run at build,
# install, or import time — run it manually only when the vendored protos
# under third_party/reapi/ change, then commit the regenerated output.
#
# Toolchain pin: grpcio-tools==1.62.3 bundles a protoc with protobuf 4.25.x
# gencode. That vintage is deliberate — 4.25-era generated code predates the
# protobuf runtime-version validation gate, so the committed stubs load on
# every protobuf runtime from 4.25 onward (verified against 7.x, the current
# major, in .github/workflows/reapi-probe.yml). Regenerating with a newer
# grpcio-tools would silently raise the [reapi] extra's real protobuf floor
# above the declared `protobuf>=4.25`; do not bump this pin without also
# re-verifying (and, if needed, honestly raising) that floor in pyproject.toml.
#
# grpcio-tools 1.62.3 publishes wheels for CPython 3.8-3.12; run this script
# with python 3.11 or 3.12 (e.g. `uv venv --python 3.12`).
#
# Usage:
#   ./scripts/regen-reapi-stubs.sh [PYTHON]
# where PYTHON is an interpreter that has (or can pip-install) grpcio-tools.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${1:-python3}"
GRPCIO_TOOLS_PIN="grpcio-tools==1.62.3"

PROTO_ROOT="${REPO_ROOT}/third_party/reapi"
OUT_ROOT="${REPO_ROOT}/src/nlfr/reapi/_gen"

if ! "${PYTHON}" -c "import grpc_tools.protoc" >/dev/null 2>&1; then
  echo "grpc_tools not importable from ${PYTHON}; install the pinned toolchain:" >&2
  echo "  ${PYTHON} -m pip install '${GRPCIO_TOOLS_PIN}'" >&2
  exit 2
fi

"${PYTHON}" - <<'PY'
import grpc_tools
import google.protobuf
print(f"generating with grpcio-tools protoc (protobuf gencode {google.protobuf.__version__})")
PY

rm -rf "${OUT_ROOT}"
mkdir -p "${OUT_ROOT}"

"${PYTHON}" -m grpc_tools.protoc \
  -I "${PROTO_ROOT}" \
  --python_out="${OUT_ROOT}" \
  "${PROTO_ROOT}/build/bazel/remote/execution/v2/remote_execution.proto" \
  "${PROTO_ROOT}/google/bytestream/bytestream.proto"

# Only *_pb2.py message modules are generated (no --grpc_python_out): the probe
# invokes its two RPCs through gRPC's generic method API with explicit,
# reviewer-checkable method paths instead of generated service stubs.

# The generated tree mirrors the proto paths; make every level an explicit
# regular package so imports never depend on namespace-package resolution.
cat > "${OUT_ROOT}/__init__.py" <<'EOF'
"""Generated REAPI protobuf message modules (committed, never hand-edited).

Regenerate with scripts/regen-reapi-stubs.sh when third_party/reapi/ changes.
Importing anything under this package requires the optional [reapi] extra
(protobuf); nothing in the NLFR core imports this package at module level.
"""
EOF
find "${OUT_ROOT}" -type d | while read -r dir; do
  if [ ! -f "${dir}/__init__.py" ]; then
    printf '"""Generated package path (see src/nlfr/reapi/_gen/__init__.py)."""\n' \
      > "${dir}/__init__.py"
  fi
done

echo "regenerated:"
find "${OUT_ROOT}" -name '*.py' | sort
