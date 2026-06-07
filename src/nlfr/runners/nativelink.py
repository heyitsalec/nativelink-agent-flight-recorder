"""NativeLink subprocess runner for recorder proof paths."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from nlfr.runners.process import ProcessResult, ProcessRunner


class NativeLinkRunner:
    """Run a NativeLink config without treating missing tools as success."""

    def __init__(
        self,
        *,
        config_path: str | Path,
        artifact_dir: str | Path,
        executable: str = "nativelink",
        process_runner: ProcessRunner | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.artifact_dir = Path(artifact_dir)
        self.executable = executable
        self.process_runner = process_runner or ProcessRunner(self.artifact_dir)

    @property
    def stdout_path(self) -> Path:
        """Path where NativeLink stdout is recorded."""

        return self.artifact_dir / "nativelink.stdout.txt"

    @property
    def stderr_path(self) -> Path:
        """Path where NativeLink stderr is recorded."""

        return self.artifact_dir / "nativelink.stderr.txt"

    def build_command(self) -> list[str]:
        """Construct the NativeLink server command for the configured file."""

        return [self.executable, str(self.config_path)]

    def run_cache_server(
        self,
        *,
        cwd: str | Path,
        timeout_seconds: float | None = None,
        evidence_refs: Sequence[str] = (),
    ) -> ProcessResult:
        """Start NativeLink with the configured file and record process evidence."""

        command = self.build_command()
        if not self._executable_available():
            return self.process_runner.environment_blocker(
                command,
                cwd=cwd,
                label="nativelink",
                detail=f"missing NativeLink executable on PATH: {self.executable}",
                evidence_refs=evidence_refs,
            )
        if not self.config_path.exists():
            return self.process_runner.configuration_blocker(
                command,
                cwd=cwd,
                label="nativelink",
                detail=f"NativeLink config does not exist: {self.config_path}",
                evidence_refs=evidence_refs,
            )
        return self.process_runner.run(
            command,
            cwd=cwd,
            label="nativelink",
            timeout_seconds=timeout_seconds,
            evidence_refs=evidence_refs,
        )

    def _executable_available(self) -> bool:
        executable_path = Path(self.executable)
        if executable_path.is_absolute() or len(executable_path.parts) > 1:
            return executable_path.exists()
        return shutil.which(self.executable) is not None
