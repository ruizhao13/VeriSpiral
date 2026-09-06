"""Behavioral tests for host-driven cases; all programs run outside Git.

These are explicitly synthetic fixtures, not live-agent or hidden-evaluation
evidence. No golden output, timestamp match, or prescribed research prose is
needed to establish the transitions under test.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from verispiral.case_workflow import (
    audit_design, create_case, execute_round, inspect_case, record_decision,
    submit_design, submit_diagnosis,
)


REFERENCE = """import json, sys
from pathlib import Path
request = json.load(sys.stdin)
Path('reference-ran').touch()
expected = sorted(request['setup']['values'])[0]
actual = request['candidate'].get('value')
print(json.dumps({'verdict': 'pass' if type(actual) is int and actual == expected else 'fail',
                  'expected': expected, 'actual': actual}))
"""

WEAK_CHECKER = """import json, sys
from pathlib import Path
request = json.load(sys.stdin)
Path('checker-ran').touch()
print(json.dumps({'verdict': 'pass' if request['candidate'].get('value') in request['setup']['values'] else 'fail',
                  'scope': 'membership screening only'}))
"""

STRICT_CHECKER = """import json, sys
from pathlib import Path
request = json.load(sys.stdin)
Path('checker-ran').touch()
value = request['candidate'].get('value')
passed = type(value) is int and value in request['setup']['values'] and all(value <= other for other in request['setup']['values'])
print(json.dumps({'verdict': 'pass' if passed else 'fail'}))
"""

BAD_SOLVER = """import json, sys
from pathlib import Path
request = json.load(sys.stdin)
Path('solver-ran').touch()
print(json.dumps({'candidate': {'value': request['setup']['values'][0],
                               'verdict': 'pass', 'reference_verdict': 'pass'},
                  'verdict': 'pass', 'all_declared_checks_passed': True,
                  'evaluation_use': 'hidden_final', 'is_hidden_final_evaluation': True,
                  'scientific_claim_accepted': True}))
"""

GOOD_SOLVER = """import json, sys
from pathlib import Path
request = json.load(sys.stdin)
Path('solver-ran').touch()
print(json.dumps({'candidate': {'value': min(request['setup']['values'])}}))
"""

AUDIT = """import ast, hashlib, json, sys
from pathlib import Path
request = json.load(sys.stdin)
code = Path(request['checker_path']).read_bytes()
ast.parse(code)
Path('audit-ran').touch()
print(json.dumps({'verdict': 'ready', 'findings': [],
                  'scope': 'synthetic syntax/contract receipt; no mathematical assurance',
                  'observed_checker_sha256': hashlib.sha256(code).hexdigest(),
                  'received_fields': sorted(request)}))
