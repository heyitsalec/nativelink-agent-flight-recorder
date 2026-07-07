"""Unit tests for packaged simulate-fixture resolution (GitHub issue #94).

These are pure/fast tests of the resolution order and the honest triple-path
error. The heavier "does it actually work from a built wheel" proof lives in
``test_simulate_wheel_install.py`` (env-gated).
"""

from pathlib import Path

import pytest

from nlfr.commands.simulate_resources import (
    no_scenario_dir_message,
    packaged_data_dir,
    resolve_scenario_dir,
    scenario_source_label,
    wheel_workspace_fallback,
)


ROOT = Path(__file__).resolve().parents[1]


def _make_scenarios(dir_path: Path) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "demo.json").write_text("{}")
    return dir_path


def test_explicit_override_wins_over_packaged_and_repo(tmp_path) -> None:
    override = _make_scenarios(tmp_path / "override")
    packaged = _make_scenarios(tmp_path / "packaged")
    repo = _make_scenarios(tmp_path / "repo")

    resolved = resolve_scenario_dir(str(override), packaged=packaged, repo=repo)

    assert resolved == override.resolve()
    assert scenario_source_label(str(override), resolved, packaged) == "override"


def test_packaged_preferred_over_repo(tmp_path) -> None:
    packaged = _make_scenarios(tmp_path / "packaged")
    repo = _make_scenarios(tmp_path / "repo")

    resolved = resolve_scenario_dir(None, packaged=packaged, repo=repo)

    assert resolved == packaged
    assert scenario_source_label(None, resolved, packaged) == "packaged"


def test_falls_back_to_repo_when_no_packaged(tmp_path) -> None:
    repo = _make_scenarios(tmp_path / "repo")

    resolved = resolve_scenario_dir(None, packaged=None, repo=repo)

    assert resolved == repo
    assert scenario_source_label(None, resolved, None) == "repo-checkout"


def test_falls_back_to_repo_when_packaged_path_absent(tmp_path) -> None:
    # A packaged path is supplied but does not exist on disk (defensive): the
    # resolver must skip it and use the repo checkout, not blindly trust it.
    missing_packaged = tmp_path / "packaged-missing"
    repo = _make_scenarios(tmp_path / "repo")

    resolved = resolve_scenario_dir(None, packaged=missing_packaged, repo=repo)

    assert resolved == repo


def test_honest_triple_path_error_names_all_three(tmp_path) -> None:
    missing_packaged = tmp_path / "pkg"  # does not exist
    missing_repo = tmp_path / "repo"  # does not exist

    with pytest.raises(ValueError) as exc_info:
        resolve_scenario_dir(None, packaged=missing_packaged, repo=missing_repo)

    message = str(exc_info.value)
    assert "--scenario-dir override" in message
    assert "packaged fixtures" in message
    assert "source checkout (demo/scenarios)" in message
    assert str(missing_repo) in message


def test_error_message_when_no_packaged_dir_present(tmp_path) -> None:
    message = no_scenario_dir_message(None, tmp_path / "repo")
    assert "not present in this install" in message


def test_packaged_data_dir_returns_none_for_missing_resource() -> None:
    assert packaged_data_dir("data/definitely-not-a-real-resource-xyz") is None


def test_packaged_data_dir_resolves_a_real_package_subdir() -> None:
    # ``commands`` is a real subpackage directory under ``nlfr/`` in every
    # layout, so this exercises the filesystem-backed importlib.resources branch
    # without depending on whether the force-included ``data/`` tree is present
    # (it is not in a source checkout).
    found = packaged_data_dir("commands")
    assert found is not None
    assert found.is_dir()
    assert (found / "simulate_cmd.py").is_file()


def test_wheel_workspace_fallback_is_none_in_source_checkout() -> None:
    # The test suite runs from a source checkout, so simulate keeps its existing
    # resolve_workspace behavior and never uses the packaged-workspace fallback.
    assert wheel_workspace_fallback(ROOT) is None
