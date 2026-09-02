# Synthetic pipeline walkthrough: executable verification stops for human acceptance

This purpose-built walkthrough explains the current deterministic pipeline. It
was written for this repository and is not a redacted research result,
experiment, manuscript, or trace from a private workspace.

## Default demonstration

The checked-in [candidate](../examples/candidate.json) enters five distinct
stages. The tracked [decision packet](../examples/expected/decision_packet.json)
records their current states:

| Stage | Current state | What the runner establishes |
| --- | --- | --- |
| `structural_validation` | `pass` | The candidate satisfies the schema and declared structural checks. |
| `evidence_integrity` | `pass` | Three repository-local evidence files resolve and match their recorded hashes. |
| `semantic_verification` | `verified` | A registered executable verifier was replayed and its output matched the receipt bound to the complete semantic subject. |
| `human_acceptance` | `pending` | No human-acceptance record is attached. |
| `candidate_lifecycle` | `ready_for_verification` | The candidate is available for review; this is not approval or activation. |

For semantic verification, the runner checks the receipt, evidence bindings,
verifier identity, verifier file hash, and registered command. It then executes
the registered verifier and compares the exit status, output hash, and parsed
result with the receipt. The relevant public inputs are the
[receipt](../examples/verification/pipeline_contract_receipt.json) and
[executable verifier](../examples/verifiers/pipeline_contract.py).

The `verified` stage value is scoped to that replay and receipt. The executable
verifier checks the declared pipeline contract and artifact-emission invariants;
it does not establish the truth, novelty, or value of a scientific claim.

Because human acceptance remains pending, the decision is
`await_human_acceptance`. The current run writes only:

- [the decision packet](../examples/expected/decision_packet.json); and
- [the artifact manifest](../examples/expected/manifest.json).

It does not write `success_trace.json` or an induced Skill. It does not activate
or persist a new capability, and it does not learn from a user over time.

## Missing-locator negative path

The negative-path test makes a temporary copy of the checked-in candidate,
changes one evidence locator to a nonexistent repository-relative file, and
runs the same pipeline in a temporary directory. The evidence-integrity gate
then records `fail` and the decision is `revise`. The temporary packet records
the five stage states as `pass / fail / invalid / pending /
ready_for_verification`. Although the registered verifier subprocess can still
complete, the unresolved evidence binding makes the overall semantic stage
invalid and no verification receipt is retained in the packet.

```text
temporary candidate copy
        |
        v
one evidence locator is missing
        |
        v
temporary decision packet -------- revise
```

The test reads that temporary packet directly. The repository does not track a
second generated decision packet for the negative path, and this Markdown file
is only its narrative explanation. See
[`tests/test_pipeline.py`](../tests/test_pipeline.py).

## Authority boundary

The user owns the accepted scientific model, research target, verifier contract,
and scientific judgment. A replayed receipt can inform that judgment, but the
runner cannot accept, reject, modify, or branch a research specification on the
user's behalf.

See [decision_packet.md](decision_packet.md),
[claim_firewall.md](claim_firewall.md), and
[independent_audit.md](independent_audit.md) for the corresponding review
notes.
