# Claim-evidence matrix

This matrix states what the checked-in repository can demonstrate and where
each claim stops.

| Public claim | Inspectable evidence | Boundary |
| --- | --- | --- |
| The default candidate run separates five review stages and stops at pending human acceptance. | Candidate, registered executable verifier and receipt, decision packet, manifest, rejection tests, and golden outputs. | `semantic_verification: verified` is scoped to the replayed verifier. With `human_acceptance: pending`, the decision is `await_human_acceptance` and no success trace or Skill is emitted. |
| One synthetic process-feedback event can produce one constrained patch proposal. | Registered executable control source/component hashes and tracked proposal, patch, and manifest. | The patch is `proposed_for_human_review` and `not_applied`; it does not change the research specification. |
| Registered minimax certificate fields can be compared after interface and assumption checks. | Source registry, certificate inventory, field diffs, exact rational exponent algebra, and golden trace. | The checker does not verify papers, proofs, extraction validity, or class containment. `minimax_rate_match` is only a field-compatibility status. |
| An assumption-incompatible minimax candidate does not mutate the target. | Synthetic candidate-branch record with `target_mutated=false` and `merge_status=not_merged`. | This is checker bookkeeping, not evidence that a user accepted a new model branch. |
| An accepted verifier-only revision can become an immutable successor on the same target lineage. | [`research_spec.py`](../src/verispiral/research_spec.py), target-lineage fields, successor status, registered fixtures, schemas, and tests. | The user decision is fixture data; later candidates must be rechecked under the successor, and no scientific claim is automatically accepted. |
| A model revision creates a separate target lineage. | Branch registry, lineage relation, event links, specification hashes, and progress-isolation invariants. | Work on that model branch cannot solve the original target; branch creation does not make either model scientifically correct. |
| Model, verifier, and coupled model-and-verifier revisions are typed. | Scenario/schema revision kinds and validation of changed fields. | A coupled revision must expose both deltas; no revision may be disguised as a solution change. |
| Checked-in fixture transformations are deterministic. | Golden artifacts, manifests, and tests. | Determinism is reproducibility of software behavior, not theorem correctness, novelty, personalization, learning, or production readiness. |

Use `make test`, `make golden-check`, and `make audit` to inspect the executable
boundary. Source locators in the minimax fixture remain citations to be reviewed
by a human; their presence is not proof verification.
