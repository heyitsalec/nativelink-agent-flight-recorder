"""Enforce contracts/*.v1.json against REAL exporter output (GitHub issue #27).

Before this file, nothing validated any exported payload against the versioned
JSON Schemas under ``contracts/`` — schema drift was undetectable. Each test here
produces a payload through the *actual* projector/exporter code path (fixture-
backed, from a temporary SQLite built with the same ``upsert_*`` ingest helpers
the other tests use) and validates it against its contract with a JSON Schema
Draft 2020-12 validator. A negative-control test mutates a valid payload and
asserts the validator REJECTS it, proving the gate can actually fail.

Contract → producer → exporter mapping (from
docs/wiki/reference/contracts/README.md, verified against the code):

* canvas_projection.v1.json        <- projectors/graph.py  export_action_graph
* proof_packet.v1.json             <- projectors/proof.py  export_proof_packet
* compare_projection.v1.json       <- projectors/compare.py export_compare_projection
* agent_receipt.v1.json            <- agent_receipt.py     build_receipt
* artifact_manifest.v1.json        <- artifacts.py         write_artifact/read_manifest
* in_toto_proof_predicate.v1.json  <- projectors/in_toto.py export_in_toto_statement

The validation runway export (projection_kind ``validation_runway``) has no
contract file and is not in the contracts index; see
``test_runway_export_is_uncontracted`` for the honest status.

Contract policy — additive by design (do NOT mistake permissiveness for oversight):
Most contracts here deliberately omit ``additionalProperties: false``. This repo's
contract policy is intentionally ADDITIVE: fields have been (and will be) added to
projections without a breaking version bump, so consumers MUST tolerate unknown
keys and validation checks the presence/type/enum of KNOWN fields, not closure.
The one place strictness is deliberately tight is redaction/privacy: agent_receipt
and the in-toto predicate forbid raw-prompt key names and pin prompt_sha256 to a
64-char lowercase hex digest. compare_projection tightens the numeric SUBSTANCE of
each dimension (counts are integers >= 0, hit rates are numbers in [0,1], deltas are
signed) while still permitting additive extra keys. See
docs/wiki/reference/contracts/README.md for the full policy statement.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"

# Guarantee sibling test modules are importable regardless of pytest import mode,
# so the idiomatic fixtures are reused (not duplicated).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from nlfr.agent_receipt import build_receipt, sha256_text  # noqa: E402
from nlfr.artifacts import read_manifest, write_artifact  # noqa: E402
from nlfr.db import connect, initialize  # noqa: E402
from nlfr.db.ingest import upsert_cache_event, upsert_run  # noqa: E402
from nlfr.projectors import (  # noqa: E402
    export_action_graph,
    export_in_toto_statement,
    export_proof_packet,
    export_validation_runway,
)
from nlfr.projectors.compare import export_compare_projection  # noqa: E402

# Reused idiomatic fixtures — real ingest seeds, not hand-written payloads.
from test_in_toto_export import RUN_GROUP as IN_TOTO_RUN_GROUP  # noqa: E402
from test_in_toto_export import seed_db as seed_in_toto_db  # noqa: E402
from test_projectors import seed_agent_loop_db, seed_projection_db  # noqa: E402


def _validator(contract_name: str) -> Draft202012Validator:
    """Load a contract, assert it is itself a valid JSON Schema, return a validator."""

    schema = json.loads((CONTRACTS / contract_name).read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _stub_cli_result() -> dict[str, object]:
    """A deterministic parsed ``claude -p --output-format json`` result.

    Fixed bytes only — no live CLI call. Mirrors tests/test_agent_receipt.py.
    """

    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 4200,
        "duration_api_ms": 3100,
        "num_turns": 1,
        "result": "Done.\n\n```python\nVALUE = 1\n```\n",
        "session_id": "11111111-2222-3333-4444-555555555555",
        "total_cost_usd": 0.01,
        "usage": {
            "input_tokens": 321,
            "output_tokens": 45,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 100,
        },
        "modelUsage": {"claude-sonnet-4-5-20250929": {"output_tokens": 45}},
    }


def _seed_compare_db(tmp_path: Path):
    """Two run groups with recorded cache evidence -> a real compare projection."""

    conn = initialize(connect(tmp_path / "compare.sqlite"))
    for group, hits, misses in (("left", 1, 1), ("right", 2, 0)):
        run_id = upsert_run(
            conn,
            stable_key=f"run:{group}",
            run_group=group,
            scenario="cold-cache" if group == "left" else "warm-cache",
            mode="cache-only",
            status="completed",
            source_kind="collectable_v1",
            confidence="high",
            evidence_refs=[f"artifact:{group}.json"],
            redaction_state="safe",
        )
        for index in range(hits):
            upsert_cache_event(
                conn,
                stable_key=f"cache:{group}:hit:{index}",
                run_id=run_id,
                event_key=f"{group}-hit-{index}",
                event_kind="action_cache",
                hit=True,
                source_kind="derived_v1",
                confidence="medium",
                evidence_refs=["bep:cache"],
                redaction_state="safe",
            )
        for index in range(misses):
            upsert_cache_event(
                conn,
                stable_key=f"cache:{group}:miss:{index}",
                run_id=run_id,
                event_key=f"{group}-miss-{index}",
                event_kind="action_cache",
                hit=False,
                source_kind="derived_v1",
                confidence="medium",
                evidence_refs=["bep:cache"],
                redaction_state="safe",
            )
    return conn


def _dimension(payload: dict[str, object], dim_id: str) -> dict[str, object]:
    """Return the compare dimension with the given id (fails loudly if absent)."""

    for dim in payload["dimensions"]:  # type: ignore[index]
        if dim.get("id") == dim_id:
            return dim
    raise AssertionError(f"compare payload has no dimension id={dim_id!r}")


# Committed compare-projection samples audited against the TIGHTENED schema.
# Relative to ROOT; any that exist must still validate (regression guard so the
# tightened numeric constraints never silently diverge from shipped evidence).
_COMMITTED_COMPARE_SAMPLES = (
    "tests/fixtures/compare/compare-projection.json",
    "docs/proof-samples/compare-projection-sample.json",
    "apps/canvas/public/projections/compare-projection.json",
    "tests/fixtures/compare-agent-runs/projections/compare-canvas-dev-vs-agent-bugfix-1.json",
)


# --------------------------------------------------------------------------- #
# Real exporter output vs. its contract
# --------------------------------------------------------------------------- #


def test_action_graph_export_validates_against_canvas_contract(tmp_path: Path) -> None:
    """graph.py action_graph output satisfies canvas_projection.v1.json."""

    validator = _validator("canvas_projection.v1.json")
    graph = export_action_graph(seed_agent_loop_db(tmp_path), run_group="agent-loop")
    assert graph["projection_kind"] == "action_graph"
    assert graph["nodes"] and graph["edges"]
    validator.validate(graph)


def test_action_graph_generic_seed_validates(tmp_path: Path) -> None:
    """A second, differently-shaped run group also validates against the contract."""

    validator = _validator("canvas_projection.v1.json")
    graph = export_action_graph(seed_projection_db(tmp_path), run_group="latest")
    validator.validate(graph)


def test_proof_packet_export_validates_against_contract(tmp_path: Path) -> None:
    """proof.py proof_packet output satisfies proof_packet.v1.json."""

    validator = _validator("proof_packet.v1.json")
    proof = export_proof_packet(seed_projection_db(tmp_path), run_group="latest")
    assert proof["projection_kind"] == "proof_packet"
    assert proof["blocks"]
    validator.validate(proof)


def test_compare_export_validates_against_contract(tmp_path: Path) -> None:
    """compare.py compare output satisfies the NEW compare_projection.v1.json."""

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    assert payload["projection_kind"] == "compare"
    assert len(payload["dimensions"]) == 5
    # Root and every dimension are derived_v1 (README invariant).
    assert payload["source_kind"] == "derived_v1"
    assert all(dim["source_kind"] == "derived_v1" for dim in payload["dimensions"])
    validator.validate(payload)


def test_agent_receipt_stub_path_validates_against_contract() -> None:
    """A deterministic stub-CLI receipt (simulated_v1) satisfies agent_receipt.v1.json."""

    validator = _validator("agent_receipt.v1.json")
    receipt = build_receipt(
        cli_result=_stub_cli_result(),
        prompt_sha256=sha256_text("prompt whose bytes are never stored"),
        cli_name="spark-stub-claude.sh",
        cli_version="stub-cli 0.0.1",
        requested_model="opus",
        sanitized_command=["claude", "-p", "<prompt:sha256>", "--output-format", "json"],
        status="success",
        captured_at="2026-07-06T00:00:00.000000Z",
    )
    assert receipt["source_kind"] == "simulated_v1"
    assert receipt["redaction_state"] == "redacted"
    validator.validate(receipt)


def test_agent_receipt_live_path_validates_against_contract() -> None:
    """A live-CLI receipt (collectable_v1) also satisfies agent_receipt.v1.json."""

    validator = _validator("agent_receipt.v1.json")
    receipt = build_receipt(
        cli_result=_stub_cli_result(),
        prompt_sha256=sha256_text("prompt whose bytes are never stored"),
        cli_name="claude",
        cli_version="2.1.162 (Claude Code)",
        requested_model=None,
        sanitized_command=["claude", "-p", "<prompt:sha256>", "--output-format", "json"],
        status="success",
        captured_at="2026-07-06T00:00:00.000000Z",
    )
    assert receipt["source_kind"] == "collectable_v1"
    validator.validate(receipt)


def test_artifact_manifest_validates_against_contract(tmp_path: Path) -> None:
    """artifacts.py write_artifact + read_manifest output satisfies the contract."""

    validator = _validator("artifact_manifest.v1.json")
    root = tmp_path / "artifacts"
    write_artifact(
        root,
        artifact_key="run.json",
        data=b'{"run": "contract-demo"}\n',
        producer_command=["nlfr", "record"],
        config_hash=None,
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["manifest:run"],
    )
    write_artifact(
        root,
        artifact_key="logs/bazel.stdout.txt",
        data="INFO: Build completed successfully\n",
        producer_command=["bazel", "build", "//..."],
        config_hash="deadbeef",
        redaction_state="safe",
        source_kind="collectable_v1",
        confidence="high",
        evidence_refs=["manifest:bazel.stdout.txt"],
    )
    manifest = read_manifest(root)
    assert manifest["schema_version"] == 1
    assert len(manifest["artifacts"]) == 2
    validator.validate(manifest)


def test_in_toto_predicate_validates_against_contract(tmp_path: Path) -> None:
    """in_toto.py Statement's predicate satisfies in_toto_proof_predicate.v1.json.

    The contract's root object IS the predicate (the in-toto Statement wrapper is
    documented in ``$defs.in_toto_statement`` and its ``predicate`` self-refs the
    root via ``$ref: "#"``). The Statement envelope shape itself is asserted
    structurally in tests/test_in_toto_export.py — this test adds the missing
    JSON-Schema validation of the real predicate.
    """

    validator = _validator("in_toto_proof_predicate.v1.json")
    conn, _ = seed_in_toto_db(tmp_path)
    statement = export_in_toto_statement(conn, run_group=IN_TOTO_RUN_GROUP)
    predicate = statement["predicate"]
    # Exercises verified / mismatch / missing / remote references + agent provenance.
    assert predicate["artifact_verification"]["summary"]["mismatched"] == 1
    assert predicate["agent_provenance"]
    validator.validate(predicate)


# --------------------------------------------------------------------------- #
# Negative controls — the gate must be able to FAIL
# --------------------------------------------------------------------------- #


def test_negative_control_dropped_truth_field_is_rejected(tmp_path: Path) -> None:
    """Dropping a required truth-label field from a node must fail validation."""

    validator = _validator("canvas_projection.v1.json")
    graph = export_action_graph(seed_agent_loop_db(tmp_path), run_group="agent-loop")
    validator.validate(graph)  # baseline: the real payload is valid

    mutated = copy.deepcopy(graph)
    del mutated["nodes"][0]["redaction_state"]  # drop a required truth label
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_negative_control_wrong_enum_is_rejected(tmp_path: Path) -> None:
    """Injecting a value outside the source_kind enum must fail validation."""

    validator = _validator("proof_packet.v1.json")
    proof = export_proof_packet(seed_projection_db(tmp_path), run_group="latest")
    validator.validate(proof)  # baseline

    mutated = copy.deepcopy(proof)
    mutated["blocks"][0]["source_kind"] = "totally_made_up_kind"
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_negative_control_missing_required_root_field_is_rejected(tmp_path: Path) -> None:
    """Dropping a required root field from the compare projection must fail."""

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    validator.validate(payload)  # baseline

    mutated = copy.deepcopy(payload)
    del mutated["dimensions"]
    assert not validator.is_valid(mutated)


# --- F1: the numeric substance of each dimension is now actually enforced --- #
# The old $defs.dimension left/right/delta were bare {"type":"object"}, so every
# metric could be replaced with a string, a count could go negative, a hit_rate
# could exceed 1, and left could be emptied — all while validating. These controls
# prove the tightened per-dimension schema rejects each of those.


def test_negative_control_string_in_metric_is_rejected(tmp_path: Path) -> None:
    """A numeric cache metric replaced with a string must fail validation."""

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    validator.validate(payload)  # baseline: real payload valid under tightened schema

    mutated = copy.deepcopy(payload)
    _dimension(mutated, "cache_metrics")["left"]["metrics"]["hits"] = "NOT_A_NUMBER"
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_negative_control_empty_left_is_rejected(tmp_path: Path) -> None:
    """An emptied dimension side must fail: the exporter always emits its keys."""

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    validator.validate(payload)

    mutated = copy.deepcopy(payload)
    _dimension(mutated, "run_counts")["left"] = {}
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_negative_control_negative_count_is_rejected(tmp_path: Path) -> None:
    """A negative run COUNT is rejected — while a negative run-count DELTA stays valid.

    Models reality: counts cannot be negative (minimum 0), but a right-minus-left
    delta legitimately can, so the schema must not over-constrain deltas.
    """

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    validator.validate(payload)

    bad_count = copy.deepcopy(payload)
    _dimension(bad_count, "run_counts")["left"]["runs"] = -999999
    assert not validator.is_valid(bad_count)

    # A negative delta is honest reality and MUST remain valid.
    negative_delta = copy.deepcopy(payload)
    _dimension(negative_delta, "run_counts")["delta"]["runs"] = -999999
    validator.validate(negative_delta)


def test_negative_control_hit_rate_above_one_is_rejected(tmp_path: Path) -> None:
    """A hit_rate outside [0,1] must fail validation."""

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    validator.validate(payload)

    mutated = copy.deepcopy(payload)
    _dimension(mutated, "cache_metrics")["left"]["metrics"]["hit_rate"] = 1.5
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_committed_compare_samples_validate_against_tightened_contract() -> None:
    """Every committed compare-projection sample still validates under the tightened schema.

    Audit guard: the F1 tightening was derived from the real exporter, so the shipped
    sample files must remain valid. If one ever fails here, fix the producer or the
    sample — never loosen the contract back toward vacuity.
    """

    validator = _validator("compare_projection.v1.json")
    seen = 0
    for rel in _COMMITTED_COMPARE_SAMPLES:
        path = ROOT / rel
        if not path.exists():
            continue
        sample = json.loads(path.read_text(encoding="utf-8"))
        assert sample.get("projection_kind") == "compare", rel
        validator.validate(sample)  # raises ValidationError naming the file's field
        seen += 1
    assert seen, "no committed compare-projection samples were found to audit"


def test_negative_control_forbidden_prompt_key_rejected_by_receipt_contract() -> None:
    """agent_receipt.v1.json's ``not`` clause rejects a leaked raw-prompt key."""

    validator = _validator("agent_receipt.v1.json")
    receipt = build_receipt(
        cli_result=_stub_cli_result(),
        prompt_sha256=sha256_text("p"),
        cli_name="claude",
        cli_version="x",
        requested_model=None,
        sanitized_command=["claude", "-p", "<prompt:sha256>"],
        status="success",
        captured_at="2026-07-06T00:00:00.000000Z",
    )
    validator.validate(receipt)  # baseline

    mutated = copy.deepcopy(receipt)
    mutated["prompt"] = "the raw prompt text leaked in"
    assert not validator.is_valid(mutated)


