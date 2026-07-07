"""in-toto Statement projection for NLFR proof packets (GitHub issue #26).

Emits a bare, UNSIGNED, DSSE-ready in-toto attestation Statement (spec v1) whose
subjects are the run group's SHA-256'd manifest artifacts and whose predicate
carries the NLFR proof packet: truth labels, the independent artifact-integrity
verification summary, agent-receipt provenance class (hashes only), and run/
run-group identity.

Positioning (non-negotiable): this is evidence that plugs into an existing
safety-case / provenance stack (SLSA / in-toto / Sigstore). NLFR does NOT sign it
and makes NO claim of auditor acceptance or compliance certification.

Determinism: every subject digest comes from RECORDED evidence (the ``artifacts``
row's ``sha256``), never recomputed at export time; the export-time wall-clock
``generated_at`` of the proof packet is dropped so two exports of the same
database are byte-identical under ``json.dumps(sort_keys=True)``.
"""

from __future__ import annotations

import sys
from sqlite3 import Connection, OperationalError
from typing import Any

from nlfr.agent_receipt import FORBIDDEN_PROMPT_KEYS
from nlfr.projectors.common import rows, run_rows, truth
from nlfr.projectors.proof import export_proof_packet

#: in-toto attestation Statement type (spec v1).
IN_TOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"

#: predicateType URL under a namespace NLFR controls.
PREDICATE_TYPE = (
    "https://github.com/heyitsalec/nativelink-agent-flight-recorder"
    "/attestation/proof-packet/v1"
)

#: Builder identity embedded in the predicate.
BUILDER_ID = "https://github.com/heyitsalec/nativelink-agent-flight-recorder"

#: Positioning guardrail language (non-negotiable — never claim auditor acceptance).
POSITIONING = (
    "Evidence that plugs into your existing safety case / provenance stack "
    "(SLSA / in-toto / Sigstore). NLFR does not sign this attestation and makes "
    "no claim of auditor acceptance or compliance certification."
)

#: Honest limits carried inside the predicate so a downstream reader cannot miss them.
LIMITS = [
    "UNSIGNED by NLFR: wrap and sign externally (e.g. cosign attest-blob) to add a "
    "cryptographic signature; NLFR emits only the bare, DSSE-ready Statement.",
    "Every subject digest is the SHA-256 NLFR recorded when it captured the "
    "artifact; digests are NOT recomputed at export time.",
    "Presence of local_mismatch or missing entries in artifact_verification is "
    "surfaced, not hidden: an attestation over failing evidence is still an honest "
    "attestation of exactly what was recorded.",
]


class EmptySubjectError(ValueError):
    """An in-toto export would have an empty subject, and empties were not allowed.

    A Statement with ``subject: []`` is schema-valid: cosign will happily sign AND
    verify it, yet it proves nothing. A first-timer who exports one by mistake (a
    wrong ``--db`` path, or a ``--run-group`` that matches no recorded group) can
    ship a cryptographically signed attestation over an empty subject. That silent
    failure mode is exactly what this hard error exists to stop — the message names
    the empty run group and lists the run groups that ARE present, turning the
    failure into guidance instead of a one-line, easy-to-miss stderr warning.
    """

    def __init__(self, run_group: str, available: list[dict[str, Any]]) -> None:
        self.run_group = run_group
        self.available = available
        super().__init__(self._render())

    def _render(self) -> str:
        lines = [
            f"nlfr: run group '{self.run_group}' has no recorded artifacts to "
            "attest; refusing to emit an in-toto Statement with an empty subject.",
            "An empty-subject attestation is schema-valid and can be signed and "
            "verified, yet proves nothing — so this is a hard error, not a warning.",
        ]
        if self.available:
            lines.append("Run groups present in this database:")
            lines.extend(
                f"  - {item['run_group']} ({item['run_count']} run(s))"
                for item in self.available
            )
            lines.append(
                "Re-run with one of the above via --run-group. Note: --run-group "
                "is a literal match — there is no 'latest' resolver."
            )
        else:
            lines.append(
                "No run groups are recorded in this database. Record a build first "
                "(e.g. `nlfr record -- bazel test //...`), or point --db at the "
                "right data/nlfr-record/<run-group>/nlfr.sqlite."
            )
        lines.append("List run groups any time with: `nlfr compare index --db <db>`.")
        lines.append(
            "To export the empty Statement anyway (automation edge cases), pass "
            "--allow-empty-subject."
        )
        return "\n".join(lines)


