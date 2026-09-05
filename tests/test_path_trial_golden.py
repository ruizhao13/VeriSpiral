from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verispiral.cli import main
from verispiral.path_workflow import run_path_trial
from verispiral import path_workflow
from verispiral.pipeline import file_digest, repository_root


ROOT = repository_root()
EXPECTED = ROOT / "examples" / "expected" / "path-trial"


class PathTrialGoldenTests(unittest.TestCase):
    def test_report_and_manifest_are_byte_exact_and_bind_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "path-trial"
            report_path = run_path_trial(output, ROOT)
            self.assertEqual(report_path, output / "path_trial_report.json")
            filenames = ["manifest.json", "path_trial_report.json"]
            self.assertEqual(sorted(path.name for path in output.iterdir()), filenames)
            self.assertEqual(sorted(path.name for path in EXPECTED.iterdir()), filenames)
            for filename in filenames:
                self.assertEqual(
                    (output / filename).read_bytes(),
                    (EXPECTED / filename).read_bytes(),
                    f"golden artifact is stale: {filename}",
                )
            report = json.loads(report_path.read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_sha256"], file_digest(report_path))
        plan_digest = file_digest(ROOT / "examples" / "path" / "experiment_plan.json")
        self.assertEqual(report["plan_sha256"], plan_digest)
        self.assertEqual(manifest["plan_sha256"], plan_digest)
        repair_digest = file_digest(ROOT / "examples" / "path" / "witness_repair_plan.json")
        self.assertEqual(report["witness_repair"]["plan_sha256"], repair_digest)
        self.assertEqual(manifest["repair_plan_sha256"], repair_digest)
        self.assertEqual(manifest["source_sha256"], {
            name: file_digest(ROOT / "src" / "verispiral" / name)
            for name in ("path_workflow.py", "path_reference.py")
        })
        self.assertEqual(report["artifact_type"], "public_path_workflow_trial")
        self.assertIn("development evidence only", report["scope"])
        self.assertEqual(manifest["human_acceptance"], "not_requested_development_trial")
        self.assertFalse(manifest["revision_applied"])

    def test_audited_verifier_cannot_supply_its_own_ground_truth_cost(self) -> None:
        plan = json.loads((ROOT / "examples" / "path" / "experiment_plan.json").read_text())
        graph = path_workflow.public_graphs(plan)[0]
        original_check = path_workflow.check

        def misreport(*args, **kwargs):
            return {**original_check(*args, **kwargs), "cost": -999}

        with patch.object(path_workflow, "check", side_effect=misreport):
            report = path_workflow.evaluate_graph(graph, plan)
        for row in report["evaluations"]:
            self.assertEqual(row["result"]["cost"], -999)
            self.assertEqual(row["independently_scored_cost"], 10 if row["solver"] == "greedy_edge" else 3)
            self.assertEqual(row["regret"], 7 if row["solver"] == "greedy_edge" else 0)

    def test_followup_rejects_changed_baseline_instead_of_silently_reusing_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            altered_graph = {"id": "different", "group": "development", "n": 2,
                             "edges": [(0, 1, 1)]}
            with patch.object(path_workflow, "public_graphs", return_value=[altered_graph]):
                with self.assertRaisesRegex(ValueError, "baseline changed"):
                    run_path_trial(Path(temporary), ROOT)
            self.assertFalse((Path(temporary) / "path_trial_report.json").exists())

    def test_command_writes_report_and_displays_verifier_summary_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "cli-output"
            displayed = io.StringIO()
            with contextlib.redirect_stdout(displayed):
                result = main(["path-trial", "--output", str(output)])
            self.assertEqual(result, 0)
            report_path = output / "path_trial_report.json"
            report = json.loads(report_path.read_text())
            text = displayed.getvalue()
            self.assertIn(f"Scope: {report['scope']}", text)
            self.assertIn(f"Report: {report_path}", text)
            self.assertIn("Witness repair: paths_preserved=26", text)
            for verifier, summary in report["verifier_summary"].items():
                self.assertIn(
                    f"{verifier}: accepted={summary['accepted_count']}/"
                    f"{summary['candidate_evaluations']}", text,
                )
                self.assertIn(f"false_accept={summary['false_accept_count']}", text)
                self.assertIn(f"false_reject={summary['false_reject_count']}", text)
                self.assertIn(f"optimal_unverified={summary['unverified_optimal_count']}", text)


if __name__ == "__main__":
    unittest.main()
