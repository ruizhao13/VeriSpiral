# Public repository protocol

This repository is a deliberately small, public-safe implementation of a
user-governed research-specification loop. Its examples are purpose-built
public fixtures; they do not contain material copied from a private research
workspace.

## Non-negotiable rules

- Never copy private memory, chats, human preference ledgers, unpublished
  manuscripts, third-party papers, datasets, credentials, or raw experiment
  outputs into this repository.
- Every scientific-looking claim must point to a public artifact in this
  repository and state its scope and limitations.
- AI-generated text is a proposal, not evidence. Promotion requires an
  executable check, an independent audit, a literature anchor, or explicit
  human acceptance.
- Keep the reference workflows deterministic and small enough to review in ten
  minutes.
- Run `make verify golden-check` before proposing a public release.
- Do not add files larger than 20 MB.

## Editing contract

Prefer small, reviewable changes. Update the relevant documentation whenever
the demo contract, evidence schema, or human/AI responsibility boundary
changes. Do not weaken a validation gate merely to make an example pass.
