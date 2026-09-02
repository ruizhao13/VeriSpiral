# Minimax certificate-field compatibility checker

The public `minimax` runner compares registered theorem-certificate fields. It
is a compatibility checker, not a theorem verifier. It does not
prove a theorem, check a proof line by line, or infer a missing result from a
promising rate expression.

Its job is narrower: determine whether an upper certificate and a lower
certificate declare the same statistical problem. Only then does it compare
their stored rates. The status `minimax_rate_match` means that compatible
registered interfaces have matching recorded exponents. It cannot turn that
status into a theorem or a user-approved scientific claim.

## What a certificate records

An upper or lower certificate must identify its source and carry the interface
needed for comparison:

| Field | Questions answered |
| --- | --- |
| Problem signature | What environment, observation process, feedback, parameter class, and time model are covered? |
| Assumptions | Which structural, distributional, information, and algorithm-interface conditions are required? |
| Loss and risk | Is the target expected regret, high-probability regret, simple regret, estimation error, or another quantity? Where are expectation and supremum taken? |
| Algorithm class | Which policies compete in the lower bound, and does the upper-bound algorithm belong to the target class? |
| Regime | Which relations among sample size, horizon, dimension, number of arms, gaps, and other parameters are required? |
| Rate | What dependencies, logarithms, constants, and lower-order terms are recorded? |
| Source scope | Which theorem, lemma, or corollary states the result, and what does the registered certificate leave unchecked? |

The source text and the extracted certificate are separate objects. Public-demo
registration means that the source, theorem locator, and extracted interface
are checked into the fixture. It does not mean that this repository has
reproduced the proof or that a human has approved a manuscript-facing claim.

The runnable public demo uses a deliberately smaller machine contract. Its
`problem_signature` contains exactly `observation_model`, `parameter_class`,
`loss`, `algorithm_class`, and `regime`. Assumptions are stored separately. A
certificate records exact rational exponents for polynomial and logarithmic
rate factors. A machine-readable source registry carries the title, URL,
source locator, `registration_status: registered_public_extract`, and
`proof_status: cited_not_reproved`. The runner checks those fields are present
and linked; it does not fetch the paper, validate the extraction, or check
constants.

Every machine-readable certificate must set `registered: true`. The runner
rejects an unregistered certificate instead of guessing whether its scope is
sound.

## Public runner

The deterministic runner accepts a JSON scenario and writes a reviewable
trace:

```text
PYTHONPATH=src python3 -B -m verispiral minimax \
  --scenario examples/minimax_scenario.json \
  --output demo/output/minimax
```

The shorter clean-checkout command is `make minimax-demo`.

The scenario freezes one `problem_signature`, one `target_assumptions` map, a
registered lower certificate, and an ordered list of registered upper
certificates. A certificate stores its kind, signature, assumptions, and two
maps of exact rational exponents: `polynomial_exponents` and `log_exponents`.
Every candidate, `algorithm_change`, and `search_hypothesis` is present before
the replay starts. The runner evaluates that fixed sequence and records an
advisory `next_search_action`; it does not use the action to create or choose a
later candidate.

The output directory contains:

- `evolution_trace.json`, with field checks and the compatibility status for each candidate;
- `assumption_branches.json`, with immutable target state and explicit branch
  patches;
- `insight_ledger.json`, with an append-only status summary and advisory action
  for each round;
  and
- `manifest.json`, with input and artifact hashes.

Each artifact repeats the boundary that the runner checks registered scope,
assumptions, and rate algebra only. It does not re-prove either theorem.
The evolution trace also records `source_review_status: human_review_required`,
the source-verification boundary, the source registry, and the certificate
inventory.

## Compatibility comes before rate algebra

For a target parameter class `Theta` and policy class `A`, the distribution-free
minimax risk has the form

```text
inf_{pi in A} sup_{theta in Theta} Risk(pi, theta).
```

The public checker applies the following checks before it treats rate algebra
as applicable to the target:

1. All five problem-signature fields must match the target exactly.
2. The registered upper and lower assumptions must match the target exactly.
3. The upper-bound algorithm must belong to the target policy class. Prior
   knowledge of the horizon, oracle parameters, restarts, or extra feedback are
   part of this check.
4. Both certificates must hold on the recorded regime.

The implementation intentionally does not infer containment between parameter
or policy classes. A user may register a target-specific specialization as a new
certificate after checking the logical direction. For example, an upper bound
must cover every target instance, while a lower-bound hard subclass must sit
inside the target class. Until the registered certificate itself carries the
exact target fields, the strings remain incompatible.

