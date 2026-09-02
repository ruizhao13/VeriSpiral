# VeriSpiral: project brief

**A user-governed, verifier-guided workflow for research-specification
co-evolution and solution search.**

VeriSpiral explores a narrow question: how can AI help search a scientific
problem while making it difficult to change the problem, its success criterion,
or its verifier without the user's explicit decision?

The project changes external, inspectable artifacts rather than model weights.
Its central object is a **research specification**: the accepted model,
assumptions, target, verifier contract, and scientific judgment boundary.

## Division of responsibility

| User authority | AI assistance |
| --- | --- |
| Define or revise the model and assumptions | Search literature and organize source-backed comparisons |
| Choose the target and acceptable trade-offs | Propose solution candidates and proof routes |
| Approve the verifier contract and evidence standard | Look for counterexamples and failed proof obligations |
| Make scientific judgments | Plan and analyze experiments within the accepted specification |
| `accept`, `reject`, `modify`, or `branch` a specification revision | Prepare a reviewable discussion packet for a possible revision |

AI output is advisory. A model or verifier proposal does not become part of the
accepted specification merely because it is internally consistent or passes a
mechanical check.

## Two loops

The **inner loop** searches for solutions under a frozen research specification:

```text
accepted specification
    -> literature / candidates / proof routes / counterexamples / experiments
    -> verifier and provenance checks
    -> decision packet for the user
```

The **outer loop** handles evidence that the specification itself may need to
change:

```text
observed mismatch or explicit user request
    -> model- or verifier-revision discussion packet
    -> user: accept / reject / modify / branch
    -> versioned specification, only if the user chooses
```

See [Research-specification co-evolution](docs/research-specification-coevolution.md)
for the full contract.

## Three change classes

Every proposed change belongs to exactly one class:

1. **Solution change:** changes a candidate algorithm, construction, proof route,
   supporting lemma, or experiment while leaving the accepted specification
   unchanged.
2. **Model change:** changes the observation model, parameter class, assumptions,
   loss, target, regime, or admissible algorithm class.
3. **Verifier change:** changes what is checked, the evidence needed, or the rule
   that maps evidence to a status.

A coupled model-and-verifier proposal contains two explicit deltas and two
impact analyses in one discussion packet; it is never mislabeled as a solution
change. Model and verifier changes leave the inner loop. Only the user can
decide whether either change is accepted, modified, rejected, or branched.

## What the public repository demonstrates

The current repository contains deterministic, checked-in replays for four
bounded mechanisms:

1. **Five-stage candidate review.** The default fixture passes structural and
   evidence-integrity checks, replays a registered executable verifier, and
   binds its receipt to the semantic subject. Human acceptance remains pending,
   so the decision is `await_human_acceptance` and no success trace or Skill is
   emitted.
2. **Synthetic feedback to process-patch proposal.** A checked-in feedback event
   and registered executable control source produce one constrained, unapplied
   process patch marked for human review.
3. **Minimax certificate-field comparison.** A checker compares registered
   problem-signature, assumption, and rate fields. An incompatible candidate
   produces synthetic branch bookkeeping, not a user decision to change the
   model.
4. **Research-specification co-evolution.** A runner validates a pre-registered
   human-decision fixture. An accepted verifier-only revision becomes an
   immutable successor on the same target lineage; a model revision creates a
   separate lineage whose work cannot solve the original target.

Schemas, rejection tests, golden outputs, executable receipts, and content
hashes make these replay claims inspectable. A receipt pass remains scoped to
its registered verifier; without explicit human acceptance it cannot produce a
success trace or activatable Skill.

## What the public repository does not implement

It does not capture live user input, prove that a recorded decision came from a
real person, or implement autonomous literature review, real algorithm
generation, theorem proving, personalization, a user profile, long-term
learning, automatic specification revision, or unattended policy activation.
The minimax candidates and hypotheses are pre-registered inputs, not discoveries
made by the checker.

## Reproduce the bounded claims

```bash
make demo
make evolution-demo
make minimax-demo
make research-loop-demo
make test
make golden-check
make audit
```

The repository contains purpose-built public fixtures and a public theory
example. It contains no private research memory, unpublished manuscript, raw
interaction history, or proprietary dataset. Its [claim-evidence matrix](docs/claim-evidence-matrix.md)
and [related-project map](docs/related-projects.md) state the intended evidence
and comparison boundaries.