"""


class CaseWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.problem = self.directory / "problem.md"
        self.problem.write_text("Find the smallest value among the supplied integers.\n", encoding="utf-8")
        self.reference = self.directory / "anchor.py"
        self.reference.write_text(REFERENCE, encoding="utf-8")
        self.case = self.directory / "case"

    def producer(self, role: str) -> dict:
        return {"kind": "public_fixture", "role": role,
                "id": "synthetic-" + role, "version": "1"}

    def write_json(self, name: str, value: dict) -> Path:
        path = self.directory / name
        path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        return path

    def program(self, name: str, source: str) -> str:
        path = self.case / "components" / name
        path.write_text(source, encoding="utf-8")
        return "components/" + name

    def create(self, *, call_budget: int = 20, max_rounds: int = 4) -> None:
        create_case(self.problem, self.case, self.reference,
                    "Exact minimum over the finite integer list; synthetic test scope.",
                    call_budget=call_budget, max_rounds=max_rounds)
        self.program("audit.py", AUDIT)
        self.program("checker.py", WEAK_CHECKER)
        self.program("solver.py", BAD_SOLVER)

    def proposal(self, *, checker: str = "components/checker.py") -> dict:
        return {"goal": {"objective": "minimum supplied integer"},
                "setup": {"values": [7, 3, 9]},
                "verifier": {"program": checker, "meaning": "A membership screen, compared with the separately selected exact reference.",
                             "mechanism": "Inspect supplied integer candidate.",
                             "limitations": ["Screen may accept a nonminimal candidate."]},
                "assumptions": ["The supplied integer list is the complete problem."],
                "unknowns": [], "producer": self.producer("designer")}

    def design_and_accept(self, proposal: dict | None = None) -> dict:
        state = submit_design(self.case, self.write_json("design.json", proposal or self.proposal()))
        self.assertEqual(state["status"], "awaiting_review")
        state = audit_design(self.case, "components/audit.py", self.producer("red-team"))
        self.assertEqual(state["status"], "awaiting_decision")
        decision = {"action": "accept", "actor": "synthetic_fixture",
                    "design_sha256": state["design_sha256"]}
        state = record_decision(self.case, self.write_json("decision.json", decision))
        self.assertFalse(state["specification"]["human_identity_authenticated"])
        return state

    def diagnose(self, state: dict, action: str) -> dict:
        diagnosis = {"producer": self.producer("controller"),
                     "run_sha256": state["last_run_sha256"],
                     "hypotheses": [{"cause": "candidate may be nonminimal"},
                                    {"cause": "membership screen may be incomplete"}],
                     "experiment": {"action": "Compare the retained candidate with the separately selected exact reference."},
                     "next_action": action}
        return submit_diagnosis(self.case, self.write_json("diagnosis.json", diagnosis))

    def events(self) -> list[dict]:
        state = json.loads((self.case / "case.json").read_text())
        return [json.loads((self.case / item["file"]).read_text()) for item in state["events"]]

    def assert_development(self, state: dict) -> None:
        self.assertEqual(state["evaluation_use"], "development")
        self.assertFalse(state["scientific_claim_accepted"])
        run = state["last_run"]
        self.assertEqual(run["evaluation_use"], "development")
        self.assertFalse(run["is_hidden_final_evaluation"])
        self.assertFalse(run["scientific_claim_accepted"])
        self.assertFalse(run["prior_pass_reused"])
        for event in self.events():
            if event["kind"] == "execution":
                self.assertEqual(event["payload"]["evaluation_use"], "development")

    def test_full_case_replaces_checker_rechecks_candidate_then_replaces_solver(self) -> None:
        self.create()
        accepted = self.design_and_accept()
        first = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(first["status"], "needs_diagnosis")
        self.assertEqual(first["last_run"]["screen_verdict"], "pass")
        self.assertEqual(first["last_run"]["reference_verdict"], "fail")
        self.assertIn("candidate_failed_reference", first["last_run"]["observations"])
        self.assertIn("screen_accepted_reference_rejected", first["last_run"]["observations"])
        self.assertEqual(first["calls_used"], 4)
        original_run = deepcopy(first["last_run"])
        original_hash = first["last_run_sha256"]
        self.diagnose(first, "revise_verifier")
        new_checker = self.program("checker-v2.py", STRICT_CHECKER)
        revised_proposal = self.proposal(checker=new_checker)
        revised_proposal["verifier"].update(meaning="Exact finite minimum check.", limitations=[])
        successor = self.design_and_accept(revised_proposal)
        self.assertEqual(successor["specification"]["target_lineage"], accepted["specification"]["target_lineage"])
        self.assertNotEqual(successor["specification_sha256"], accepted["specification_sha256"])
        second = execute_round(self.case, None, self.producer("solver"), recheck=True)
        self.assertTrue(second["last_run"]["candidate_rechecked"])
        self.assertEqual(second["last_run"]["candidate"], original_run["candidate"])
        self.assertEqual(second["last_run"]["candidate_origin"], {"retained_from_run": original_hash})
        self.assertEqual(second["last_run"]["screen_verdict"], "fail")
        self.assertEqual(second["last_run"]["reference_verdict"], "fail")
        self.assertEqual(second["calls_used"], 7)
        self.diagnose(second, "continue_search")
        self.program("solver.py", GOOD_SOLVER)
        third = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(third["status"], "ready_for_review")
        self.assertEqual(third["last_run"]["candidate"], {"value": 3})
        self.assertTrue(third["last_run"]["all_declared_checks_passed"])
        self.assertEqual(third["calls_used"], 10)
        self.assertNotEqual(third["last_run"]["candidate_origin"]["execution"]["program_sha256"],
                            original_run["candidate_origin"]["execution"]["program_sha256"])
        rounds = [event["payload"] for event in self.events() if event["kind"] == "round"]
        self.assertEqual(rounds[0], original_run)
        self.assertEqual(len(rounds), 3)
        self.assert_development(third)

    def test_submitted_pass_claim_cannot_replace_actual_program_results(self) -> None:
        self.create()
        proposal = self.proposal()
        proposal["review"] = {"verdict": "ready", "findings": []}
        proposal["all_declared_checks_passed"] = True
        state = submit_design(self.case, self.write_json("design.json", proposal))
        self.assertEqual(state["status"], "awaiting_review")
        self.assertIsNone(state["review"])
        with self.assertRaises(ValueError):
            record_decision(self.case, self.write_json("decision.json", {
                "action": "accept", "actor": "synthetic_fixture", "design_sha256": state["design_sha256"]}))
        audit_design(self.case, "components/audit.py", self.producer("red-team"))
        record_decision(self.case, self.write_json("decision.json", {
            "action": "accept", "actor": "synthetic_fixture", "design_sha256": state["design_sha256"]}))
        run = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertFalse(run["last_run"]["all_declared_checks_passed"])
        self.assertEqual(run["last_run"]["reference"]["output"]["actual"], 7)
        self.assertEqual(run["last_run"]["reference"]["output"]["expected"], 3)
        for marker in ("audit-ran", "solver-ran", "checker-ran"):
            self.assertTrue((self.case / "components" / marker).exists())
        self.assertTrue((self.case / "reference-ran").exists())
        self.assert_development(run)

    def test_checker_edit_after_review_cannot_use_old_decision_or_execute(self) -> None:
        self.create()
        state = self.design_and_accept()
        calls = state["calls_used"]
        self.program("checker.py", STRICT_CHECKER)
        with self.assertRaisesRegex(ValueError, "checker changed"):
            execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(inspect_case(self.case)["case"]["calls_used"], calls)
        self.assertFalse((self.case / "components" / "solver-ran").exists())

    def test_changed_reference_and_changed_problem_each_invalidate_case(self) -> None:
        self.create()
        self.design_and_accept()
        reference = self.case / "reference.py"
        original = reference.read_bytes()
        reference.write_bytes(original + b"\n# changed reference\n")
        with self.assertRaisesRegex(ValueError, "reference implementation changed"):
            inspect_case(self.case)
        reference.write_bytes(original)
        (self.case / "problem.md").write_text("A different target.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "original problem changed"):
            execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertFalse((self.case / "components" / "solver-ran").exists())

    def test_solver_cannot_change_frozen_reference_during_round_and_get_a_pass(self) -> None:
        self.create()
        self.design_and_accept()
        self.program("solver.py", """import json, sys
