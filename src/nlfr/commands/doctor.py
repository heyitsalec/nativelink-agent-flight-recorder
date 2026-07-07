"""Environment checks for local NLFR proof paths."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from nlfr.config import (
    doc_hint,
    is_within_source_checkout,
    nativelink_config_from_toml,
)
from nlfr.ingest.bazel import (
    TESTED_BAZEL_VERSIONS,
    bazel_major,
    bazel_release_from_version_output,
    out_of_range_bazel_warning,
)


ADOPTION_GUIDE = "docs/ADOPTION_GUIDE.md"
DEV_ENVIRONMENT = "docs/DEV_ENVIRONMENT.md"
FIRST_EVIDENCE_LOOP = "docs/wiki/tutorial/first-evidence-loop.md"
LOCAL_EXEC_CONFIG = "demo/nativelink/local-execution.json5"


def adoption_hint() -> str:
    """Return the resolvable "adoption docs" pointer line (both personas).

    Formatted at call time so persona detection reflects the runtime
    environment, and routed through :func:`doc_hint` so it can never regress to
    a bare, no-clone dead-end path (GitHub issue #39).
    """

    return "Adoption: " + " · ".join(
        doc_hint(path)
        for path in (ADOPTION_GUIDE, DEV_ENVIRONMENT, FIRST_EVIDENCE_LOOP)
    )


def tool_adoption_hint(name: str) -> str | None:
    """Return the resolvable per-tool "what to install next" hint, or ``None``."""

    hints = {
        "bazel": f"Install Bazel or Bazelisk — see {doc_hint(DEV_ENVIRONMENT)}",
        "nativelink": f"Install NativeLink — see {doc_hint(ADOPTION_GUIDE)}",
        "local-exec-config": (
            "Configure local execution — see "
            f"{doc_hint(DEV_ENVIRONMENT)} and {doc_hint(LOCAL_EXEC_CONFIG)}"
        ),
    }
    return hints.get(name)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class BazelVersionInfo:
    """The local Bazel version doctor observed, and whether it is a tested anchor.

    ``detected`` is the release string parsed from ``bazel version`` (``None`` when
    Bazel is absent or reports no release label — a source/dev build). ``warning``
    is a NON-BLOCKING "untested version" message when the major is outside NLFR's
    tested anchors, or ``None`` (unknown or in-range). The warning never changes
    doctor's exit code — it is advisory only (GitHub issue #85).
    """

    detected: str | None
    major: int | None
    in_tested_range: bool
    warning: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "detected": self.detected,
            "major": self.major,
            "tested_versions": list(TESTED_BAZEL_VERSIONS),
            "in_tested_range": self.in_tested_range,
            "warning": self.warning,
        }


def detect_bazel_version(bazel_path: str | None) -> str | None:
    """Return the local Bazel release string via ``bazel version``, or ``None``.

    ``None`` when Bazel is absent, the subprocess fails/times out, or the output
    carries no ``Build label`` — an honestly *unknown* version, never a guess. This
    is the only place doctor shells out; it is best-effort and never raises.
    """

    if bazel_path is None:
        return None
    try:
        completed = subprocess.run(
            [bazel_path, "version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bazel_release_from_version_output(completed.stdout)


def bazel_version_info(bazel_path: str | None) -> BazelVersionInfo:
    """Assemble the version/anchor/warning triple doctor reports."""

    detected = detect_bazel_version(bazel_path)
    warning = out_of_range_bazel_warning(detected)
    return BazelVersionInfo(
        detected=detected,
        major=bazel_major(detected),
        in_tested_range=detected is not None and warning is None,
        warning=warning,
    )


def find_any(names: tuple[str, ...]) -> str | None:
    """Return the first executable found on PATH from ``names``."""

    for name in names:
        found = shutil.which(name)
        if found is not None:
            return found
    return None


def tool_checks(mode: str, local_exec_config: str | None = None) -> list[Check]:
    """Build environment checks for the requested proof mode."""

    python_ok = sys.version_info >= (3, 11)
    bazel_path = find_any(("bazel", "bazelisk"))
    nativelink_path = find_any(("nativelink", "native-link"))

    return [
        Check(
            "python",
            python_ok,
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            if python_ok
            else "Python 3.11 or newer is required",
        ),
        Check(
            "bazel",
            bazel_path is not None,
            bazel_path or "missing bazel or bazelisk on PATH",
        ),
        Check(
            "nativelink",
            nativelink_path is not None,
            nativelink_path or "missing nativelink or native-link on PATH",
        ),
        *(_local_exec_checks(local_exec_config) if mode == "local-exec" else []),
    ]


def resolve_local_exec_config(args: argparse.Namespace) -> str | None:
    """Resolve which NativeLink local-exec config to check.

    Precedence:
      1. ``--nativelink-config`` flag.
      2. ``nativelink_config`` in the workspace ``nlfr.toml``.
      3. bundled demo config, ONLY when run inside the NLFR source checkout.
      4. otherwise ``None`` -> an honest "no config found" failed check.
    """

    flag = getattr(args, "nativelink_config", None)
    if flag:
        return flag

    workspace = Path(getattr(args, "workspace", None) or Path.cwd()).resolve()
    from_toml = nativelink_config_from_toml(workspace)
    if from_toml:
        candidate = Path(from_toml)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        return str(candidate)

    if is_within_source_checkout(workspace):
        return str(_repo_root() / "demo" / "nativelink" / "local-execution.json5")

    return None


def emit_text(
    mode: str,
    checks: list[Check],
    nativelink_config_checked: str | None = None,
    bazel_version: BazelVersionInfo | None = None,
) -> None:
    """Print human-readable doctor results to stdout and stderr."""

    print(f"nlfr doctor ({mode})")
    if mode == "local-exec":
        print(f"nativelink_config_checked: {nativelink_config_checked or '(none found)'}")
    for check in checks:
        status = "ok" if check.ok else "missing"
        print(f"[{status}] {check.name}: {check.detail}")
    if bazel_version is not None and bazel_version.detected is not None:
        range_note = "tested anchor" if bazel_version.in_tested_range else "UNTESTED anchor"
        print(f"[info] bazel version: {bazel_version.detected} ({range_note})")

    # The out-of-range version signal is a NON-BLOCKING warning: it goes to stderr
    # like an advisory, but never joins ``missing`` and never changes the exit code.
    if bazel_version is not None and bazel_version.warning is not None:
        print(f"[warn] {bazel_version.warning}", file=sys.stderr)

    missing = [check.name for check in checks if not check.ok]
    if missing:
        sys.stdout.flush()
        print(
            f"{mode} proof path is not ready; missing: " + ", ".join(missing),
            file=sys.stderr,
        )
        for check in checks:
            if check.ok:
                continue
            hint = tool_adoption_hint(check.name)
            if hint:
                print(f"  → {hint}", file=sys.stderr)
        print(f"  → {adoption_hint()}", file=sys.stderr)
        print(f"  → Run: nlfr doctor --mode {mode} --json", file=sys.stderr)


def emit_json(
    mode: str,
    checks: list[Check],
    nativelink_config_checked: str | None = None,
    bazel_version: BazelVersionInfo | None = None,
) -> None:
    """Print machine-readable doctor results as JSON."""

    payload = {
        "mode": mode,
        # ``ok`` is computed from the required checks ONLY. The bazel_version
        # warning below is advisory and deliberately excluded, so an untested
        # Bazel version never flips ``ok`` false (GitHub issue #85).
        "ok": all(check.ok for check in checks),
        "nativelink_config_checked": nativelink_config_checked,
        "checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "detail": check.detail,
            }
            for check in checks
        ],
        "bazel_version": (bazel_version or bazel_version_info(None)).as_dict(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def run(args: argparse.Namespace) -> int:
    """Run environment checks and return a process exit code."""

    config_checked = (
        resolve_local_exec_config(args) if args.mode == "local-exec" else None
    )
    checks = tool_checks(args.mode, config_checked)
    version_info = bazel_version_info(find_any(("bazel", "bazelisk")))
    if args.json:
        emit_json(args.mode, checks, config_checked, version_info)
    else:
        emit_text(args.mode, checks, config_checked, version_info)
    # The out-of-range version warning is advisory: the exit code reflects the
    # required tool checks only, never the Bazel-version anchor status.
    return 0 if all(check.ok for check in checks) else 1


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``doctor`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "doctor",
        help="check local tool availability",
        description="Check local tool availability for NativeLink proof modes.",
    )
    parser.add_argument(
        "--mode",
        choices=("cache-only", "local-exec"),
        default="cache-only",
        help="proof mode to validate",
    )
    parser.add_argument(
        "--nativelink-config",
        help=(
            "NativeLink local-exec config to check (local-exec mode). Precedence: "
            "this flag > nativelink_config in the workspace nlfr.toml > bundled "
            "demo config (only inside the NLFR source checkout)"
        ),
    )
    parser.add_argument(
        "--workspace",
        help="workspace directory whose nlfr.toml is consulted (default: cwd)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable check results",
    )
    parser.set_defaults(handler=run)


def _local_exec_checks(config: str | None = None) -> list[Check]:
    if config is None:
        return [
            Check(
                "local-exec-config",
                False,
                "no NativeLink local-execution config found; pass --nativelink-config "
                "PATH or set nativelink_config in nlfr.toml",
            )
        ]

    config_path = Path(config)
    if not config_path.exists():
        return [
            Check(
                "local-exec-config",
                False,
                f"missing NativeLink local execution config: {config_path}",
            )
        ]

    try:
        config_data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        return [
            Check(
                "local-exec-config",
                False,
                f"invalid NativeLink local execution config JSON: {config_path}: {exc}",
            )
        ]

    services = {
        service
        for server in config_data.get("servers", [])
        if isinstance(server, dict)
        for service in (server.get("services") or {})
    }
    has_scheduler = bool(config_data.get("schedulers"))
    has_worker = bool(config_data.get("workers"))
    required_services = {"execution", "worker_api", "capabilities", "cas", "ac"}
    missing_services = sorted(required_services - services)
    ok = has_scheduler and has_worker and not missing_services
    detail_parts = [
        "scheduler" if has_scheduler else "missing scheduler",
        "worker" if has_worker else "missing worker",
    ]
    if missing_services:
        detail_parts.append("missing services: " + ", ".join(missing_services))
    else:
        detail_parts.append("services: " + ", ".join(sorted(required_services)))
    return [
        Check(
            "local-exec-config",
            ok,
            f"{config_path}: " + "; ".join(detail_parts),
        )
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
