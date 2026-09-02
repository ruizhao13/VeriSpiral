# Limitations of the synthetic case

## Scope

- The scenario is purpose-built for this public repository.
- The negative scenario is a narrative explanation of a temporary test run;
  this folder does not contain a separately tracked generated negative packet.
- It contains no private research question, algorithm, dataset, experiment,
  result, identity, or decision history.
- The executable verifier checks a declared pipeline contract and
  artifact-emission invariants, not an arbitrary scientific claim.
- The public fixture does not call an LLM or a remote literature service.
- No benchmark, scientific novelty, or autonomous-discovery claim follows from
  the example.

## Verification

- The pipeline tests use the implementation they test; they are not an
  independently written reimplementation.
- Byte-identical replay detects drift but cannot establish that the policy is
  correct.
- `semantic_verification=verified` means that the registered executable verifier
  replayed successfully and matched its bound receipt. It does not establish
  theorem correctness, novelty, literature completeness, or paper-worthiness.
- The receipt binds named evidence files and a complete semantic-subject digest,
  but those bindings do not make the evidence scientifically true.
- A fixed set of negative tests cannot enumerate every filesystem, concurrency,
  serialization, or adversarial-input failure.
- The public-release audit uses conservative patterns and still requires a
  human staged-diff review.

## System boundary

The demo has no production scheduler, sandbox, remote evidence authentication,
access-control layer, or long-running multi-agent runtime. Its hashes bind
public files to a decision record; they do not certify the truth or ownership
of file contents.

The default demonstration stops at `decision=await_human_acceptance`. It records
`human_acceptance=pending`, writes only a decision packet and manifest, and
produces no success trace or Skill. It does not apply or activate a change and
does not create persistent or longitudinal learning state.

The user owns the accepted scientific model, research target, verifier contract,
and scientific judgment. Mechanical gates cannot change those objects, approve
a scientific claim, or make a model or verifier revision on the user's behalf.
