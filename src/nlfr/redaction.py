"""Secret-pattern scanning and redaction for NLFR projection JSON.

Stdlib only (``re`` + ``json``). This module is the shared engine behind
``scripts/redact-projection.py`` and the repo-level ``--check`` gate.

Two things happen here, honestly labelled:

1. **Home-path scrubbing** (legacy behaviour, preserved): ``/Users/<name>`` and
   ``/home/<name>`` prefixes collapse to ``${HOME}``.
2. **Secret-pattern detection**: a registry of named detectors finds credential
   shapes (AWS access-key ids + secret keys, GitHub classic *and* fine-grained
   (``github_pat_``) tokens, GitLab/Slack tokens, PEM private keys, bearer
   credentials, JWTs, URL userinfo) and a separate **PII tier** (emails, public
   IPv4, hostnames). Matched spans are replaced with ``[REDACTED:<detector>]``.
3. **Absolute local-path detection** (``abs_path``, on by default): non-home
   absolute filesystem paths (``/private/tmp/…``, ``/data/…``) and local
   ``file:///`` URIs that the home-only scrub misses. It shares recognition and
   replacement with :func:`scrub_local_paths` (the projection-time scrubber), so
   ``--check`` reports exactly what write-mode scrubs — collapsing the directory
   to ``[REDACTED:abs_path]/<basename>`` while keeping the basename (and a
   ``file://`` scheme). ``/Users``/``/home`` stay with ``home_path`` (``${HOME}``);
   Bazel labels, ``../`` relatives, and remote URI authorities are never flagged.

**Scope and limits — read this before trusting a published projection.**
This layer is *defense-in-depth pattern matching, not a guarantee.* It reliably
catches credentials that carry a recognizable **shape**: a known prefix
(``AKIA`` / ``ghp_`` / ``github_pat_`` / ``glpat-`` / ``xox…``), a structural
marker (a PEM header, a ``Bearer …`` scheme, a ``secret_access_key=…`` /
``"SecretAccessKey": …`` assignment), or a credential-named JSON key. It
**cannot** catch a *free-standing high-entropy secret* that has no prefix and no
contextual marker — e.g. a bare 40-char AWS secret access key pasted into
narrative log/stdout text with nothing around it — because a context-free
"high-entropy string" rule would false-positive over the SHA-1/SHA-256 digests
and base64 payloads that fill NLFR's corpus. Operators handling sensitive
workspaces must treat published projections as *scrubbed on a best-effort
basis*, not as *proven secret-free*, and should review evidence at the source
rather than relying on regex redaction alone.

Design constraints that keep the detectors honest on NLFR's own corpus:

* NLFR projection JSON is *full* of 64-hex SHA-256 digests and 40-hex SHA-1
  shapes. **No detector flags a bare hex digest.** The AWS secret-key detector
  fires on a 40-char base64-ish value only when it is either (a) under a
  credential-ish key or (b) introduced by an in-text ``secret_access_key=…``
  marker — and in *both* paths a value that is pure hex (upper- **or** lowercase)
  or all-digits is rejected, so it can never collide with a SHA-1/SHA-256 digest.
* Loopback / link-local endpoints are **not** sensitive: ``grpc://127.0.0.1``
  and friends are excluded from the IPv4 detector.
* Bazel labels (``//foo:bar``), file names (``flake.nix``), Python module paths
  (``nlfr.ingest.worker``) and contract versions (``receipt.v1``) are *not*
  hostnames — the hostname detector requires a real TLD from a curated list.

Redaction is structure-aware: the JSON tree is walked, string values *and* dict
keys are scanned. A secret-shaped **key** is reported but never rewritten
(rewriting a key would break consumers) — it is a ``--check`` failure, not a
silent mutation. When any value is redacted inside an object that carries a
``redaction_state`` field, that object's state is honestly upgraded
(``safe``/``unknown`` -> ``redacted``); ``blocked`` and existing ``redacted``
are never downgraded.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

__all__ = [
    "RedactionConfig",
    "Finding",
    "RedactionResult",
    "redact_payload",
    "redact_json_text",
    "redact_string",
    "scrub_local_paths",
    "SECRET_DETECTORS",
    "PATH_DETECTORS",
    "PII_DETECTORS",
    "DETECTORS",
]

# ---------------------------------------------------------------------------
# Detector primitives
# ---------------------------------------------------------------------------

#: Substitution written in place of a matched secret span.
_REDACTED = "[REDACTED:{name}]"

#: Replacement used by the legacy home-path scrubber (kept for compatibility).
_HOME_REPLACEMENT = "${HOME}"

#: Placeholder for an absolute local path scrubbed at the projection sharing
#: boundary. Keeps the basename so the scrubbed path stays interpretable
#: (``/a/b/c/bazel-bep.json`` -> ``[REDACTED:abs_path]/bazel-bep.json``).
_ABS_PATH_PLACEHOLDER = "[REDACTED:abs_path]"

Span = tuple  # (start: int, end: int)
Finder = Callable[[str, Optional[str]], Iterable[Span]]


@dataclass(frozen=True)
class Detector:
    """A single named secret/PII/path detector.

    ``find`` returns non-overlapping-agnostic ``(start, end)`` spans within
    ``value``; overlap resolution happens centrally in :func:`_resolve_spans`.
    ``replacement`` defaults to ``[REDACTED:<name>]`` but the home-path detector
    overrides it with ``${HOME}``. ``replace`` (when set) is a per-match callable
    that computes the substitution from the matched text — used by the
    ``abs_path`` detector to keep the basename (``[REDACTED:abs_path]/<basename>``)
    and preserve a ``file://`` scheme; it wins over ``replacement`` when present.
    """

    name: str
    tier: str  # "secret" | "path" | "pii"
    find: Finder
    replacement: str | None = None
    replace: Callable[[str], str] | None = None

    def replacement_text(self) -> str:
        return self.replacement or _REDACTED.format(name=self.name)


# --- helpers for building regex-based finders ------------------------------


def _regex_finder(
    pattern: re.Pattern,
    *,
    group: int = 0,
    reject: re.Pattern | None = None,
) -> Finder:
    """Build a finder that yields the span of ``group`` for each match.

    ``reject`` (when given) drops any match whose captured text *fully* matches
    it — used to exclude SHA-1 hex shapes from the AWS secret-key detector.
    """

    def _find(value: str, key: str | None) -> Iterable[Span]:
        for match in pattern.finditer(value):
            text = match.group(group)
            if not text:
                continue
            if reject is not None and reject.fullmatch(text):
                continue
            yield match.span(group)

    return _find


# --- secret detectors ------------------------------------------------------

_AWS_ACCESS_KEY_ID = re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")

_GITHUB_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")

# Fine-grained personal access tokens: prefix ``github_pat_`` then GitHub's
# documented 82-char body (22 alnum + ``_`` + 59 alnum, char set ``[A-Za-z0-9_]``
# — the same shape gitleaks matches as ``github_pat_[0-9a-zA-Z_]{82}``). The
# classic ``gh[pousr]_`` detector above cannot see these (``github_pat_`` has no
# ``gh[pousr]_`` prefix), so without this they are entirely undetected. Tail
# bounded ``{50,255}`` — tolerant of length drift while staying distinctive.
_GITHUB_FINE_GRAINED_PAT = re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,255}\b")

_GITLAB_PAT = re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")

_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")

_PRIVATE_KEY_PEM = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"
    r"(?:[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----)?"
)

_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")

# scheme://user:pass@host  -> redact just the "user:pass" userinfo.
_URL_USERINFO = re.compile(
    r"(?<=://)(?P<cred>[^/\s:@]+:[^/\s:@]+)(?=@)"
)

# Authorization credential: capture only the token after Bearer/Basic/Token so
# the scheme word survives ("Bearer [REDACTED:...]" stays readable).
_AUTH_CREDENTIAL = re.compile(
    r"(?i)\b(?:bearer|basic|token)\s+(?P<cred>[A-Za-z0-9._~+/=-]{12,})"
)

# 40-char base64-ish AWS secret-access-key shape. Only meaningful under a
# credential-ish key (see _aws_secret_finder). Pure lowercase hex is rejected so
# a 40-hex SHA-1 can never be flagged.
_AWS_SECRET_CANDIDATE = re.compile(
    r"(?<![A-Za-z0-9/+])[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+=])"
)
# Reject pure-hex digests. Case-INSENSITIVE on purpose: SHA digests in NLFR are
# lowercase, but an uppercase/mixed-case 40-hex string in evidence is still a
# digest, not a live secret — matching only ``[0-9a-f]`` here would let an
# UPPERCASE 40-hex under a credential-ish key be mislabelled an AWS secret.
_SHA1_HEX = re.compile(r"[0-9a-fA-F]{40}")
_ALL_DIGITS = re.compile(r"[0-9]+")

# In-text credential marker: an AWS secret-access-key name, a ``:`` or ``=``
# separator (JSON ``"SecretAccessKey": "…"`` or shell ``KEY=…``, optional
# quotes/whitespace), then a 40-char base64-ish value. This catches the
# realistic log/stdout-capture case where the credential *name* lives inside a
# string body rather than as the JSON key — without going context-free.
_AWS_SECRET_IN_TEXT = re.compile(
    r"(?i)(?:aws[_-]?)?secret[_-]?access[_-]?key"
    r"['\"]?\s*[:=]\s*['\"]?"
    r"(?P<val>[A-Za-z0-9/+]{40})"
    r"(?![A-Za-z0-9/+=])"
)

#: Key names that make a 40-char base64-ish value look like a live secret.
#: Deliberately excludes bare ``token`` (NLFR JSON has ``input_tokens`` etc.).
_SECRET_KEY_CONTEXT = re.compile(
    r"(?i)(secret|passwd|password|pwd|api[_-]?key|access[_-]?key|"
    r"client[_-]?secret|private[_-]?key|credential)"
)

_HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s\"'\\]+")


# --- absolute local-path recognition (shared by the abs_path detector and the
#     projection-time scrubber :func:`scrub_local_paths`) ---------------------
#
# An absolute POSIX path with at least two segments (a directory and a
# basename). The leading lookbehind excludes Bazel labels (``//foo:bar``),
# external repos (``@repo//pkg:tgt``), relative paths (``../x``, ``./x``) and
# remote URI authorities (``grpc://host``, ``bytestream://h``, ``https://h``,
# ``ssh://h``): a ``/`` preceded by a word char, ``.``, ``/``, ``:``, ``-``,
# ``}`` (a ``${HOME}`` tail) or ``]`` (a ``[REDACTED:…]`` tail — idempotency)
# never opens a match, so only a genuine path boundary (start-of-string,
# whitespace, ``=`` in a flag value, a quote) does. Segment chars stop at ``:``
# so a trailing ``:port`` never joins a path.
_ABS_PATH = re.compile(r"(?<![\w./:}\]-])/[^/\s:\"'\\]+(?:/[^/\s:\"'\\]+)+")

#: ``file://`` is a *local* path scheme (unlike ``bytestream://``/``grpc://``/
#: ``https://``/``ssh://`` remote authorities), so the empty-authority
#: ``file:///abs/path`` form leaks a local path and must be scrubbed. Only the
#: triple-slash (empty authority) form matches — ``file://host/share`` is a
#: remote authority and is deliberately left intact. The scheme is preserved in
#: the replacement (``file://[REDACTED:abs_path]/out.txt``).
_FILE_URI = re.compile(r"\bfile://(?P<path>/[^/\s:\"'\\]+(?:/[^/\s:\"'\\]+)*)")

_FILE_URI_SCHEME = "file://"


def _abs_path_replacement(matched: str) -> str:
    """:func:`scrub_local_paths` semantics for a single matched absolute path.

    Collapses the directory portion to :data:`_ABS_PATH_PLACEHOLDER` while
    preserving the basename so the value stays interpretable
    (``/a/b/bep.json`` -> ``[REDACTED:abs_path]/bep.json``). A ``file://`` scheme
    is preserved honestly (``file:///Users/a/out.txt`` ->
    ``file://[REDACTED:abs_path]/out.txt``).
    """

    scheme = ""
    body = matched
    if body.startswith(_FILE_URI_SCHEME):
        scheme = _FILE_URI_SCHEME
        body = body[len(_FILE_URI_SCHEME):]
    basename = body.rsplit("/", 1)[-1]
    if basename:
        return f"{scheme}{_ABS_PATH_PLACEHOLDER}/{basename}"
    return f"{scheme}{_ABS_PATH_PLACEHOLDER}"


def _abs_path_finder(value: str, key: str | None) -> Iterable[Span]:
    """Absolute local filesystem paths, minus the home paths ``home_path`` owns.

    Recognition is shared with :func:`scrub_local_paths`: the generic
    multi-segment absolute-path shape (:data:`_ABS_PATH`) plus local
    ``file:///`` URIs (:data:`_FILE_URI`). Home paths (``/Users``/``/home``) are
    skipped so the ``home_path`` detector keeps ownership of them and its
    ``${HOME}`` replacement — the ``abs_path`` detector adds only the *non-home*
    class (``/private/tmp/…``, ``/var/folders/…``, ``/data/…``) that the
    home-only scrub misses. A ``file:///Users/…`` URI is still caught here (the
    scheme, not the home segment, is what makes it an abs_path finding).
    """

    spans: set[Span] = set()
    for match in _FILE_URI.finditer(value):
        spans.add(match.span(0))
    for match in _ABS_PATH.finditer(value):
        if _HOME_PATH.match(match.group(0)):
            continue
        spans.add(match.span(0))
    yield from sorted(spans)


def _is_aws_secret_shape(text: str) -> bool:
    """A 40-char base64-ish window is a *candidate* secret unless it is a digest.

    Pure hex (upper- or lowercase — an SHA-1/short digest) and all-digit windows
    are NLFR's ubiquitous non-secret shapes, so they are rejected in every path.
    """

    if _SHA1_HEX.fullmatch(text):
        return False
    if _ALL_DIGITS.fullmatch(text):
        return False
    return True


def _aws_secret_finder(value: str, key: str | None) -> Iterable[Span]:
    """Flag 40-char base64-ish AWS secret keys via two contextual paths.

    Path 1 (JSON key context): under a credential-ish JSON *key*, any 40-char
    base64-ish value is a candidate. Path 2 (in-text marker): a
    ``secret_access_key=…`` / ``"SecretAccessKey": …`` assignment *inside* a
    string body (e.g. a stdout/log capture under an innocuous key) flags the
    value that follows the marker. Both paths reject digests via
    :func:`_is_aws_secret_shape`. Spans are de-duplicated so a value that matches
    both paths is reported once.
    """

    spans: set[Span] = set()
    if key and _SECRET_KEY_CONTEXT.search(key):
        for match in _AWS_SECRET_CANDIDATE.finditer(value):
            if _is_aws_secret_shape(match.group(0)):
                spans.add(match.span(0))
    for match in _AWS_SECRET_IN_TEXT.finditer(value):
        if _is_aws_secret_shape(match.group("val")):
            spans.add(match.span("val"))
    yield from sorted(spans)


SECRET_DETECTORS: list[Detector] = [
    Detector("home_path", "secret", _regex_finder(_HOME_PATH), replacement=_HOME_REPLACEMENT),
    Detector("private_key_pem", "secret", _regex_finder(_PRIVATE_KEY_PEM)),
    Detector("aws_access_key_id", "secret", _regex_finder(_AWS_ACCESS_KEY_ID)),
    Detector("github_token", "secret", _regex_finder(_GITHUB_TOKEN)),
    Detector("github_pat", "secret", _regex_finder(_GITHUB_FINE_GRAINED_PAT)),
    Detector("gitlab_pat", "secret", _regex_finder(_GITLAB_PAT)),
    Detector("slack_token", "secret", _regex_finder(_SLACK_TOKEN)),
    Detector("jwt", "secret", _regex_finder(_JWT)),
    Detector("url_credentials", "secret", _regex_finder(_URL_USERINFO, group="cred")),
    Detector("authorization_credential", "secret", _regex_finder(_AUTH_CREDENTIAL, group="cred")),
    Detector("aws_secret_access_key", "secret", _aws_secret_finder),
]


# --- path tier detector ----------------------------------------------------
#
# ``abs_path`` closes the gap the reviewer of #63 found: the projection-time
# scrubber :func:`scrub_local_paths` collapses non-home absolute paths at the
# *sharing boundary*, but until now it was NOT in the detector registry, so
# ``nlfr redact --check`` — the documented belt-and-suspenders before sharing —
# could not *see* the leak class it closes. A stale/pre-fix projection or a
# future producer bypassing ``redact_projection_node`` (e.g. ``"cwd":
# "/private/tmp/ci-runner/ws"`` under a ``redaction_state: safe`` node) would
# pass ``--check`` silently. This detector reuses the same recognition
# (``_abs_path_finder``) and replacement (``_abs_path_replacement``) as the
# scrubber, so ``--check`` reports what write-mode scrubs. It is on by default
# (see :class:`RedactionConfig.enable_abs_path`).
PATH_DETECTORS: list[Detector] = [
    Detector("abs_path", "path", _abs_path_finder, replace=_abs_path_replacement),
]


# --- PII tier detectors ----------------------------------------------------

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_IPV4 = re.compile(
    r"(?<![0-9.])"
    r"(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])"
    r"(?![0-9.])"
)

#: Curated TLDs. Public infra + the internal TLDs that actually matter for a
#: security review. A curated list (not "any dotted token") is what keeps
#: ``flake.nix`` / ``receipt.v1`` / ``nlfr.ingest.worker`` from being flagged.
#:
#: Deliberately omits ``sh`` (a real ccTLD, but in NLFR's corpus every
#: ``foo.sh`` is a shell script — ``record-agent-change.sh`` is not a host).
#: This is why the whole hostname detector is opt-in (see ``enable_hostname``):
#: in this domain, host shapes and tool/file names are genuinely ambiguous.
_HOSTNAME_TLDS = (
    # public
    "com|net|org|io|dev|ai|co|app|cloud|gov|edu|info|biz|xyz|tech|me|us|uk|"
    "ca|de|fr|jp|cn|au|eu|nl|se|es|it|ch|in|ru|br|"
    # internal / private-network conventions
    "internal|local|localdomain|corp|lan|intranet|priv|private"
)
_HOSTNAME = re.compile(
    r"(?<![A-Za-z0-9._-])"
    r"(?:[A-Za-z0-9-]+\.)+"
    r"(?:" + _HOSTNAME_TLDS + r")"
    r"(?![A-Za-z0-9.-])",
    re.IGNORECASE,
)


def _ipv4_finder(value: str, key: str | None) -> Iterable[Span]:
    """Public / RFC1918 IPv4 only; loopback and link-local are not sensitive."""
    for match in _IPV4.finditer(value):
        octets = [int(part) for part in match.group(0).split(".")]
        first, second = octets[0], octets[1]
        # 127.0.0.0/8 loopback, 0.0.0.0/8 "this network", 169.254/16 link-local.
        if first in (0, 127):
            continue
        if first == 169 and second == 254:
            continue
        yield match.span(0)


def _hostname_finder(value: str, key: str | None) -> Iterable[Span]:
    for match in _HOSTNAME.finditer(value):
        # A dotted quad is handled by the IPv4 detector, not here.
        if _IPV4.fullmatch(match.group(0)):
            continue
        yield match.span(0)


PII_DETECTORS: list[Detector] = [
    Detector("email", "pii", _regex_finder(_EMAIL)),
    Detector("ipv4", "pii", _ipv4_finder),
    Detector("hostname", "pii", _hostname_finder),
]

#: Registry order defines tie-break priority in overlap resolution: secrets
#: first (home-path and PEM before the generic shapes), then the path tier
#: (abs_path), then PII. home_path (secret) precedes abs_path so ``/Users``/
#: ``/home`` keep their ``${HOME}`` collapse; abs_path skips those anyway.
DETECTORS: list[Detector] = SECRET_DETECTORS + PATH_DETECTORS + PII_DETECTORS


# ---------------------------------------------------------------------------
# Projection-boundary local-path scrubbing (issue #60)
# ---------------------------------------------------------------------------
#
# The detector registry above scrubs *secret shapes*. The recorder additionally
# captures the adopter's real absolute local paths — an invocation ``cwd`` and
# the injected ``--build_event_json_file=<abs path>`` inside ``command``. Those
# are not secrets, but on a projection the adopter is told to *share* (a PR /
# dashboard), a plaintext ``/Users/<name>/...`` or ``/private/tmp/...`` leaks the
# local filesystem layout on a node that would otherwise self-label
# ``redaction_state: safe``. :func:`scrub_local_paths` is the projection-time
# scrubber the graph/runway projectors run over every shareable field. It shares
# its recognition (:data:`_ABS_PATH`/:data:`_FILE_URI`) and per-match
# replacement (:func:`_abs_path_replacement`) with the ``abs_path`` detector, so
# ``nlfr redact --check`` reports exactly the class write-mode scrubs. The
# recorder never mutates SQLite evidence with it — scrubbing happens only when a
# projection is built at the sharing boundary.


def scrub_local_paths(value: str, roots: Iterable[str] | None = None) -> tuple[str, int]:
    """Replace absolute local filesystem paths with a basename-preserving marker.

    Catches home directories (``/Users/<n>``, ``/home/<n>``) *and* the arbitrary
    absolute paths the home-only :data:`_HOME_PATH` detector misses
    (``/private/tmp/...``, ``/var/folders/...``), plus local ``file:///`` URIs.
    Each match keeps its basename so the projection stays interpretable::

        /Users/a/proj/workspace                  -> [REDACTED:abs_path]/workspace
        --build_event_json_file=/tmp/x/bep.json  -> --build_event_json_file=[REDACTED:abs_path]/bep.json
        file:///Users/a/out.txt                  -> file://[REDACTED:abs_path]/out.txt

    Remote URI authorities are left intact (``grpc://``, ``bytestream://``,
    ``https://``, ``ssh://``, and ``file://host/share`` with a non-empty
    authority); only the empty-authority ``file:///abs`` form is a local path.

    Deterministic and idempotent (the placeholder carries no ``/seg/seg`` shape,
    so re-running is a no-op). Returns ``(scrubbed, replacement_count)``; a
    non-string ``value`` returns ``(value, 0)`` unchanged.

    ``roots`` is an optional list of known-sensitive absolute roots. The generic
    pass already collapses every multi-segment absolute path, so ``roots`` is a
    boundary-anchored belt-and-suspenders catch for a *single-segment* root
    (e.g. ``/data``) that the 2+-segment generic rule would otherwise leave.
    """

    if not isinstance(value, str):
        return value, 0
    count = 0

    def _replace(match: re.Match) -> str:
        nonlocal count
        count += 1
        return _abs_path_replacement(match.group(0))

    normalized_roots = sorted(
        {r.rstrip("/") for r in (roots or []) if isinstance(r, str) and r.startswith("/")},
        key=len,
        reverse=True,
    )
    if normalized_roots:
        # Boundary-anchored so a root can only match as a whole path token
        # (never inside another word): same leading lookbehind as the generic
        # pass, and the tail may extend through further path segments.
        alternation = "|".join(re.escape(root) for root in normalized_roots)
        # ``\]`` in the lookbehind keeps a single-segment root (e.g. ``/data``)
        # from re-matching the ``]/data`` tail of a placeholder we just wrote,
        # so the scrub stays idempotent even with ``roots``.
        root_re = re.compile(
            r"(?<![\w./:\]-])(?:" + alternation + r")(?:/[^/\s:\"'\\]+)*(?![\w])"
        )
        value = root_re.sub(_replace, value)

    # Local ``file:///`` URIs first (the generic pass's lookbehind excludes the
    # scheme-anchored path), then the generic absolute-path pass.
    value = _FILE_URI.sub(_replace, value)
    result = _ABS_PATH.sub(_replace, value)
    return result, count


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class RedactionConfig:
    """Which detectors run and whether we rewrite (default) or scan (``--check``).

    Secret-tier detectors are always on. The path tier (``abs_path``) is on by
    default (``enable_abs_path``): a non-home absolute local path on a projection
    told to ``safe`` is exactly the leak ``nlfr redact --check`` must catch. Of
    the PII tier, ``email`` and ``ipv4`` are on by default in the publish path
    (both genuinely sensitive and, on NLFR's corpus, false-positive-free).
    ``hostname`` is **opt-in** (``--hostname``): host shapes are
    indistinguishable from tool/file names in this domain
    (``record-agent-change.sh``, ``receipt.v1``, ``nlfr.ingest.worker``), so
    redacting them by default would block honest publishes rather than protect
    anything. Each toggleable detector is individually controllable.
    """

    redact: bool = True
    enable_abs_path: bool = True
    enable_email: bool = True
    enable_ip: bool = True
    enable_hostname: bool = False

    def is_enabled(self, detector: Detector) -> bool:
        if detector.tier == "secret":
            return True
        if detector.tier == "path":
            return self.enable_abs_path
        return {
            "email": self.enable_email,
            "ipv4": self.enable_ip,
            "hostname": self.enable_hostname,
        }.get(detector.name, True)

    def enabled_detectors(self) -> list[Detector]:
        return [d for d in DETECTORS if self.is_enabled(d)]


# ---------------------------------------------------------------------------
# Findings + result containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One detected span, for the ``--check`` report. Never carries a raw secret."""

    json_path: str
    detector: str
    tier: str
    location: str  # "value" | "key"
    excerpt: str  # already masked

    def format_line(self) -> str:
        return f"  {self.detector} ({self.tier}) at {self.json_path} [{self.location}] :: {self.excerpt}"


@dataclass
class RedactionResult:
    payload: object
    findings: list[Finding] = field(default_factory=list)
    counts: Counter = field(default_factory=Counter)

    @property
    def total_replacements(self) -> int:
        return sum(self.counts.values())


# ---------------------------------------------------------------------------
# Core span resolution + string redaction
# ---------------------------------------------------------------------------


def _resolve_spans(value: str, key: str | None, config: RedactionConfig):
    """Collect enabled-detector spans and greedily pick non-overlapping ones.

    Deterministic: sort by (start, longest-first, registry-order); earliest
    wins, longest breaks ties, registry order is the final tie-break.
    """

    candidates = []
    for idx, detector in enumerate(DETECTORS):
        if not config.is_enabled(detector):
            continue
        for start, end in detector.find(value, key):
            if end > start:
                candidates.append((start, end, idx, detector))

    candidates.sort(key=lambda c: (c[0], -(c[1] - c[0]), c[2]))
    chosen: list[tuple[int, int, Detector]] = []
    last_end = -1
    for start, end, _idx, detector in candidates:
        if start >= last_end:
            chosen.append((start, end, detector))
            last_end = end
    return chosen


def redact_string(value: str, key: str | None, config: RedactionConfig):
    """Return ``(new_value, applied_detectors)`` for one string.

    ``applied_detectors`` is the ordered list of :class:`Detector` objects whose
    spans were replaced (empty when nothing matched).
    """

    chosen = _resolve_spans(value, key, config)
    if not chosen:
        return value, []
    out: list[str] = []
    cursor = 0
    applied: list[Detector] = []
    for start, end, detector in chosen:
        out.append(value[cursor:start])
        if detector.replace is not None:
            out.append(detector.replace(value[start:end]))
        else:
            out.append(detector.replacement_text())
        applied.append(detector)
        cursor = end
    out.append(value[cursor:])
    return "".join(out), applied


def _mask_excerpt(redacted_value: str, window: int = 32) -> str:
    """Build a short, already-masked excerpt around the first redaction marker.

    Operates on the *redacted* string, so no raw secret can leak into a report.
    """

    marker = redacted_value.find("[REDACTED:")
    if marker == -1:
        marker = redacted_value.find(_HOME_REPLACEMENT)
    if marker == -1:
        snippet = redacted_value[: 2 * window]
        return snippet + ("..." if len(redacted_value) > len(snippet) else "")
    start = max(0, marker - window)
    end = min(len(redacted_value), marker + window)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(redacted_value) else ""
    return f"{prefix}{redacted_value[start:end]}{suffix}"


# ---------------------------------------------------------------------------
# Structure-aware walk
# ---------------------------------------------------------------------------


_UPGRADEABLE_STATES = {"safe", "unknown"}


def redact_payload(payload: object, config: RedactionConfig | None = None) -> RedactionResult:
    """Walk a decoded JSON value, redacting strings and honestly relabelling.

    Dict keys are scanned (report-only — a secret-shaped key is a finding, never
    a rewrite). When a value is redacted inside an object carrying
    ``redaction_state``, that object is upgraded ``safe``/``unknown`` ->
    ``redacted`` (in redact mode); ``blocked`` and ``redacted`` are preserved.
    """

    config = config or RedactionConfig()
    result = RedactionResult(payload=None)

    def _record(finding: Finding) -> None:
        result.findings.append(finding)

    def walk(node: object, path: str, key: str | None):
        # Returns (new_node, redacted_in_scope: bool).
        if isinstance(node, str):
            new_value, applied = redact_string(node, key, config)
            if applied:
                masked = _mask_excerpt(new_value)
                for detector in applied:
                    result.counts[detector.name] += 1
                    _record(Finding(path, detector.name, detector.tier, "value", masked))
                return (new_value if config.redact else node), True
            return node, False

        if isinstance(node, list):
            redacted_here = False
            new_list = []
            for index, item in enumerate(node):
                new_item, child_redacted = walk(item, f"{path}[{index}]", None)
                new_list.append(new_item)
                redacted_here = redacted_here or child_redacted
            return new_list, redacted_here

        if isinstance(node, dict):
            carries_state = "redaction_state" in node
            redacted_children = False
            new_dict: dict = {}
            for dict_key, dict_value in node.items():
                _scan_key(dict_key, path)
                new_value, child_redacted = walk(dict_value, _join(path, dict_key), dict_key)
                new_dict[dict_key] = new_value
                redacted_children = redacted_children or child_redacted

            if carries_state and redacted_children:
                if config.redact:
                    current = new_dict.get("redaction_state")
                    if isinstance(current, str) and current in _UPGRADEABLE_STATES:
                        new_dict["redaction_state"] = "redacted"
                # This object owns its scope: stop the flag from bubbling higher.
                return new_dict, False
            return new_dict, redacted_children

        # int / float / bool / None pass through untouched.
        return node, False

    def _scan_key(dict_key: str, parent_path: str) -> None:
        if not isinstance(dict_key, str):
            return
        # Keys are never rewritten; scan for secret shapes only and report.
        masked_key, applied = redact_string(dict_key, None, config)
        for detector in applied:
            result.counts[detector.name] += 1
            _record(
                Finding(
                    _join(parent_path, dict_key) + "<key>",
                    detector.name,
                    detector.tier,
                    "key",
                    _mask_excerpt(masked_key),
                )
            )

    new_payload, _ = walk(payload, "$", None)
    result.payload = new_payload
    return result


def _join(path: str, key: str) -> str:
    return f"{path}.{key}"


# ---------------------------------------------------------------------------
# JSON text convenience wrappers
# ---------------------------------------------------------------------------


def redact_json_text(text: str, config: RedactionConfig | None = None) -> RedactionResult:
    """Parse ``text`` as JSON, redact, and return the result (payload decoded)."""
    return redact_payload(json.loads(text), config)


def dumps(payload: object) -> str:
    """Deterministic serialisation used by the CLI (sorted keys, 2-space indent)."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
