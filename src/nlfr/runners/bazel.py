"""Bazel subprocess runner for cache-only proof collection."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from nlfr.runners.process import ProcessResult, ProcessRunner


class BazelRunner:
    """Construct and run Bazel commands with NLFR artifact flags."""

    def __init__(
        self,
        *,
        workspace: str | Path,
        artifact_dir: str | Path,
        bazel_executable: str = "bazel",
        startup_args: Sequence[str] = (),
        remote_cache_url: str | None = None,
        remote_executor_url: str | None = None,
        remote_instance_name: str = "main",
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.artifact_dir = Path(artifact_dir)
        self.bazel_executable = bazel_executable
        self.startup_args = [str(arg) for arg in startup_args]
        self.remote_cache_url = remote_cache_url
        self.remote_executor_url = remote_executor_url
        self.remote_instance_name = remote_instance_name
        self.process_runner = process_runner or ProcessRunner(self.artifact_dir)

    def describe_artifacts(self) -> dict[str, Path]:
        return {
            "bep": self.artifact_dir / "bazel.bep.json",
            "profile": self.artifact_dir / "bazel.profile.json",
            "execution_log": self.artifact_dir / "bazel.execution-log.json",
        }

    def build_command(
        self,
        targets: Sequence[str] | str = ("//...",),
        *,
        extra_args: Sequence[str] = (),
    ) -> list[str]:
        target_args = [targets] if isinstance(targets, str) else list(targets)
        artifacts = self.describe_artifacts()
        command = [
            self.bazel_executable,
            *self.startup_args,
            "test",
            *target_args,
            f"--build_event_json_file={artifacts['bep']}",
            f"--profile={artifacts['profile']}",
            f"--execution_log_json_file={artifacts['execution_log']}",
        ]
        if self.remote_cache_url is not None:
            command.extend(
                [
                    f"--remote_cache={self.remote_cache_url}",
                    *(
                        [f"--remote_executor={self.remote_executor_url}"]
                        if self.remote_executor_url is not None
                        else []
                    ),
                    f"--remote_instance_name={self.remote_instance_name}",
                    "--remote_upload_local_results=true",
                    "--remote_download_toplevel",
                ]
            )
        command.extend(extra_args)
        return command

    def run_tests(
        self,
        targets: Sequence[str] | str = ("//...",),
        *,
        extra_args: Sequence[str] = (),
        evidence_refs: Sequence[str] = (),
    ) -> ProcessResult:
        command = self.build_command(targets, extra_args=extra_args)
        if not self._executable_available():
            return self.process_runner.environment_blocker(
                command,
                cwd=self.workspace,
                label="bazel",
                detail=f"missing Bazel executable on PATH: {self.bazel_executable}",
                evidence_refs=evidence_refs,
            )
        return self.process_runner.run(
            command,
            cwd=self.workspace,
            label="bazel",
            evidence_refs=evidence_refs,
        )

    def _executable_available(self) -> bool:
        executable_path = Path(self.bazel_executable)
        if executable_path.is_absolute() or len(executable_path.parts) > 1:
            return executable_path.exists()
        return shutil.which(self.bazel_executable) is not None