def _available_run_groups(conn: Connection) -> list[dict[str, Any]]:
    """Run groups actually present in the DB, so an empty-subject failure can guide.

    Queries the ``runs`` table directly. A missing/unrelated SQLite file has no
    ``runs`` table; that is reported as "no run groups" rather than a traceback.
    """

    try:
        result = conn.execute(
            """
            SELECT run_group, COUNT(*) AS run_count
            FROM runs
            GROUP BY run_group
            ORDER BY MAX(started_at) DESC, run_group ASC
            """
        ).fetchall()
    except OperationalError:
        return []
    return [
        {"run_group": row["run_group"], "run_count": row["run_count"]}
        for row in result
    ]


def export_in_toto_statement(
    conn: Connection, *, run_group: str, allow_empty_subject: bool = False
) -> dict[str, Any]:
    """Build an unsigned in-toto Statement for a run group's proof packet.

    With ZERO subjects this raises :class:`EmptySubjectError` — a hard error, so a
    vacuous but signable Statement is never emitted by accident. Pass
    ``allow_empty_subject=True`` to restore the old warn-but-export behavior for
    automation that deliberately wants the empty envelope.
    """

    proof = export_proof_packet(conn, run_group=run_group)
    runs = run_rows(conn, run_group)
    run_ids = [run["id"] for run in runs]
    artifacts = rows(conn, "artifacts", run_ids)

    subjects = _subjects(artifacts)
    if not subjects:
        if not allow_empty_subject:
            # An in-toto Statement with an empty subject is schema-valid but
            # vacuous — and cosign will sign and verify it anyway. Fail hard and
            # tell the operator which run groups actually exist.
            raise EmptySubjectError(run_group, _available_run_groups(conn))
        # Opt-in escape hatch: warn on stderr but still export (the old behavior),
        # so automation that deliberately wants the empty envelope can proceed.
        print(
            f"nlfr: run group '{run_group}' has no recorded artifacts; "
            "statement has empty subject (--allow-empty-subject)",
            file=sys.stderr,
        )

    statement = {
        "_type": IN_TOTO_STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": PREDICATE_TYPE,
        "predicate": _predicate(proof, runs),
    }
    # Structural privacy gate: reject the forbidden prompt KEY NAMES
    # (FORBIDDEN_PROMPT_KEYS) at every depth of the tree. This is a key-name
    # gate, not a content scan; raw prompt CONTENT never reaches here because the
    # receipt builder (nlfr.agent_receipt) only ever records the prompt's
    # SHA-256, never the prompt text itself.
    _reject_forbidden_keys(statement, path="statement")
    return statement


