# VeriSpiral: project brief

**A user-governed workflow for Goal–Setup–Verifier–Algorithm co-design,
guided by multi-fidelity evidence and failure diagnosis.**

VeriSpiral asks: when a promising candidate fails a more faithful check, which
experiment should the system buy next, and should the evidence lead to better
algorithms, better verifiers, a better setup, or a reconsidered goal?

The intended workflow has two approximation steps and a search step:

```text
real problem -> Goal + Setup -> affordable Verifier -> candidate Algorithm search
      ^                ^                ^                       |
      +------ higher-fidelity evidence and failure diagnosis ----+
```

The first step selects which real mechanisms and decision criteria to retain.
The second seeks mathematical constructions that make an expensive goal cheap
to check. Large candidate search then uses that checker, with promotion to
stronger checks and explicit reconsideration when the layers disagree.

The core research tasks are **verifier synthesis** and **budgeted diagnostic
experiment selection**. A verifier proposal must account for construction cost,
per-call cost, selected-candidate transfer, gaming, and actionable failure
feedback. A diagnosis must distinguish competing explanations rather than
choose a convenient story. These are research objectives, not established
capabilities. The [research agenda](docs/research-agenda.md) defines a falsifiable
hypothesis, comparable-budget baselines, metrics, and stopping criteria.

The project changes external, inspectable artifacts rather than model weights.
Its central object is a **research specification**: the accepted model,
assumptions, target, verifier contract, and scientific judgment boundary.
Goal/Metric maps to its target, Setup to its model and assumptions, and Verifier
to its evaluation contract. User control and immutable versions make joint
design reviewable; they support the research objective.

## From a problem document to a workflow

Use [problem compilation](prompts/protocols/problem_compilation.md) as the entry
protocol. It separates explicit requirements, inferences, assumptions, and
unknowns; checks that a trustworthy reference evaluator exists; and prepares
goal choices, a setup ladder, and a verifier frontier before scored search.
The reusable architecture is a common protocol plus a domain adapter plus a
problem document. Private cases belong in separate workspaces.

The [connected DAG workflow](docs/connected-workflow.md) now implements document
intake plus explicit typed data, a recorded accept/reject decision, execution,
concurrent checks, repair, and a verifier successor with fresh evidence. It
requires the user to confirm the adapter's interpretation; general semantic
extraction and broader domain adapters are not implemented.

Start with structured analysis, then freeze a user-selected specification and
search, then add diagnosis-led revision. Without a reference evaluator, the
next deliverable is an anchor-building plan rather than a proxy success claim.

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

The current repository contains deterministic demonstrations for seven
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
5. **Finite failure diagnosis and verifier comparison.** A small loss-table
   adapter executes seven registered checks on ten cases, including a no-fault
   control and two concurrent-failure cases. A controller selects affordable
   pending checks in cost order, preserves all observed failures and untested
   factors, and requires complete registered coverage before finishing.
   Two prewritten verifiers expose a selected-candidate false promotion and
   different amortized costs. [Public evidence and limits](docs/diagnosis-demo.md)
   describe why this is a mechanism test, not research-effectiveness evidence.
6. **Problem-driven shortest-path trial.** Two prewritten solvers and three
   checker variants run on 26 public DAGs, with a separately authored path
   scorer and exhaustive reference. A follow-up repairs witness coverage while
   preserving the paths and charging construction costs. The
   [study](docs/path-workflow-study.md) reports both the soundness/coverage result
   and the absence of an efficiency benefit over direct solving.
7. **Connected problem-to-recheck workflow.** A problem document, typed DAG
   setup, and matching decision drive candidate execution, four nonexclusive
   checks, repair, a screen-revision proposal, and a rechecked successor on the
   same target. [Public outputs and scope](docs/connected-workflow.md) demonstrate
   this connection using synthetic decisions; final human acceptance remains
   pending, and no general prose interpretation or new algorithm is claimed.

Schemas, rejection tests, golden outputs, executable receipts, and content
hashes make these replay claims inspectable. A receipt pass remains scoped to
its registered verifier; without explicit human acceptance it cannot produce a
success trace or activatable Skill.

## What the public repository does not implement

It accepts caller-supplied decision files but does not authenticate a real
person or implement autonomous literature review, new algorithm
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
make diagnosis-demo
make path-trial
make workflow-demo
make test
make golden-check
make audit
```

The repository contains purpose-built public fixtures and a public theory
example. It contains no private research memory, unpublished manuscript, raw
interaction history, or proprietary dataset. Its [claim-evidence matrix](docs/claim-evidence-matrix.md)
and [related-project map](docs/related-projects.md) state the intended evidence
and comparison boundaries.
