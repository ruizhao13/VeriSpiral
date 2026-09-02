# Design principles

VeriSpiral separates AI-assisted search from authority over the scientific
problem. The system can organize evidence and propose changes; the user owns
the research specification and the decision to revise it.

## The user owns the research specification

The accepted model, assumptions, target, verifier contract, and scientific
judgment boundary are user-governed state. AI may surface a conflict or draft a
revision discussion packet, but it cannot accept its own proposal.

For every model or verifier revision, the user decision is explicit:
`accept`, `reject`, `modify`, or `branch`. The public co-evolution replay can
validate a pre-registered decision event. An accepted verifier successor stays
on the same target lineage; a changed model starts a separate lineage. The
replay does not capture a live decision or establish the decision-maker's
identity.

## Freeze the specification during solution search

The inner loop may search literature, algorithms, constructions, proof routes,
counterexamples, and experiments. It may not silently improve a result by
narrowing the parameter class, strengthening an assumption, changing the loss,
or weakening the verifier.

Such a mismatch stops the inner-loop comparison and is routed to the outer
research-specification loop.

## Separate solution, model, and verifier changes

A solution change preserves the accepted specification. A model change alters
the problem or target. A verifier change alters the evidence contract or status
rule. These classes must not share an ambiguous patch.

A coupled model-and-verifier revision may be represented in one discussion
packet only when it contains separately reviewable deltas and consequences for
both parts. It remains a specification revision and cannot be counted as a
solution to the parent target.

## Verifiers are contracts, not scientific oracles

A verifier can check only what its registered inputs and rules encode. Passing a
schema, hash, rate-field comparison, or test suite does not prove that a theorem
is true, a paper was extracted correctly, or a result is novel.

The minimax demo is therefore a certificate-field compatibility checker. Its
`minimax_rate_match` status means that compatible registered fields carry
matching stored exponents. It is not a theorem verdict.

## Evidence before reuse

Generated output is a candidate, not a learning signal. A reusable artifact
must cite a declared source such as a local executable check, an independent
audit, a literature locator, or an explicit user decision. It must also state
what that evidence cannot establish.

The five-stage candidate demo checks structure and evidence integrity, then
replays a repository-registered executable verifier and binds its receipt to the
semantic subject. Human acceptance remains pending. The default run therefore
stops at `await_human_acceptance` and emits no success trace or Skill.

## Keep claim scope next to evidence

A simulation is not a theorem. A conditional result is not unconditional. A
comparison in one observation model does not transfer automatically to another.
Decision packets therefore preserve assumptions, evidence status, limitations,
and exact questions for the user alongside a recommendation.

## Preserve failures and provenance

Negative and inconclusive results remain visible. The public case study uses a
purpose-built missing-locator mutation to show one rejection path; it does not
claim that a comparator defeated a method or that a proof failed a uniformity
argument.

Inputs, decisions, and generated artifacts carry stable identifiers and content
hashes where the runnable contract supports them. Later output should not erase
the evidence that motivated an earlier decision.

## Discussion packets precede specification changes

When the inner loop encounters a possible model or verifier change, AI may
prepare a packet containing the current specification, the observed mismatch,
the smallest proposed delta, evidence for and against it, consequences, open
questions, and the four user choices. Producing that packet is analysis, not a
user decision.

The public replay validates a checked-in decision fixture. A verifier-only
acceptance creates an immutable successor on the same target lineage and
supersedes the earlier verifier; a model change creates a separate lineage.
This demonstrates decision binding, verifier succession, and model isolation,
not live approval or autonomous revision.

## Deterministic replay is a bounded claim

The public repository demonstrates deterministic artifact generation for
checked-in fixtures. It does not demonstrate personalization, long-term
learning, autonomous algorithm discovery, automatic scientific judgment, or
proof generation.

The fixed minimax replay records pre-registered candidates and hypotheses; the
checker does not generate the next algorithm. The synthetic feedback replay
stops at an unapplied process-patch proposal for human review.

## Privacy is part of the interface

A public architecture demo does not need private working memory. The repository
uses purpose-built public fixtures, small generated outputs, and release checks
that reject known private-path classes, machine-specific paths, large payloads,
and credential-like content.