# --- F3: the in-toto predicate now mirrors the receipt's redaction strictness --- #
# agent_provenance_entry.prompt_sha256 was type-only (any string); the entry had no
# forbidden-raw-prompt-key clause. It now pins the 64-hex pattern and forbids raw
# prompt key names, matching agent_receipt.v1.json.


def test_negative_control_non_hex_prompt_sha256_rejected_by_predicate(tmp_path: Path) -> None:
    """in_toto_proof_predicate.v1.json now rejects a non-hex prompt_sha256."""

    validator = _validator("in_toto_proof_predicate.v1.json")
    conn, _ = seed_in_toto_db(tmp_path)
    predicate = export_in_toto_statement(conn, run_group=IN_TOTO_RUN_GROUP)["predicate"]
    assert predicate["agent_provenance"]
    validator.validate(predicate)  # baseline: real predicate valid under tightened schema

    mutated = copy.deepcopy(predicate)
    mutated["agent_provenance"][0]["prompt_sha256"] = "not-a-64-char-lowercase-hex-digest"
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


def test_negative_control_raw_prompt_key_in_provenance_entry_rejected(tmp_path: Path) -> None:
    """A provenance entry carrying a raw ``prompt`` key must fail validation."""

    validator = _validator("in_toto_proof_predicate.v1.json")
    conn, _ = seed_in_toto_db(tmp_path)
    predicate = export_in_toto_statement(conn, run_group=IN_TOTO_RUN_GROUP)["predicate"]
    validator.validate(predicate)  # baseline

    mutated = copy.deepcopy(predicate)
    mutated["agent_provenance"][0]["prompt"] = "the raw prompt text leaked into the entry"
    assert not validator.is_valid(mutated)
    with pytest.raises(ValidationError):
        validator.validate(mutated)


