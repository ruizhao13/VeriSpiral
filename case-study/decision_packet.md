# Decision packet walkthrough

**Current decision:** `await_human_acceptance`.

This note explains the tracked public
[decision packet](../examples/expected/decision_packet.json). It is not itself a
generated packet, a user decision, or a scientific result.

## Five-stage state

| Stage | Status | Evidence and boundary |
| --- | --- | --- |
| Structural validation | `pass` | Schema, assumption audit, comparison scope, falsifiability, and induction-readiness checks pass. These are structural checks. |
| Evidence integrity | `pass` | Declared repository-local evidence resolves and is content-addressed. File presence and hashes do not establish semantic truth. |
| Semantic verification | `verified` | The registered executable verifier is actually replayed; its exact output matches the bound receipt. The result is limited to the receipt's pipeline-contract scope. |
| Human acceptance | `pending` | `human_acceptance_records` is empty. No user acceptance is inferred. |
| Candidate lifecycle | `ready_for_verification` | The candidate is ready for review, not approved or active. |

The semantic stage uses the checked-in
[receipt](../examples/verification/pipeline_contract_receipt.json) and
[verifier](../examples/verifiers/pipeline_contract.py). The runner verifies their
registration and hashes, binds the receipt to the current semantic subject and
evidence, executes the registered command, and compares the replayed result with
the receipt.

## Artifact result

The tracked [manifest](../examples/expected/manifest.json) lists exactly one
generated content artifact, `decision_packet.json`. The manifest itself is the
second tracked output. The current default demonstration produces no
`success_trace.json` and no induced Skill because human acceptance is still
pending.

`semantic_verification: verified` does not mean that a theorem, novelty claim,
literature comparison, or research direction has been scientifically verified.
It means only that the registered executable check replayed successfully within
its declared scope.

## Missing-locator test

The rejection test creates a temporary candidate copy and replaces one evidence
locator with `missing/public-evidence.json`. The temporary run records an
evidence-integrity failure, marks semantic verification `invalid` because the
receipt's evidence binding cannot be resolved, and returns `revise`. Human
acceptance remains `pending`. The test reads its temporary decision packet
directly; there is no tracked negative-path packet in `examples/expected/`.

The executable check is in
[`tests/test_pipeline.py`](../tests/test_pipeline.py). Repairing the locator
would create a new test state and would not alter the earlier result.

## User decision boundary

Only the user may accept, reject, modify, or branch a proposed change to the
scientific model, research target, verifier contract, or scientific judgment
boundary. This packet records none of those decisions, performs no activation,
and creates no persistent learning state.
