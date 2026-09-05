from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from verispiral import diagnosis_demo as demo
from verispiral.diagnosis import choose_diagnostic_action, choose_factor_diagnostic_action
from verispiral.pipeline import file_digest


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "examples" / "expected" / "diagnosis"
# Independent behavioral expectations, not derived from the production signatures.
EXPECTED_FAILURES = {
    "case_01": (("algorithm_dominated",), ("search_has_support",)),
    "case_02": (("verifier_disagreement",), ("cheap_matches_exact",)),
    "case_03": (("setup_mean_disagreement",), ("setup_transfers",)),
    "case_04": (("goal_rank_disagreement",), ("metric_rank_stable",)),
    "case_05": (("implementation_disagreement",), ("implementation_match",)),
    "case_06": (("replicate_disagreement",), ("repeat_stable",)),
    "case_07": (("fresh_mean_disagreement",), ("fresh_suite_transfer",)),
    "case_08": ((), ()),
    "case_09": (("implementation_disagreement", "replicate_disagreement"),
                ("implementation_match", "repeat_stable")),
    "case_10": (("fresh_mean_disagreement", "verifier_disagreement"),
                ("cheap_matches_exact", "fresh_suite_transfer")),
}
EXPECTED_COSTS = {
    "implementation_match": 1, "cheap_matches_exact": 1, "repeat_stable": 2,
    "metric_rank_stable": 2, "search_has_support": 3,
    "fresh_suite_transfer": 4, "setup_transfers": 5,
}