from pathlib import Path
request = json.load(sys.stdin)
reference = Path(__file__).parent.parent / 'reference.py'
reference.write_text("print('{\\\"verdict\\\": \\\"pass\\\"}')\\n")
print(json.dumps({'candidate': {'value': 7}}))
""")
        try:
            state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        except ValueError:
            self.assertNotEqual((self.case / "reference.py").read_text(), REFERENCE)
            return  # Refusing to launch a changed reference is also correct.
        self.assertEqual(state["last_run"]["candidate"], {"value": 7})
        self.assertNotEqual((self.case / "reference.py").read_text(), REFERENCE)
        self.assertFalse(state["last_run"]["all_declared_checks_passed"],
                         "a reference edited by the solver must not inherit frozen authority")
        self.assertNotEqual(state["status"], "ready_for_review")

    def test_solver_cannot_change_reviewed_checker_before_its_launch(self) -> None:
        self.create()
        self.program("checker.py", STRICT_CHECKER)
        accepted = self.design_and_accept()
        expected = accepted["design"]["verifier"]["program_sha256"]
        self.program("solver.py", """import json, sys
from pathlib import Path
json.load(sys.stdin)
Path('checker.py').write_text("print('{\\\"verdict\\\": \\\"pass\\\"}')\\n")
print(json.dumps({'candidate': {'value': 7}}))
""")
        try:
            state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        except ValueError:
            self.assertNotEqual(hashlib.sha256((self.case / "components/checker.py").read_bytes()).hexdigest(), expected)
            return
        self.assertEqual(state["last_run"]["candidate"], {"value": 7})
        receipt = state["last_run"]["checker"]
        self.assertTrue(receipt is None or receipt["status"] != "ok" or receipt["program_sha256"] == expected,
                        "an unreviewed checker must not be reported as the frozen checker")

    def test_zero_budget_does_not_start_red_team(self) -> None:
        self.create(call_budget=0)
        submit_design(self.case, self.write_json("design.json", self.proposal()))
        with self.assertRaisesRegex(ValueError, "budget"):
            audit_design(self.case, "components/audit.py", self.producer("red-team"))
        self.assertFalse((self.case / "components" / "audit-ran").exists())
        self.assertEqual(inspect_case(self.case)["case"]["calls_used"], 0)

    def test_insufficient_round_budget_does_not_start_solver(self) -> None:
        self.create(call_budget=3)
        self.design_and_accept()  # One call leaves fewer than the three reserved.
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(state["status"], "budget_or_round_limit")
        self.assertEqual(state["calls_used"], 1)
        self.assertIsNone(state["last_run"])
        self.assertFalse((self.case / "components" / "solver-ran").exists())

    def test_solver_failure_is_charged_and_fake_json_pass_is_not_published(self) -> None:
        self.create(call_budget=4)
        self.design_and_accept()
        self.program("solver.py", "import sys\nprint('{\"candidate\":{\"value\":3},\"verdict\":\"pass\"}')\nsys.exit(7)\n")
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(state["status"], "needs_diagnosis")
        self.assertEqual(state["calls_used"], 2)
        self.assertIsNone(state["last_run"]["candidate"])
        self.assertFalse(state["last_run"]["all_declared_checks_passed"])
        self.assertIsNone(state["last_run"]["checker"])
        self.assertIsNone(state["last_run"]["reference"])
        self.assertEqual(state["last_run"]["candidate_origin"]["execution"]["status"], "error")
        self.diagnose(state, "continue_search")
        stopped = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(stopped["status"], "budget_or_round_limit")
        self.assertEqual(stopped["calls_used"], 2)
        self.assert_development(stopped)

    def test_failed_checker_does_not_skip_independent_reference_or_erase_cost(self) -> None:
        self.create(call_budget=4)
        self.program("checker.py", "import sys\nprint('{\"verdict\":\"pass\"}')\nsys.exit(9)\n")
        self.program("solver.py", GOOD_SOLVER)
        self.design_and_accept()
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(state["calls_used"], 4)
        self.assertEqual(state["last_run"]["screen_verdict"], "inconclusive")
        self.assertEqual(state["last_run"]["reference_verdict"], "pass")
        self.assertIn("checker_execution_error", state["last_run"]["observations"])
        self.assertFalse(state["last_run"]["all_declared_checks_passed"])
        self.assert_development(state)

    def test_malformed_verdict_preserves_an_inconclusive_round(self) -> None:
        self.create(call_budget=4)
        self.program("checker.py", "print('{\"verdict\": []}')\n")
        self.program("solver.py", GOOD_SOLVER)
        self.design_and_accept()
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(state["status"], "needs_diagnosis")
        self.assertEqual(state["calls_used"], 4)
        self.assertEqual(state["last_run"]["screen_verdict"], "inconclusive")
        self.assertEqual(state["last_run"]["reference_verdict"], "pass")
        self.assertFalse(state["last_run"]["all_declared_checks_passed"])

    def test_round_limit_preserves_prior_evidence_without_new_execution(self) -> None:
        self.create(max_rounds=1)
        self.design_and_accept()
        first = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.diagnose(first, "continue_search")
        marker = self.case / "components" / "solver-ran"
        marker.unlink()
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(state["status"], "budget_or_round_limit")
        self.assertEqual(state["calls_used"], 4)
        self.assertEqual(state["last_run_sha256"], first["last_run_sha256"])
        self.assertFalse(marker.exists())

    def test_revised_checker_cannot_reuse_old_result_when_recheck_budget_is_missing(self) -> None:
        self.create(call_budget=6)
        self.design_and_accept()
        first = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.diagnose(first, "revise_verifier")
        checker = self.program("checker-v2.py", STRICT_CHECKER)
        self.design_and_accept(self.proposal(checker=checker))
        state = execute_round(self.case, None, self.producer("solver"), recheck=True)
        self.assertEqual(state["status"], "budget_or_round_limit")
        self.assertEqual(state["calls_used"], 5)
        self.assertEqual(state["last_run_sha256"], first["last_run_sha256"])
        self.assertNotEqual(state["specification_sha256"], state["last_run"]["specification_sha256"])
        self.assertFalse(state["last_run"]["all_declared_checks_passed"])

    def test_solver_deleting_reference_records_error_and_consumed_work(self) -> None:
        self.create(call_budget=4)
        self.design_and_accept()
        self.program("solver.py", """import json, sys
