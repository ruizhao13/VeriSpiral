# Protocol: Improve the workflow through observed problem failures

This is an authored iteration protocol, not evidence that joint design improves
research. Use it with [problem compilation](problem_compilation.md) and the
[research agenda](../../docs/research-agenda.md). It does not change executable
evidence gates or authorize unattended runs or scheduled work.

Reusable task invocation:

```text
Apply prompts/protocols/problem_driven_iteration.md to one bounded problem.
Freeze its charter, comparison, costs, and predicted failure before evaluation.
Diagnose one observed deficiency, make the smallest justified repair, and
recheck old and prospective cases. Preserve negative results and limitations.
```

## 1. Freeze the question and the comparison

Record a versioned charter: intended decision, external goal, assumptions,
scope, inputs, outputs, and exclusions. Separate confirmed requirements from
inferences, assumptions, and material unknowns. Identify which unknowns would
change the goal, comparator, feasibility, or interpretation before scoring.
Name the reference and its scope; internal consistency does not establish value.

Freeze a small common problem/candidate pool, comparator versions, acceptance
rules, and budget. Include the strongest practical direct solution available
within this scope; a costly exhaustive oracle alone is not an adequate baseline
when a more efficient direct method exists. Compare the same submitted objects
against the same goal, with identical information and resource constraints.

Record a cost vector: verifier design, witness/certificate construction,
calibration, candidate generation, checks, reference evaluation, repair,
retries, human review, and maintenance. Separate logical operation counts from
measured time and state any unmeasured cost; do not call omitted work free.
Report total cost before optional amortization, and state the reuse assumptions.
Before execution, name a predicted failure, at least one competing explanation,
and an observation that would distinguish them. Specify a useful improvement
threshold and a stopping condition. An after-the-fact explanation is exploratory.

## 2. Run a small reviewable case

Use a purpose-built public fixture with executable checks and a reproducible
command. Keep private inputs, conversations, extracts, and raw research outputs
outside this repository. Abstract ideas from a discussion may motivate a
hypothesis, but the discussion and AI-generated proposals are not evidence.
Do not place personal conversation links or history in the public ledger.

Retain every comparator outcome, false acceptance, false rejection, error,
budget exhaustion, and abstention. Record expected versus observed behavior,
the exact problem/code/protocol versions, and reference-check limitations.
If available observations do not distinguish explanations, record `unknown`
and stop the diagnosis or propose one bounded additional check within budget.

## 3. Repair what the evidence supports

Create a proposal tying an observed deficiency to an exact change in the
algorithm, verifier, setup, or goal. State competing repairs and why the chosen
one is supported. A failed verifier does not justify weakening acceptance or
silently dropping the case. A goal change creates a separate problem branch;
it cannot count as improvement against the original goal.

Apply already-authorized reversible repository repairs without an added
approval step. Authoritative choices for a real problem's goal, setup, verifier,
and responsibility boundary remain user-owned; use the existing
[revision protocol](research_specification_revision.md) when such a choice changes.
Do not present a public demonstration's design choices as user acceptance of a
real research specification.

## 4. Recheck and leave an iteration ledger

Run the original case, all affected old regressions, and predeclared prospective
cases after the repair. Freeze the repaired method before inspecting new results.
Record whether anticipated benefits survived and what regressed, including cost.
Every case whose feedback influenced the repair is development material. Public
cases are visible checks; prospective cases are not automatically hidden holdouts.
Fresh cases can test additional boundaries but do not alone establish generality.

| Ledger field | Required record |
| --- | --- |
| Problem and versions | Charter, external goal, scope, code/protocol identity |
| Prediction and check | Competing explanations, discriminator, command/artifact |
| Observation and costs | All outcomes, reference limits, complete cost vector |
| Proposal | Exact repair, evidence, alternatives, responsibility boundary |
| Regression outcome | Old and prospective cases, failures, abstentions, costs |
| Remaining limits | Unresolved unknowns, development exposure, next distinct case |

Stop this cycle after one concrete deficiency is repaired and rechecked, or
when the predeclared budget is spent or useful benefit is absent. Preserve the
failure if repair does not help. A next cycle needs a distinct case or a specific
unresolved boundary; repeatedly rewriting the protocol is not progress evidence.