class DiagnosisAdapterTests(unittest.TestCase):
    def test_public_tables_have_the_stated_individual_and_simultaneous_failed_checks(self) -> None:
        cases = demo.public_cases()
        self.assertEqual({case_id for case_id, _, _ in cases}, set(EXPECTED_FAILURES))
        self.assertEqual(demo.TEST_COSTS, EXPECTED_COSTS)
        for case_id, labels, case in cases:
            with self.subTest(case_id=case_id):
                expected_factors, failed_tests = EXPECTED_FAILURES[case_id]
                self.assertEqual(labels, expected_factors)
                observed = {test: demo.observe(case, test)["passed"] for test in EXPECTED_COSTS}
                expected = {test: test not in failed_tests for test in EXPECTED_COSTS}
                self.assertEqual(observed, expected)
                result = demo.diagnose_case(case)
                self.assertEqual(result["decision"]["status"], "diagnosis_supported")
                self.assertEqual(result["decision"]["supported_factors"], list(expected_factors))
                self.assertTrue(result["decision"]["coverage_checked"])
                self.assertEqual(result["decision"]["unresolved_factors"], [])
                self.assertEqual(result["budget_spent"], 18)
                self.assertFalse(result["revision_applied"])
                self.assertFalse(result["scientific_claim_accepted"])

    def test_paid_observation_values_are_computed_from_the_table(self) -> None:
        cases = {case_id: case for case_id, _, case in demo.public_cases()}
        self.assertEqual(demo.observe(cases["case_01"], "search_has_support"), {
            "passed": False, "unanimously_dominated": True,
        })
        expected_values = {
            ("case_02", "cheap_matches_exact"): ["0", "3"],
            ("case_03", "setup_transfers"): ["0", "8"],
            ("case_04", "metric_rank_stable"): ["True", "False"],
            ("case_05", "implementation_match"): ["1", "2"],
            ("case_06", "repeat_stable"): ["2", "3"],
            ("case_07", "fresh_suite_transfer"): ["0", "8"],
        }
        for (case_id, test), values in expected_values.items():
            with self.subTest(case_id=case_id, test=test):
                self.assertEqual(demo.observe(cases[case_id], test), {
                    "passed": False, "compared_values": values,
                })

    def test_budget_accounting_for_every_case_and_partial_budget(self) -> None:
        for case_id, _, case in demo.public_cases():
            for budget in range(19):
                with self.subTest(case_id=case_id, budget=budget):
                    result = demo.diagnose_case(case, budget)
                    remaining = budget
                    observed = {}
                    for row in result["trace"]:
                        test = row["test"]
                        self.assertNotIn(test, observed)
                        self.assertEqual(row["selection"], choose_factor_diagnostic_action(
                            demo.FACTORS, EXPECTED_COSTS, observed, remaining
                        ))
                        self.assertEqual(row["result"], demo.observe(case, test))
                        self.assertEqual(row["selection"]["cost"], EXPECTED_COSTS[test])
                        remaining -= EXPECTED_COSTS[test]
                        self.assertEqual(row["remaining_budget"], remaining)
                        self.assertGreaterEqual(remaining, 0)
                        observed[test] = row["result"]["passed"]
                    self.assertEqual(result["budget_spent"], budget - remaining)
                    self.assertLessEqual(result["budget_spent"], budget)
                    self.assertEqual(result["decision"], choose_factor_diagnostic_action(
                        demo.FACTORS, EXPECTED_COSTS, observed, remaining
                    ))

    def test_healthy_case_requires_all_checks_and_all_eighteen_cost_units(self) -> None:
        result = demo.diagnose_case(demo.FiniteCase())
        self.assertEqual([row["test"] for row in result["trace"]], [
            "cheap_matches_exact", "implementation_match", "metric_rank_stable",
            "repeat_stable", "search_has_support", "fresh_suite_transfer", "setup_transfers",
        ])
        self.assertTrue(all(row["result"]["passed"] for row in result["trace"]))
        self.assertEqual(result["budget_spent"], 18)
        self.assertEqual(result["next_action_proposals"], ["report_scoped_checks_only"])
        limited = demo.diagnose_case(demo.FiniteCase(), budget=17)
        self.assertEqual(limited["decision"]["status"], "budget_exhausted")
        self.assertEqual(limited["decision"]["unresolved_factors"], ["setup_mean_disagreement"])
        self.assertEqual(limited["decision"]["pending_tests"], ["setup_transfers"])
        self.assertFalse(limited["decision"]["coverage_checked"])
        self.assertEqual(limited["budget_spent"], 13)

    def test_budget_exhaustion_preserves_ambiguity_and_does_not_authorize_revision(self) -> None:
        result = demo.diagnose_case(demo.public_cases()[0][2], budget=1)
        self.assertEqual(result["decision"]["status"], "budget_exhausted")
        self.assertEqual(result["budget_spent"], 1)
        self.assertEqual(result["decision"]["supported_factors"], [])
        self.assertEqual(result["decision"]["unresolved_factors"], [
            "algorithm_dominated", "fresh_mean_disagreement", "goal_rank_disagreement",
            "implementation_disagreement", "replicate_disagreement", "setup_mean_disagreement",
        ])
        self.assertEqual(result["next_action_proposals"], ["collect_evidence_for_pending_checks"])
        self.assertFalse(result["revision_applied"])

    def test_scoring_labels_do_not_reach_diagnosis_or_change_decisions(self) -> None:
        self.assertEqual(list(inspect.signature(demo.diagnose_case).parameters), ["case", "budget"])
        self.assertEqual(list(inspect.signature(demo.observe).parameters), ["case", "test"])
        cases = demo.public_cases()
        relabeled = [(case_id, ("untrusted_scoring_label",), case) for case_id, _, case in cases]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            ordinary = json.loads(demo.run_diagnosis_demo(base / "ordinary").read_text())
            with patch.object(demo, "public_cases", return_value=relabeled), patch.object(
                demo, "choose_factor_diagnostic_action", wraps=choose_factor_diagnostic_action
            ) as controller:
                changed = json.loads(demo.run_diagnosis_demo(base / "relabeled").read_text())
            for call in controller.call_args_list:
                self.assertEqual(len(call.args), 4)
                self.assertNotIn("untrusted_scoring_label", repr(call))
        for original, changed_case in zip(ordinary["diagnostic_cases"], changed["diagnostic_cases"]):
            self.assertTrue(original.pop("matches_planted_factors"))
            self.assertFalse(changed_case.pop("matches_planted_factors"))
            original.pop("planted_factors_for_scoring_only")
            self.assertEqual(changed_case.pop("planted_factors_for_scoring_only"), ["untrusted_scoring_label"])
            self.assertEqual(original, changed_case)

    def test_original_early_singleton_counterexample_now_returns_both_indicators(self) -> None:
        case = replace(demo.FiniteCase(), reported_offset=-1, replicate_offsets=(0, 1))
        all_observations = {test: demo.observe(case, test)["passed"] for test in EXPECTED_COSTS}
        self.assertEqual(sorted(test for test, passed in all_observations.items() if not passed),
                         ["implementation_match", "repeat_stable"])
        # The legacy model makes no invented compound prediction and reports its mismatch.
        observations = {}
        remaining = 18
        while True:
            decision = choose_diagnostic_action(demo.HYPOTHESES, EXPECTED_COSTS, observations, remaining)
            if decision["status"] != "test_proposed":
                break
            test = decision["proposed_test"]
            observations[test] = demo.observe(case, test)["passed"]
            remaining -= decision["cost"]
        self.assertEqual(decision["status"], "model_mismatch")
        self.assertIn("repeat_stable", observations)
        result = demo.diagnose_case(case)
        self.assertEqual(result["decision"]["supported_factors"],
                         ["implementation_disagreement", "replicate_disagreement"])
        self.assertTrue(result["decision"]["coverage_checked"])
        self.assertEqual(result["budget_spent"], 18)
        self.assertEqual(result["next_action_proposals"], [
            "repair_and_recompute_implementation", "collect_replicates_and_quantify_uncertainty",
        ])
        self.assertFalse(result["scientific_claim_accepted"])
        # Seeing the first failure cannot hide the pending second check under a small budget.
        partial = demo.diagnose_case(case, budget=2)
        self.assertEqual(partial["decision"]["status"], "budget_exhausted")
        self.assertEqual(partial["decision"]["supported_factors"], ["implementation_disagreement"])
        self.assertIn("replicate_disagreement", partial["decision"]["unresolved_factors"])
        self.assertFalse(partial["decision"]["coverage_checked"])

    def test_unmodeled_mean_preserving_variation_is_invisible_to_these_checks(self) -> None:
        case = replace(demo.FiniteCase(), setup=(1, 3, 1, 3))
        self.assertNotEqual(case.setup, case.reference)
        self.assertTrue(all(demo.observe(case, test)["passed"] for test in EXPECTED_COSTS))
        result = demo.diagnose_case(case)
        self.assertEqual(result["decision"]["supported_factors"], [])
        self.assertTrue(result["decision"]["coverage_checked"])
        self.assertEqual(result["next_action_proposals"], ["report_scoped_checks_only"])
        self.assertFalse(result["scientific_claim_accepted"])

    def test_verifier_comparison_exposes_the_prefix_false_promotion(self) -> None:
        comparison = demo.verifier_comparison()
        self.assertEqual(comparison["candidate_losses"], {
            "stable": (2, 2, 2, 2), "tail_failure": (0, 0, 0, 12), "weak": (8, 8, 8, 8),
        })
        self.assertEqual(comparison["reference_scores"], {"stable": "2", "tail_failure": "3", "weak": "8"})
        self.assertEqual(comparison["acceptance_threshold"], 2)
        prefix, exact = comparison["rows"]
        self.assertEqual(prefix["verifier"], "prefix_screen")
        self.assertEqual(prefix["scores"], {"stable": "2", "tail_failure": "0", "weak": "8"})
        self.assertEqual(prefix["selected_candidate"], "tail_failure")
        self.assertEqual(prefix["false_promotions"], ["tail_failure"])
        self.assertEqual(prefix["reference_regret_of_selected"], "1")
        self.assertEqual(exact["verifier"], "exact_enumeration")
        self.assertEqual(exact["scores"], comparison["reference_scores"])
        self.assertEqual(exact["selected_candidate"], "stable")
        self.assertEqual(exact["false_promotions"], [])
        self.assertEqual(exact["reference_regret_of_selected"], "0")
        for row, build, per_call, amortized in ((prefix, 1, 2, "201/100"), (exact, 6, 4, "203/50")):
            self.assertEqual(row["false_rejections"], [])
            self.assertEqual(row["build_cost_units"], build)
            self.assertEqual(row["call_cost_units"], per_call)
            self.assertEqual(row["planned_calls"], 100)
            self.assertEqual(row["amortized_cost_units"], amortized)
            self.assertEqual(Fraction(amortized), Fraction(build, 100) + per_call)
        self.assertEqual(comparison["cost_basis"], "declared illustrative units, not measured runtime")
        self.assertIn("no verifier synthesis executed", comparison["construction_status"])


class DiagnosisGoldenTests(unittest.TestCase):
    def test_report_and_manifest_are_byte_exact_and_limit_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "diagnosis"
            report_path = demo.run_diagnosis_demo(output)
            for filename in ("diagnosis_report.json", "manifest.json"):
                self.assertEqual((output / filename).read_bytes(), (EXPECTED / filename).read_bytes(), filename)
            report = json.loads(report_path.read_text())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["artifacts"], {"diagnosis_report.json": file_digest(report_path)})
        self.assertEqual(report["scope"], "public finite loss tables and separately observable failed-check indicators")
        limitations = " ".join(report["limitations"])
        self.assertIn("Not real-world validation, causal identification", limitations)
        self.assertIn("not their causes or interactions", limitations)
        self.assertIn("mean-preserving faults invisible", limitations)
        self.assertIn("no hidden or independent final holdout", limitations)
        self.assertFalse(manifest["scientific_claim_accepted"])
        self.assertEqual(manifest["sources"], {
            name: file_digest(ROOT / "src" / "verispiral" / name)
            for name in ("diagnosis.py", "diagnosis_demo.py")
        })


if __name__ == "__main__":
    unittest.main()
