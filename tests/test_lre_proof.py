import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lre-proof.sh"


def _stub_bin(tmp_path: Path, name: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    path = bindir / name
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_lre_proof_records_blocker_without_config(tmp_path, monkeypatch):
    out = tmp_path / "lre-proof"
    nativelink = _stub_bin(tmp_path, "nativelink")
    bazel = _stub_bin(tmp_path, "bazel")
    monkeypatch.setenv("NLFR_LRE_OUTPUT", str(out))
    monkeypatch.setenv("NLFR_LRE_CONFIG", str(tmp_path / "missing-lre.json5"))
    monkeypatch.setenv("NLFR_NATIVELINK_BIN", str(nativelink))
    monkeypatch.setenv("NLFR_BAZEL_BIN", str(bazel))
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    blocker = out / "environment-blocker.json"
    probe = out / "probe.json"
    assert probe.is_file()
    assert blocker.is_file()
    payload = json.loads(blocker.read_text(encoding="utf-8"))
    assert payload["status"] == "environment_blocker"
    assert payload["source_kind"] == "collectable_v1"
    assert "lre.json5" in payload["reason"]
