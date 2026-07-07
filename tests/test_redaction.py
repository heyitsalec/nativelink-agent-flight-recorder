"""Tests for the secret-pattern redaction layer (issue #29).

Covers: per-detector positives (synthetic, documented-fake tokens), negative
controls that must never be flagged (SHA digests, Bazel labels, loopback
endpoints, data: URIs, token *counts*), redaction_state transitions, the
``--check`` gate contract, key-scanning semantics, determinism, and a permanent
gate asserting the committed projections carry zero findings.

All "secrets" here are synthetic and documented-fake (AWS's own documentation
example keys, repeated-character fills). None is a live credential shape with a
valid checksum, so none should trip GitHub push protection.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from nlfr.redaction import (
    RedactionConfig,
    redact_json_text,
    redact_payload,
    scrub_local_paths,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "redact-projection.py"

# Roots whose committed *.json must always scan clean under the publish config.
COMMITTED_ROOTS = [
    ROOT / "apps" / "canvas" / "public" / "projections",
    ROOT / "docs" / "proof-samples",
]

# --- documented-fake secret fixtures ---------------------------------------
# AWS canonical documentation example credentials.
FAKE_AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
FAKE_AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # 40 chars, base64-ish
FAKE_GH_TOKEN = "ghp_" + "A" * 36
# Fine-grained PAT: the prefix is assembled from fragments (never a contiguous
# ``github_pat_`` literal) — same technique as the Slack fixture below — so
# GitHub push protection cannot flag this synthetic token, while the runtime
# value still exercises the github_pat detector. Body is 82 chars of [A-Za-z0-9]
# (GitHub's documented 22 + "_" + 59 shape length).
FAKE_GITHUB_PAT = "github" + "_pat_" + ("A1b2C3d4E5" * 9)[:82]
FAKE_GITLAB_PAT = "glpat-" + "EXAMPLE1234567890abcd"
# Assembled from fragments (never a contiguous literal) so GitHub push
# protection cannot match a synthetic-but-real-shaped Slack token; the runtime
# value still exercises the xox[baprs]- detector.
FAKE_SLACK_TOKEN = "xox" + "b-" + "EXAMPLEFAKESLACKTOKENZZ"
FAKE_PEM = "-----BEGIN RSA PRIVATE KEY-----\nFAKEKEYBODYNOTREAL\n-----END RSA PRIVATE KEY-----"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJFWEFNUExFIn0.FAKESIGNATUREEXAMPLE00000"


def _detectors(result) -> set[str]:
    return {finding.detector for finding in result.findings}


# ---------------------------------------------------------------------------
# Per-detector positives
# ---------------------------------------------------------------------------

POSITIVE_CASES = [
    ("aws_access_key_id", {"note": f"key {FAKE_AWS_ACCESS_KEY_ID} used"}),
    ("aws_secret_access_key", {"aws_secret_access_key": FAKE_AWS_SECRET}),
    ("github_token", {"gh": FAKE_GH_TOKEN}),
    ("github_pat", {"gh": FAKE_GITHUB_PAT}),
    ("gitlab_pat", {"gl": FAKE_GITLAB_PAT}),
    ("slack_token", {"sl": FAKE_SLACK_TOKEN}),
    ("private_key_pem", {"pem": FAKE_PEM}),
    ("jwt", {"jwt": FAKE_JWT}),
    ("url_credentials", {"dsn": "postgres://user:s3cr3tpass@db.example.com:5432/app"}),
    ("authorization_credential", {"h": "Authorization: Bearer EXAMPLEFAKEBEARER1234567890"}),
    ("email", {"owner": "alice@example.com"}),
    ("ipv4", {"peer": "203.0.113.42"}),
    ("ipv4", {"peer": "10.1.2.3"}),  # RFC1918 is sensitive
]


@pytest.mark.parametrize("detector, obj", POSITIVE_CASES)
def test_detector_flags_positive(detector: str, obj: dict) -> None:
    result = redact_json_text(json.dumps(obj))
    assert detector in _detectors(result), result.findings
    # The secret span was replaced; the raw secret value is gone from output.
    dumped = json.dumps(result.payload)
    assert f"[REDACTED:{detector}]" in dumped
    for raw in obj.values():
        # url/authorization keep a scheme/prefix, so check the secret sub-token.
        secret_token = str(raw).split()[-1].split("@")[0].split(":")[-1]
        if len(secret_token) >= 12:
            assert secret_token not in dumped


def test_redaction_examples_are_masked_not_leaked() -> None:
    result = redact_json_text(json.dumps({"gh": FAKE_GH_TOKEN}))
    (finding,) = result.findings
    assert FAKE_GH_TOKEN not in finding.excerpt
    assert "[REDACTED:github_token]" in finding.excerpt


# ---------------------------------------------------------------------------
# Negative controls -- must NEVER be flagged
# ---------------------------------------------------------------------------

NEGATIVE_CASES = [
    ("sha256_digest", {"digest": "5b326db8593b9713861de82dea61a2b9d01d04a95f2919dc88f35dba5820932d"}),
    ("sha1_under_secret_key", {"aws_secret_access_key": "a" * 40}),  # pure hex == SHA-1 shape
    # G3: an uppercase / mixed-case 40-hex digest under a credential-ish key must
    # NOT be mislabelled an AWS secret. The SHA reject is case-insensitive.
    ("sha1_upper_under_secret_key", {"aws_secret_access_key": "A" * 40}),
    ("hex40_upper_under_secret_key", {"aws_secret_access_key": "ABCDEF0123456789" * 2 + "ABCDEF01"}),
    ("hex40_mixed_under_secret_key", {"aws_secret_access_key": "AbCdEf0123456789" * 2 + "AbCdEf01"}),
    ("hex64_upper_under_secret_key", {"secret": "ABCDEF0123456789" * 4}),  # 64-hex, uppercase
    ("bazel_label", {"target": "//tasks:escalation_policy_test"}),
    ("bazel_external_repo", {"target": "@local-remote-execution//examples:lre-cc"}),
    ("loopback_grpc", {"flag": "--remote_cache=grpc://127.0.0.1:50051"}),
    ("loopback_ip", {"ip": "127.0.0.1"}),
    ("link_local_ip", {"ip": "169.254.10.20"}),
    ("this_network_ip", {"ip": "0.0.0.0"}),
    ("version_string", {"v": "2.1.170"}),
    ("token_counts", {"input_tokens": 14965, "output_tokens": 471}),
    ("script_filename", {"proof_script": "record-agent-change.sh"}),
    (
        "data_image_base64",
        {
            "asset": "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        },
    ),
]


@pytest.mark.parametrize("label, obj", NEGATIVE_CASES)
def test_negative_control_not_flagged(label: str, obj: dict) -> None:
    result = redact_json_text(json.dumps(obj))
    assert result.findings == [], f"{label}: unexpected {[f.detector for f in result.findings]}"
    assert result.payload == obj  # bytes-identical passthrough


def test_sha256_digest_stream_untouched() -> None:
    """A dict full of 64-hex digests (NLFR's common shape) is passed through."""
    obj = {"a": "0" * 64, "b": "f" * 64, "c": "deadbeef" * 8}
    result = redact_json_text(json.dumps(obj))
    assert result.findings == []


# ---------------------------------------------------------------------------
# G1: fine-grained github_pat_ tokens (invisible to the classic gh_ detector)
# ---------------------------------------------------------------------------


def test_github_fine_grained_pat_is_detected() -> None:
    """github_pat_ tokens are their own shape; the classic gh[pousr]_ detector
    cannot see them, so a dedicated detector must fire."""
    assert len(FAKE_GITHUB_PAT) == len("github_pat_") + 82  # documented shape
    result = redact_json_text(json.dumps({"note": FAKE_GITHUB_PAT}))
    assert "github_pat" in _detectors(result)
    dumped = json.dumps(result.payload)
    assert "[REDACTED:github_pat]" in dumped
    assert FAKE_GITHUB_PAT not in dumped


def test_github_pat_prefix_lookalikes_not_flagged() -> None:
    """The bare prefix, a short tail, or a plain word beginning 'github_pat...'
    is not a token and must not be flagged."""
    obj = {
        "a": "github_pat_short",  # tail < 50 chars
        "b": "github_pattern_matcher",  # not the github_pat_ prefix
    }
    assert redact_json_text(json.dumps(obj)).findings == []


# ---------------------------------------------------------------------------
# G2: AWS secret pasted into narrative / log text (in-text marker path)
# ---------------------------------------------------------------------------


def test_aws_secret_detected_in_narrative_log_text() -> None:
    """A secret captured in stdout/log text — credential *name* in the body, an
    innocuous JSON key — is caught by the in-text ``KEY=value`` marker path."""
    obj = {"stdout": f"env dump: aws_secret_access_key={FAKE_AWS_SECRET} (captured)"}
    result = redact_json_text(json.dumps(obj))
    assert "aws_secret_access_key" in _detectors(result)
    assert FAKE_AWS_SECRET not in json.dumps(result.payload)


def test_aws_secret_detected_in_embedded_json_string() -> None:
    """A ``"SecretAccessKey": "…"`` pair embedded *inside* a string value (e.g. a
    captured API response) is caught even though the outer key is innocuous."""
    obj = {"response_body": f'{{"SecretAccessKey": "{FAKE_AWS_SECRET}", "ok": true}}'}
    result = redact_json_text(json.dumps(obj))
    assert "aws_secret_access_key" in _detectors(result)
    assert FAKE_AWS_SECRET not in json.dumps(result.payload)


def test_aws_secret_in_text_still_rejects_hex_digest() -> None:
    """The in-text path shares the digest reject: a marker followed by a pure-hex
    (any case) 40-char value is a digest, not a secret."""
    obj = {"stdout": "secret_access_key=" + "ABCDEF0123456789" * 2 + "ABCDEF01"}
    assert redact_json_text(json.dumps(obj)).findings == []


# ---------------------------------------------------------------------------
# redaction_state transitions
# ---------------------------------------------------------------------------


def test_redaction_state_transitions() -> None:
    doc = {
        "blocks": [
            {"id": "clean", "redaction_state": "safe", "summary": "nothing here"},
            {"id": "safe_hit", "redaction_state": "safe", "tok": FAKE_GH_TOKEN},
            {"id": "blocked_hit", "redaction_state": "blocked", "tok": FAKE_GH_TOKEN},
            {"id": "unknown_hit", "redaction_state": "unknown", "k": FAKE_AWS_ACCESS_KEY_ID},
        ]
    }
    states = {b["id"]: b["redaction_state"] for b in redact_payload(doc).payload["blocks"]}
    assert states == {
        "clean": "safe",  # no redaction -> unchanged
        "safe_hit": "redacted",  # safe -> redacted
        "blocked_hit": "blocked",  # blocked never downgraded
        "unknown_hit": "redacted",  # unknown -> redacted (now known)
    }


def test_redaction_state_scoped_to_nearest_carrier() -> None:
    """A redaction marks the innermost object that carries redaction_state."""
    doc = {
        "id": "outer",
        "redaction_state": "safe",
        "child": {"id": "inner", "redaction_state": "safe", "tok": FAKE_GH_TOKEN},
        "sibling": "clean value",
    }
    out = redact_payload(doc).payload
    assert out["child"]["redaction_state"] == "redacted"
    assert out["redaction_state"] == "safe"  # outer delegates the redacted region to inner


def test_check_mode_never_mutates_state() -> None:
    doc = {"redaction_state": "safe", "tok": FAKE_GH_TOKEN}
    result = redact_payload(doc, RedactionConfig(redact=False))
    assert result.payload["redaction_state"] == "safe"
    assert result.findings  # but it is still reported


# ---------------------------------------------------------------------------
# Key scanning: secret-shaped keys are reported, never rewritten
# ---------------------------------------------------------------------------


def test_secret_shaped_key_reported_not_rewritten() -> None:
    doc = {FAKE_AWS_ACCESS_KEY_ID: "some value"}
    result = redact_payload(doc)
    key_findings = [f for f in result.findings if f.location == "key"]
    assert len(key_findings) == 1
    assert key_findings[0].detector == "aws_access_key_id"
    # The key itself is preserved verbatim so consumers do not break.
    assert FAKE_AWS_ACCESS_KEY_ID in result.payload


# ---------------------------------------------------------------------------
# PII tier defaults and hostname opt-in
# ---------------------------------------------------------------------------


def test_hostname_off_by_default_on_when_opted_in() -> None:
    obj = {"endpoint": "grpc://cache.prod.internal:443"}
    assert redact_json_text(json.dumps(obj)).findings == []
    opted = redact_json_text(json.dumps(obj), RedactionConfig(enable_hostname=True))
    assert "hostname" in _detectors(opted)


def test_pii_toggles() -> None:
    obj = {"owner": "alice@example.com", "peer": "203.0.113.42"}
    assert _detectors(redact_json_text(json.dumps(obj))) == {"email", "ipv4"}
    assert redact_json_text(json.dumps(obj), RedactionConfig(enable_email=False, enable_ip=False)).findings == []


def test_hostname_opt_in_still_ignores_tool_and_file_names() -> None:
    """Opt-in hostname must not mislabel filenames / module paths / versions."""
    obj = {
        "a": "record-agent-change.sh",
        "b": "nlfr.ingest.worker",
        "c": "receipt.v1",
        "d": "flake.nix",
    }
    result = redact_json_text(json.dumps(obj), RedactionConfig(enable_hostname=True))
    assert result.findings == [], [f.excerpt for f in result.findings]


# ---------------------------------------------------------------------------
# Determinism + home-path backward compatibility
# ---------------------------------------------------------------------------


def test_output_is_deterministic() -> None:
    doc = {"z": FAKE_GH_TOKEN, "a": FAKE_AWS_ACCESS_KEY_ID, "m": "alice@example.com"}
    first = json.dumps(redact_payload(doc).payload, sort_keys=True)
    second = json.dumps(redact_payload(doc).payload, sort_keys=True)
    assert first == second


def test_home_path_scrub_preserved() -> None:
    obj = {"artifact_root": "/Users/example/person/project/data/run/artifacts"}
    result = redact_json_text(json.dumps(obj))
    assert result.payload["artifact_root"] == "${HOME}/person/project/data/run/artifacts"
    assert "home_path" in _detectors(result)


# ---------------------------------------------------------------------------
# CLI contract (subprocess) -- default redact + --check gate
# ---------------------------------------------------------------------------


def _run_cli(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_backward_compatible_redact(tmp_path: Path) -> None:
    src = tmp_path / "raw.json"
    dst = tmp_path / "out.json"
    src.write_text(json.dumps({"artifact_root": "/Users/example/x/y"}), encoding="utf-8")
    result = _run_cli(str(src), str(dst))
    assert result.returncode == 0, result.stderr
    payload = json.loads(dst.read_text(encoding="utf-8"))
    assert payload["artifact_root"] == "${HOME}/x/y"


def test_cli_redacts_secret_and_flips_state(tmp_path: Path) -> None:
    src = tmp_path / "raw.json"
    dst = tmp_path / "out.json"
    src.write_text(
        json.dumps({"redaction_state": "safe", "tok": FAKE_GH_TOKEN}),
        encoding="utf-8",
    )
    result = _run_cli(str(src), str(dst))
    assert result.returncode == 0, result.stderr
    payload = json.loads(dst.read_text(encoding="utf-8"))
    assert payload["tok"] == "[REDACTED:github_token]"
    assert payload["redaction_state"] == "redacted"
    assert "github_token=1" in result.stdout


def test_cli_check_fails_on_seeded_secret(tmp_path: Path) -> None:
    src = tmp_path / "seed.json"
    src.write_text(
        json.dumps({"blocks": [{"redaction_state": "safe", "note": f"key {FAKE_AWS_ACCESS_KEY_ID}"}]}),
        encoding="utf-8",
    )
    result = _run_cli("--check", str(src))
    assert result.returncode == 1
    # Report shape: detector, JSON path, masked excerpt -- never the raw secret.
    assert "aws_access_key_id" in result.stderr
    assert "$.blocks[0].note" in result.stderr
    assert "[REDACTED:aws_access_key_id]" in result.stderr
    assert FAKE_AWS_ACCESS_KEY_ID not in result.stderr


def test_cli_check_writes_nothing(tmp_path: Path) -> None:
    src = tmp_path / "seed.json"
    out = tmp_path / "should-not-exist.json"
    src.write_text(json.dumps({"tok": FAKE_GH_TOKEN}), encoding="utf-8")
    _run_cli("--check", str(src), str(out))
    assert not out.exists()


def test_cli_check_passes_on_clean_input(tmp_path: Path) -> None:
    src = tmp_path / "clean.json"
    src.write_text(json.dumps({"digest": "a" * 64, "label": "//foo:bar"}), encoding="utf-8")
    result = _run_cli("--check", str(src))
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Permanent gate: committed projections + proof samples scan clean
# ---------------------------------------------------------------------------


def _committed_json_files() -> list[Path]:
    files: list[Path] = []
    for root in COMMITTED_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("*.json")))
    return files


