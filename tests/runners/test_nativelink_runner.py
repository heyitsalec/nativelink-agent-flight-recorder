import json
from pathlib import Path

from nlfr.runners.nativelink import NativeLinkRunner

ROOT = Path(__file__).resolve().parents[2]


def test_nativelink_runner_reports_missing_binary_as_environment_blocker(tmp_path):
    runner = NativeLinkRunner(
        config_path=tmp_path / "cache-only.json",
        artifact_dir=tmp_path / "artifacts",
        executable="definitely-missing-nativelink-for-nlfr",
    )

    result = runner.run_cache_server(cwd=tmp_path)

    assert result.status == "environment_blocker"
    assert result.exit_code is None
    assert result.source_kind == "collectable_v1"
    assert result.confidence == "high"
    assert "definitely-missing-nativelink-for-nlfr" in result.detail


def test_nativelink_runner_builds_cache_only_command(tmp_path):
    config_path = tmp_path / "cache-only.json"
    runner = NativeLinkRunner(
        config_path=config_path,
        artifact_dir=tmp_path / "artifacts",
        executable="/opt/nativelink/bin/nativelink",
    )

    assert runner.build_command() == ["/opt/nativelink/bin/nativelink", str(config_path)]
    assert runner.stdout_path == Path(tmp_path / "artifacts" / "nativelink.stdout.txt")
    assert runner.stderr_path == Path(tmp_path / "artifacts" / "nativelink.stderr.txt")


def test_demo_nativelink_config_is_cache_only():
    config = json.loads((ROOT / "demo" / "nativelink" / "cache-only.json").read_text())

    assert "schedulers" not in config
    assert "workers" not in config
    for server in config["servers"]:
        assert "execution" not in server["services"]
        assert "worker_api" not in server["services"]


def test_demo_nativelink_local_execution_config_has_scheduler_and_worker():
    config = json.loads(
        (ROOT / "demo" / "nativelink" / "local-execution.json5").read_text()
    )

    assert config["schedulers"][0]["name"] == "MAIN_SCHEDULER"
    assert config["workers"][0]["local"]["worker_api_endpoint"]["uri"] == (
        "grpc://127.0.0.1:50061"
    )
    services = {service for server in config["servers"] for service in server["services"]}
    assert {"execution", "worker_api", "capabilities"} <= services
