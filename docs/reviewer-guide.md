# Reviewer guide

This guide is for a fast, skeptical review of VeriSpiral's public claims. The
central question is whether evidence can guide work to the right research layer
within a budget, while preserving the user's goal and the scope of each check.
The finite demos establish mechanisms, not research effectiveness.

## Ten-minute reading path

1. Read the [README](../README.md) for the bounded claim.
2. Read [the main case workflow](case-workflow.md) and its
   [behavioral tests](../tests/test_case_workflow.py) for actual component execution,
   feedback and replacement. The [research agenda](research-agenda.md) defines
   hypotheses and comparable-budget evaluation. Earlier finite diagnosis and
   DAG examples are supporting mechanisms, not the primary case interface.
3. Inspect [architecture](architecture.md) and
   [specification co-evolution](research-specification-coevolution.md) for the
   authority model and its implementation boundaries.
4. Check the [claim-evidence matrix](claim-evidence-matrix.md) before inferring
   any scientific or product capability.

## Authority checks

Confirm that the documentation and artifacts agree on these points:

- the user owns the accepted scientific model, target, verifier contract, and
  scientific judgment boundary;
- AI may organize literature, candidates, proof routes, counterexamples, and
  experiments, but these are intended responsibilities rather than capabilities
  demonstrated by the repository;
- AI may draft a model- or verifier-revision discussion packet but cannot
  authorize it;
- only a user decision may `accept`, `reject`, `modify`, or `branch` a
  specification revision; and
- replaying a checked-in event with `actor: human` does not prove that a real
  person supplied it live.

## Change-class checks

Classify every proposed delta before reading its outcome:

| Class | Must remain frozen | Required route |
| --- | --- | --- |
| Solution | Model, target, verifier, judgment boundary | Continue inner-loop search |
| Model | Parent specification | User-reviewed new version or branch |
| Verifier | Model and target | User review plus re-evaluation of affected results |

A `model_and_verifier_revision` is acceptable only when the model delta and
verifier delta are separately visible and neither is disguised as a solution
change. A verifier-only successor may continue the same target lineage; a model
change starts a separate lineage and cannot receive progress credit on the
original target.

## Executable replay checks

### Main problem-first case workflow

- Does the host supply actual role work, clearly distinguished from public fixtures?
- Are checker, solver and independently configured reference actually executed?
- Do false passes, crashes and malformed outputs retain their real outcomes and costs?
- Does diagnosis consume the latest run and preserve candidate/verifier disagreements?
- Do component changes require appropriate decisions and fresh evaluation?
- Are local execution permissions, unmeasured host/model costs and development-only
  evidence stated without claiming scientific or hidden-test guarantees?

### Finite diagnosis

- Do planted labels remain isolated to scoring after observations are collected?
- Do ten public cases include seven individual patterns, a passing control, and
  two simultaneous failures reported as nonexclusive check indicators?
- Does supported completion require all registered checks, including zero-score
  coverage checks in the older signature API?
- Does insufficient budget preserve observed failures and unresolved checks,
  while contradictory or indistinguishable signatures remain explicit?
- Do limitation tests retain check-invisible changes, and avoid causal certainty?
- Are the finite reference and illustrative costs distinguished from independent
  calibration and equal-budget research evaluation?

### Connected DAG workflow

Inspect the [runner](../src/verispiral/research_workflow.py) and
[summary](../examples/expected/workflow/demo_summary.json).

- Does a proposal-bound recorded decision precede candidate execution?
- Do missing checks prevent readiness, with generation, repair and rechecks
  included in the declared edge-work budget?
- Does a weak-screen disagreement persist after repair and require a separate
  recorded screen-revision decision?
- Does the successor preserve the goal/setup and recheck the retained candidate
  without accepting old evidence as current?
- Are prose understanding, general synthesis, identity authentication, and
  real research effectiveness outside the demonstrated claim?

### Five-stage candidate review

- Are structural validation, evidence integrity, semantic verification, human
  acceptance, and candidate lifecycle reported separately?
- Is the registered executable verifier actually replayed, with its receipt
  bound to the complete semantic subject and evidence hashes?
- Does the default packet report `human_acceptance: pending` and
  `decision: await_human_acceptance`?
- Does the tracked manifest contain only the decision packet, with no success
  trace or Skill?

### Feedback to process patch

- Is the `FeedbackEvent` synthetic and process-only?
- Is the registered executable control source, manifest, component version, and
  hashes bound before a proposal is emitted?
- Does output remain `proposed_for_human_review` and `not_applied`?
- Is it kept separate from model or verifier revision?

### Minimax certificate compatibility

- Are candidates and search hypotheses pre-registered?
- Are problem-signature and assumption fields compared before stored rate
  exponents?
- Is `minimax_rate_match` limited to compatible registered fields with matching
  exponents?
- Is the synthetic assumption branch distinguished from a user decision?
- Does the documentation avoid claiming proof checking, source-extraction
  validation, or algorithm generation?

### Research-specification co-evolution

- Does the discussion bind the exact parent and proposed specification hashes?
- Does the recorded human decision reference that discussion and selected
  specification?
- Does `modify` select a distinct user-modified registered specification?
- Does an accepted verifier-only revision create an immutable successor on the
  same target lineage and supersede the earlier verifier version?
- Does a model revision create a separate lineage whose work cannot count on the
  original target?
- Are live input capture, identity verification, algorithm generation, proof
  generation, and scientific truth explicitly outside the claim?

## Reproduce the bounded claims

From the repository root, run:

```bash
make research-loop-demo
make diagnosis-demo
make workflow-demo
make test
make golden-check
make audit
```

Golden equality supports deterministic replay of checked-in fixtures. It does
not support theorem correctness, novelty, source accuracy, personalization,
long-term learning, or production readiness.

## Questions to ask before reuse

1. Who defines the model, target, and verifier for the new setting?
2. What evidence may each verifier status support, and what remains a human
   scientific judgment?
3. How are solution, model, and verifier changes routed and versioned?
4. How is a real user decision authenticated outside this public fixture?
5. Which failures and counterexamples remain visible after branching?
6. What additional semantic review is required beyond schemas, hashes, and
   deterministic tests?
