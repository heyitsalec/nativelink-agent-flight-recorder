import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_redact_projection_scrubs_home_paths(tmp_path: Path) -> None:
    source = tmp_path / "raw.json"
    destination = tmp_path / "redacted.json"
    home = "/Users/example/person/project"
    source.write_text(
        json.dumps({"artifact_root": f"{home}/data/run/artifacts"}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "redact-projection.py"), str(source), str(destination)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert "${HOME}" in payload["artifact_root"]
    assert "/Users/example" not in payload["artifact_root"]
