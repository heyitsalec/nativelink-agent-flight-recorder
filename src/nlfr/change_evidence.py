"""Shared per-path change-evidence derivation (GitHub issue #62).

One derivation, two callers. Both ``nlfr run --mode generic``
(:mod:`nlfr.commands.generic_run`) and ``nlfr simulate``
(:mod:`nlfr.commands.simulate_cmd`) turn a set of ``--change-path`` /
``affected_paths`` observations into the SAME per-path evidence shape:

    {
        "before_sha256": <hash|null>,
        "after_sha256":  <hash|null>,
        "changed":       <bool>,          # DERIVED, never asserted
        "changed_basis": <str>,           # HOW `changed` was derived
        "note":          <str>,           # optional honesty caveat
        # git-baseline paths additionally carry:
        "baseline_sha256": ..., "baseline_source": ...,
    }

``changed`` is always derived, never a literal, and the derivation says WHAT it
was derived against via ``changed_basis``:

* ``git_baseline`` — a sidecar-supplied, re-verified pre-edit baseline
  (``git show <commit>:<path>``); ``changed`` is ``baseline != after``. Only the
  generic recorder supplies these (they survive the documented edit-first flow).
* the caller's *observation window* otherwise — ``changed`` is ``before != after``.
  The window's honest name is the caller's to give (``window_basis``):
  ``recorder_window`` for the live generic recorder (a before/after sample around
  real command execution), ``simulate_fixture`` for ``nlfr simulate`` (a copied
  pristine template hashed, a deterministic scenario diff applied, then re-hashed
  — a controlled fixture window, not a live recording). Naming them apart keeps
  one consumer-facing change-evidence schema self-describing about how each
  before/after pair was actually observed.

Before #62 the generic recorder owned this logic (a rich per-path map with
``changed_basis``) while simulate derived a bare ``before != after`` boolean with
no per-path evidence. Factoring it here gives simulate the same shape without
re-trusting anything: simulate never supplies git baselines, so its paths always
carry ``changed_basis == window_basis``.

Stdlib only.
"""

from __future__ import annotations

from typing import Any

# Per-path change notes. Single-sourced here so the generic recorder's stderr
# warnings (:func:`nlfr.commands.generic_run._warn_unobservable_paths`) and the
# JSON evidence can never drift apart.
NOTE_NEVER_OBSERVED = "path never observed on disk"
NOTE_UNOBSERVABLE = (
    "file already at its final state when recording began; change not observable "
    "in the recording window (no git baseline available)"
)
# A supplied sidecar git_baseline that this workspace's git object store could
# not confirm. Both are recorded honestly and fall back to the recorder window.
NOTE_BASELINE_UNVERIFIABLE = "baseline unverifiable in this workspace"
# Ref-agnostic prefix (a matched baseline may be HEAD *or* a non-HEAD
# ``--baseline-ref``): the note always opens ``file matches …`` so the generic
# recorder's stderr warning can key on it either way.
NOTE_MATCHES_BASELINE_PREFIX = "file matches "
NOTE_BASELINE_MISMATCH_PREFIX = "sidecar git_baseline did not match"


def _ref_label(source: Any) -> str | None:
    """The symbolic ref label a git baseline was pinned to (``git:<label>:<path>``).

    ``--baseline-ref`` defaults to HEAD but may name a non-HEAD ref (``HEAD~1``,
    a commit sha); the sidecar records it as the middle segment of ``source.ref``.
    """

    if not isinstance(source, dict):
        return None
    ref = source.get("ref")
    if not isinstance(ref, str):
        return None
    parts = ref.split(":", 2)
    if len(parts) == 3 and parts[0] == "git":
        return parts[1]
    return None


def note_matches_head(commit: str | None, ref_label: str | None = None) -> str:
    """Baseline == after under the strongest label is AMBIGUOUS, not proof.

    The recorder cannot tell a genuine no-op (file truly unchanged) from an edit
    that was committed *before* recording began (the pre-edit ref already holds
    the final bytes). It must SAY so rather than emit a silent ``changed=false``
    under ``git_baseline`` — and point at the escape hatch (``--baseline-ref``).

    Worded from the RESOLVED ref (#62 nit): a baseline pinned to a non-HEAD
    ``--baseline-ref`` (``HEAD~1``, a commit sha) is named as such instead of
    being mislabelled "HEAD".
    """

    commit_label = commit or "unknown commit"
    ref = ref_label or "HEAD"
    subject = (
        f"file matches HEAD ({commit_label})"
        if ref == "HEAD"
        else f"file matches baseline ref {ref} ({commit_label})"
    )
    return (
        f"{subject} — either no change occurred, or the change was already "
        "committed before recording began; pass --baseline-ref <pre-edit-ref> "
        "to attest a committed change"
    )


