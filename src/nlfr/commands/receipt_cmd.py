"""`nlfr receipt import` — attach an externally produced agent receipt.

Cloud and pod builds run the agent where NLFR isn't. When wrapping the
invocation in-pod with ``nlfr agent-invoke`` is impossible, the receipt file
(``nlfr.agent_receipt.v1``) can be moved as a build artifact and imported
here. The honesty contract is strict:

* the receipt is schema- and privacy-validated (``validate_receipt``) before
  anything is written — a rejected receipt writes nothing;
* the provenance class is ALWAYS ``receipt_imported_v1``. It is never
  ``receipt_verified_v1`` (reserved for invocations NLFR itself observed) and
  the receipt summary is stamped ``live: false`` / ``observed_by_nlfr:
  false`` so graph/compare projections render ``receipt_verified: false``.
  ``is_live_receipt`` is deliberately never consulted on this path — a
  well-formed claude/success receipt that merely ARRIVED as a file is an
  unverified third-party assertion with structured telemetry, not a verified
  observation;
* the receipt content itself is collected evidence (``collectable_v1``) with
  ``confidence: medium`` — the downgrade encodes "invocation unobserved".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nlfr.agent_receipt import load_receipt, receipt_provenance_summary, receipt_sha256
from nlfr.db.connection import UnreadableDatabaseError, connect, connect_readonly
from nlfr.db.ingest import upsert_artifact, upsert_proof_block
from nlfr.projectors.common import run_rows

IMPORTED_PROVENANCE_CLASS = "receipt_imported_v1"


def imported_receipt_provenance(
    receipt: dict[str, Any],
    *,
    run_id: str,
    run_key: str,
    run_status: str | None,
    run_group: str,
    scenario: str | None,
) -> dict[str, Any]:
    """Build agent provenance for a receipt whose invocation NLFR never saw.

    Deliberately NOT routed through the generic provenance builder: that path
    derives ``receipt_verified_v1`` from receipt shape via ``is_live_receipt``,
    which is only honest when NLFR itself performed the invocation.
    """

    summary = receipt_provenance_summary(receipt)
    summary["live"] = False
    summary["observed_by_nlfr"] = False
    cli = receipt.get("cli") if isinstance(receipt.get("cli"), dict) else {}
    model = receipt.get("model") if isinstance(receipt.get("model"), dict) else {}
    evidence_refs = [
        f"run:{run_id}",
        f"receipt:sha256:{summary['receipt_sha256']}",
        f"prompt:sha256:{receipt.get('prompt_sha256')}",
    ]
    if summary.get("session_id"):
        evidence_refs.append(f"session:{summary['session_id']}")
    return {
        "schema_version": "nlfr.agent_provenance.v1",
        "generated_at": _timestamp(),
        "scenario_id": scenario or "imported-receipt",
        "title": "Imported agent receipt (invocation not observed by NLFR)",
        "agent": {
            "kind": "imported_receipt_v1",
            "name": str(cli.get("name") or "unknown-cli"),
            "input_signal": "redacted: prompt withheld, hash retained",
            "model": model.get("resolved") or model.get("requested") or "unknown",
            "model_label_operator": None,
            "prompt_sha256": receipt.get("prompt_sha256"),
            "provenance_class": IMPORTED_PROVENANCE_CLASS,
            "receipt": summary,
        },
        "change": {},
        "build": {
            "run_id": run_id,
            "run_key": run_key,
            "status": run_status,
            "artifact_root": None,
        },
        "run_group": run_group,
        "mode": "imported",
        "source_kind": "collectable_v1",
        "confidence": "medium",
        "evidence_refs": evidence_refs,
        "redaction_state": "redacted",
    }


def run_import(args: argparse.Namespace) -> int:
    receipt_path = Path(args.receipt)
    try:
        receipt = load_receipt(receipt_path)
    except FileNotFoundError:
        print(f"receipt file not found: {receipt_path}", file=sys.stderr)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"invalid agent receipt: {exc}", file=sys.stderr)
        return 2

    try:
        reader = connect_readonly(args.db)
    except UnreadableDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        runs = run_rows(reader, args.run_group)
    finally:
        reader.close()
    if not runs:
        print(
            f"run group {args.run_group!r} has no recorded runs in {args.db}; "
            "record the build before importing its agent receipt",
            file=sys.stderr,
        )
        return 2
    if args.run_key:
        matching = [run for run in runs if run.get("stable_key") == args.run_key]
        if not matching:
            print(
                f"run key {args.run_key!r} not found in run group {args.run_group!r}",
                file=sys.stderr,
            )
            return 2
        run = matching[-1]
    else:
        run = runs[-1]

    receipt_bytes = receipt_path.read_bytes()
    sha12 = receipt_sha256(receipt)[:12]
    provenance = imported_receipt_provenance(
        receipt,
        run_id=run["id"],
        run_key=str(run.get("stable_key")),
        run_status=run.get("status"),
        run_group=args.run_group,
        scenario=run.get("scenario"),
    )

    writer = connect(args.db)
    try:
        upsert_artifact(
            writer,
            stable_key=f"{run['id']}:agent-receipt-imported:{sha12}",
            run_id=run["id"],
            artifact_key=f"agent-receipt-imported-{sha12}.json",
            artifact_path=str(receipt_path),
            sha256=hashlib.sha256(receipt_bytes).hexdigest(),
            size_bytes=len(receipt_bytes),
            content_type="application/json",
            producer_command=["nlfr", "receipt", "import"],
            source_kind="collectable_v1",
            confidence="medium",
            evidence_refs=[f"receipt:sha256:{receipt_sha256(receipt)}"],
            redaction_state="redacted",
        )
        upsert_proof_block(
            writer,
            stable_key=f"{run['id']}:agent-receipt-imported:{sha12}",
            run_id=run["id"],
            block_key=f"agent-receipt-imported:{sha12}",
            block_kind="agent_provenance",
            title=provenance["title"],
            summary=(
                f"{provenance['agent']['name']} receipt imported as "
                f"{IMPORTED_PROVENANCE_CLASS} (invocation not observed)"
            ),
            payload=provenance,
            source_kind=provenance["source_kind"],
            confidence=provenance["confidence"],
            evidence_refs=provenance["evidence_refs"],
            redaction_state=provenance["redaction_state"],
        )
        writer.commit()
    finally:
        writer.close()

    print(
        json.dumps(
            {
                "imported": True,
                "run_group": args.run_group,
                "run_key": run.get("stable_key"),
                "provenance_class": IMPORTED_PROVENANCE_CLASS,
                "receipt_sha256": receipt_sha256(receipt),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``receipt`` command group."""

    parser = subparsers.add_parser(
        "receipt",
        help="agent receipt commands (import externally produced receipts)",
        description="Agent receipt commands.",
    )
    receipt_subparsers = parser.add_subparsers(
        dest="receipt_command", metavar="command", required=True
    )
    import_parser = receipt_subparsers.add_parser(
        "import",
        help="import an agent receipt produced outside NLFR (cloud/pod build)",
        description=(
            "Validate and attach an nlfr.agent_receipt.v1 file produced by an "
            "invocation NLFR did not observe (CI runner, pod, hosted agent). "
            "Imported receipts are classed receipt_imported_v1 — never "
            "receipt_verified_v1 — and render receipt_verified: false."
        ),
    )
    import_parser.add_argument("--receipt", required=True, help="receipt JSON file to import")
    import_parser.add_argument("--db", default="data/nlfr/nlfr.sqlite", help="SQLite database path")
    import_parser.add_argument("--run-group", default="latest", help="run group to attach to")
    import_parser.add_argument(
        "--run-key", help="attach to this run stable key (default: newest run in group)"
    )
    import_parser.set_defaults(handler=run_import)
