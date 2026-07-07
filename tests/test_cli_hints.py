"""Resolvable "read next" hint tests (GitHub issue #39).

Every CLI doc pointer routes through ``nlfr.config.doc_hint`` so it resolves for
BOTH documented personas:

* the uvx/pip adopter who never cloned the repo — needs the canonical GitHub URL
  (a bare ``docs/…`` path is a dead end for them); and
* the in-repo contributor — additionally gets the on-disk ``(local: <path>)``.

``source_checkout_root()`` is package-location based, so the wheel/uvx persona is
exercised by monkeypatching it to ``None`` (there is no ``demo/`` tree beside a
site-packages install — the same signal). The checkout persona uses the real
source tree these tests run from.
"""

import re

import pytest

from nlfr.commands.doctor import Check, adoption_hint, emit_text, tool_adoption_hint
from nlfr.config import doc_hint, doc_url, source_checkout_root


REPO_RELATIVE = "docs/DEV_ENVIRONMENT.md"
# Repo-relative doc paths look like ``docs/...`` or ``demo/...`` — used to prove
# no BARE path (one not embedded in a URL) is ever presented as actionable.
BARE_PATH = re.compile(r"(?<![/\w.-])(?:docs|demo)/[\w./-]+")


def _bare_paths_outside_urls(text: str) -> list[str]:
    """Return repo-relative paths that appear as bare, dead-end pointers.

    URLs are stripped first, so a path that only ever appears inside a
    ``https://github.com/.../blob/main/<path>`` URL does not count.
    """

    without_urls = re.sub(r"https://\S+", "", text)
    return BARE_PATH.findall(without_urls)


# --------------------------------------------------------------------------- #
# doc_hint() — the single centralized formatter
# --------------------------------------------------------------------------- #


def test_doc_hint_no_checkout_is_url_only(monkeypatch) -> None:
    # uvx/pip persona: no source checkout detectable.
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    hint = doc_hint(REPO_RELATIVE)

    assert hint == doc_url(REPO_RELATIVE)
    assert hint.startswith(
        "https://github.com/heyitsalec/nativelink-agent-flight-recorder/blob/main/"
    )
    # No local annotation, and the path never appears as a bare actionable pointer.
    assert "(local:" not in hint
    assert _bare_paths_outside_urls(hint) == []


def test_doc_hint_in_checkout_has_url_and_local() -> None:
    # Contributor persona: these tests run from the real source checkout.
    assert source_checkout_root() is not None
    hint = doc_hint(REPO_RELATIVE)

    assert doc_url(REPO_RELATIVE) in hint  # canonical URL always present
    assert f"(local: {REPO_RELATIVE})" in hint  # plus the on-disk pointer


def test_doc_hint_no_local_annotation_for_absent_file() -> None:
    # In a real checkout, a path that does not exist gets the URL but NO local
    # annotation — never claim a local file that is not there.
    assert source_checkout_root() is not None
    hint = doc_hint("docs/DOES_NOT_EXIST.md")

    assert hint == doc_url("docs/DOES_NOT_EXIST.md")
    assert "(local:" not in hint


def test_doc_hint_is_formatted_at_call_time(monkeypatch) -> None:
    # Persona detection must reflect the runtime environment at emit time, not a
    # value frozen at import — the guard against regressing to bare paths.
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    assert "(local:" not in doc_hint(REPO_RELATIVE)
    monkeypatch.undo()
    assert "(local:" in doc_hint(REPO_RELATIVE)


# --------------------------------------------------------------------------- #
# doctor emit_text() — the "what to do next" block for a failing check
# --------------------------------------------------------------------------- #


def _failing_checks() -> list[Check]:
    return [
        Check("python", True, "3.12.0"),
        Check("bazel", False, "missing bazel or bazelisk on PATH"),
        Check("nativelink", False, "missing nativelink on PATH"),
    ]


def test_doctor_hints_resolvable_no_checkout(monkeypatch, capsys) -> None:
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    emit_text("cache-only", _failing_checks())
    err = capsys.readouterr().err

    assert (
        "https://github.com/heyitsalec/nativelink-agent-flight-recorder/blob/main/"
        in err
    )
    # No local pointers offered, and NO bare repo-relative path presented as
    # actionable to a reader who has no clone.
    assert "(local:" not in err
    assert _bare_paths_outside_urls(err) == []


def test_doctor_hints_resolvable_in_checkout(capsys) -> None:
    assert source_checkout_root() is not None
    emit_text("cache-only", _failing_checks())
    err = capsys.readouterr().err

    # Both personas served: canonical URL AND the on-disk pointer.
    assert doc_url("docs/DEV_ENVIRONMENT.md") in err
    assert "(local: docs/DEV_ENVIRONMENT.md)" in err


def test_adoption_and_tool_hints_carry_urls(monkeypatch) -> None:
    monkeypatch.setattr("nlfr.config.source_checkout_root", lambda: None)
    assert doc_url("docs/ADOPTION_GUIDE.md") in adoption_hint()
    assert doc_url("docs/DEV_ENVIRONMENT.md") in tool_adoption_hint("bazel")
    assert doc_url("docs/ADOPTION_GUIDE.md") in tool_adoption_hint("nativelink")
    lx = tool_adoption_hint("local-exec-config")
    assert doc_url("demo/nativelink/local-execution.json5") in lx
    assert tool_adoption_hint("unknown-check") is None


@pytest.mark.parametrize(
    "path",
    [
        "docs/ADOPTION_GUIDE.md",
        "docs/DEV_ENVIRONMENT.md",
        "docs/wiki/tutorial/first-evidence-loop.md",
        "demo/nativelink/local-execution.json5",
    ],
)
def test_referenced_docs_exist_in_checkout(path) -> None:
    # The local pointer must never be a lie: every path a hint references exists.
    root = source_checkout_root()
    assert root is not None
    assert (root / path).is_file(), f"hint references a missing file: {path}"
