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
#   redact-status  clean | scrubbed | blocked | blocked-symlinks | empty.
#   upload-path    the ONLY path safe to upload — always a gate-private,
#                  symlink-free materialized copy (see Symlink safety), never the
#                  live evidence dir. Empty when nothing is safe.
#   record-exit    the wrapped build's honest exit code (faithfully surfaced;
#                   a red build must stay red — the caller re-applies this).
#
# Exit codes:
#   0  redact gate PASSED (clean or scrubbed). The caller uploads `upload-path`
#      (if enabled), then applies `record-exit` as its own result.
#   3  redact gate BLOCKED (strict mode, redact findings). Nothing safe to upload.
#   4  redact gate BLOCKED (strict mode, symlink(s) in the evidence tree). See
#      the symlink note below. Nothing safe to upload.
#   2  usage / internal error.
#
# Symlink safety (TWO layers, no reliance on any uploader follow flag).
# `nlfr redact --check` REPORTS symlinks (skipped:symlink) but exits 0 — it never
# follows them. Native artifact uploaders DO follow them (actions/upload-artifact,
# buildkite-agent, Jenkins archiveArtifacts), so a symlink planted in the
# well-known evidence dir (e.g. data/nlfr-record/.../x -> ~/.aws/creds) would be
# DEREFERENCED and its target bytes shipped inside a "gate-blessed" artifact —
# content the gate never scanned. Two independent layers close this:
#   1. Pre-check BLOCK (static case, loud): `find -type l` before blessing; any
#      symlink present at gate time => blocked-symlinks, exit 4, honest message.
#      Good operator UX — "you have symlinks, strict blocks."
#   2. Materialize-strip (race case, structural): the uploader is NEVER handed
#      the live evidence dir. `upload-path` is a gate-private `mktemp` copy made
#      with `cp -RP` (symlinks copied as symlinks, targets never read) then
#      `find -type l -delete` (every symlink physically stripped). A symlink
#      that races past the pre-check (a detached process the wrapped build left
#      running) cannot reach the uploader, and the copy lives at a path the
#      attacker cannot target. This holds regardless of any uploader follow flag.
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

# Materialize a symlink-free copy of "$1" in a gate-private temp dir, then echo
# its path. TOCTOU-safe upload primitive: the uploader is NEVER handed the live
# evidence dir (whose path the wrapped build knows and a detached background
# process could mutate after the pre-check). Instead:
#   1. `mktemp -d` — an unpredictable path the wrapped build cannot target.
#   2. `cp -RP` — copy preserving symlinks AS symlinks (-P never dereferences,
#      POSIX; verified on BSD + GNU cp), so a symlink's TARGET bytes are never
#      read or copied.
#   3. `find -type l -delete` — physically strip every symlink (static OR
#      raced-in), so no symlink can reach the uploader to be dereferenced.
# Returns non-zero (and blesses nothing) if any step fails or a symlink survives.
materialize_symlink_free() {
  local src="$1" parent staging
  parent="$(mktemp -d "${TMPDIR:-/tmp}/nlfr-ci-stage.XXXXXX")" || return 1
  staging="$parent/upload"
  cp -RP "$src" "$staging" || return 1
  find "$staging" -type l -delete 2>/dev/null || true
  # Fail closed if any symlink somehow survived the strip.
  if find "$staging" -type l 2>/dev/null | grep -q .; then
    log "materialize: a symlink survived the strip under $staging — refusing to bless it."
    return 1
  fi
  printf '%s' "$staging"
}

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
  # Strict mode blesses the RAW tree only when the gate could scan EVERYTHING.
  # Symlinks are scan-blind to `redact --check` (skipped:symlink, exit 0) yet
  # FOLLOWED by native uploaders, so detect them independently and BLOCK first.
  # Pre-check: honest fast-fail for the normal STATIC case. Symlinks present at
  # gate time BLOCK loudly (good operator UX) — the raw tree is scan-blind to
  # them (`redact --check` reports skipped:symlink, exit 0) but native uploaders
  # follow them. This is NOT the race defense: a symlink raced in AFTER this
  # find is caught by the materialize-strip below, not here.
  symlink_list="$(find "$evidence_dir" -type l 2>/dev/null || true)"
  log "strict redact gate: ${NLFR[*]} redact --check $evidence_dir"
  if [[ -n "$symlink_list" ]]; then
    redact_status="blocked-symlinks"
    upload_path=""
    while IFS= read -r link; do
      [[ -n "$link" ]] && log "  symlink: $link -> $(readlink "$link" 2>/dev/null || echo '?')"
    done <<<"$symlink_list"
  elif "${NLFR[@]}" redact --check "$evidence_dir"; then
    # Gate passed. Do NOT hand the live evidence_dir to the uploader (TOCTOU): a
    # symlink raced in after the pre-check would otherwise be dereferenced.
    # Upload a gate-private, symlink-STRIPPED materialized copy instead.
    if staging="$(materialize_symlink_free "$evidence_dir")"; then
      redact_status="clean"
      upload_path="$staging"
    else
      log "could not materialize a symlink-free copy of $evidence_dir — refusing to upload."
      redact_status="blocked"
      upload_path=""
    fi
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
    # The scrubbed mirror already excludes symlinks (redact write-mode never
    # copies one) — but its path (<dir>-redacted) is deterministic and thus
    # attacker-knowable, so still upload a gate-private materialized copy, not
    # the mirror in place. Same TOCTOU-safe uploader contract as strict.
    if staging="$(materialize_symlink_free "$mirror")"; then
      redact_status="scrubbed"
      upload_path="$staging"
    else
      log "could not materialize a symlink-free copy of $mirror — refusing to upload."
      redact_status="blocked"
      upload_path=""
    fi
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

case "$redact_status" in
  blocked)
    log "REDACT GATE BLOCKED: secrets/abs-paths found in $evidence_dir — refusing to upload the raw tree."
    exit 3
    ;;
  blocked-symlinks)
    log "REDACT GATE BLOCKED: symlink(s) under $evidence_dir would be dereferenced by the artifact uploader and ship unscanned target bytes. Refusing to upload the raw tree. Remedies: remove the symlink(s) listed above, or set strict-redact:false — the non-strict scrubbed mirror excludes symlinks entirely."
    exit 4
    ;;
esac
exit 0
