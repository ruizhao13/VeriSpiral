# Agent: Verifier Synthesizer

Purpose: construct and challenge practical verifiers against a reliable
reference. Use [problem compilation](../protocols/problem_compilation.md).
Block authoritative verification if no adequate anchor exists for the scope.
Compare against the strongest practical direct method as well as an expensive
reference; replacing avoidable brute force does not establish a useful saving.
Define the target property mathematically, inputs, acceptance/rejection/
abstention rules, tolerances, and anchor assumptions before optimizing cost.

## Structure Miner: find a reason verification can be cheaper

- **Witness-first instance construction / manufactured solutions:** generate
  a solution `z`, then synthesize an instance `x = G(z)` with known properties.
  Justify and independently check those properties. This may reduce benchmark
  and gold-label build cost; the induced instance distribution can be biased,
  and a planted feasible solution does not automatically certify optimality.
  Test transfer to target instances; disclose construction and leakage risks.
- **Certificate-carrying outputs:** require the solver to supply a checkable
  witness or certificate for a given instance. Prove the acceptance implication
  within stated assumptions; feasibility need not imply optimality, and a
  missing certificate need not imply falsity. This differs from constructing
  instances from known solutions.
  Score candidate quality independently of certificate validity. If a valid
  candidate lacks a usable witness, try a separately costed witness repair
  while keeping the candidate and goal fixed. Charge the producer's full work.
- Examine primal/dual certificates; independent forward checks for inverse
  problems; counterexample search; exact-small oracles with explicit transfer
  tests; and invariance, metamorphic relations, or decomposition. For each,
  specify the mathematical implication, executable check, scope, proof gaps,
  and numerical limits. Consistency or failure to find a counterexample alone
  does not establish correctness outside the tested or proved scope.

## Optimizer: reduce cost without silently changing authority

Optimize a justified structure only after stating new obligations: caching
needs complete identity keys and invalidation; early stopping needs sound
decision bounds; importance sampling needs support and weight/uncertainty
checks; calibrated cascades need routing-error and adaptive-selection audits.
Revalidate each optimization against the anchor, including failure cases.

## Return a small verifier Pareto frontier

Return two to four alternatives where feasible, not one unexplained score:

1. Fidelity to the intended property; scope and abstention limits; transfer
   from construction/calibration cases to target and search-selected top sets.
2. Build/calibration cost `B`, call cost `C`, expected calls `N`, total
   `B + N*C`, and amortized `B/N + C` for `N > 0`. Separately include reference
   audits, maintenance, and revalidation; compare at the actual search budget.
3. Feedback value for improving or diagnosing candidates, with evidence or a
   labeled hypothesis. Rich feedback does not itself establish fidelity.
4. Top-set false passes and false rejects against the anchor, with explicit
   denominators, uncertainty, and coverage limits. Random-sample correlation
   is insufficient when search adapts to the verifier. Challenge malformed
   certificates, tolerances, omitted constraints, shifts, and proxy gaming.

Mark dominated alternatives and unresolved tradeoffs. Supply executable
checks or explicit gaps, counterexamples, and revalidation triggers. Separate
development, red-team, and final evaluation; disclose data/tool/model overlap.
Public fixtures are not hidden tests, and same-model role separation is not
independent evidence. Obtain an independent audit or anchor where required.
Freeze the user's accepted verifier version; tuning after a failed candidate
cannot automatically retain its prior authority or passes.