After exact scope checks pass, the checker compares registered polynomial and
logarithmic exponents using rational arithmetic. `minimax_rate_match` means
those exponents match. It says nothing automatic about constants or unregistered
lower-order terms.

The comparison is coordinatewise. For each variable, a polynomial-exponent
difference takes precedence over its logarithmic-exponent difference. If the
result is better in one variable but worse in another, the runner returns
`not_comparable` unless a joint growth regime has been encoded in a future,
more expressive contract.

When the upper and lower signatures match but their assumptions do not, the
runner may still display their exponent comparison as a diagnostic. It marks
that algebra `rate_algebra_applicable_to_target: false`, sets the certificates
to `scope_incompatible`, and returns `not_comparable` for the target. The MOSS
round below illustrates this distinction.

## Assumption mismatches create candidate-branch records

Changing an assumption changes the problem being solved. In the synthetic
replay, the runner records a separate **candidate-branch artifact** when a
candidate requires known horizon, equal gaps, Gaussian noise, oracle rank, a
stronger signal condition, extra feedback, or a narrower loss. That artifact is
bookkeeping for the demo. It does not record a user decision to adopt or branch
the scientific model.

This rule blocks a common minimax error: tighten the parameter class until an
upper bound matches a lower bound, then report the result as if it solved the
original problem. The restricted theorem may be correct and useful, but it
would belong to a separate specification only if the user chooses to branch.

In the intended research architecture, an assumption or target change must
become a model-revision discussion packet. Only the user may `accept`, `reject`,
`modify`, or `branch` it. This standalone `minimax` runner does not implement
that user-decision step and does not accept or evaluate a bridge-certificate
input. The separate `research-loop` replay does validate a checked-in human-
decision fixture and keeps any changed model on a distinct target lineage.

A later replay round is labeled as returning to the parent only when its upper
certificate fields match the original target. A sentence such as "the same
proof should work" cannot change those fields.

The public scenario schema requires `assumption_order`. Its values must be
listed from weaker to stronger. For example,
`horizon_knowledge: [unknown, known]` lets the runner classify revealing the
horizon as `strengthening`. This order is registered input, not a theoretical
judgment inferred by the checker. A changed field missing from the registered
order is labeled `unclassified_change`, and it still receives a separate
branch.

For a strengthening, the synthetic branch artifact records
`operation: create_candidate_branch`, `target_mutated: false`, and
`merge_status: not_merged`. Returning to a candidate with the original
assumptions is recorded as `returned_to_target`; neither status accepts the
branch or merges it into a user-owned research specification.

## Purpose-built public bandit example

The example uses a classic stochastic `K`-armed bandit because its interfaces
are small enough to inspect without private research data. It is a certificate
comparison demo. It does not reproduce either paper's proof or experiments.

### User-specified target

The target branch fixes:

```text
environment:       stochastic K-armed bandit
reward process:    rewards are independent over time and i.i.d. within each arm
reward class:      distributions supported on [0, 1]
feedback:          reward of the selected arm only
horizon access:    unknown; one policy must be valid at every time t
loss:              cumulative pseudo-regret through time t
risk:              expected regret, worst case over the reward class
policy class:      nonanticipating anytime policies
target rate:       Theta(sqrt(K t)), up to universal constants and O(1) terms
```

The lower certificate is the classical distribution-free lower bound of order
`sqrt(K t)`. Audibert and Bubeck state a `sqrt(nK)/20` lower bound over stochastic
reward distributions on `[0, 1]`. Degenne and Perchet restate the same minimax
scale for their anytime analysis.

### Candidate 1: a UCB-like policy

A standard gap-dependent UCB analysis gives a logarithmic bound of the form

```text
sum_{i: Delta_i > 0} log(t) / Delta_i.
```

When gaps are chosen at the difficult scale, the corresponding
distribution-free upper certificate is of order `sqrt(K t log t)`. The policy
fits the unknown-horizon interface, but its registered upper rate has a
`sqrt(log t)` gap from the lower certificate.

Compatibility status: `log_gap`.

Pre-registered search hypothesis: confidence bonuses calibrated uniformly with
`log(t)` pay too much in the worst gap regime. A later solution-search process
could investigate exploration based on the global `K t` budget rather than
attach the full time logarithm to every arm.

The hypothesis is checked-in scenario input, not an insight generated by the
checker, a theorem, or an executed next step.

### Candidate 2: MOSS

Audibert and Bubeck's MOSS index uses the known terminal horizon `T` and the
number of pulls `s` through a term based on

```text
sqrt(max{log(T / (K s)), 0} / s).
```

Their Theorem 5 gives the distribution-free upper bound

