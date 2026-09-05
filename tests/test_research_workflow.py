from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verispiral import path_adapter
from verispiral.pipeline import PipelineError, file_digest, object_digest
from verispiral.research_workflow import prepare_workflow, execute_workflow


ROOT = Path(__file__).resolve().parents[1]
TRAP = {
    "node_count": 4,
    "edges": [[0, 1, 1], [1, 3, 9], [0, 2, 2], [2, 3, 1]],
}
ERRORS = (ValueError, PipelineError)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return path


class ConnectedResearchWorkflowTests(unittest.TestCase):
    """Public synthetic inputs exercise decisions, evidence, and stopping behavior."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.problem = self.base / "problem.md"
        self.problem.write_text(
            "# Public synthetic path problem\n\n"
            "Find the minimum integer edge-weight path from node 0 to node 3 "
            "in the explicitly supplied finite directed acyclic graph.\n",
            encoding="utf-8",
        )
        self.setup = write(self.base / "setup.json", copy.deepcopy(TRAP))

    def prepare(self, name: str = "proposal") -> Path:
        return prepare_workflow(self.problem, self.setup, self.base / name, ROOT)

    def decision(self, proposal: Path, **updates) -> Path:
        value = {
            "action": "accept",
            "proposal_sha256": file_digest(proposal),
            "selection": {
                "screen_verifier": "all_edges_certificate",
                "initial_algorithm": "greedy_edge",
            },
            "budget_edge_operations": 1000,
            "max_rounds": 3,
            "actor": "synthetic_fixture",
        }
        value.update(updates)
        return write(self.base / (proposal.parent.name + "-decision.json"), value)

    def execute(self, proposal: Path, **updates) -> dict:
        decision = self.decision(proposal, **updates)
        return read(execute_workflow(proposal, decision, self.base / "run", ROOT))

    def test_plain_document_without_typed_setup_pauses(self) -> None:
        proposal = prepare_workflow(self.problem, None, self.base / "proposal", ROOT)
        self.assertEqual(read(proposal)["status"], "needs_input")
        with self.assertRaises(ERRORS):
            self.execute(proposal)

    def test_unsupported_sparse_setup_pauses_before_execution(self) -> None:
        # The target is reachable, but this adapter requires every node reachable.
        write(self.setup, {"node_count": 3, "edges": [[0, 2, -1]]})
        proposal = self.prepare()
        self.assertEqual(read(proposal)["status"], "needs_input")
        with self.assertRaises(ERRORS):
            self.execute(proposal)

    def test_acceptance_binds_exact_proposal_bytes(self) -> None:
        proposal = self.prepare()
        decision = self.decision(proposal)
        proposal.write_text(proposal.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(ERRORS):
            execute_workflow(proposal, decision, self.base / "run", ROOT)

    def test_source_changes_invalidate_prior_proposal(self) -> None:
        proposal = self.prepare()
        decision = self.decision(proposal)
        self.problem.write_text("A different public synthetic research goal.\n", encoding="utf-8")
        with self.assertRaises(ERRORS):
            execute_workflow(proposal, decision, self.base / "run", ROOT)

    def test_setup_changes_invalidate_prior_proposal(self) -> None:
        proposal = self.prepare()
        decision = self.decision(proposal)
        changed = copy.deepcopy(TRAP)
        changed["edges"][0][2] = -8
        write(self.setup, changed)
        with self.assertRaises(ERRORS):
            execute_workflow(proposal, decision, self.base / "run", ROOT)

    def test_boolean_or_negative_budget_is_not_accepted_as_integer_budget(self) -> None:
        proposal = self.prepare()
        for budget in (True, -1, 3.5):
            with self.subTest(budget=budget), self.assertRaises(ERRORS):
                self.execute(proposal, budget_edge_operations=budget)

    def test_unknown_producer_and_verifier_are_rejected(self) -> None:
        proposal = self.prepare()
        selections = [
            {"screen_verifier": "unchecked", "initial_algorithm": "greedy_edge"},
            {"screen_verifier": "all_edges_certificate", "initial_algorithm": "undeclared"},
        ]
        for selection in selections:
            with self.subTest(selection=selection), self.assertRaises(ERRORS):
                self.execute(proposal, selection=selection)

    def test_external_problem_cannot_write_artifacts_into_public_repository(self) -> None:
        with tempfile.TemporaryDirectory(prefix="workflow-audit-", dir=ROOT) as public_output:
            with self.assertRaises(ERRORS):
                prepare_workflow(self.problem, self.setup, Path(public_output), ROOT)
            self.assertEqual(list(Path(public_output).iterdir()), [])

    def test_pending_template_does_not_authorize_solver_execution(self) -> None:
        proposal = self.prepare()
        with patch.object(path_adapter, "generate") as generate, self.assertRaises(ERRORS):
            execute_workflow(
                proposal, proposal.parent / "decision_template.json", self.base / "run", ROOT
            )
        generate.assert_not_called()

    def test_rejection_records_no_search_or_claim_acceptance(self) -> None:
        proposal = self.prepare()
        with patch.object(path_adapter, "generate") as generate:
            report = self.execute(proposal, action="reject")
        generate.assert_not_called()
        self.assertEqual(report["status"], "rejected_by_recorded_decision")
        self.assertEqual(report["budget_spent"], 0)
        self.assertEqual(report["rounds"], [])
        self.assertFalse(report["human_identity_authenticated"])

    def test_modified_adapter_proposal_cannot_be_self_resealed_and_accepted(self) -> None:
        proposal = self.prepare()
        content = read(proposal)
        content["adapter_proposal"]["setup"]["edges"][0][2] = -8
        write(proposal, content)
        # A new decision hash alone cannot replace the source-bound setup.
        with self.assertRaises(ERRORS):
            self.execute(proposal)

    def test_modified_implementation_fingerprint_invalidates_acceptance(self) -> None:
        proposal = self.prepare()
        content = read(proposal)
        content["implementation"]["path_reference.py"] = "0" * 64
        write(proposal, content)
        with self.assertRaises(ERRORS):
            self.execute(proposal)

    def test_solver_repair_uses_fresh_identity_and_rechecks_every_factor(self) -> None:
        report = self.execute(self.prepare())
        self.assertEqual(report["status"], "candidate_ready_for_human_acceptance")
        first, repaired = report["rounds"]
        self.assertEqual(
            first["diagnosis"]["supported_factors"],
            ["candidate_not_optimal", "certificate_invalid"],
        )
        self.assertEqual(first["repair"]["kind"], "candidate_replacement")
        self.assertNotEqual(
            first["candidate"]["content_sha256"], repaired["candidate"]["content_sha256"]
        )
        self.assertEqual(first["candidate"]["value"]["path"], [0, 1, 3])
        self.assertEqual(repaired["candidate"]["value"]["path"], [0, 2, 3])
        self.assertEqual(repaired["diagnosis"]["supported_factors"], [])
        for row in report["rounds"]:
            self.assertTrue(row["diagnosis"]["coverage_checked"])
            self.assertEqual(set(row["observations"]), set(path_adapter.FACTORS.values()))
            self.assertEqual(len(row["receipts"]), len(path_adapter.FACTORS))
            for receipt in row["receipts"]:
                self.assertEqual(receipt["candidate_sha256"], row["candidate"]["content_sha256"])
                self.assertEqual(receipt["specification_sha256"], report["specification_sha256"])
                body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
                self.assertEqual(receipt["receipt_sha256"], object_digest(body))
        self.assertFalse(report["scientific_claim_accepted"])
        self.assertEqual(report["human_acceptance"], "pending")

    def test_concurrent_faults_survive_first_positive_and_require_spec_revision(self) -> None:
        report = self.execute(
            self.prepare(),
            selection={"screen_verifier": "path_edges_only", "initial_algorithm": "greedy_edge"},
        )
        self.assertEqual(
            report["rounds"][0]["diagnosis"]["supported_factors"],
            ["candidate_not_optimal", "certificate_invalid", "screen_disagreement"],
        )
        self.assertTrue(report["rounds"][0]["diagnosis"]["coverage_checked"])
        self.assertEqual(report["rounds"][-1]["diagnosis"]["supported_factors"], [])
        self.assertEqual(report["status"], "awaiting_verifier_decision")
        self.assertEqual(report["specification"]["screen_verifier"], "path_edges_only")
        self.assertTrue((self.base / "run/revision_proposal.json").is_file())
        packet = read(self.base / "run/decision_packet.json")
        self.assertEqual(packet["all_observed_factors"],
                         ["candidate_not_optimal", "certificate_invalid", "screen_disagreement"])
        self.assertNotEqual(packet["next_action"], "review_candidate")

    def test_missing_certificate_does_not_trigger_algorithm_replacement(self) -> None:
        write(self.setup, {"node_count": 4,
                           "edges": [[0, 1, -2], [1, 3, 1], [0, 2, 5], [2, 3, -4]]})
        report = self.execute(self.prepare())
        self.assertEqual(report["status"], "candidate_ready_for_human_acceptance")
        first, repaired = report["rounds"]
        self.assertTrue(first["observations"]["path_optimal"])
        self.assertFalse(first["observations"]["certificate_valid"])
        self.assertNotIn("candidate_not_optimal", first["diagnosis"]["supported_factors"])
        self.assertEqual(first["repair"]["kind"], "witness_only")
        self.assertEqual(first["candidate"]["value"]["path"], repaired["candidate"]["value"]["path"])
        self.assertNotEqual(first["candidate"]["content_sha256"], repaired["candidate"]["content_sha256"])
        self.assertEqual(repaired["diagnosis"]["supported_factors"], [])

    def test_zero_budget_does_not_execute_candidate_producer(self) -> None:
        with patch.object(path_adapter, "generate") as generate:
            report = self.execute(self.prepare(), budget_edge_operations=0)
        generate.assert_not_called()
        self.assertEqual(report["status"], "budget_exhausted")
        self.assertEqual(report["rounds"], [])
        self.assertEqual(report["cost_ledger"], [])
        self.assertEqual(report["budget_spent"], 0)
        packet = read(self.base / "run/decision_packet.json")
        self.assertEqual(packet["unresolved_factors"], sorted(path_adapter.FACTORS))

    def test_partial_budget_leaves_unobserved_factors_explicit(self) -> None:
        report = self.execute(self.prepare(), budget_edge_operations=20)
        self.assertEqual(report["status"], "budget_exhausted")
        self.assertLessEqual(report["budget_spent"], 20)
        self.assertEqual(len(report["rounds"]), 1)
        diagnosis = report["rounds"][0]["diagnosis"]
        self.assertFalse(diagnosis["coverage_checked"])
        self.assertTrue(diagnosis["unresolved_factors"])
        self.assertFalse(report["scientific_claim_accepted"])

    def test_round_limit_retains_failed_candidate_without_unchecked_repair(self) -> None:
        report = self.execute(self.prepare(), max_rounds=1)
        self.assertEqual(report["status"], "max_rounds_exhausted")
        self.assertEqual(len(report["rounds"]), 1)
        self.assertTrue(report["rounds"][0]["diagnosis"]["supported_factors"])
        self.assertNotIn("repair", report["rounds"][0])
        self.assertNotIn("solution_repair", [entry["kind"] for entry in report["cost_ledger"]])

    def test_cost_ledger_reservations_reconcile_actual_work_and_remaining_budget(self) -> None:
        report = self.execute(self.prepare())
        remaining = report["budget_limit"]
        for entry in report["cost_ledger"]:
            self.assertLessEqual(entry["reservation"], remaining)
            self.assertGreaterEqual(entry["actual_cost"], 0)
            self.assertLessEqual(entry["actual_cost"], entry["reservation"])
            remaining -= entry["actual_cost"]
            self.assertEqual(entry["remaining"], remaining)
        self.assertEqual(report["remaining_budget"], remaining)
        self.assertEqual(report["budget_spent"], sum(entry["actual_cost"] for entry in report["cost_ledger"]))

    def test_over_reservation_observation_is_not_published(self) -> None:
        proposal = self.prepare()
        real_observe = path_adapter.observe

        def exceeds_reservation(*args):
            result = real_observe(*args)
            result["cost"] = 1_000_001
            return result

        with patch.object(path_adapter, "observe", side_effect=exceeds_reservation):
            with self.assertRaisesRegex(ValueError, "exceeded reservation"):
                self.execute(proposal)
        self.assertFalse((self.base / "run/workflow_report.json").exists())
        self.assertFalse((self.base / "run/decision_packet.json").exists())

    def initial_weak_run(self) -> tuple[Path, dict]:
        parent = self.execute(
            self.prepare(),
            selection={"screen_verifier": "path_edges_only", "initial_algorithm": "greedy_edge"},
        )
        return self.base / "run/revision_proposal.json", parent

    def test_accepted_successor_retains_lineage_but_discards_prior_evidence(self) -> None:
        proposal, parent = self.initial_weak_run()
        original = (self.base / "run/workflow_report.json").read_bytes()
        successor_path = execute_workflow(
            proposal, self.decision(proposal), self.base / "successor", ROOT
        )
        successor = read(successor_path)
        self.assertEqual(successor["status"], "candidate_ready_for_human_acceptance")
        self.assertEqual(successor["specification"]["version"], 2)
        self.assertEqual(parent["specification"]["version"], 1)
        self.assertEqual(parent["specification"]["target_lineage"], successor["specification"]["target_lineage"])
        self.assertNotEqual(parent["specification_sha256"], successor["specification_sha256"])
        self.assertFalse(successor["prior_evidence_applicable"])
        self.assertEqual(successor["retained_candidate_status"], "rechecked_under_successor")
        self.assertEqual(len(successor["rounds"]), 1)
        self.assertEqual(successor["rounds"][0]["candidate"]["origin"], "retained_requires_recheck")
        self.assertEqual(successor["rounds"][0]["candidate"]["content_sha256"],
                         parent["rounds"][-1]["candidate"]["content_sha256"])
        self.assertEqual(len(successor["rounds"][0]["receipts"]), len(path_adapter.FACTORS))
        self.assertEqual(original, (self.base / "run/workflow_report.json").read_bytes())

    def test_successor_without_budget_keeps_retained_candidate_unverified(self) -> None:
        proposal, parent = self.initial_weak_run()
        successor = read(execute_workflow(
            proposal, self.decision(proposal, budget_edge_operations=0), self.base / "successor", ROOT
        ))
        self.assertEqual(successor["status"], "budget_exhausted")
        self.assertEqual(successor["retained_candidate_status"], "requires_recheck")
        self.assertFalse(successor["prior_evidence_applicable"])
        self.assertFalse(successor["rounds"][0]["diagnosis"]["coverage_checked"])
        self.assertEqual(successor["rounds"][0]["receipts"], [])

    def test_successor_cannot_reaccept_weak_screen(self) -> None:
        proposal, _ = self.initial_weak_run()
        decision = self.decision(
            proposal,
            selection={"screen_verifier": "feasibility_only", "initial_algorithm": "greedy_edge"},
        )
        with self.assertRaises(ERRORS):
            execute_workflow(proposal, decision, self.base / "successor", ROOT)

    def test_parent_artifact_drift_invalidates_successor(self) -> None:
        proposal, _ = self.initial_weak_run()
        decision = self.decision(proposal)
        parent_path = self.base / "run/workflow_report.json"
        parent_path.write_text(parent_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(ERRORS):
            execute_workflow(proposal, decision, self.base / "successor", ROOT)

    def test_repeated_execution_is_deterministic(self) -> None:
        proposal = self.prepare()
        decision = self.decision(proposal)
        first = execute_workflow(proposal, decision, self.base / "first", ROOT)
        second = execute_workflow(proposal, decision, self.base / "second", ROOT)
        self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
