import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "lre-proof.sh"
NIX_TOOLCHAIN_SCRIPT = ROOT / "scripts" / "lre-nix-toolchain-proof.sh"
LRE_CONFIG = ROOT / "demo" / "nativelink" / "lre.json5"
SUMMARY_SAMPLE = ROOT / "docs" / "proof-samples" / "lre-proof-summary-sample.json"
NIX_TOOLCHAIN_SUMMARY_SAMPLE = (
    ROOT / "docs" / "proof-samples" / "lre-nix-toolchain-proof-summary-sample.json"
)
NIX_TOOLCHAIN_BLOCKER_SAMPLE = (
    ROOT / "docs" / "proof-samples" / "lre-nix-toolchain-proof-blocker-sample.json"
)

_LRE_SUMMARY_WRITER = """
import json
import os
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
local_exec_summary = out / "local-exec" / "summary.json"
local_exec_payload = {}
if local_exec_summary.is_file():
    local_exec_payload = json.loads(local_exec_summary.read_text(encoding="utf-8"))

summary = {
    "status": "lre_substrate_ready",
    "source_kind": "collectable_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:lre-proof.sh",
        "script:local-exec-proof.sh",
        "demo/nativelink/lre.json5",
    ],
    "lre_config": "demo/nativelink/lre.json5",
    "remote_cache": "grpc://127.0.0.1:50071",
    "remote_executor": "grpc://127.0.0.1:50071",
    "local_exec_summary": local_exec_payload.get("status"),
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "claim_boundary": {
        "supported": [
            "LRE NativeLink server substrate configured",
            "remote_executor smoke with lre.json5 endpoints",
            "worker_endpoints_ready for one local worker",
        ],
        "unsupported_until_nix_lre_toolchain": [
            "hermetic Nix toolchain parity across local and remote",
            "generated lre.bazelrc / --config=lre cache hit parity",
            "fleet scheduler dashboards",
            "queue time and action placement correlation",
        ],
    },
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\\n")
print(json.dumps(summary, indent=2))
"""

_LRE_NIX_TOOLCHAIN_SUMMARY_WRITER = """
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

out = Path(os.environ["OUT"])
build_attempted = os.environ.get("BUILD_ATTEMPTED") == "true"
build_ok = os.environ.get("BUILD_OK") == "true"
build_target = os.environ.get("BUILD_TARGET") or None
build_skip = os.environ.get("BUILD_SKIP_REASON") or None

summary = {
    "status": "lre_bazelrc_generated",
    "source_kind": "collectable_v1",
    "confidence": "medium",
    "redaction_state": "safe",
    "evidence_refs": [
        "script:lre-nix-toolchain-proof.sh",
        "flake.nix",
        "demo/bazel-monorepo/.bazelrc",
        "demo/bazel-monorepo/MODULE.bazel",
    ],
    "lre_bazelrc_path": "lre.bazelrc",
    "monorepo_lre_bazelrc_path": "demo/bazel-monorepo/lre.bazelrc",
    "platform": platform.system().lower(),
    "machine": platform.machine(),
    "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "build_config_lre": {
        "attempted": build_attempted,
        "succeeded": build_ok if build_attempted else None,
        "target": build_target,
        "skip_reason": build_skip,
    },
    "claim_boundary": {
        "supported": [
            "Nix devShell generates lre.bazelrc with build:lre flags",
            "demo/bazel-monorepo try-imports generated lre.bazelrc",
            "MODULE.bazel resolves @local-remote-execution at pinned NativeLink rev",
        ],
        "unsupported": [
            "hermetic local and remote cache hit parity",
            "nlfr run --bazel-arg=--config=lre end-to-end ingest",
            "aarch64-darwin full lre-cc builds",
            "fleet scheduler dashboards",
            "queue time and action placement correlation",
        ],
    },
}
(out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\\n")
print(json.dumps(summary, indent=2))
"""