def _subjects(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """in-toto subjects: one ResourceDescriptor per recorded manifest artifact.

    The digest is the ``sha256`` NLFR recorded at capture time (never recomputed
    here). Subjects are sorted by (name, digest) for byte-stable output.
    """

    subjects: list[dict[str, Any]] = []
    for artifact in artifacts:
        sha256 = artifact.get("sha256")
        if not _is_sha256(sha256):
            # An artifact without a recomputable SHA-256 cannot be an in-toto
            # sha256 subject; skip rather than emit an invalid digest.
            continue
        name = str(artifact.get("artifact_path") or artifact.get("artifact_key") or "")
        subjects.append(
            {
                "name": name,
                "digest": {"sha256": str(sha256).lower()},
                "annotations": {
                    "nlfr": {
                        "artifact_key": artifact.get("artifact_key"),
                        "size_bytes": artifact.get("size_bytes"),
                        "content_type": artifact.get("content_type"),
                        "recorded_manifest_path": artifact.get("manifest_path"),
                        "source_kind": artifact.get("source_kind"),
                        "confidence": artifact.get("confidence"),
                    }
                },
            }
        )
    subjects.sort(key=lambda item: (item["name"], item["digest"]["sha256"]))
    return subjects


def _predicate(proof: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    """The proof-packet predicate: truth-labeled subset of the proof projection."""

    return {
        "predicate_schema_version": 1,
        "builder": {
            "id": BUILDER_ID,
            "component": "nlfr proof export --format in-toto",
        },
        "run_group": proof.get("run_group"),
        "run_identity": [_run_identity(run) for run in runs],
        "proof_packet": _proof_subset(proof),
        "artifact_verification": _artifact_verification(proof),
        "agent_provenance": _agent_provenance(proof),
        "positioning": POSITIONING,
        "limits": LIMITS,
    }


def _run_identity(run: dict[str, Any]) -> dict[str, Any]:
    """Stable run identity from recorded evidence (recorded timestamps are kept)."""

    return {
        "run_id": run.get("id"),
        "stable_key": run.get("stable_key"),
        "run_group": run.get("run_group"),
        "scenario": run.get("scenario"),
        "mode": run.get("mode"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "ended_at": run.get("ended_at"),
        **truth(run),
    }


def _proof_subset(proof: dict[str, Any]) -> dict[str, Any]:
    """Stable proof-packet subset: drops the export-time wall-clock ``generated_at``.

    The blocks already carry per-block truth labels (source_kind, confidence,
    evidence_refs, redaction_state); the summary carries the artifact-verification
    rollup. Recorded timestamps inside stored block payloads are retained because
    they are recorded evidence, not export wall-clock.
    """

    return {
        "projection_kind": proof.get("projection_kind"),
        "schema_version": proof.get("schema_version"),
        "summary": proof.get("summary"),
        "blocks": proof.get("blocks"),
    }


def _artifact_verification(proof: dict[str, Any]) -> dict[str, Any]:
    """Independent artifact-integrity verification: rollup + per-reference presence."""

    block = _find_block(proof, "artifact_verification")
    payload = block.get("payload") if isinstance(block, dict) else None
    references = payload.get("references") if isinstance(payload, dict) else None
    summary = proof.get("summary") or {}
    result: dict[str, Any] = {
        "summary": summary.get("artifact_verification", {}),
        "references": references or [],
    }
    if isinstance(block, dict):
        result["truth"] = truth(block)
    return result


def _agent_provenance(proof: dict[str, Any]) -> list[dict[str, Any]]:
    """Agent-receipt provenance class per agent_provenance block — hashes only.

    Emits only ``prompt_sha256`` and the receipt provenance summary (itself
    hash/id/usage only). Two independent, mechanically true properties keep raw
    prompt text out of the Statement:

    1. Forbidden prompt KEY NAMES (``FORBIDDEN_PROMPT_KEYS`` = ``prompt``,
       ``raw_prompt``, ``prompt_text``, ``system_prompt``) are structurally
       rejected at every depth of the tree by ``_reject_forbidden_keys`` before
       the Statement is returned. This is a forbidden-key-name gate, not a scan
       of value content.
    2. Raw prompt CONTENT never enters storage in the first place: the receipt
       builder (``nlfr.agent_receipt.build_receipt``) records only the prompt's
       SHA-256 (``prompt_sha256``); the raw prompt is never stored or exported
       (AGENTS.md privacy rule), so there is no prompt-text value anywhere below
       for a content scan to find.
    """

    provenance: list[dict[str, Any]] = []
    for block in proof.get("blocks") or []:
        kind = block.get("kind") or block.get("block_kind")
        if kind != "agent_provenance":
            continue
        payload = block.get("payload") if isinstance(block.get("payload"), dict) else {}
        agent = payload.get("agent") if isinstance(payload.get("agent"), dict) else {}
        provenance.append(
            {
                "block_id": block.get("id"),
                "provenance_class": agent.get("provenance_class"),
                "model": agent.get("model"),
                "model_label_operator": agent.get("model_label_operator"),
                "prompt_sha256": agent.get("prompt_sha256"),
                "receipt": agent.get("receipt"),
                **truth(block),
            }
        )
    return provenance


def _find_block(proof: dict[str, Any], block_id: str) -> dict[str, Any] | None:
    for block in proof.get("blocks") or []:
        if block.get("id") == block_id:
            return block
    return None


def _reject_forbidden_keys(obj: Any, *, path: str) -> None:
    """Raise if any raw-prompt key appears anywhere in the Statement tree."""

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in FORBIDDEN_PROMPT_KEYS:
                raise ValueError(
                    f"in-toto Statement must not contain raw prompt field: {path}.{key}"
                )
            _reject_forbidden_keys(value, path=f"{path}.{key}")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _reject_forbidden_keys(item, path=f"{path}[{index}]")


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True
