"""Resolve packaged ``nlfr simulate`` fixtures (scenarios + demo workspace).

Scenario JSON fixtures and the demo Bazel workspace ship inside the wheel under
``nlfr/data/`` (hatch force-include from the repo's ``demo/`` tree). Resolving
them via :mod:`importlib.resources` — stdlib, no runtime dependency added — is
what makes ``nlfr simulate`` work from a bare ``pip``/``uv tool install`` with no
source checkout present (GitHub issue #94).

The historical resolution used ``Path(__file__).resolve().parents[3] / "demo" /
"scenarios"``, which only ever pointed at real files inside a git checkout; from a
wheel it resolved to a venv-internal path that never contained the fixtures,
producing the misleading ``no scenarios found in <venv>/.../demo/scenarios``
error the issue filed.

Resolution order (both scenarios and the demo workspace):

1. an explicit user override (``--scenario-dir`` / ``--workspace-template``);
2. the packaged fixtures inside the installed wheel (this module);
3. the repo ``demo/`` tree (dev/source-checkout path — unchanged).
"""

from __future__ import annotations

import importlib.resources as resources
from pathlib import Path

PACKAGE_ANCHOR = "nlfr"
SCENARIOS_RESOURCE = "data/scenarios"
DEMO_WORKSPACE_RESOURCE = "data/demo-workspace"


def packaged_data_dir(relative: str) -> Path | None:
    """Return the on-disk path of a packaged data directory, or ``None``.

    ``importlib.resources.files("nlfr")`` anchors at the installed ``nlfr``
    package. NLFR wheels are unpacked to ``site-packages`` (never zip-imported),
    so a filesystem-backed directory resolves to a real path the caller can glob
    and ``copytree``. In a source checkout the force-included ``data/`` tree is
    absent (it only materializes in the built wheel), so this returns ``None`` and
    the caller falls back to the repo ``demo/`` path — keeping dev workflows
    unchanged.
    """

    try:
        anchor = resources.files(PACKAGE_ANCHOR)
    except (ModuleNotFoundError, TypeError):
        return None
    candidate = anchor.joinpath(*relative.split("/"))
    try:
        if not candidate.is_dir():
            return None
    except (FileNotFoundError, NotADirectoryError, OSError):
        return None
    path = Path(str(candidate))
    return path if path.is_dir() else None


def resolve_scenario_dir(
    explicit: str | None,
    *,
    packaged: Path | None,
    repo: Path,
) -> Path:
    """Resolve the scenario directory: explicit override > packaged > repo.

    Raises :class:`ValueError` naming all three resolution paths when none resolve
    — so the failure is honest and actionable instead of a bare venv-internal
    path that never held the fixtures.
    """

    if explicit is not None:
        return Path(explicit).resolve()
    if packaged is not None and packaged.is_dir():
        return packaged
    if repo.is_dir():
        return repo
    raise ValueError(no_scenario_dir_message(packaged, repo))


def scenario_source_label(explicit: str | None, resolved: Path, packaged: Path | None) -> str:
    """Return which resolution tier served ``resolved``: override/packaged/repo."""

    if explicit is not None:
        return "override"
    if packaged is not None and resolved == packaged:
        return "packaged"
    return "repo-checkout"


def no_scenario_dir_message(packaged: Path | None, repo: Path) -> str:
    """Honest triple-path error naming every resolution tier that was tried."""

    packaged_line = str(packaged) if packaged is not None else "not present in this install"
    return (
        "no scenario directory found. Tried, in order:\n"
        "  1. --scenario-dir override: not provided "
        "(pass --scenario-dir PATH to point at your own scenarios)\n"
        f"  2. packaged fixtures (importlib.resources '{PACKAGE_ANCHOR}/{SCENARIOS_RESOURCE}'): "
        f"{packaged_line}\n"
        f"  3. source checkout (demo/scenarios): {repo}\n"
        "Install a release wheel (which bundles the scenarios), run from a source "
        "checkout, or pass --scenario-dir PATH."
    )


def packaged_demo_workspace() -> Path | None:
    """Return the packaged demo Bazel workspace path, or ``None`` (source tree)."""

    return packaged_data_dir(DEMO_WORKSPACE_RESOURCE)


def wheel_workspace_fallback(cwd: Path) -> Path | None:
    """Packaged demo workspace to use when no workspace is otherwise resolvable.

    Returns the packaged demo workspace ONLY for a wheel install with no local
    Bazel workspace — so ``nlfr simulate`` runs offline from a bare directory
    (GitHub issue #94). A source checkout keeps its existing ``resolve_workspace``
    behavior (bundled ``demo/bazel-monorepo`` + stderr notice), and a ``cwd``
    Bazel marker keeps winning. Reads config heuristics only; never mutates them.
    """

    from nlfr.config import bazel_marker, source_checkout_root

    if source_checkout_root() is not None:
        return None
    if bazel_marker(cwd) is not None:
        return None
    return packaged_demo_workspace()
