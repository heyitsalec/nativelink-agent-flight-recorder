"""Redact absolute paths from projection JSON before committing."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def redact_text(text: str) -> str:
    text = re.sub(r"/Users/[^/\"\\s]+", "${HOME}", text)
    text = re.sub(r"/home/[^/\"\\s]+", "${HOME}", text)
    return text


def redact_payload(payload: object) -> object:
    serialized = redact_text(json.dumps(payload, ensure_ascii=True))
    return json.loads(serialized)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print("usage: redact-projection.py INPUT.json OUTPUT.json", file=sys.stderr)
        return 2
    source = Path(args[0])
    destination = Path(args[1])
    payload = json.loads(source.read_text(encoding="utf-8"))
    redacted = redact_payload(payload)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(redacted, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
