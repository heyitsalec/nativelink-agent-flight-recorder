#!/usr/bin/env bash
set -euo pipefail

# Research-only fleet claim matrix — no UI, no invented backend state.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${NLFR_FLEET_CLAIMS_OUTPUT:-$ROOT/data/fleet-claims-audit}"

mkdir -p "$OUT"
PYTHONPATH=src uv run python "$ROOT/scripts/fleet_claims_audit.py" --output "$OUT/claim-matrix.json"
echo "fleet-claims-audit complete: $OUT/claim-matrix.json"
