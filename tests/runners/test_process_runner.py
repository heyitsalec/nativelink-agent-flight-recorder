import json
import sys

from nlfr.runners.process import ProcessRunner


def test_process_runner_records_command_paths_exit_code_and_timestamps(tmp_path):
    runner = ProcessRunner(artifact_dir=tmp_path / "artifacts")

    result = runner.run(
        [
            sys.executable,
            "-c",
            "import sys; print('hello stdout'); print('hello stderr', file=sys.stderr)",
        ],
        cwd=tmp_path,
        label="probe",
    )

    assert result.command[:2] == [sys.executable, "-c"]
    assert result.cwd == tmp_path
    assert result.exit_code == 0
    assert result.status == "completed"
    assert result.stdout_path == tmp_path / "artifacts" / "probe.stdout.txt"
    assert result.stderr_path == tmp_path / "artifacts" / "probe.stderr.txt"
    assert result.stdout_path.read_text(encoding="utf-8") == "hello stdout\n"
    assert result.stderr_path.read_text(encoding="utf-8") == "hello stderr\n"
    assert result.started_at.endswith("Z")
    assert result.ended_at.endswith("Z")
    assert result.started_at <= result.ended_at

    metadata = result.to_metadata()
    assert json.loads(json.dumps(metadata)) == metadata
    assert metadata["source_kind"] == "collectable_v1"
    assert metadata["confidence"] == "high"
    assert metadata["redaction_state"] == "safe"
