#!/usr/bin/env python3
"""Write conservative NativeLink worker-readiness evidence for smoke scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

UNSUPPORTED_CLAIMS = [
    "worker_identity",
    "action_placement",
    "queue_time",
    "scheduler_assignment",
    "load_distribution",
]


def main() -> int:
    args = _parser().parse_args()
    payload = build_payload(
        config_path=Path(args.config),
        expected_workers=args.expected_workers,
        phase=args.phase,
        public_port_open=args.public_port_open,
        worker_api_port_open=args.worker_api_port_open,
        evidence_refs=args.evidence_ref,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"worker readiness recorded: {output}")
    return 0 if payload["status"] in {"configuration_ready", "worker_endpoints_ready"} else 2


def build_payload(
    *,
    config_path: Path,
    expected_workers: int,
    phase: str,
    public_port_open: bool,
    worker_api_port_open: bool,
    evidence_refs: list[str],
) -> dict[str, Any]:
    try:
        config = json.loads(config_path.read_text())
        config_error = None
    except OSError as exc:
        config = {}
        config_error = f"config_read_error:{exc.__class__.__name__}"
    except json.JSONDecodeError as exc:
        config = {}
        config_error = f"config_parse_error:{exc.__class__.__name__}"

    services = _service_names(config)
    scheduler_names = [
        item.get("name")
        for item in config.get("schedulers", [])
        if isinstance(item, dict) and item.get("name")
    ]
    workers = config.get("workers", [])
    configured_workers = len(workers) if isinstance(workers, list) else 0
    worker_api_endpoints = _worker_api_endpoints(config)
    required_services = {"execution", "worker_api", "capabilities", "cas", "ac"}
    missing_services = sorted(required_services - set(services))
    reasons: list[str] = []
    if config_error is not None:
        reasons.append(config_error)
    if configured_workers < expected_workers:
        reasons.append(
            f"configured worker count {configured_workers} below expected {expected_workers}"
        )
    if missing_services:
        reasons.append(f"missing services: {', '.join(missing_services)}")
    if not scheduler_names:
        reasons.append("missing scheduler")

    if reasons:
        status = "configuration_blocker"
    elif phase == "preflight":
        status = "configuration_ready"
    elif public_port_open and worker_api_port_open:
        status = "worker_endpoints_ready"
    else:
        status = "endpoint_blocker"
        if not public_port_open:
            reasons.append("public endpoint port did not open")
        if not worker_api_port_open:
            reasons.append("worker API endpoint port did not open")

    return {
        "status": status,
        "phase": phase,
        "config_path": str(config_path),
        "config_sha256": _sha256(config_path) if config_error is None else None,
        "expected_workers": expected_workers,
        "configured_workers": configured_workers,
        "scheduler_names": scheduler_names,
        "services": services,
        "worker_api_endpoints": worker_api_endpoints,
        "port_checks": {
            "public_endpoint_open": public_port_open,
            "worker_api_endpoint_open": worker_api_port_open,
        },
        "claims": _claims(status, configured_workers, expected_workers),
        "unsupported_claims": UNSUPPORTED_CLAIMS,
        "reasons": reasons,
        "source_kind": "collectable_v1",
        "confidence": "high",
        "redaction_state": "safe",
        "evidence_refs": _dedupe(
            [
                f"config:{config_path.name}",
                "script:local-exec-proof.sh",
                *evidence_refs,
            ]
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="NativeLink config path")
    parser.add_argument("--output", required=True, help="readiness JSON output path")
    parser.add_argument(
        "--expected-workers",
        type=int,
        default=1,
        help="minimum configured worker count required for this smoke",
    )
    parser.add_argument(
        "--phase",
        choices=("preflight", "ports"),
        default="preflight",
        help="evidence phase to record",
    )
    parser.add_argument("--public-port-open", action="store_true")
    parser.add_argument("--worker-api-port-open", action="store_true")
    parser.add_argument("--evidence-ref", action="append", default=[])
    return parser


def _service_names(config: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for server in config.get("servers", []):
        if isinstance(server, dict) and isinstance(server.get("services"), dict):
            names.update(str(name) for name in server["services"])
    return sorted(names)


def _worker_api_endpoints(config: dict[str, Any]) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    seen: set[str] = set()
    workers = config.get("workers", [])
    if not isinstance(workers, list):
        return endpoints
    for worker in workers:
        if not isinstance(worker, dict):
            continue
        local = worker.get("local")
        if not isinstance(local, dict):
            continue
        endpoint = local.get("worker_api_endpoint")
        if not isinstance(endpoint, dict):
            continue
        uri = endpoint.get("uri")
        if isinstance(uri, str) and uri not in seen:
            seen.add(uri)
            endpoints.append(_endpoint_summary(uri))
    return endpoints


def _endpoint_summary(uri: str) -> dict[str, Any]:
    parsed = urlsplit(uri)
    hostname = parsed.hostname or ""
    safe_loopback = hostname in {"127.0.0.1", "localhost", "::1"}
    has_credentials = parsed.username is not None or parsed.password is not None
    if safe_loopback and not has_credentials:
        return {"label": uri, "fingerprint": _fingerprint(uri), "redacted": False}
    scheme = f"{parsed.scheme}://" if parsed.scheme else ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    return {
        "label": f"{scheme}<redacted>{port}#{_fingerprint(uri)}",
        "fingerprint": _fingerprint(uri),
        "redacted": True,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _claims(status: str, configured_workers: int, expected_workers: int) -> list[str]:
    if status == "configuration_ready":
        return [
            f"NativeLink config declares at least {expected_workers} worker(s).",
            "This does not prove worker registration or remote action execution.",
        ]
    if status == "worker_endpoints_ready":
        return [
            f"NativeLink config declares {configured_workers} worker(s), and smoke endpoints opened.",
            "This proves endpoint readiness, not worker identity or action placement.",
        ]
    return [
        "Worker smoke proof is blocked before endpoint readiness.",
        "No remote action execution claim is available.",
    ]


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value not in deduped:
            deduped.append(value)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
