"""Secret-pattern scanning and redaction for NLFR projection JSON.

Stdlib only (``re`` + ``json``). This module is the shared engine behind
``scripts/redact-projection.py`` and the repo-level ``--check`` gate.

Two things happen here, honestly labelled:

1. **Home-path scrubbing** (legacy behaviour, preserved): ``/Users/<name>`` and
   ``/home/<name>`` prefixes collapse to ``${HOME}``.
2. **Secret-pattern detection**: a registry of named detectors finds credential
   shapes (AWS keys, GitHub/GitLab/Slack tokens, PEM private keys, bearer
   credentials, JWTs, URL userinfo) and a separate **PII tier** (emails, public
   IPv4, hostnames). Matched spans are replaced with ``[REDACTED:<detector>]``.

Design constraints that keep the detectors honest on NLFR's own corpus:

* NLFR projection JSON is *full* of 64-hex SHA-256 digests and 40-hex SHA-1
  shapes. **No detector flags a bare hex digest.** The AWS secret-key detector
  only fires on a 40-char base64-ish value that is (a) under a credential-ish
  key and (b) *not* pure lowercase hex — so it can never collide with SHA-1.
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
    "SECRET_DETECTORS",
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

Span = tuple  # (start: int, end: int)
Finder = Callable[[str, Optional[str]], Iterable[Span]]


@dataclass(frozen=True)
class Detector:
    """A single named secret/PII detector.

    ``find`` returns non-overlapping-agnostic ``(start, end)`` spans within
    ``value``; overlap resolution happens centrally in :func:`_resolve_spans`.
    ``replacement`` defaults to ``[REDACTED:<name>]`` but the home-path
    detector overrides it with ``${HOME}``.
    """

    name: str
    tier: str  # "secret" | "pii"
    find: Finder
    replacement: str | None = None

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
_SHA1_HEX = re.compile(r"[0-9a-f]{40}")
_ALL_DIGITS = re.compile(r"[0-9]+")

#: Key names that make a 40-char base64-ish value look like a live secret.
#: Deliberately excludes bare ``token`` (NLFR JSON has ``input_tokens`` etc.).
_SECRET_KEY_CONTEXT = re.compile(
    r"(?i)(secret|passwd|password|pwd|api[_-]?key|access[_-]?key|"
    r"client[_-]?secret|private[_-]?key|credential)"
)

_HOME_PATH = re.compile(r"/(?:Users|home)/[^/\s\"'\\]+")


def _aws_secret_finder(value: str, key: str | None) -> Iterable[Span]:
    """Flag 40-char base64-ish secrets, but only under a credential-ish key.

    Rejects pure-hex (SHA-1) and all-digit windows so NLFR's ubiquitous digests
    never trip it.
    """

    if not key or not _SECRET_KEY_CONTEXT.search(key):
        return
    for match in _AWS_SECRET_CANDIDATE.finditer(value):
        text = match.group(0)
        if _SHA1_HEX.fullmatch(text):
            continue
        if _ALL_DIGITS.fullmatch(text):
            continue
        yield match.span(0)


SECRET_DETECTORS: list[Detector] = [
    Detector("home_path", "secret", _regex_finder(_HOME_PATH), replacement=_HOME_REPLACEMENT),
    Detector("private_key_pem", "secret", _regex_finder(_PRIVATE_KEY_PEM)),
    Detector("aws_access_key_id", "secret", _regex_finder(_AWS_ACCESS_KEY_ID)),
    Detector("github_token", "secret", _regex_finder(_GITHUB_TOKEN)),
    Detector("gitlab_pat", "secret", _regex_finder(_GITLAB_PAT)),
    Detector("slack_token", "secret", _regex_finder(_SLACK_TOKEN)),
    Detector("jwt", "secret", _regex_finder(_JWT)),
    Detector("url_credentials", "secret", _regex_finder(_URL_USERINFO, group="cred")),
    Detector("authorization_credential", "secret", _regex_finder(_AUTH_CREDENTIAL, group="cred")),
    Detector("aws_secret_access_key", "secret", _aws_secret_finder),
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
#: first (home-path and PEM before the generic shapes), then PII.
DETECTORS: list[Detector] = SECRET_DETECTORS + PII_DETECTORS


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class RedactionConfig:
    """Which detectors run and whether we rewrite (default) or scan (``--check``).

    Secret-tier detectors are always on. Of the PII tier, ``email`` and ``ipv4``
    are on by default in the publish path (both genuinely sensitive and, on
    NLFR's corpus, false-positive-free). ``hostname`` is **opt-in**
    (``--hostname``): host shapes are indistinguishable from tool/file names in
    this domain (``record-agent-change.sh``, ``receipt.v1``,
    ``nlfr.ingest.worker``), so redacting them by default would block honest
    publishes rather than protect anything. Each PII detector is individually
    toggleable.
    """

    redact: bool = True
    enable_email: bool = True
    enable_ip: bool = True
    enable_hostname: bool = False

    def is_enabled(self, detector: Detector) -> bool:
        if detector.tier == "secret":
            return True
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
