# VeriSpiral: project brief

**A problem-first research workflow for jointly developing Goal, Setup,
Verifier and Algorithm through multi-fidelity evidence and failure diagnosis.**

The user supplies a paragraph or document. The workflow clarifies the intended
decision, proposes a tractable setup, seeks a mathematical checking mechanism,
searches for algorithms and tests selected candidates against a more faithful
reference. When observations disagree, it chooses an experiment that can help
decide which layer needs work. Final target and scientific judgments remain
user-owned.

```text
problem -> Goal + Setup -> Verifier design and challenge -> Algorithm search
                    ^                  ^                         |
                    +---- diagnosis <- reference evaluation <----+
```

The central research tasks are verifier synthesis and budgeted diagnostic
experiment selection. The first approximation is from real requirements to a
setup and goal. The second is from expensive target evaluation to an affordable
checker. Both need to be assessed by the quality of the candidates actually
selected, their transfer and their full costs. The
[research agenda](docs/research-agenda.md) defines proposed comparisons; no
research-effectiveness or cross-task learning gain has been established.

## Primary implementation

Use [the host case workflow](prompts/protocols/run_case.md) and `verispiral case`.
The host invokes Goal/Setup, Verifier Designer, Solver, Red Team and Research
Controller. The runner accepts their submitted work, executes actual standalone
Python programs, keeps original inputs and receipts, and routes diagnosis,
solution changes and reviewed specification revisions. The
[case guide](docs/case-workflow.md) describes the exact interface.

Goal, setup, checker and reference identity are bound to the accepted design.
A replaced solver produces a new candidate and new evaluation. A checker
successor receives review and an applicable decision; retained candidates get
fresh checks. A goal/setup change opens a different target lineage. A changed
reference requires a separately scoped case. An agent's proposed explanation,
self-reported score or producer label cannot replace an actual execution receipt.

The new case kernel is independent of the earlier candidate-review pipeline.
It does not require a paper novelty assessment, minimax certificate or Skill
blueprint to process an ordinary problem. Those tools can be used when relevant.

## Components and learning

The verifier-design agent, its executable checker, candidate producer and
reference evaluator are distinct components. A researcher can supply their own
role artifacts and Python implementations through the same case interface.
General plugin discovery, installation and automatic model routing are future
work; a built-in LLM provider is not implemented.

[Role experience learning](docs/agent-learning-architecture.md) is an extension
that may improve later research methods. It is not a required endpoint for every
case, and persistent retrieval or automatic strategy activation is not implemented.

## Retained implementation and scope

Existing version, budget, reference-checking and recheck mechanisms remain useful.
The finite DAG, loss-table diagnosis, specification replay, candidate review,
process-patch and certificate-comparison demos remain optional examples and
regression checks. Their documented limitations continue to apply; they are not
a substitute for actual agent work in the primary host workflow.

The new executable behavior is covered by
[case tests](tests/test_case_workflow.py) and
[program execution tests](tests/test_case_execution.py). These purpose-built
public fixtures establish control behavior, not mathematical validity or a
model's ability to invent useful methods. The runner handles development cases,
not hidden final evaluation. Host/model work and program-internal cost claims
are distinct from enforced program-attempt budgets and timeouts. Local programs
run with the host's permissions; this is not a security sandbox or a verifier
of arbitrary dependency closure.

Actual problem inputs, private conversations and raw research outputs stay in
separate authorized workspaces outside Git. The public repository keeps generic
protocols, code, tests and purpose-built public fixtures. Use
`make verify golden-check` to check the bounded mechanisms before release.