```text
sup Risk_T <= 49 sqrt(K T)
```

for stochastic rewards supported on `[0, 1]`. Its polynomial and logarithmic
exponents match those recorded for the lower certificate, but the algorithm
requires `T` before play starts. That violates the target branch's
unknown-horizon interface.

Compatibility status: `not_comparable`, with a synthetic candidate-branch
record.

The candidate-branch artifact records the fixed-known-horizon interface. Its
polynomial and logarithmic exponents equal those in the registered lower
certificate, but that lower certificate belongs to the unknown-horizon target.
The replay therefore sets `rate_algebra_applicable_to_target: false`. It does
not establish a minimax rate match for either the original target or the
candidate branch, and it does not record a user `branch` decision. That decision
belongs to the separate research-specification control path, not this checker.

The checked-in narrative lists a doubling-trick version as another possible
solution candidate, not an automatic rewrite of the MOSS certificate. This
suggestion comes from the cited literature and scenario authoring; the runner
does not generate it. Degenne and Perchet note that this adaptation can retain
the distribution-free `sqrt(Kt)` scale while losing the simultaneous
single-parameter behavior that motivates their direct anytime construction.

### Candidate 3: MOSS-anytime

Degenne and Perchet replace the terminal horizon in the exploration term with
the current time. For `alpha = 1.35`, their Theorem 3 gives, for every `t >= 1`,

```text
E[R_t] <= 113 sqrt(K t) + Delta_max.
```

Their reward assumption is centered `1/2`-sub-Gaussian noise, and the paper
explicitly includes `[0, 1]` rewards as a main example. The public fixture
registers the bounded-class specialization; the checker does not infer that
containment from free text, and a human must review the extraction before any
external claim. Since `Delta_max <= 1` on the bounded class, the additive term
does not change the minimax rate.

The registered fields state that the algorithm is anytime, the loss and risk
match, the bounded-class specialization is applicable, and the upper and lower
certificates have the same `sqrt(Kt)` scale. The checker does not validate those
scientific statements against the papers.

Compatibility status: `minimax_rate_match`.

Pre-registered search hypothesis: the horizon mismatch points to the
exploration clock rather than a narrower reward class. The cited direct-anytime
construction is registered as returning to the original interface with stored
rate exponents matching the lower certificate.

The status is limited to the registered certificate fields. It does not
certify the proof, claim that MOSS-anytime is the unique solution, or establish
novelty for a new candidate inspired by it.

## Example comparison table

| Candidate | Registered rate field | Horizon interface | Compatibility status |
| --- | --- | --- | --- |
| UCB-like | `O(sqrt(K t log t))` worst case | Unknown horizon | `log_gap` |
| MOSS | `O(sqrt(K T))` | Known terminal `T` | `not_comparable`; exponents match diagnostically, but no branch-level rate match is reported |
| MOSS-anytime | `O(sqrt(K t)) + O(1)` for every `t` | Unknown horizon | `minimax_rate_match` |

The middle row preserves a useful registered comparison without enlarging the
checker's claim. This replay has no compatible lower certificate registered for
that candidate branch.

## What the checker may report

The checker may report:

- which certificate fields align;
- the first incompatible field;
- the upper/lower rate gap after alignment;
- a synthetic candidate-branch record caused by an assumption mismatch;
- the pre-registered mechanism or search hypothesis associated with the
  mismatch; and
- the exact unresolved question for human review.

It may not report that it proved a theorem, repaired a source proof, established
novelty, or made a candidate paper-worthy.

## User authority boundary

The user owns the target, accepted certificate extraction, checker contract,
and scientific interpretation. An assumption mismatch may motivate a
model-revision discussion packet, but only the user may `accept`, `reject`,
`modify`, or `branch` it. The checker can make a mismatch hard to overlook. It
cannot decide that a changed problem is "close enough" to the original one or
approve a manuscript-facing minimax statement.

## Primary sources

- Jean-Yves Audibert and Sebastien Bubeck,
  [Minimax Policies for Adversarial and Stochastic Bandits](https://www.microsoft.com/en-us/research/publication/minimax-policies-adversarial-stochastic-bandits/),
  COLT 2009. The demo uses the stochastic-bandit lower bound, MOSS definition,
  known-horizon interface, and Theorem 5 upper rate.
- Remy Degenne and Vianney Perchet,
  [Anytime optimal algorithms in stochastic multi-armed bandits](https://proceedings.mlr.press/v48/degenne16.html),
  ICML 2016. The demo uses the reward and anytime definitions and Theorem 3 for
  MOSS-anytime.
