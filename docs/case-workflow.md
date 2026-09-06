# Research cases: submitted agent work and executable feedback

`verispiral case` is the main workflow: problem → Goal/Setup → Verifier design and audit →
recorded decision → Algorithm execution → separate checker/reference results → diagnosis and revision.
The [host protocol](../prompts/protocols/run_case.md) invokes real agents; the runner has no built-in
LLM provider, prose interpreter, or automatic agent dispatcher. External role implementations use the same submissions.
Old candidate-review, Skill and bandit demos are optional mechanisms. A case requires neither novelty fields nor a Skill blueprint.

## Create and advance a case

Use Python 3.10 or later. Select standalone standard-library Python components whose execution the host authorizes.
Keep all live inputs, submissions and outputs outside Git; the destination must be new and outside any Git repository.
The original input is a nonempty UTF-8 `.md`/`.txt` document of at most 100000 bytes.
The host separately supplies `reference.py` and its exact scope; the runner does not establish its mathematical correctness or independence.
The host produces the named files before these commands are run:

```bash
verispiral case new --problem problem.md --workspace ../research-case \
  --reference reference.py --reference-scope "Exact minimum over a finite integer list" \
  --calls 20 --rounds 4 --timeout 10
verispiral case next --workspace ../research-case
verispiral case design --workspace ../research-case --input ../research-case/design.json
verispiral case audit --workspace ../research-case --program components/audit.py --producer ../research-case/red-team.json
verispiral case decide --workspace ../research-case --input ../research-case/decision.json
verispiral case run --workspace ../research-case --program components/solver.py --producer ../research-case/solver.json
verispiral case diagnose --workspace ../research-case --input ../research-case/diagnosis.json
verispiral case report --workspace ../research-case
```

`new` copies the problem and reference, then creates `case.json`, `events/` and `components/` for submitted work.
`--program` is relative to that case;
`--input` and `--producer` identify JSON files using the caller's working directory.
`next` and `report` inspect the same state; neither invokes a model nor writes a separate report artifact.

## Design, producer, decision and diagnosis JSON

This is a synthetic design example; the host must supply the actual problem-specific goal and setup:
```json
{
  "goal": {"objective": "minimum supplied integer"},
  "setup": {"values": [7, 3, 9]},
  "verifier": {
    "program": "components/checker.py",
    "meaning": "The candidate is a supplied integer no greater than every other entry.",
    "mechanism": "Membership and complete pairwise comparison with the candidate.",
    "limitations": ["The supplied list is the entire scope."]
  },
  "assumptions": ["The supplied list is nonempty and contains integers."],
  "unknowns": [],
  "producer": {"role": "verifier_designer", "id": "example-author", "version": "1", "kind": "public_fixture"}
}
```

`goal`, `setup` and `verifier` must be nonempty objects; `assumptions`, `unknowns` and verifier `limitations` are lists.
Nonempty `unknowns` yields `needs_input`. The runner records the checker hash and computes `design_sha256`.
Each producer needs nonempty `role`, `id`, `version` strings and `kind`: `live_agent`, `external` or `public_fixture`.
Audit/run producer files contain this producer object directly. These are declared identities, not authenticated authorship.

After an executed audit returns ready, bind a decision to the exact `design_sha256` from `case.json`:
```json
{"action": "accept", "actor": "synthetic_fixture", "design_sha256": "REPLACE_WITH_CURRENT_DESIGN_SHA256"}
```

`action` is `accept` or `reject`; `actor` is `user_record` or `synthetic_fixture`.
For a live case, the host records the user's applicable existing authorization or explicit concrete decision as `user_record`.
Do not invent another approval requirement when authorization already covers the design; do not label a fixture as a real decision.
Acceptance freezes the specification; rejection stops the case. The runner does not authenticate the human identity.

Diagnosis consumes the current `last_run_sha256`, not a self-reported success or an earlier round:
```json
{
  "run_sha256": "REPLACE_WITH_CURRENT_LAST_RUN_SHA256",
  "producer": {"role": "research_controller", "id": "example-author", "version": "1", "kind": "public_fixture"},
  "hypotheses": ["Candidate is inadequate", "Checker misses a required condition"],
  "experiment": {"action": "Recheck the retained candidate with the proposed complete checker."},
  "next_action": "revise_verifier"
}
```

`hypotheses` must be a nonempty list; `experiment` a nonempty object describing a distinguishing test or scoped stop reason.
Actions are `continue_search`, `revise_verifier`, `revise_setup`, `revise_goal`, `stop`.

## Standalone Python / JSON program interface

Each program reads one JSON object from stdin and prints exactly one JSON object to stdout; diagnostics may use stderr.
It runs as `sys.executable -I -B program.py`, with its own directory as the working directory. JSON must have finite numbers and unique keys.

| Component | Request | Required result |
| --- | --- | --- |
| Solver | `{"goal": {...}, "setup": {...}}` | `{"candidate": {...}}`; candidate must be an object |
| Checker and reference, each independently executed | The same request plus `"candidate": {...}` | `{"verdict": "pass"}`; alternatively `fail` or `inconclusive` |
| Audit | `goal`, `setup`, `assumptions`, `verifier_contract`, `verifier_meaning`, `checker_path`, `reference_scope` | `{"verdict": "ready", "findings": [...]}` advances to decision; other results retain review |

Audit receives the submitted verifier contract and source path, without the design's top-level rationale.
Additional result fields are retained. Use them for counterexamples, candidate/proof distinctions and separately defined costs.
Only the runner's actual receipts determine run status; a program's claimed success cannot replace checker/reference execution.
Both verdicts must pass with intact frozen identities to reach `ready_for_review`; this is not accepted scientific truth.

## Revision, budget and evidence

`continue_search` permits another solver execution under the frozen specification. A verifier revision requires a new design,
executed audit and bound decision, preserving goal/setup/assumptions. Goal/setup revisions also return through design and decision.
After acceptance, `verispiral case run --workspace ../research-case --recheck --producer ../research-case/solver.json`
executes checker and reference again on the retained candidate, only when its target lineage still matches. No old pass is reused.
Changing the original problem or selected reference requires a new case. Preserve unsuccessful versions and their events.

The budget counts top-level program attempts, including failed/unavailable attempts; defaults are 20 calls, 4 rounds and 10 seconds per attempt.
An audit costs one attempt. A new round needs three available attempts; recheck needs two. A failed solver may consume only its own attempt.
Subprocesses launched inside components, component operation counts, model calls, host work and human time are not charged by this counter; report them separately.
Timeouts, nonzero exits, invalid/missing output and unavailable or changed components cannot count as passing checks.
Execution captures at most 1000000 combined stdout/stderr bytes; timeout cleanup and hashing may add elapsed time.

`events/` stores reservations, receipts and transitions; `case.json` binds their identities and the latest state.
Hashes bind submitted files and executed requests/results, not arbitrary dependencies or a tamper-proof external authority.
Execution is not a security sandbox: programs retain host filesystem/network permissions; even transient edits restored before hashing can escape detection.
All current results are `development`, with `is_hidden_final_evaluation: false` and `scientific_claim_accepted: false`.
No hidden-test isolation, automatic scientific acceptance or cross-task improvement is established.

Implementation: [case workflow](../src/verispiral/case_workflow.py), [executor](../src/verispiral/case_execution.py).
Behavioral evidence: [workflow tests](../tests/test_case_workflow.py), [execution tests](../tests/test_case_execution.py).
