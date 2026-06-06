from pathlib import Path

from nlfr.runners.bazel import BazelRunner


def test_bazel_runner_builds_cache_only_command_with_artifact_flags(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    runner = BazelRunner(
        workspace=workspace,
        artifact_dir=artifact_dir,
        bazel_executable="bazelisk",
        remote_cache_url="grpc://127.0.0.1:50051",
    )

    command = runner.build_command(["//tasks:priority_test"])

    assert command[:3] == ["bazelisk", "test", "//tasks:priority_test"]
    assert f"--build_event_json_file={artifact_dir / 'bazel.bep.json'}" in command
    assert f"--profile={artifact_dir / 'bazel.profile.json'}" in command
    assert (
        f"--experimental_execution_log_json_file={artifact_dir / 'bazel.execution-log.json'}"
        in command
    )
    assert "--remote_cache=grpc://127.0.0.1:50051" in command
    assert "--remote_instance_name=main" in command
    assert "--remote_upload_local_results=true" in command
    assert "--remote_download_toplevel" in command


def test_bazel_runner_builds_remote_execution_command(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    runner = BazelRunner(
        workspace=workspace,
        artifact_dir=artifact_dir,
        bazel_executable="bazelisk",
        remote_cache_url="grpc://127.0.0.1:50051",
        remote_executor_url="grpc://127.0.0.1:50051",
    )

    command = runner.build_command("//tasks:priority_test")

    assert "--remote_cache=grpc://127.0.0.1:50051" in command
    assert "--remote_executor=grpc://127.0.0.1:50051" in command
    assert "--remote_instance_name=main" in command
    assert "--remote_download_toplevel" in command


def test_bazel_runner_appends_extra_test_args_after_nlfr_flags(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    runner = BazelRunner(
        workspace=workspace,
        artifact_dir=artifact_dir,
        bazel_executable="bazelisk",
        remote_cache_url="grpc://127.0.0.1:50051",
        remote_executor_url="grpc://127.0.0.1:50051",
    )

    command = runner.build_command(
        "//tasks:priority_test",
        extra_args=["--config=lre", "--remote_default_exec_properties=cpu_count=1"],
    )

    assert command[-2:] == [
        "--config=lre",
        "--remote_default_exec_properties=cpu_count=1",
    ]
    assert command.index("--remote_executor=grpc://127.0.0.1:50051") < command.index(
        "--config=lre"
    )


def test_bazel_runner_places_startup_args_before_command(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    runner = BazelRunner(
        workspace=workspace,
        artifact_dir=artifact_dir,
        bazel_executable="bazelisk",
        startup_args=[f"--output_base={tmp_path / 'output-base'}"],
    )

    command = runner.build_command("//tasks:priority_test")

    assert command[:3] == [
        "bazelisk",
        f"--output_base={tmp_path / 'output-base'}",
        "test",
    ]


def test_bazel_runner_defaults_to_demo_workspace_paths(tmp_path):
    runner = BazelRunner(
        workspace=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        bazel_executable="bazel",
    )

    metadata = runner.describe_artifacts()

    assert metadata == {
        "bep": Path(tmp_path / "artifacts" / "bazel.bep.json"),
        "profile": Path(tmp_path / "artifacts" / "bazel.profile.json"),
        "execution_log": Path(tmp_path / "artifacts" / "bazel.execution-log.json"),
    }
