from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from verispiral.cli import main
from verispiral.pipeline import object_digest, read_json, repository_root
from verispiral.research_workflow import run_workflow_demo


def relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


class WorkflowGoldenTests(unittest.TestCase):
    def test_connected_workflow_is_byte_exact_and_retains_review_boundary(self):
        root = repository_root()
        expected = root / "examples/expected/workflow"
        with tempfile.TemporaryDirectory() as temporary:
            actual = Path(temporary) / "actual"
            summary_path = run_workflow_demo(actual, root)
            self.assertTrue(relative_files(expected), "tracked workflow reference output is missing")
            self.assertEqual(relative_files(actual), relative_files(expected))
            for relative in relative_files(expected):
                self.assertEqual((actual / relative).read_bytes(), (expected / relative).read_bytes(),
                                 f"workflow golden artifact is stale: {relative}")
            summary = read_json(summary_path)
            self.assertEqual(summary["initial_status"], "awaiting_verifier_decision")
            self.assertEqual(summary["first_round_factors"],
                             ["candidate_not_optimal", "certificate_invalid", "screen_disagreement"])
            self.assertEqual(summary["successor_status"], "candidate_ready_for_human_acceptance")
            self.assertTrue(summary["target_lineage_preserved"])
            self.assertEqual(summary["successor_recheck"], "rechecked_under_successor")
            self.assertFalse(summary["scientific_claim_accepted"])
            initial = read_json(actual / "initial_run/workflow_report.json")
            successor = read_json(actual / "successor_run/workflow_report.json")
            for report in (initial, successor):
                self.assertEqual(report["kind"], "connected_research_workflow")
                self.assertEqual(report["schema_version"], "1.0")
                self.assertEqual(report["specification_sha256"], object_digest(report["specification"]))
                self.assertEqual(report["human_acceptance"], "pending")
                self.assertFalse(report["human_identity_authenticated"])
                self.assertLessEqual(report["budget_spent"], report["budget_limit"])
            self.assertEqual(initial["specification"]["target_lineage"],
                             successor["specification"]["target_lineage"])
            self.assertNotEqual(initial["specification_sha256"], successor["specification_sha256"])
            self.assertFalse(successor["prior_evidence_applicable"])

    def test_cli_prepare_reports_missing_setup_and_leaves_decision_pending(self):
        root = repository_root()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "proposal"
            console = StringIO()
            with redirect_stdout(console):
                code = main(["workflow-prepare", "--problem", str(root / "examples/workflow/problem.md"),
                             "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertIn("needs_input", console.getvalue())
            self.assertEqual(read_json(output / "decision_template.json")["action"], "pending")
            error = StringIO()
            with redirect_stderr(error):
                code = main(["workflow-run", "--proposal", str(output / "proposal.json"),
                             "--decision", str(output / "decision_template.json"),
                             "--output", str(Path(temporary) / "run")])
            self.assertEqual(code, 1)
            self.assertIn("proposal needs input", error.getvalue())
            self.assertFalse((Path(temporary) / "run/workflow_report.json").exists())

    def test_cli_demo_prints_summary_and_run_prints_cost_and_factors(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "demo"
            console = StringIO()
            with redirect_stdout(console):
                code = main(["workflow-demo", "--output", str(output)])
            self.assertEqual(code, 0)
            self.assertIn("Concurrent factors:", console.getvalue())
            self.assertIn("synthetic specification decisions", console.getvalue())
            console = StringIO()
            with redirect_stdout(console):
                code = main(["workflow-run", "--proposal", str(output / "proposal/proposal.json"),
                             "--decision", str(output / "first_decision.json"),
                             "--output", str(Path(temporary) / "replayed")])
            self.assertEqual(code, 0)
            self.assertIn("awaiting_verifier_decision", console.getvalue())
            self.assertIn("edge_operations=", console.getvalue())
            self.assertIn("candidate_not_optimal", console.getvalue())


if __name__ == "__main__":
    unittest.main()
