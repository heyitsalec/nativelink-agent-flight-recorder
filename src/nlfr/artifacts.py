"""Immutable artifact writes and manifest helpers."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from collections.abc import Sequence
from pathlib import Path

MANIFEST_FILENAME = "artifact_manifest.json"
MANIFEST_SCHEMA_VERSION = 1


class ArtifactExistsError(RuntimeError):
    """Raised when an artifact key would overwrite recorded evidence."""


@dataclass(frozen=True)
class ArtifactManifestEntry:
    artifact_key: str
    path: str
    sha256: str
    size_bytes: int
    producer_command: list[str]
    config_hash: str | None
    redaction_state: str
    source_kind: str
    confidence: str
    evidence_refs: list[str]

    def to_manifest(self) -> dict[str, object]:
        """Serialize this entry for ``artifact_manifest.json``."""

        return asdict(self)


def write_artifact(
    artifact_root: str | Path,
    *,
    artifact_key: str,
    data: bytes | str,
    producer_command: Sequence[str],
    config_hash: str | None,
    redaction_state: str,
    source_kind: str,
    confidence: str,
    evidence_refs: Sequence[str] = (),
) -> ArtifactManifestEntry:
    """Write an artifact once and append its manifest entry."""

    root = Path(artifact_root)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    relative_path = _safe_relative_path(artifact_key)
    destination = root / relative_path
    entry = ArtifactManifestEntry(
        artifact_key=artifact_key,
        path=relative_path.as_posix(),
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        producer_command=list(producer_command),
        config_hash=config_hash,
        redaction_state=redaction_state,
        source_kind=source_kind,
        confidence=confidence,
        evidence_refs=list(evidence_refs),
    )

    root.mkdir(parents=True, exist_ok=True)
    manifest = read_manifest(root)
    existing_entry = _find_entry(manifest, artifact_key)
    if existing_entry is not None:
        return _reuse_existing_entry(destination, entry, existing_entry)

    if destination.exists():
        existing_sha = hashlib.sha256(destination.read_bytes()).hexdigest()
        if existing_sha != entry.sha256:
            raise ArtifactExistsError(f"artifact already exists: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("xb") as artifact_file:
                artifact_file.write(payload)
        except FileExistsError as exc:
            raise ArtifactExistsError(f"artifact already exists: {destination}") from exc

    manifest["artifacts"].append(entry.to_manifest())
    _write_manifest(root, manifest)
    return entry


def read_manifest(artifact_root: str | Path) -> dict[str, object]:
    """Read the artifact manifest, returning an empty schema if absent."""

    manifest_path = Path(artifact_root) / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {"schema_version": MANIFEST_SCHEMA_VERSION, "artifacts": []}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _reuse_existing_entry(
    destination: Path,
    requested_entry: ArtifactManifestEntry,
    existing_entry: dict[str, object],
) -> ArtifactManifestEntry:
    if existing_entry != requested_entry.to_manifest():
        raise ArtifactExistsError(f"manifest entry already exists: {requested_entry.path}")
    if not destination.exists():
        raise ArtifactExistsError(f"manifest entry exists but artifact is missing: {destination}")

    existing_sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    if existing_sha != requested_entry.sha256:
        raise ArtifactExistsError(f"artifact content differs from manifest: {destination}")
    return requested_entry


def _find_entry(
    manifest: dict[str, object],
    artifact_key: str,
) -> dict[str, object] | None:
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ValueError("artifact manifest must contain an artifacts list")
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("artifact manifest entries must be objects")
        if artifact.get("artifact_key") == artifact_key:
            return artifact
    return None


def _write_manifest(artifact_root: Path, manifest: dict[str, object]) -> None:
    manifest_path = artifact_root / MANIFEST_FILENAME
    temp_path = manifest_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, manifest_path)


def _safe_relative_path(artifact_key: str) -> Path:
    relative_path = Path(artifact_key)
    if relative_path.is_absolute():
        raise ValueError("artifact_key must be relative")
    if not artifact_key or any(part in ("", ".", "..") for part in relative_path.parts):
        raise ValueError("artifact_key must not contain empty, current, or parent segments")
    return relative_path