def note_baseline_mismatch(commit: str) -> str:
    return (
        f"sidecar git_baseline did not match the git object at {commit} — "
        "baseline ignored"
    )


def derive_change_details(
    change_paths: list[str],
    before_hashes: dict[str, str | None],
    after_hashes: dict[str, str | None],
    git_baselines: dict[str, dict[str, Any]] | None = None,
    baseline_rejections: dict[str, str] | None = None,
    *,
    window_basis: str = "recorder_window",
    unobservable_note: str | None = NOTE_UNOBSERVABLE,
) -> dict[str, dict[str, Any]]:
    """Derive per-path change evidence honestly, by OBSERVATION MODE.

    ``changed`` is always derived, never asserted. What it is derived *against*
    depends on what the caller could actually OBSERVE:

    - **git baseline present** (``changed_basis="git_baseline"``): the pre-edit
      bytes came from ``git show <ref>:<path>`` and were RE-VERIFIED against the
      workspace git object store by the caller — verifiable evidence that
      survives the documented edit-first workflow. ``changed`` is
      ``baseline_sha256 != after_sha256``. A ``null`` baseline means the path was
      absent at the ref, so a present ``after`` is an honest *appeared*. When the
      baseline EQUALS ``after`` the caller cannot tell a genuine no-op from an
      edit committed *before* recording began, so an explicit note is emitted
      (and the generic recorder additionally warns on stderr) pointing at
      ``--baseline-ref`` — never a silent false.
    - **no git baseline** (``changed_basis=window_basis``): fall back to the
      caller's own before/after sample. ``changed`` is ``before != after``.

      - ``sha != sha'`` (edited in window) / ``null -> sha`` (appeared) /
        ``sha -> null`` (deleted) -> ``changed=true``.
      - ``null == null`` (never on disk) -> ``changed=false`` + ``NOTE_NEVER_OBSERVED``,
        so an operator typo in a change path stays visible.
      - ``sha == sha`` -> ``changed=false``; ``unobservable_note`` (when not
        ``None``) records the caveat. The generic recorder passes
        ``NOTE_UNOBSERVABLE`` here (it cannot attest a pre-edit state without a
        git baseline — issue #52); simulate passes ``None`` because its fixture
        window fully observed both states, so an unchanged declared path is an
        honest, self-explanatory ``changed=false``.
      - a REFUSED sidecar baseline (forged or unverifiable, see
        ``baseline_rejections``) falls here too, carrying the refusal note.
    """

    git_baselines = git_baselines or {}
    baseline_rejections = baseline_rejections or {}
    details: dict[str, dict[str, Any]] = {}
    for path in change_paths:
        before = before_hashes.get(path)
        after = after_hashes.get(path)
        entry: dict[str, Any] = {
            "before_sha256": before,
            "after_sha256": after,
        }
        baseline = git_baselines.get(path)
        if baseline is not None:
            baseline_sha = baseline.get("baseline_sha256")
            source = baseline.get("source")
            entry["baseline_sha256"] = baseline_sha
            entry["baseline_source"] = source
            entry["changed"] = baseline_sha != after
            entry["changed_basis"] = "git_baseline"
            if baseline_sha is not None and baseline_sha == after:
                commit = source.get("commit") if isinstance(source, dict) else None
                entry["note"] = note_matches_head(commit, _ref_label(source))
        else:
            entry["changed"] = before != after
            entry["changed_basis"] = window_basis
            rejection = baseline_rejections.get(path)
            if rejection is not None:
                # A supplied baseline was refused (forged / unverifiable). The
                # refusal is the salient story; it takes note precedence over the
                # generic recorder-window notes below.
                entry["note"] = rejection
            elif before is None and after is None:
                entry["note"] = NOTE_NEVER_OBSERVED
            elif before is not None and before == after:
                if unobservable_note is not None:
                    entry["note"] = unobservable_note
        details[path] = entry
    return details


def patch_applied_from(change_details: dict[str, dict[str, Any]]) -> bool:
    """``True`` iff at least one derived path actually changed.

    Derived from :func:`derive_change_details` output so ``patch_applied`` and the
    per-path ``change.paths`` map can never disagree.
    """

    return any(entry["changed"] for entry in change_details.values())
