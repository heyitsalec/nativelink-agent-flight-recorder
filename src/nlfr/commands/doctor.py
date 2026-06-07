"""Environment checks for local NLFR proof paths."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def find_any(names: tuple[str, ...]) -> str | None:
    """Return the first executable found on PATH from ``names``."""

    for name in names:
        found = shutil.which(name)
        if found is not None:
            return found
    return None


def tool_checks(mode: str) -> list[Check]:
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
        *(_local_exec_checks() if mode == "local-exec" else []),
    ]


def emit_text(mode: str, checks: list[Check]) -> None:
    """Print human-readable doctor results to stdout and stderr."""

    print(f"nlfr doctor ({mode})")
    for check in checks:
        status = "ok" if check.ok else "missing"
        print(f"[{status}] {check.name}: {check.detail}")

    missing = [check.name for check in checks if not check.ok]
    if missing:
        sys.stdout.flush()
        print(
            f"{mode} proof path is not ready; missing: " + ", ".join(missing),
            file=sys.stderr,
        )


def emit_json(mode: str, checks: list[Check]) -> None:
    """Print machine-readable doctor results as JSON."""

    payload = {
        "mode": mode,
        "ok": all(check.ok for check in checks),
        "checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "detail": check.detail,
            }
            for check in checks
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def run(args: argparse.Namespace) -> int:
    """Run environment checks and return a process exit code."""

    checks = tool_checks(args.mode)
    if args.json:
        emit_json(args.mode, checks)
    else:
        emit_text(args.mode, checks)
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
        "--json",
        action="store_true",
        help="emit machine-readable check results",
    )
    parser.set_defaults(handler=run)


def _local_exec_checks() -> list[Check]:
    config_path = _repo_root() / "demo" / "nativelink" / "local-execution.json5"
    if not config_path.exists():
        return [
            Check(
                "local-exec-config",
                False,
                f"missing NativeLink local execution config: {config_path}",
            )
        ]

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        return [
            Check(
                "local-exec-config",
                False,
                f"invalid NativeLink local execution config JSON: {exc}",
            )
        ]

    services = {
        service
        for server in config.get("servers", [])
        if isinstance(server, dict)
        for service in (server.get("services") or {})
    }
    has_scheduler = bool(config.get("schedulers"))
    has_worker = bool(config.get("workers"))
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