# --------------------------------------------------------------------------- #
# Schema-of-schemas + uncontracted-export honesty
# --------------------------------------------------------------------------- #


def test_every_contract_is_a_valid_json_schema() -> None:
    """Every contracts/*.json is itself a structurally valid Draft 2020-12 schema."""

    contract_files = sorted(CONTRACTS.glob("*.json"))
    assert contract_files, "no contract files found under contracts/"
    for path in contract_files:
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema", path.name
        assert schema["title"].startswith("NLFR"), path.name
        # check_schema raises SchemaError if the document is not a valid schema.
        Draft202012Validator.check_schema(schema)


def test_runway_export_is_uncontracted(tmp_path: Path) -> None:
    """The validation runway export has no contract and is NOT a canvas projection.

    Documents an honest gap: runway (projection_kind ``validation_runway``) is not
    in the contracts index and has no schema file. It is a distinct shape (lanes +
    events, not nodes + edges), so it cannot borrow canvas_projection.v1.json.
    Authoring a runway contract is intentionally out of this PR's write scope.
    """

    runway = export_validation_runway(seed_projection_db(tmp_path), run_group="latest")
    assert runway["projection_kind"] == "validation_runway"
    assert "lanes" in runway and "events" in runway
    assert not (CONTRACTS / "runway.v1.json").exists()
    # It genuinely does not satisfy the canvas contract (distinct projection_kind).
    canvas = _validator("canvas_projection.v1.json")
    assert not canvas.is_valid(runway)


def test_negative_control_unknown_dimension_id_is_rejected(tmp_path: Path) -> None:
    """An unknown dimension id must not silently bypass per-dimension tightening.

    The per-dimension if/then constraints key on ``dimension.id``; without the
    enum on ``dimension_base.id`` a sixth/typo'd id would validate against only
    the loose base shape — reopening the vacuity this contract exists to close.
    """

    validator = _validator("compare_projection.v1.json")
    payload = export_compare_projection(_seed_compare_db(tmp_path), "left", "right")
    validator.validate(payload)

    rogue = copy.deepcopy(payload)
    dimension = copy.deepcopy(_dimension(rogue, "run_counts"))
    dimension["id"] = "totally_unknown_dimension_id"
    dimension["left"] = {"anything": "goes"}
    rogue["dimensions"].append(dimension)
    assert not validator.is_valid(rogue)
