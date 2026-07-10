# Capture agent telemetry from cloud and pod builds

← [Docs index](../../INDEX.md) · [How-to guides](.)

Locally, agent receipts exist because `nlfr agent-invoke` wraps the agent CLI
itself: NLFR observes the invocation, parses the CLI's JSON output, and writes
a validated `nlfr.agent_receipt.v1` receipt (prompt SHA-256 only — never the
raw prompt). In cloud builds — CI runners, Kubernetes jobs, hosted agent
sessions — the agent runs where NLFR isn't. There are exactly three honest
rungs, and each one is labeled as what it is:

| Rung | How the receipt gets in | Provenance class | Rendered as |
| --- | --- | --- | --- |
| 1. Wrap in-pod | `nlfr agent-invoke` inside the pod/CI step | `receipt_verified_v1` | `receipt_verified: true` |
| 2. Drop-box import | receipt file moved as a build artifact, `nlfr receipt import` | `receipt_imported_v1` | `receipt_verified: false` |
| 3. No receipt | operator asserts the agent leg | `operator_asserted_v1` | `receipt_verified: false` |

The ladder is a statement about **evidence shape, not trust**:
`receipt_imported_v1` means "a schema-valid receipt with structured telemetry
arrived from an invocation NLFR did not observe" — an unverified third-party
assertion. It never renders as verified, and NLFR will not upgrade it.

## Rung 1 (preferred): wrap the invocation in the pod

The `nlfr` recorder is a stdlib-only Python package — installing it inside a
container adds zero transitive dependencies:

```yaml
# GitHub Actions step / any pod that has the agent CLI authenticated
- name: Agent change with receipt
  run: |
    pip install nativelink-agent-flight-recorder  # or: uv tool install ...
    nlfr agent-invoke \
      --prompt-file task-prompt.txt \
      --receipt-output receipts/agent-receipt.json \
      --response-output responses/agent-response.md \
      --claude-bin claude \
      --cwd "$(mktemp -d)" \
      --json
- name: Keep the receipt as a build artifact
  uses: actions/upload-artifact@v4
  with:
    name: agent-receipt
    path: receipts/agent-receipt.json
```

Receipts produced this way keep full `receipt_verified_v1` semantics when the
validation run records them (`nlfr run ... --agent-receipt receipts/agent-receipt.json`),
because NLFR itself performed and parsed the invocation.

The same pattern works in a Kubernetes job: run `pip install
nativelink-agent-flight-recorder && nlfr agent-invoke ...` in the container
that has the agent CLI, and ship `agent-receipt.json` out with your artifact
store of choice.

## Rung 2: import a receipt NLFR did not capture

When wrapping is impossible (a hosted agent produced its own receipt file, or
the invocation happened in a system you don't control), move the receipt JSON
as a build artifact and attach it to the recorded run group at the proof step:

```bash
nlfr receipt import \
  --receipt artifacts/agent-receipt.json \
  --db data/nlfr-record/pr-validation/nlfr.sqlite \
  --run-group pr-validation
```

What happens, in order:

1. The file is validated as `nlfr.agent_receipt.v1` — schema shape, SHA-256
   digests, and the privacy invariants (any raw-prompt key rejects the whole
   import with exit 2; nothing is written).
2. The receipt file is recorded as an artifact (content-hashed).
3. An `agent_provenance` proof block is attached with
   `provenance_class: receipt_imported_v1`, `source_kind: collectable_v1`
   (the file is collected evidence), and `confidence: medium` (the invocation
   was not observed). The receipt summary is stamped `live: false` and
   `observed_by_nlfr: false`, so the canvas, graph, and compare projections
   all render `receipt_verified: false`.

An imported receipt is trivially forgeable by whoever writes the file — that
is exactly why it can never become `receipt_verified_v1`. If your threat model
needs stronger imported telemetry, sign the receipt file in the pod (cosign,
DSSE) and verify the signature before import; NLFR records what arrived and
its class, not a trust judgment.

## Rung 3: no receipt

A validation run recorded with `--provenance-sidecar` but no `--agent-receipt`
keeps the agent leg at `operator_asserted_v1` — an explicit operator claim,
clearly labeled. This is still better than nothing: the change hashes and the
validation evidence remain fully collectable.

## Verifying what landed

```bash
nlfr proof export --db <db> --run-group <group> | \
  python3 -c "import json,sys; [print(b['payload']['agent']['provenance_class']) \
    for b in json.load(sys.stdin)['blocks'] if b.get('kind')=='agent_provenance']"
```

`nlfr evaluate --db <db> --run-group <group>` also rolls up the provenance
classes present in a run group under `agent_provenance.classes`.