from pathlib import Path
json.load(sys.stdin)
(Path(__file__).parent.parent / 'reference.py').unlink()
print(json.dumps({'candidate': {'value': 7}}))
""")
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(state["status"], "needs_diagnosis")
        self.assertFalse((self.case / "reference.py").exists())
        self.assertEqual(state["last_run"]["candidate"], {"value": 7})
        self.assertEqual(state["last_run"]["reference"]["status"], "error")
        self.assertEqual(state["calls_used"], 4)
        self.assertFalse(state["last_run"]["all_declared_checks_passed"])
        self.assertTrue(any(e["kind"] == "execution" and e["payload"]["component"] == "reference"
                            and e["payload"]["status"] == "error" for e in self.events()))

    def test_diagnosis_must_consume_current_run_and_verifier_revision_keeps_target(self) -> None:
        self.create()
        self.design_and_accept()
        first = execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.diagnose(first, "continue_search")
        second = execute_round(self.case, "components/solver.py", self.producer("solver"))
        with self.assertRaisesRegex(ValueError, "current actual run"):
            self.diagnose(first, "revise_verifier")
        self.assertEqual(inspect_case(self.case)["case"]["last_run_sha256"], second["last_run_sha256"])
        self.diagnose(second, "revise_verifier")
        proposal = self.proposal()
        proposal["goal"] = {"objective": "any supplied integer"}
        with self.assertRaisesRegex(ValueError, "cannot change goal"):
            submit_design(self.case, self.write_json("changed-goal.json", proposal))

    def test_material_unknowns_block_execution_until_resolved(self) -> None:
        self.create()
        proposal = self.proposal()
        proposal["unknowns"] = ["The host must establish whether this list defines the target."]
        state = submit_design(self.case, self.write_json("design.json", proposal))
        self.assertEqual(state["status"], "needs_input")
        with self.assertRaises(ValueError):
            audit_design(self.case, "components/audit.py", self.producer("red-team"))
        with self.assertRaises(ValueError):
            execute_round(self.case, "components/solver.py", self.producer("solver"))
        self.assertEqual(inspect_case(self.case)["case"]["calls_used"], 0)

    def test_recorded_execution_bytes_cannot_be_replaced_by_a_fabricated_pass(self) -> None:
        self.create()
        self.design_and_accept()
        state = execute_round(self.case, "components/solver.py", self.producer("solver"))
        binding = next(item for item in state["events"] if item["file"].endswith("-execution.json"))
        path = self.case / binding["file"]
        event = json.loads(path.read_text())
        event["payload"]["output"] = {"verdict": "pass"}
        path.write_text(json.dumps(event), encoding="utf-8")
        self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), binding["sha256"])
        with self.assertRaisesRegex(ValueError, "event identity changed"):
            inspect_case(self.case)


if __name__ == "__main__":
    unittest.main()
