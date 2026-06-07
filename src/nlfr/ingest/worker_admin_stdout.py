"""Parse NativeLink admin stdout for worker identity evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

WORKER_STARTED = re.compile(r"Worker\s+(\S+)\s+started", re.IGNORECASE)
WORKER_NAME_KV = re.compile(r"worker_name=(\S+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class WorkerIdentityEvent:
    """One worker identity line parsed from NativeLink admin stdout."""

    worker_name: str
    line_number: int
    evidence_ref: str


def parse_worker_admin_stdout(
    path: str | Path,
    *,
    evidence_ref: str | None = None,
) -> list[WorkerIdentityEvent]:
    """Return structured worker identity rows from NativeLink admin stdout."""

    evidence_path = Path(path)
    resolved_ref = evidence_ref or f"collectable_v1:{evidence_path.name}"
    events: list[WorkerIdentityEvent] = []
    seen: set[tuple[int, str]] = set()

    for line_number, line in enumerate(evidence_path.read_text().splitlines(), start=1):
        for pattern in (WORKER_STARTED, WORKER_NAME_KV):
            match = pattern.search(line)
            if match is None:
                continue
            worker_name = match.group(1).strip()
            if not worker_name:
                continue
            key = (line_number, worker_name)
            if key in seen:
                continue
            seen.add(key)
            events.append(
                WorkerIdentityEvent(
                    worker_name=worker_name,
                    line_number=line_number,
                    evidence_ref=resolved_ref,
                )
            )
    return events
