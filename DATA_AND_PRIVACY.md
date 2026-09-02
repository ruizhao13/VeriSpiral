# Data, provenance, and privacy

VeriSpiral follows a data-minimization rule: a public reference implementation
should contain only the material needed to understand, run, and verify its
claims.

## Included

- source code and tests for the public demonstrations;
- small synthetic fixtures created for this repository;
- one synthetic explicit-feedback event and a registry of public-demo source
  and target hashes;
- registered public research specifications plus synthetic discussion and
  human-decision fixtures for deterministic branch replay;
- generalized workflow schemas, Prompt examples, Skills, and documentation;
- a synthetic case study of an evidence-integrity gate; and
- a purpose-built stochastic-bandit fixture based on public citations.

The minimax fixture contains registered certificate fields and public source
locators. Its generated artifacts compare those fields; they do not reproduce
the source papers' proofs or experiments.

## Deliberately excluded

- source papers, PDFs, books, and other third-party copyrighted material;
- private or licensed datasets;
- unpublished manuscripts, theorem statements, proofs, and exact experiment
  configurations;
- raw interactions, feedback events from real users, preference profiles, or
  private agent memory;
- large arrays, model outputs, caches, environments, and execution logs;
- personal details of users, collaborators, reviewers, or other third parties;
- credentials, tokens, cookies, machine identifiers, and local absolute paths;
  and
- Git history or files from a private source workspace.

## Synthetic fixture policy

The checked-in examples demonstrate interfaces and failure behavior. They are
not measurements copied from a private research project and should not be read
as evidence for an unpublished scientific result. Software claims link to
public tests; narrative claims state their illustrative scope.

Before adding material from another workspace, the project owner should:

1. establish ownership or permission to publish;
2. scan for secrets, personal data, local paths, and embedded metadata;
3. replace raw research outputs with minimal synthetic fixtures where possible;
4. record the source and license of any retained third-party component;
5. verify that unpublished and collaborator-owned material is absent; and
6. review the staged diff rather than relying only on filename exclusions.

## Interaction and decision fixtures

The current demos do not collect, transmit, or persist live user interactions.
The feedback demo reads one checked-in event labeled
`synthetic_public_demo`; it is not a real user record. The
research-specification demo reads a checked-in event whose actor is `human`;
the repository validates its references and hashes but cannot establish that a
real person supplied it.

Any separate system that collects live interactions should define, before
collection:

- which interactions are stored and for what purpose;
- whether storage is task-local, user-scoped, or shared;
- the legal basis or user consent for retention and reuse;
- access controls, encryption, retention duration, and deletion behavior;
- how a user can inspect, correct, export, or remove their state;
- whether an event may be used to propose a shared policy or research-
  specification change; and
- how data from one user is prevented from affecting another user's work.

Silence is not feedback, and continued use is not consent to retain or
generalize private context. This repository does not claim personalization,
long-term learning, or a user-profile mechanism.

## Provenance

Every evidence or feedback record should identify its source, scope, and
version. Generated text is labeled as a proposal until it is linked to an
appropriate external anchor such as a primary source, executable result,
independent review, or explicit human decision. Provenance establishes where a
record came from; it does not establish that the record is true.

## Third-party material

Third-party works are not relicensed by this repository's license. A citation,
URL, package name, or dependency declaration does not transfer ownership of the
referenced work. Dependencies and cited material remain governed by their own
licenses and terms.

If you find information here that should not be public, use the private
reporting route described in [SECURITY.md](SECURITY.md).
