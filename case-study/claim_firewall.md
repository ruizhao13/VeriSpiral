# Claim firewall for the synthetic pipeline case

This file limits how the default receipt replay and the missing-evidence test may
be described.

## Permitted claims

- The public pipeline resolves declared evidence locators inside the repository
  and hashes files that resolve.
- The default demonstration records five distinct stage states:
  `structural_validation=pass`, `evidence_integrity=pass`,
  `semantic_verification=verified`, `human_acceptance=pending`, and
  `candidate_lifecycle=ready_for_verification`.
- Semantic verification actually replays the repository-registered executable
  verifier and requires its result to match the receipt bound to the candidate
  and evidence.
- The replay result is limited to the pipeline-contract scope declared by the
  receipt. It is not a scientific-verification verdict.
- The default decision is `await_human_acceptance`. The tracked run contains a
  decision packet and manifest, but no success trace or induced Skill.
- In the checked negative-path test, a missing locator changes the decision to
  `revise`. The test constructs and evaluates that input in a temporary
  directory; evidence integrity is `fail`, semantic verification is `invalid`,
  human acceptance remains `pending`, and no generated negative-path packet is
  tracked in the repository.
- The tracked decision packet and manifest are reproduced byte for byte by the
  golden test.
- The case is a purpose-built synthetic walkthrough of these public checks.
- The user owns the accepted scientific model, research target, verifier
  contract, and scientific judgment.

## Forbidden or unsupported claims

- The case is an anonymized experiment or decision from a private research
  project.
- Passing schema and locator checks establishes that an evidence file is true,
  complete, novel, or scientifically sufficient.
- `semantic_verification=verified` means that a scientific claim, theorem,
  novelty statement, or research direction has been verified.
- The presence of a passed receipt means that a human accepted the candidate.
- The current default demo emits a success trace, induces a Skill, activates a
  capability, or learns persistently from a user.
- The tests constitute an independent implementation audit.
- The public demo proves a theorem, evaluates an LLM, or measures autonomous
  research performance.
- The gate covers every possible path, symlink, race, remote source, or
  production threat model.
- This folder contains a tracked generated packet for the negative-path test.
- The runner may change the model, target, verifier, or scientific judgment
  boundary on the user's behalf.
- Repairing a locator retroactively changes the already evaluated temporary
  packet.

## Required wording

Use:

> In the public synthetic test, an unresolved evidence locator blocks
> the evidence-integrity stage and returns `revise`.

Avoid:

> An independent research audit validated the system.

Use:

> The golden test establishes deterministic replay of the public positive
> fixture.

Avoid:

> The evidence itself has been independently proven correct.

Use:

> In the default demo, the registered executable verifier is replayed and its
> result matches the scoped receipt; human acceptance remains pending, so the
> decision is `await_human_acceptance` and no success trace or Skill is emitted.

## Interpretation rule

Changing a forbidden claim requires new public evidence and an explicit user
decision. Rephrasing a claim or repairing one locator does not alter the status
of an already evaluated packet. Only the user may accept, reject, modify, or
branch a proposed change to the model, target, verifier contract, or scientific
judgment boundary.
