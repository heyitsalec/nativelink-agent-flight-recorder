# Security Policy

NativeLink Agent Flight Recorder (NLFR) is a local-first, stdlib-only Python
CLI. It records Bazel / NativeLink build evidence into truth-labeled proof
packets. This policy describes which versions receive security fixes and how to
report a vulnerability.

For the design rationale behind these boundaries — trust boundaries, what NLFR
does and does not protect, and the zero-runtime-dependency posture — see the
[threat model](docs/SECURITY_MODEL.md).

## Supported versions

NLFR is versioned from `pyproject.toml` (currently the `0.2.x` line). Security
fixes land on the latest released minor and on `main`. Older lines are not
back-patched; upgrade to the latest release to receive fixes.

| Version | Supported |
| ------- | --------- |
| `0.2.x` (latest) | Yes |
| `< 0.2` | No — upgrade to latest |

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**. Do not open a public
issue, pull request, or discussion for an unfixed vulnerability.

**Preferred channel — GitHub private security advisories (GHSA).** Use
[**Report a vulnerability**](https://github.com/heyitsalec/nativelink-agent-flight-recorder/security/advisories/new)
on the repository's Security tab. This opens a private advisory visible only to
you and the maintainers, keeps disclosure coordinated, and lets us collaborate
on a fix and (if warranted) request a CVE before anything is public.

<!-- OWNER TODO (#80): add a fallback disclosure contact for reporters who
cannot use GitHub advisories (e.g. a security email or PGP key). Do not invent
one — this must be an address the maintainer actually monitors. -->

When you report, please include where practical:

- affected version(s) and platform;
- a description of the issue and its impact (what an attacker gains);
- minimal reproduction steps or a proof-of-concept;
- any known mitigation or workaround.

### What to expect

<!-- OWNER TODO (#80): state the response SLA — e.g. time to first
acknowledgement and target time to a fix or coordinated-disclosure date. Do not
invent an SLA the maintainer cannot honor. -->

We follow **coordinated disclosure**: please give us a reasonable window to
investigate and ship a fix before any public disclosure, and we will keep you
updated on progress and credit you (if you wish) once a fix is released.

## Scope

**In scope** — vulnerabilities in NLFR's own code and its documented behavior:

- the `nlfr` CLI and the `nlfr` Python package (`src/nlfr/**`);
- evidence-integrity issues (e.g. a path where the recorder would accept a build
  tool's self-reported digest without independent verification);
- prompt-privacy issues (any path where a raw prompt could reach storage or a
  projection instead of a SHA-256 hash — see `FORBIDDEN_PROMPT_KEYS` in
  `src/nlfr/agent_receipt.py`);
- redaction bypasses at the **projection / sharing boundary**
  (`src/nlfr/redaction.py`, `nlfr redact`) that would leak a
  recognizable-shape secret or an absolute local path into a shared projection.

**Out of scope** — by design, and documented in the
[threat model](docs/SECURITY_MODEL.md):

- NLFR is **not a sandbox**; it does not isolate or contain the agent or the
  build it records;
- NLFR does **not vet the agent's code** for vulnerabilities — it records what
  ran, it does not judge whether what ran is safe;
- NLFR does **not sign** artifacts — signing (cosign / Sigstore) is an external,
  operator-owned step;
- the best-effort nature of regex redaction is a documented limitation, not a
  vulnerability: a free-standing high-entropy secret with no recognizable prefix
  or contextual marker is explicitly *not* guaranteed to be caught (see the
  scope note in `src/nlfr/redaction.py`);
- vulnerabilities in Bazel, NativeLink, CPython, or other operator-supplied
  tooling — report those to their respective projects;
- remote-CAS (REAPI / bytestream) references are currently **downgraded, not
  verified** — this is a known, tracked limitation
  ([#81](https://github.com/heyitsalec/nativelink-agent-flight-recorder/issues/81)),
  not a private vulnerability.

## A note on attack surface

NLFR ships with **zero runtime dependencies** (`dependencies = []` in
`pyproject.toml`, enforced by `tests/test_stdlib_only_posture.py`). There is no
transitive package tree to compromise: the only runtime trust root is the
CPython standard library plus the operator's own Bazel / NativeLink. See the
[threat model](docs/SECURITY_MODEL.md) for why this matters and how to verify it.
