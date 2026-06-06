"""Small subprocess runner that records local process evidence."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    command: list[str]
    cwd: Path
    stdout_path: Path
    stderr_path: Path
    exit_code: int | None
    started_at: str
    ended_at: str
    status: str
    source_kind: str = "collectable_v1"
    confidence: str = "high"
    redaction_state: str = "safe"
    evidence_refs: list[str] = field(default_factory=list)
    detail: str | None = None

    def to_metadata(self) -> dict[str, object]:
        metadata: dict[str, object] = {
            "command": self.command,
            "cwd": str(self.cwd),
            "stdout_path": str(self.stdout_path),
            "stderr_path": str(self.stderr_path),
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "source_kind": self.source_kind,
            "confidence": self.confidence,
            "redaction_state": self.redaction_state,
            "evidence_refs": self.evidence_refs,
        }
        if self.detail is not None:
            metadata["detail"] = self.detail
        return metadata


class ProcessRunner:
    """Run a subprocess and persist stdout/stderr alongside metadata."""

    def __init__(self, artifact_dir: str | Path) -> None:
        self.artifact_dir = Path(artifact_dir)

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path,
        label: str,
        env: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
        evidence_refs: Sequence[str] = (),
    ) -> ProcessResult:
        command_list = [str(part) for part in command]
        cwd_path = Path(cwd)
        stdout_path = self._stream_path(label, "stdout")
        stderr_path = self._stream_path(label, "stderr")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = _timestamp()
        try:
            with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
                completed = subprocess.run(
                    command_list,
                    cwd=cwd_path,
                    env=dict(env) if env is not None else None,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    check=False,
                    timeout=timeout_seconds,
                )
            exit_code: int | None = completed.returncode
            status = "completed"
            detail = None
        except FileNotFoundError as exc:
            detail = f"executable not found: {command_list[0]}"
            stdout_path.write_bytes(b"")
            stderr_path.write_text(detail + "\n", encoding="utf-8")
            exit_code = None
            status = "environment_blocker"
            if exc.filename and exc.filename != command_list[0]:
                detail = f"{detail} ({exc.filename})"
        except subprocess.TimeoutExpired:
            detail = f"process timed out after {timeout_seconds} seconds"
            exit_code = None
            status = "timeout"
        ended_at = _timestamp()

        return ProcessResult(
            command=command_list,
            cwd=cwd_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            exit_code=exit_code,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            evidence_refs=list(evidence_refs),
            detail=detail,
        )

    def environment_blocker(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path,
        label: str,
        detail: str,
        evidence_refs: Sequence[str] = (),
    ) -> ProcessResult:
        command_list = [str(part) for part in command]
        cwd_path = Path(cwd)
        stdout_path = self._stream_path(label, "stdout")
        stderr_path = self._stream_path(label, "stderr")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_bytes(b"")
        stderr_path.write_text(detail + "\n", encoding="utf-8")
        timestamp = _timestamp()
        return ProcessResult(
            command=command_list,
            cwd=cwd_path,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            exit_code=None,
            started_at=timestamp,
            ended_at=timestamp,
            status="environment_blocker",
            evidence_refs=list(evidence_refs),
            detail=detail,
        )

    def configuration_blocker(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path,
        label: str,
        detail: str,
        evidence_refs: Sequence[str] = (),
    ) -> ProcessResult:
        result = self.environment_blocker(
            command,
            cwd=cwd,
            label=label,
            detail=detail,
            evidence_refs=evidence_refs,
        )
        return ProcessResult(
            command=result.command,
            cwd=result.cwd,
            stdout_path=result.stdout_path,
            stderr_path=result.stderr_path,
            exit_code=result.exit_code,
            started_at=result.started_at,
            ended_at=result.ended_at,
            status="configuration_blocker",
            evidence_refs=result.evidence_refs,
            detail=result.detail,
        )

    def _stream_path(self, label: str, stream: str) -> Path:
        if not label or any(part in label for part in ("/", "\\")):
            raise ValueError("label must be a simple artifact name")
        return self.artifact_dir / f"{label}.{stream}.txt"


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
