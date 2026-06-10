# Reference: artifact manifest v1

**Quadrant:** Reference · **Audience:** contributors implementing ingest and record paths

An artifact manifest lists immutable evidence files captured **before** SQLite
ingest. Each entry includes a SHA-256 digest so re-ingest is idempotent and
tamper-evident.

Schema: [`contracts/artifact_manifest.v1.json`](../../../../contracts/artifact_manifest.v1.json)  
Writer: [`src/nlfr/artifacts.py`](../../../../src/nlfr/artifacts.py)  
Filename on disk: `artifact_manifest.json` under the run artifact root.

← [Contracts index](README.md) · [Proof packet v1](proof-packet-v1.md)

## Root object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | integer | yes | Must be `1` |
| `artifacts` | array | yes | Ordered list of artifact entries |

## Artifact entry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `artifact_key` | string | yes | Stable relative key (also relative path under artifact root) |
| `path` | string | yes | POSIX relative path to the file |
| `sha256` | string | yes | Lowercase hex SHA-256 (`^[a-f0-9]{64}$`) |
| `size_bytes` | integer | yes | Payload size (≥ 0) |
| `producer_command` | string[] | yes | argv that produced the artifact |
| `config_hash` | string \| null | yes | Hash of relevant config, or `null` |
| `redaction_state` | enum | yes | `safe`, `redacted`, `blocked`, `unknown` |
| `source_kind` | enum | yes | `collectable_v1`, `derived_v1`, `simulated_v1`, `future`, `unknown` |
| `confidence` | enum | yes | `high`, `medium`, `low`, `unknown` |
| `evidence_refs` | string[] | yes | Stable refs (may be empty) |

### Truth label notes

| Field | Typical value | When |
|-------|---------------|------|
| `source_kind` | `collectable_v1` | Bazel BEP, execution log, NativeLink stdout attached at record time |
| `source_kind` | `simulated_v1` | `nlfr simulate` fixture artifacts |
| `confidence` | `high` | Parser matched without ambiguity |
| `redaction_state` | `safe` | Public-safe path and content |
| `redaction_state` | `redacted` | Path or span redacted; hash preserved |

Every entry must include all four truth fields. Ingest promotes them into SQLite
`artifacts` rows unchanged.

## Write semantics

`write_artifact()` enforces immutability:

- Same `artifact_key` + same SHA-256 → idempotent reuse.
- Same key + different SHA-256 → `ArtifactExistsError`.
- Manifest is atomically replaced via a `.json.tmp` file.

`artifact_key` must be a safe relative path (no `..`, `.`, or empty segments).

## Example (redacted)

From a cache-only proof run; paths shortened:

```json
{
  "schema_version": 1,
  "artifacts": [
    {
      "artifact_key": "bazel/execution-log.json",
      "path": "bazel/execution-log.json",
      "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
      "size_bytes": 4821,
      "producer_command": ["bazel", "test", "//tasks:priority_test", "--remote_cache=grpc://127.0.0.1:50051"],
      "config_hash": null,
      "redaction_state": "safe",
      "source_kind": "collectable_v1",
      "confidence": "high",
      "evidence_refs": ["run:tri-agent-loop:cache-only"]
    }
  ]
}
```

## Proof samples

Manifest entries mirror rows ingested from real proof runs. See grounded cache
economics in:

- [`cold-warm-summary.json`](../../../proof-samples/cold-warm-summary.json) — `collectable_v1` · `high`
- [`agent-loop-summary.json`](../../../proof-samples/agent-loop-summary.json) — mixed agent/validation chain

## Out of scope

The manifest does not embed file bodies, raw prompts, credentials, or environment
variables. Content integrity is proven by `sha256` + on-disk file at ingest time.

## Related

- CLI: `nlfr ingest` — [CLI reference](../cli.md#ingest)
- [Proof packet v1](proof-packet-v1.md) — `artifacts` proof block cites manifest rows