def _stub_bin(tmp_path: Path, name: str) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    path = bindir / name
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _run_lre_proof(
    tmp_path: Path,
    *,
    output: Path,
    lre_config: Path,
    nativelink: Path,
    bazel: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NLFR_LRE_OUTPUT"] = str(output)
    env["NLFR_LRE_CONFIG"] = str(lre_config)
    env["NLFR_NATIVELINK_BIN"] = str(nativelink)
    env["NLFR_BAZEL_BIN"] = str(bazel)
    return subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_lre_summary(output: Path) -> dict:
    env = os.environ.copy()
    env["OUT"] = str(output)
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python3", "-c", _LRE_SUMMARY_WRITER],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads((output / "summary.json").read_text(encoding="utf-8"))


def _run_lre_nix_toolchain_proof(
    tmp_path: Path,
    *,
    output: Path,
    lre_bazelrc: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NLFR_LRE_NIX_OUTPUT"] = str(output)
    env["NLFR_LRE_BAZELRC"] = str(lre_bazelrc)
    env["NLFR_LRE_NIX_TRY_BUILD"] = "0"
    return subprocess.run(
        [str(NIX_TOOLCHAIN_SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_lre_nix_toolchain_summary(
    output: Path,
    *,
    build_attempted: bool = True,
    build_ok: bool = True,
    build_target: str = "@local-remote-execution//examples:lre-cc",
    build_skip_reason: str | None = None,
) -> dict:
    env = os.environ.copy()
    env["OUT"] = str(output)
    env["BUILD_ATTEMPTED"] = "true" if build_attempted else "false"
    env["BUILD_OK"] = "true" if build_ok else "false"
    env["BUILD_TARGET"] = build_target
    if build_skip_reason is not None:
        env["BUILD_SKIP_REASON"] = build_skip_reason
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["python3", "-c", _LRE_NIX_TOOLCHAIN_SUMMARY_WRITER],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads((output / "summary.json").read_text(encoding="utf-8"))


def test_lre_proof_records_blocker_without_config(tmp_path):
    out = tmp_path / "lre-proof"
    nativelink = _stub_bin(tmp_path, "nativelink")
    bazel = _stub_bin(tmp_path, "bazel")
    result = _run_lre_proof(
        tmp_path,
        output=out,
        lre_config=tmp_path / "missing-lre.json5",
        nativelink=nativelink,
        bazel=bazel,
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


def test_lre_json5_port_validation():
    text = LRE_CONFIG.read_text(encoding="utf-8")
    assert LRE_CONFIG.is_file()
    assert "127.0.0.1:50071" in text
    assert "127.0.0.1:50081" in text
    assert "grpc://127.0.0.1:50081" in text
    assert "50051" not in text
    assert "50061" not in text


def test_lre_proof_probe_when_config_present(tmp_path):
    out = tmp_path / "lre-proof"
    nativelink = _stub_bin(tmp_path, "nativelink")
    bazel = _stub_bin(tmp_path, "bazel")
    result = _run_lre_proof(
        tmp_path,
        output=out,
        lre_config=LRE_CONFIG,
        nativelink=nativelink,
        bazel=bazel,
    )
    probe = json.loads((out / "probe.json").read_text(encoding="utf-8"))
    assert probe["status"] == "probe"
    assert probe["lre_config_present"] is True
    assert probe["lre_config_path"] == "demo/nativelink/lre.json5"
    assert probe["source_kind"] == "collectable_v1"
    assert probe["confidence"] == "high"
    assert probe["redaction_state"] == "safe"
    assert "recorded_at" in probe
    assert result.returncode != 0


def test_lre_summary_shape_with_stubbed_delegation(tmp_path):
    out = tmp_path / "lre-proof"
    local_exec = out / "local-exec"
    local_exec.mkdir(parents=True)
    (local_exec / "summary.json").write_text(
        json.dumps({"status": "completed"}) + "\n",
        encoding="utf-8",
    )

    summary = _write_lre_summary(out)
    sample = json.loads(SUMMARY_SAMPLE.read_text(encoding="utf-8"))

    for key in (
        "status",
        "source_kind",
        "confidence",
        "redaction_state",
        "lre_config",
        "remote_cache",
        "remote_executor",
        "local_exec_summary",
    ):
        assert summary[key] == sample[key]

    assert summary["evidence_refs"] == sample["evidence_refs"]
    assert summary["claim_boundary"] == sample["claim_boundary"]
    assert "recorded_at" in summary
    assert summary["recorded_at"].endswith("Z")
    assert (out / "summary.json").is_file()


def test_lre_nix_toolchain_proof_records_blocker_without_bazelrc(tmp_path):
    out = tmp_path / "lre-nix-toolchain-proof"
    result = _run_lre_nix_toolchain_proof(
        tmp_path,
        output=out,
        lre_bazelrc=tmp_path / "missing-lre.bazelrc",
    )
    assert result.returncode == 2
    blocker = out / "environment-blocker.json"
    probe = out / "probe.json"
    assert probe.is_file()
    assert blocker.is_file()
    payload = json.loads(blocker.read_text(encoding="utf-8"))
    sample = json.loads(NIX_TOOLCHAIN_BLOCKER_SAMPLE.read_text(encoding="utf-8"))
    assert payload["status"] == sample["status"]
    assert payload["source_kind"] == sample["source_kind"]
    assert payload["confidence"] == sample["confidence"]
    assert payload["redaction_state"] == sample["redaction_state"]
    assert payload["evidence_refs"] == sample["evidence_refs"]
    assert payload["claim_boundary"] == sample["claim_boundary"]
    assert "lre.bazelrc" in payload["reason"]


def test_lre_nix_toolchain_summary_shape_with_fixture(tmp_path):
    out = tmp_path / "lre-nix-toolchain-proof"
    summary = _write_lre_nix_toolchain_summary(out)
    sample = json.loads(NIX_TOOLCHAIN_SUMMARY_SAMPLE.read_text(encoding="utf-8"))

    for key in (
        "status",
        "source_kind",
        "confidence",
        "redaction_state",
        "lre_bazelrc_path",
        "monorepo_lre_bazelrc_path",
    ):
        assert summary[key] == sample[key]

    assert summary["evidence_refs"] == sample["evidence_refs"]
    assert summary["claim_boundary"] == sample["claim_boundary"]
    assert summary["build_config_lre"]["attempted"] is True
    assert summary["build_config_lre"]["succeeded"] is True
    assert summary["build_config_lre"]["target"] == sample["build_config_lre"]["target"]
    assert "recorded_at" in summary
    assert summary["recorded_at"].endswith("Z")
    assert (out / "summary.json").is_file()


def test_lre_nix_toolchain_proof_success_with_stub_bazelrc(tmp_path):
    out = tmp_path / "lre-nix-toolchain-proof"
    lre_bazelrc = tmp_path / "lre.bazelrc"
    lre_bazelrc.write_text("build:lre --define=EXECUTOR=remote\n", encoding="utf-8")
    result = _run_lre_nix_toolchain_proof(
        tmp_path,
        output=out,
        lre_bazelrc=lre_bazelrc,
    )
    assert result.returncode == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "lre_bazelrc_generated"
    assert summary["source_kind"] == "collectable_v1"
    assert summary["build_config_lre"]["attempted"] is False
    assert summary["build_config_lre"]["skip_reason"] is not None
