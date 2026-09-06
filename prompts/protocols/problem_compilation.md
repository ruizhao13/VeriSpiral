# Protocol: Compile a problem into a research workflow

This is the scientific design protocol used by the
[host case workflow](run_case.md). The host invokes the roles; `verispiral case`
executes their submitted programs and retains actual feedback. The runner does
not implement general semantic understanding, a model provider or scientific
correctness. Earlier deterministic demos exercise only their documented
fixtures. These instructions do not bypass existing evidence boundaries.

Reusable task invocation:

```text
Apply prompts/protocols/problem_compilation.md to <paragraph or document path>.
First return a traceable charter, verifiability triage, and material unknowns.
Propose a goal/setup/verifier frontier and the next distinguishing experiment.
Keep case inputs in my approved private workspace. State missing tools/oracles;
this protocol does not itself provide domain tools or autonomous execution.
```

## 1. Intake and Problem Charter

Accept a paragraph or document as a starting point. Keep source documents and
case-specific extracts in a separate, user-approved private case workspace.
Never copy private inputs, chats, or research outputs into this public repo.
Public examples must be purpose-built fixtures. Use document/version and
section/page/paragraph locators in the case workspace for traceability.

Compile a charter with the intended decision, scientific question, population,
inputs, outputs, deployment setting, available resources, and exclusions.
Label every material statement as `explicit`, `inferred`, `assumed`, or
`unknown`; attach its locator or explain the inference. A plausible inference
does not become a user requirement. List conflicting requirements separately.
Block freezing any material unresolved choice that could change the goal,
feasibility, comparison, or interpretation. Continue reversible analysis and
prepare concrete alternatives while that choice awaits the user.

## 2. Verifiability triage and domain adapter

Before broad solution search, name a reliable reference check, even if costly:
an exact small-instance oracle, independently auditable derivation, validated
measurement, or another justified reference. State its scope, assumptions,
failure modes, uncertainty, and cost. A citation can justify an assumption but
does not automatically verify a new candidate. If no adequate anchor exists,
return `verification_blocked` and propose anchor-building work; do not promote
a convenient surrogate or model consensus to authoritative evidence.

Specify a domain adapter: executable tools, oracle interfaces, input and data
contracts, measurement procedures, known invariants, and operating limits.
A general prompt is not a substitute for domain resources or validation.

## 3. Goal and setup design

Route to the [Goal and Setup Designer](../agents/goal_setup_designer.md).
Produce a goal contract separating
primary metrics, hard constraints, risk limits, deployment requirements, and
diagnostic/proxy metrics. Preserve the intended scientific meaning when a
proxy changes; if that meaning changes, propose a new goal branch.

Build a small setup frontier rather than silently choosing the easiest case.
For each setup give assumptions, tractability, anchor availability, cost,
deployment relevance, and differences from the intended problem. Maintain an
omission ledger: excluded features, reasons, likely impact, and a test or
explicit limitation for each. Specify transfer tests from simplified setups
to the intended setting, including conditions under which transfer fails.

## 4. Verifier synthesis and adversarial audit

Route to the [Verifier Synthesizer](../agents/verifier_synthesizer.md).
Treat verifier design as a research
task with a formal acceptance predicate, a reference target, soundness and
coverage limits, and a cost model. Supply an executable candidate checker or
state precisely what remains unresolved. Produce a distinct red-team audit
that targets the acceptance rule and selected candidates, using the
[verifier red-team role](../agents/verifier_red_team.md). Separate generation
from audit artifacts and evaluator access. Same-model agents are not evidence
of independence; report shared models, code, data, and assumptions.

## 5. Freeze, search, and promotion

The user owns acceptance of the goal, setup, verifier, and responsibility
boundary. Freeze these as an immutable `ResearchSpecification` before scored
search. Freeze budgets, baselines, selection rules, stopping criteria, and
development/red-team/final evaluation boundaries. Public fixtures are visible
regression examples, never a hidden evaluation. A final set accessed during
development loses that role and must be disclosed and replaced if feasible.

Search within the frozen contract. Each solver returns a complete executable
algorithm contract: input/output types, preconditions, steps or code, stopping
rules, resource limits, randomness, failure behavior, and reproducible run
instructions. Attach witnesses, certificates, or diagnostics where required.
An attractive description without executable behavior is not a completed
solver. Record unsuccessful runs and counterevidence as well as selected wins.

Evaluate the full identity: goal, setup, verifier, algorithm, code, environment,
seed, and data versions/hashes. Repeated evaluations must cite that identity.
Changes make affected conclusions stale until re-evaluation; never relabel an
old pass as evidence for a changed problem. Promotion requires the relevant
existing evidence gates and scope statement, not a score alone. Explicit human
acceptance must be labeled as such, not presented as empirical verification.

## 6. Diagnosis, revision, and continuation

Route to the [Research Controller](../agents/research_controller.md).
Distinguish algorithm weakness,
verifier defect, setup mismatch, goal misspecification, implementation error,
noise, and verifier gaming through experiments that predict different outcomes
under competing hypotheses. Preserve multiple hypotheses; abstain when the
available tests cannot distinguish them. A plausible story is not a diagnosis.

The controller allocates only the accepted budget and may propose revised
budgets, tests, or contracts. It cannot silently change an authoritative goal,
setup, or verifier. Use `research_specification_revision.md` for a concrete
proposal: evidence, exact delta, alternatives, scientific cost, affected
conclusions, and re-evaluation plan. Obtain the user's decision at the point
of authoritative revision; reversible investigation needs no added approval.
Resume under the accepted successor or problem branch and cite that decision.
