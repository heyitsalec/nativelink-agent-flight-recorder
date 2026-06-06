"""Stable identifiers for recorded evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def stable_hash(*parts: Any) -> str:
    """Return a SHA-256 hash for JSON-normalized identity parts."""

    payload = json.dumps(
        parts,
        default=_json_default,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_id(kind: str, *parts: Any) -> str:
    """Return a readable stable id with a collision-resistant suffix."""

    prefix = re.sub(r"[^A-Za-z0-9_]+", "_", kind).strip("_").lower() or "id"
    return f"{prefix}_{stable_hash(kind, *parts)[:24]}"


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)
