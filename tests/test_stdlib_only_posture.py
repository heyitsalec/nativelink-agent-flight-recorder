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

The optional ``[reapi]`` extra (issue #81 part B: grpcio + protobuf for the CAS
probe) does NOT relax the posture, and the tests below prove the boundary from
both sides: ``project.dependencies`` stays empty; no module under ``src/nlfr``
imports grpc/protobuf at module level outside the generated-stub package; and
``import nlfr`` — including ``nlfr.reapi.probe`` itself — succeeds in a process
where third-party imports are structurally blocked, while asking that process
for an actual probe fails with the honest install hint.
"""

import ast
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# The ONLY place third-party (protobuf) module-level imports are allowed:
# protoc-generated message modules, themselves imported exclusively inside
# nlfr.reapi.probe's lazy import path.
GENERATED_STUB_PACKAGE = SRC / "nlfr" / "reapi" / "_gen"

# Top-level module names whose module-level import anywhere else in src/nlfr
# would break the "import nlfr is stdlib-only" guarantee.
FORBIDDEN_TOP_LEVEL_IMPORTS = {"grpc", "google"}


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


def test_reapi_extra_is_optional_and_runtime_set_stays_empty() -> None:
    """The CAS probe's gRPC stack is an OPTIONAL extra, never a runtime dep.

    ``[project.optional-dependencies].reapi`` existing is fine — pip only
    installs it on explicit request (``nativelink-agent-flight-recorder[reapi]``).
    What must never change is that the mandatory runtime set stays empty.
    """
    pyproject = _pyproject()

    assert pyproject["project"]["dependencies"] == []
    extras = pyproject["project"].get("optional-dependencies", {})
    assert "reapi" in extras, "the [reapi] extra should declare the probe's gRPC stack"
    joined = " ".join(extras["reapi"])
    assert "grpcio" in joined
    assert "protobuf" in joined


def _module_level_import_roots(path: Path) -> set[str]:
    """Top-level module names imported at MODULE level (not inside functions).

    Imports nested in module-level ``if``/``try`` blocks still count: they
    execute at import time, so a try/except-guarded ``import grpc`` would still
    make ``import nlfr`` reach for a third-party package. Only imports inside
    function/method bodies are lazy.
    """

    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            return  # function bodies are lazy — do not descend

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            return

        def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
            for alias in node.names:
                roots.add(alias.name.split(".")[0])

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])

    Visitor().visit(tree)
    return roots


def test_core_import_graph_has_no_module_level_thirdparty_imports() -> None:
    """No module under src/nlfr imports grpc/protobuf at module level.

    The single allowed exception is the protoc-generated stub package
    ``nlfr.reapi._gen`` (its modules import ``google.protobuf`` at top level by
    protoc's design) — and nothing outside ``nlfr.reapi`` may import that
    package at module level either, so the generated modules only ever load
    inside the probe's lazy import path.
    """

    offenders: list[str] = []
    gen_importers: list[str] = []
    for path in sorted((SRC / "nlfr").rglob("*.py")):
        if GENERATED_STUB_PACKAGE in path.parents or path == GENERATED_STUB_PACKAGE:
            continue
        forbidden = _module_level_import_roots(path) & FORBIDDEN_TOP_LEVEL_IMPORTS
        if forbidden:
            offenders.append(f"{path.relative_to(ROOT)}: {sorted(forbidden)}")
        if any(
            dotted == "nlfr.reapi._gen" or dotted.startswith("nlfr.reapi._gen.")
            for dotted in _module_level_dotted_imports(path)
        ):
            gen_importers.append(str(path.relative_to(ROOT)))

    assert offenders == [], (
        "Module-level third-party imports found in the stdlib-only core "
        f"(outside {GENERATED_STUB_PACKAGE.relative_to(ROOT)}): {offenders}. "
        "gRPC/protobuf must stay behind nlfr.reapi.probe's lazy import path."
    )
    assert gen_importers == [], (
        "Generated protobuf stubs imported at module level outside the probe's "
        f"lazy path: {gen_importers}"
    )


def _module_level_dotted_imports(path: Path) -> set[str]:
    """Full dotted module paths imported at module level (helper for the gate)."""

    tree = ast.parse(path.read_text(), filename=str(path))
    dotted: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            return

        def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
            for alias in node.names:
                dotted.add(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
            if node.level == 0 and node.module:
                dotted.add(node.module)

    Visitor().visit(tree)
    return dotted


# Blocks third-party imports structurally, then proves (a) the whole nlfr core
# — probe module included — imports fine, and (b) asking for an actual probe
# fails with the honest [reapi] install hint. Runs in a subprocess so the
# guarantee holds even in environments where grpcio IS installed (the CI job
# that tests the extra).
_BLOCKED_IMPORT_PROBE = r"""
import sys

BLOCKED = ("grpc", "google")


class Blocker:
    def find_spec(self, name, path=None, target=None):
        root = name.split(".")[0]
        if root in BLOCKED:
            raise ImportError(f"blocked third-party import for posture test: {name}")
        return None


sys.meta_path.insert(0, Blocker())

import nlfr  # noqa: E402
import nlfr.cli  # noqa: E402
import nlfr.reapi  # noqa: E402
import nlfr.reapi.probe  # noqa: E402

try:
    nlfr.reapi.probe.make_cas_probe("grpc://127.0.0.1:1")
except ImportError as exc:
    message = str(exc)
    assert "[reapi]" in message, message
    assert "pip install" in message, message
else:
    raise AssertionError("make_cas_probe must fail honestly without the extra")

print("POSTURE-OK")
"""


def test_import_nlfr_succeeds_with_thirdparty_blocked() -> None:
    """``import nlfr`` (and the probe module) is stdlib-only, provably.

    A meta-path blocker makes ANY grpc/protobuf import raise, then the core —
    including ``nlfr.reapi.probe`` itself — must import cleanly, and building a
    real probe must fail with the ImportError that names the install command.
    """

    result = subprocess.run(
        [sys.executable, "-c", _BLOCKED_IMPORT_PROBE],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, (
        f"stdlib-only import proof failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "POSTURE-OK" in result.stdout