def test_gate_roots_are_populated() -> None:
    # Guard against the gate silently passing because it found nothing to scan.
    assert len(_committed_json_files()) >= 10


@pytest.mark.parametrize(
    "json_path",
    _committed_json_files(),
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_committed_projection_has_no_findings(json_path: Path) -> None:
    """Every committed projection must scan clean under the publish config."""
    result = redact_payload(
        json.loads(json_path.read_text(encoding="utf-8")),
        RedactionConfig(redact=False),
    )
    assert result.findings == [], [f.format_line() for f in result.findings]


# --- scrub_local_paths: projection-boundary local-path scrubbing (#60) ------


def test_scrub_local_paths_replaces_abs_path_preserving_basename():
    out, count = scrub_local_paths("/private/tmp/run/artifacts/bazel-bep.json")
    assert out == "[REDACTED:abs_path]/bazel-bep.json"
    assert count == 1


def test_scrub_local_paths_covers_home_and_var_folders_the_home_scrub_misses():
    assert scrub_local_paths("/Users/alec/proj/workspace")[0] == "[REDACTED:abs_path]/workspace"
    assert scrub_local_paths("/home/ci/work/repo")[0] == "[REDACTED:abs_path]/repo"
    assert scrub_local_paths("/var/folders/aa/bb/T/ws")[0] == "[REDACTED:abs_path]/ws"


def test_scrub_local_paths_scrubs_abs_path_inside_a_flag_value():
    out, count = scrub_local_paths("--build_event_json_file=/tmp/a/b/bep.json")
    assert out == "--build_event_json_file=[REDACTED:abs_path]/bep.json"
    assert count == 1


def test_scrub_local_paths_preserves_labels_endpoints_and_relative_paths():
    for token in (
        "//tasks:priority_test",
        "--remote_cache=grpc://127.0.0.1:50051",
        "--remote_executor=grpc://host.internal:50051",
        "https://example.com/path/to/thing",
        "./relative/path/file.txt",
        "../up/one/file",
        "nlfr.ingest.worker",
        "receipt.v1",
        "bazel",
        "test",
    ):
        assert scrub_local_paths(token) == (token, 0), token


def test_scrub_local_paths_is_idempotent():
    once, _ = scrub_local_paths("/private/tmp/x/y/bep.json")
    twice, count = scrub_local_paths(once)
    assert twice == once
    assert count == 0


def test_scrub_local_paths_roots_catches_single_segment_root_without_corruption():
    out, count = scrub_local_paths("/data", roots=["/data"])
    assert out == "[REDACTED:abs_path]/data"
    assert count == 1
    # A short root must never corrupt a longer word that merely starts with it.
    assert scrub_local_paths("/application/main.py", roots=["/app"])[0] == "[REDACTED:abs_path]/main.py"
    # roots stays idempotent too.
    once, _ = scrub_local_paths("/data", roots=["/data"])
    twice, n2 = scrub_local_paths(once, roots=["/data"])
    assert twice == once
    assert n2 == 0


def test_scrub_local_paths_passes_non_strings_through():
    assert scrub_local_paths(123) == (123, 0)
    assert scrub_local_paths(None) == (None, 0)
