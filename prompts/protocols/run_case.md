# Host protocol: run a research case

Start from the user's paragraph or document. The host performs real role calls and supplies their artifacts;
the [case runner](../../docs/case-workflow.md) executes Python components and records transitions.
It does not call an LLM provider. Do not describe copied fixtures, scripted replies or a producer label as a live agent invocation.
Another host or researcher may supply the same structured submissions with `kind: external`.

1. **Read the problem and existing authorization.** Preserve the original source in an authorized workspace outside Git.
   Use [problem compilation](problem_compilation.md) to separate requirements, assumptions and material unknowns.
   Invoke [Goal/Setup Designer](../agents/goal_setup_designer.md) to propose a tractable formulation and alternatives.
   Preserve the intended decision and omitted mechanisms; do not make the problem easier without identifying that change.
2. **Select a reference.** The host independently configures a runnable reference and its scope, supported by an exact small
   calculation, a source, an audit or other applicable evidence. Separate configuration does not prove mathematical independence.
   If no adequate reference exists, work on the anchor first; do not manufacture an equality/optimality claim from a proxy.
   Create the case with `case new`; retain actual role-call identities, versions and artifact associations locally.
3. **Construct the verifier.** Invoke [Verifier Synthesizer](../agents/verifier_synthesizer.md), using original requirements
   and the proposed Goal/Setup. Seek a concrete certificate, bound, forward calculation, decomposition or other justified mechanism.
   Compare a practical direct baseline and complete costs. Return `design.json` and a standalone checker in `components/`;
   submit with `case design`. Nonempty material unknowns require resolution before audit and freezing.
4. **Execute an audit.** Invoke [Verifier Red Team](../agents/verifier_red_team.md) with the contract, assumptions, checker
   and authorized reference context; initially withhold persuasive design rationale. Ask for a bounded executable audit,
   reproducible failures and uncertainty. Submit its actual program with `case audit`, not an authored pass record.
   Read the findings as well as its verdict. Shared models, tools or files remain disclosed overlaps.
5. **Freeze the concrete design.** At `awaiting_decision`, record the user's applicable existing authorization or explicit
   accept/reject decision, bound to the current `design_sha256`. Existing authorization does not require another confirmation.
   Material choices outside that authorization go to the user with the actual proposal. Use `synthetic_fixture` for synthetic decisions.
   `case decide` records the decision; it does not authenticate the person or establish reference correctness.
6. **Run the submitted algorithm.** Invoke [Solver](../agents/solver.md) under the frozen goal/setup and budget.
   Preserve its actual standalone program, producer metadata, assumptions and cost claims; run it with `case run`.
   The runner executes the solver, then checker and separately configured reference on the same candidate.
   Read their distinct outputs, execution errors and evidence identities. Candidate failure and certificate failure may coexist;
   a missing proof is not automatically a bad candidate. Do not substitute solver self-scores for observed checks.
7. **Diagnose the current feedback.** Invoke [Research Controller](../agents/research_controller.md) on the latest receipts.
   Preserve competing explanations and an unknown option. Request a small distinguishing experiment, expected outcomes,
   cost and stopping condition. Submit diagnosis with the current `last_run_sha256` through `case diagnose`.
   A recorded hypothesis is not causal proof; retain disagreements and failed attempts.
8. **Continue or revise.** `continue_search` permits a new solver under the accepted specification.
   `revise_verifier` returns to design/audit/decision while preserving goal, setup and assumptions.
   After acceptance, use `case run --recheck` to pay for new checks on the retained candidate under the same target lineage.
   Goal/setup revisions also require reviewed design and an applicable decision; incompatible lineage prevents retained-candidate recheck.
   A changed original problem or reference needs a new case. Never overwrite old evidence to make a revision look successful.
9. **Stop with a scoped result.** Use `case next` / `case report` to inspect state; these commands do not invoke agents.
   Stop at the accepted budget, round limit, scoped conclusion or unresolved user choice. Report actual outcomes and remaining uncertainty.
   Even `ready_for_review` remains development evidence with scientific acceptance false; it is not hidden final evaluation.

Use Python 3.10+ standard-library programs and the exact [JSON interfaces](../../docs/case-workflow.md#standalone-python--json-program-interface).
Call budgets count top-level program attempts, including failure. Separately record actual host/model calls, nested component work,
construction, reference cost and human effort; declared operations are not a universal cost unit.
Programs execute with host permissions. Isolation flags and file hashes are not a security sandbox or a complete dependency fingerprint.

All real problem text, private dialogue, original research data and outputs stay in authorized workspaces outside Git.
Keep final-evaluation information out of adaptation; this runner implements development cases and does not enforce hidden-test custody.
Conditional methods and useful partial results may enter authorized local experience under the
[learning contract](../../docs/agent-learning-architecture.md), without automatically activating a strategy or Skill.
Novelty review, proof auditing, bandit certificates and Skill distillation are optional tasks, not required case milestones.

Executable scope is checked by [case tests](../../tests/test_case_workflow.py) and
[program tests](../../tests/test_case_execution.py); their synthetic programs are regression evidence, not live-agent research results.
