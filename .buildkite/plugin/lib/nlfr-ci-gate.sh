#!/usr/bin/env bash
# nlfr-ci-gate.sh — the redact-gate baked into every NLFR CI primitive.
#
# ONE job: record a Bazel build's evidence with NLFR, then GATE that evidence
# through `nlfr redact` BEFORE anything can be uploaded — so no CI system can
# ever publish a raw evidence tree that has not passed the redaction boundary
# (issue #82: the exact leak class NLFR exists to prevent).
#
# Single source of truth, shared by every NLFR CI primitive so the guarantee
# cannot drift between systems:
#   * the GitHub composite Action .......... action.yml (repo root)
#   * the Buildkite plugin command hook .... .buildkite/plugin/hooks/command
#   * the Jenkins declarative snippet ...... docs/wiki/how-to/ci-integration.md
#
# This script performs the system-NEUTRAL core only:
#     record  ->  redact-gate  ->  decide what (if anything) is safe to upload
# The actual artifact upload is system-specific and is done by the CALLER, on
# the `upload-path` this script blesses. The caller must NEVER upload the raw
# evidence dir directly — only `upload-path`, which is set to the raw tree ONLY
# when `nlfr redact --check` returned clean, and to a scrubbed mirror otherwise.
#
# Inputs (environment):
#   NLFR_COMMAND    required — the bazel command to wrap, e.g. "bazel test //...".
#   NLFR_RUN_GROUP  run-group label for the recorded evidence (default: nlfr-ci).
#   NLFR_OUTPUT_DIR evidence directory (default: data/nlfr-record).
#   NLFR_STRICT     "true"  (default) => FAIL on redact findings, BEFORE upload.
#                   "false" => scrub to a redacted mirror; bless ONLY the mirror.
#   NLFR_VERSION    pin the PyPI version of nlfr (default: "" => latest).
#   NLFR_CMD        override the nlfr invocation, for tests / advanced use.
#                   Default: "uvx --from nativelink-agent-flight-recorder[==VER] nlfr".
#   NLFR_CI_OUTPUT  file to APPEND `key=value` result lines to. On GitHub set to
#                   "$GITHUB_OUTPUT"; elsewhere a temp file the caller reads.
#                   Default: /dev/stderr (visible, but not machine-consumed).
#
# Outputs (appended to NLFR_CI_OUTPUT as `key=value`, GITHUB_OUTPUT format):
#   evidence-dir   the recorded evidence directory.
#   proof-path     the proof-packet projection, if produced (else empty).
#   redact-status  clean | scrubbed | blocked | empty.
#   upload-path    the ONLY path safe to upload; empty when nothing is safe.
#   record-exit    the wrapped build's honest exit code (faithfully surfaced;
#                   a red build must stay red — the caller re-applies this).
#
# Exit codes:
#   0  redact gate PASSED (clean or scrubbed). The caller uploads `upload-path`
#      (if enabled), then applies `record-exit` as its own result.
#   3  redact gate BLOCKED (strict mode, findings). Nothing safe to upload.
#   2  usage / internal error.
set -uo pipefail

: "${NLFR_COMMAND:?nlfr-ci-gate: NLFR_COMMAND (the bazel command to wrap) is required}"
RUN_GROUP="${NLFR_RUN_GROUP:-nlfr-ci}"
OUTPUT_DIR="${NLFR_OUTPUT_DIR:-data/nlfr-record}"
STRICT="${NLFR_STRICT:-true}"
VERSION="${NLFR_VERSION:-}"
CI_OUTPUT="${NLFR_CI_OUTPUT:-/dev/stderr}"

# Build the nlfr invocation as an array (word-splitting-safe for multi-word
# overrides like "uv run python -m nlfr").
if [[ -n "${NLFR_CMD:-}" ]]; then
  read -r -a NLFR <<<"$NLFR_CMD"
else
  spec="nativelink-agent-flight-recorder"
  [[ -n "$VERSION" ]] && spec="nativelink-agent-flight-recorder==$VERSION"
  NLFR=(uvx --from "$spec" nlfr)
fi

emit() { printf '%s=%s\n' "$1" "$2" >>"$CI_OUTPUT"; }
log() { printf 'nlfr-ci-gate: %s\n' "$*" >&2; }

# --------------------------------------------------------------------------- record
# NLFR mirrors Bazel's own exit code, so a non-zero here is a VALID recording of
# a red build, not a gate failure. Capture it; never let it abort the gate.
log "record: ${NLFR[*]} record --run-group $RUN_GROUP --output-dir $OUTPUT_DIR -- $NLFR_COMMAND"
"${NLFR[@]}" record --run-group "$RUN_GROUP" --output-dir "$OUTPUT_DIR" -- $NLFR_COMMAND
record_exit=$?
log "record exit code: $record_exit"

# Evidence layout is deterministic from the args we passed (no JSON parse, no
# python3 dependency): the evidence dir IS --output-dir; the proof projection is
# projections/proof-<run-group>.json under it.
evidence_dir="$OUTPUT_DIR"
proof_path="$OUTPUT_DIR/projections/proof-$RUN_GROUP.json"
[[ -f "$proof_path" ]] || proof_path=""

# --------------------------------------------------------------------------- redact-gate
redact_status=""
upload_path=""

if [[ ! -e "$evidence_dir" ]]; then
  log "no evidence produced at $evidence_dir — nothing to gate or upload"
  redact_status="empty"
elif [[ "$STRICT" == "true" ]]; then
  log "strict redact gate: ${NLFR[*]} redact --check $evidence_dir"
  if "${NLFR[@]}" redact --check "$evidence_dir"; then
    redact_status="clean"
    upload_path="$evidence_dir"
  else
    redact_status="blocked"
    upload_path=""
  fi
else
  mirror="${evidence_dir%/}-redacted"
  rm -rf "$mirror"
  log "non-strict redact gate: scrubbing $evidence_dir -> $mirror"
  if "${NLFR[@]}" redact "$evidence_dir" "$mirror" \
    && "${NLFR[@]}" redact --check "$mirror"; then
    # Bless ONLY the scrubbed mirror. It contains just the scrubbed text/JSON —
    # binaries and the SQLite spine are skipped by redact and never copied, so
    # the mirror is strictly safer to upload than the raw tree.
    redact_status="scrubbed"
    upload_path="$mirror"
  else
    redact_status="blocked"
    upload_path=""
  fi
fi

# --------------------------------------------------------------------------- decision
emit "evidence-dir" "$evidence_dir"
emit "proof-path" "$proof_path"
emit "redact-status" "$redact_status"
emit "upload-path" "$upload_path"
emit "record-exit" "$record_exit"

log "gate result: redact-status=$redact_status upload-path=${upload_path:-<none>} record-exit=$record_exit"

if [[ "$redact_status" == "blocked" ]]; then
  log "REDACT GATE BLOCKED: secrets/abs-paths found in $evidence_dir — refusing to upload the raw tree."
  exit 3
fi
exit 0
