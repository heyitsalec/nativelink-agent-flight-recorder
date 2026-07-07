"""Guard the stdlib-only, zero-runtime-dependency security posture.

NLFR's enterprise-security-review argument rests on one auditable fact: the
runtime dependency set is empty (see the comment on ``project.dependencies`` in
``pyproject.toml`` and ``docs/SECURITY_MODEL.md``). Nothing is pulled in at
runtime, so there is no transitive supply-chain surface to compromise — the only
trust root is the CPython standard library plus the operator's own Bazel /
NativeLink.

This test fails the moment a runtime dependency is added, forcing that decision
to be explicit rather than accidental. Dev-only tooling (pytest, jsonschema)
lives in ``[dependency-groups].dev`` and is intentionally *not* covered by the
empty-set assertion.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_runtime_dependency_set_is_empty() -> None:
    """The security selling point: zero runtime dependencies, stdlib only.

    If this fails, NLFR has grown a runtime dependency. That is a security
    posture change, not a routine edit — update docs/SECURITY_MODEL.md and the
    SBOM job's rationale before relaxing this assertion.
    """
    deps = _pyproject()["project"]["dependencies"]

    assert deps == [], (
        "NLFR must stay stdlib-only at runtime (project.dependencies == []). "
        f"Found runtime dependencies: {deps!r}. Adding a runtime dependency "
        "changes the supply-chain attack surface the security review depends on "
        "— justify it in docs/SECURITY_MODEL.md before touching this list."
    )


def test_dev_tooling_is_scoped_to_dev_group() -> None:
    """Dev-only tooling stays in the dev group, never in runtime dependencies."""
    pyproject = _pyproject()
    dev = pyproject.get("dependency-groups", {}).get("dev", [])

    # Sanity: the known dev tools live here, out of the runtime set.
    joined = " ".join(dev)
    assert "pytest" in joined
    assert "jsonschema" in joined
