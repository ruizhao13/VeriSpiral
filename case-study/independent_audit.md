# Verification note for the synthetic case

## Verdict

**The declared deterministic software checks pass; human acceptance remains
pending.**

The repository contains executable checks for the default receipt-replay path
and the missing-evidence rejection path. This note does not claim an independent
implementation audit or scientific validation.

## Checks represented here

### Default receipt replay

The default demonstration runs twice in temporary directories and checks that
the generated `decision_packet.json` and `manifest.json` bytes agree. It also
asserts the five stage states:

```text
structural_validation = pass
evidence_integrity    = pass
semantic_verification = verified
human_acceptance      = pending
candidate_lifecycle   = ready_for_verification
decision              = await_human_acceptance
```

The semantic stage does not merely trust receipt text. The runner validates the
receipt and its evidence bindings, checks the registered verifier artifact and
command, executes that verifier, and requires the replayed output to match the
receipt. The tracked reference run contains only the
[decision packet](../examples/expected/decision_packet.json) and
[manifest](../examples/expected/manifest.json).

The test is in [`tests/test_pipeline.py`](../tests/test_pipeline.py). The golden
comparison is in [`tests/test_golden.py`](../tests/test_golden.py).

### Missing-evidence rejection

The negative-path test copies the public candidate fixture into a temporary
directory, changes one evidence locator to a nonexistent repository-relative
file, and runs the same pipeline there. It checks that:

- the overall decision is `revise`;
- the evidence-integrity gate records `fail`;
- semantic verification is `invalid` because the receipt's missing evidence
  binding cannot be accepted;
- human acceptance remains `pending`;
- no `success_trace.json` is written; and
- no induced `SKILL.md` is written.

The temporary run does write a decision packet so the test can inspect the
failure result. That packet is not tracked as a second reference artifact. The
test is in [`tests/test_pipeline.py`](../tests/test_pipeline.py).

### Public-release boundary

The release audit scans the repository for forbidden directories and file
types, oversized files, obvious machine-local paths, external symlinks, and
several credential patterns. Its own tests include clean and rejection cases.

The implementation and tests are in
[`src/verispiral/public_audit.py`](../src/verispiral/public_audit.py) and
[`tests/test_public_audit.py`](../tests/test_public_audit.py).

## Independence boundary

The positive and negative pipeline tests exercise the same implementation.
They establish repeatability and a specific guardrail; they do not provide the
stronger assurance of a separately implemented checker. The release audit is a
separate component, but it addresses disclosure hygiene rather than evidence
semantics.

## What this note does not establish

It does not establish scientific truth, literature completeness, theorem
correctness, production security, or performance on private or real-world
research. The `verified` semantic stage means that one registered executable
check replayed consistently with its scoped receipt. It is not a general
scientific-verification verdict.

The default demonstration records no human acceptance, emits no success trace
or Skill, performs no activation, and creates no longitudinal learning state.

The user retains authority over the accepted scientific model, research target,
verifier contract, and scientific judgment. A passing software gate cannot take
any of those decisions on the user's behalf.
