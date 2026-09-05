from __future__ import annotations

import copy
import inspect
import itertools
import unittest
from fractions import Fraction

from verispiral.diagnosis import choose_diagnostic_action, choose_factor_diagnostic_action
from verispiral.pipeline import PipelineError


class DiagnosticControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hypotheses = {
            "algorithm": {"control": False, "audit": False, "repeat": False},
            "verifier": {"control": False, "audit": True, "repeat": False},
            "setup": {"control": True, "audit": False, "repeat": False},
            "noise": {"control": True, "audit": True, "repeat": True},
        }
        self.tests = {"control": 2, "audit": 1, "repeat": 1}

    def choose(self, observations=None, budget=10):
        return choose_diagnostic_action(
            self.hypotheses, self.tests, observations or {}, budget
        )

    def assertTerminal(self, result, status, survivors):
        self.assertEqual(result["status"], status)
        self.assertEqual(result["remaining_hypotheses"], survivors)
        self.assertIsNone(result["proposed_test"])
        self.assertEqual(result["information_gain"], "0")
        self.assertEqual(result["cost"], 0)
        self.assertEqual(result["coverage_checked"], not result["pending_tests"])

    def test_cost_normalized_selection_and_exact_score(self) -> None:
        result = self.choose()
        self.assertEqual(result["status"], "test_proposed")
        self.assertEqual(result["proposed_test"], "audit")
        self.assertEqual(result["information_gain"], "2")
        self.assertEqual(result["cost"], 1)
        self.tests["audit"] = 3
        result = self.choose()
        self.assertEqual(result["proposed_test"], "repeat")
        self.assertEqual(Fraction(result["information_gain"]), Fraction(3, 2))

    def test_observations_change_the_next_check(self) -> None:
        result = self.choose({"audit": False})
        self.assertEqual(result["remaining_hypotheses"], ["algorithm", "setup"])
        self.assertEqual(result["proposed_test"], "control")
        self.assertEqual(result["information_gain"], "1/2")
        pending = self.choose({"audit": False, "control": True})
        self.assertEqual(pending["remaining_hypotheses"], ["setup"])
        self.assertEqual(pending["proposed_test"], "repeat")
        self.assertEqual(pending["information_gain"], "0")
        self.assertFalse(pending["coverage_checked"])
        self.assertTerminal(
            self.choose({"audit": False, "control": True, "repeat": False}),
            "diagnosis_supported", ["setup"],
        )

    def test_score_ties_prefer_lower_cost_then_name(self) -> None:
        self.tests = {"zeta": 1, "beta": 1, "balanced": 4}
        # Six-versus-two at cost 3 and four-versus-four at cost 4 both score 1.
        self.tests["zeta"] = self.tests["beta"] = 3
        self.hypotheses = {
            f"h{index}": {
                "balanced": index < 4, "zeta": index < 2, "beta": index < 2,
            }
            for index in range(8)
        }
        self.assertEqual(self.choose()["proposed_test"], "beta")
        self.assertEqual(self.choose()["information_gain"], "1")

    def test_affordability_is_applied_before_ranking(self) -> None:
        self.tests = {"control": 2, "audit": 3, "repeat": 4}
        result = self.choose(budget=2)
        self.assertEqual(result["proposed_test"], "control")
        self.assertEqual(result["cost"], 2)
        self.assertTerminal(self.choose(budget=1), "budget_exhausted", sorted(self.hypotheses))
        self.assertTerminal(self.choose(budget=0), "budget_exhausted", sorted(self.hypotheses))

    def test_singleton_requires_all_coverage_checks_and_budget(self) -> None:
        partial = self.choose({"repeat": True}, budget=0)
        self.assertTerminal(partial, "budget_exhausted", ["noise"])
        self.assertEqual(partial["pending_tests"], ["audit", "control"])
        self.assertEqual(self.choose({"repeat": True})["proposed_test"], "audit")
        hypotheses = {"only": {"t": True}}
        self.assertTerminal(choose_diagnostic_action(hypotheses, {"t": 1}, {}, 0),
                            "budget_exhausted", ["only"])
        self.assertEqual(choose_diagnostic_action(hypotheses, {"t": 1}, {}, 1)["proposed_test"], "t")
        complete = choose_diagnostic_action(hypotheses, {"t": 1}, {"t": True}, 0)
        self.assertTerminal(complete, "diagnosis_supported", ["only"])
        self.assertTrue(complete["coverage_checked"])

    def test_zero_information_checks_can_disconfirm_the_only_survivor(self) -> None:
        hypotheses = {"only": {"zeta": True, "alpha": True, "costly": True}}
        tests = {"costly": 3, "zeta": 1, "alpha": 1}
        first = choose_diagnostic_action(hypotheses, tests, {}, 1)
        self.assertEqual(first["proposed_test"], "alpha")
        self.assertEqual(first["information_gain"], "0")
        second = choose_diagnostic_action(hypotheses, tests, {"alpha": True}, 1)
        self.assertEqual(second["proposed_test"], "zeta")
        mismatch = choose_diagnostic_action(hypotheses, tests, {"alpha": True, "zeta": False}, 0)
        self.assertTerminal(mismatch, "model_mismatch", [])
        self.assertFalse(mismatch["coverage_checked"])

    def test_unaffordable_information_does_not_block_affordable_coverage(self) -> None:
        hypotheses = {"a": {"split": True, "coverage": True},
                      "b": {"split": False, "coverage": True}}
        result = choose_diagnostic_action(hypotheses, {"split": 2, "coverage": 1}, {}, 1)
        self.assertEqual(result["proposed_test"], "coverage")
        self.assertEqual(result["information_gain"], "0")

    def test_explicit_joint_signature_supports_multiple_failure_outcomes(self) -> None:
        hypotheses = {"a": {"x": False, "y": True}, "b": {"x": True, "y": False},
                      "a_and_b": {"x": False, "y": False}}
        tests = {"x": 1, "y": 1}
        partial = choose_diagnostic_action(hypotheses, tests, {"x": False}, 1)
        self.assertEqual(partial["remaining_hypotheses"], ["a", "a_and_b"])
        self.assertEqual(partial["proposed_test"], "y")
        self.assertTerminal(choose_diagnostic_action(hypotheses, tests, {"x": False, "y": False}, 0),
                            "diagnosis_supported", ["a_and_b"])

    def test_conflicting_observations_return_model_mismatch(self) -> None:
        self.assertTerminal(
            self.choose({"repeat": True, "audit": False}), "model_mismatch", []
        )

    def test_identical_signatures_require_coverage_then_remain_inconclusive(self) -> None:
        hypotheses = {"implementation": {"t": True}, "goal": {"t": True}}
        self.assertEqual(choose_diagnostic_action(hypotheses, {"t": 1}, {}, 5)["proposed_test"], "t")
        self.assertTerminal(choose_diagnostic_action(hypotheses, {"t": 1}, {}, 0),
                            "budget_exhausted", ["goal", "implementation"])
        for budget in (0, 5):
            result = choose_diagnostic_action(hypotheses, {"t": 1}, {"t": True}, budget)
            self.assertTerminal(result, "inconclusive", ["goal", "implementation"])
            self.assertTrue(result["coverage_checked"])

    def test_order_invariance_and_no_input_mutation(self) -> None:
        observations = {"audit": True}
        before = copy.deepcopy((self.hypotheses, self.tests, observations))
        expected = self.choose(observations)
        for hypothesis_order in itertools.permutations(self.hypotheses):
            for test_order in itertools.permutations(self.tests):
                hypotheses = {
                    h: {t: self.hypotheses[h][t] for t in test_order}
                    for h in hypothesis_order
                }
                tests = {t: self.tests[t] for t in test_order}
                self.assertEqual(
                    choose_diagnostic_action(hypotheses, tests, observations, 10), expected
                )
        self.assertEqual((self.hypotheses, self.tests, observations), before)

    def test_controller_has_no_truth_argument_and_cannot_use_cause_names(self) -> None:
        self.assertEqual(
            list(inspect.signature(choose_diagnostic_action).parameters),
            ["hypotheses", "tests", "observations", "remaining_budget"],
        )
        result = self.choose({"audit": False})
        opaque = {f"opaque-{i}": predictions for i, predictions in enumerate(self.hypotheses.values())}
        renamed = choose_diagnostic_action(opaque, self.tests, {"audit": False}, 10)
        for field in ("status", "proposed_test", "information_gain", "cost"):
            self.assertEqual(renamed[field], result[field])
        with self.assertRaises(TypeError):
            choose_diagnostic_action(self.hypotheses, self.tests, {}, 10, ground_truth="setup")

    def test_invalid_inputs_raise_pipeline_error(self) -> None:
        cases = [
            ({}, {"t": 1}, {}, 1),
            ({"h": {}}, {}, {}, 1),
            ([], {"t": 1}, {}, 1),
            ({"h": {"t": True}}, [], {}, 1),
            ({"h": {"t": True}}, {"t": 1}, [], 1),
            ({"h": []}, {"t": 1}, {}, 1),
            ({"h": {"t": True}}, {"t": 1}, {"other": True}, 1),
            ({"h": {"other": True}}, {"t": 1}, {}, 1),
            ({"h": {"t": True, "extra": False}}, {"t": 1}, {}, 1),
            ({"h": {"t": True}, "missing": {}}, {"t": 1}, {}, 1),
            ({"": {"t": True}}, {"t": 1}, {}, 1),
            ({1: {"t": True}}, {"t": 1}, {}, 1),
            ({"h": {"": True}}, {"": 1}, {}, 1),
            ({"h": {1: True}}, {1: 1}, {}, 1),
        ]
        for invalid in (0, 1, "true", None, [], {}):
            cases.append(({"h": {"t": invalid}}, {"t": 1}, {}, 1))
            cases.append(({"h": {"t": True}}, {"t": 1}, {"t": invalid}, 1))
        for invalid in (True, False, -1, 0, 1.0, "1", None):
            cases.append(({"h": {"t": True}}, {"t": invalid}, {}, 1))
        for invalid in (True, False, -1, 1.0, "1", None):
            cases.append(({"h": {"t": True}}, {"t": 1}, {}, invalid))
        for case in cases:
            with self.subTest(case=case), self.assertRaises(PipelineError):
                choose_diagnostic_action(*case)


class FactorDiagnosticControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factors = {"reported_value_disagrees": "implementation", "replicates_disagree": "repeat"}
        self.tests = {"implementation": 1, "repeat": 2}

    def choose(self, observations=None, budget=3):
        return choose_factor_diagnostic_action(self.factors, self.tests, observations or {}, budget)

    def test_two_failed_checks_remain_supported_together(self) -> None:
        initial = self.choose()
        self.assertEqual(initial["proposed_test"], "implementation")
        self.assertEqual(initial["supported_factors"], [])
        partial = self.choose({"implementation": False}, budget=2)
        self.assertEqual(partial["status"], "test_proposed")
        self.assertEqual(partial["supported_factors"], ["reported_value_disagrees"])
        self.assertEqual(partial["unresolved_factors"], ["replicates_disagree"])
        self.assertEqual(partial["proposed_test"], "repeat")
        complete = self.choose({"implementation": False, "repeat": False}, budget=0)
        self.assertEqual(complete["status"], "diagnosis_supported")
        self.assertEqual(complete["supported_factors"], ["replicates_disagree", "reported_value_disagrees"])
        self.assertEqual(complete["unresolved_factors"], [])
        self.assertTrue(complete["coverage_checked"])
        self.assertIsNone(complete["proposed_test"])
        self.assertEqual(complete["cost"], 0)
        self.assertIn("not identified causes", " ".join(complete["limitations"]))

    def test_budget_exhaustion_preserves_supported_and_unresolved_factors(self) -> None:
        result = self.choose({"implementation": False}, budget=1)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["supported_factors"], ["reported_value_disagrees"])
        self.assertEqual(result["unresolved_factors"], ["replicates_disagree"])
        self.assertEqual(result["pending_tests"], ["repeat"])
        self.assertFalse(result["coverage_checked"])

    def test_all_passed_clears_only_the_registered_indicators(self) -> None:
        result = self.choose({"implementation": True, "repeat": True}, budget=0)
        self.assertEqual(result["status"], "diagnosis_supported")
        self.assertEqual(result["supported_factors"], [])
        self.assertEqual(result["cleared_factors"], sorted(self.factors))
        self.assertIn("unknown or check-invisible", " ".join(result["limitations"]))

    def test_extra_check_is_required_for_coverage(self) -> None:
        self.tests["coverage"] = 1
        partial = self.choose({"implementation": True, "repeat": True}, budget=0)
        self.assertEqual(partial["status"], "budget_exhausted")
        self.assertEqual(partial["unresolved_factors"], [])
        self.assertEqual(partial["pending_tests"], ["coverage"])
        self.assertEqual(self.choose(budget=1)["proposed_test"], "coverage")
        complete = self.choose({"implementation": True, "repeat": True, "coverage": False}, budget=0)
        self.assertTrue(complete["coverage_checked"])
        self.assertEqual(complete["supported_factors"], [])
        # An unmapped outcome never gets assigned a factor or guessed cause.

    def test_identifier_order_inputs_and_labels_do_not_change_selection(self) -> None:
        before = copy.deepcopy((self.factors, self.tests))
        original = self.choose()
        result = choose_factor_diagnostic_action(dict(reversed(list(self.factors.items()))),
                                                 dict(reversed(list(self.tests.items()))), {}, 3)
        self.assertEqual(result, original)
        renamed = choose_factor_diagnostic_action({"opaque1": "repeat", "opaque2": "implementation"},
                                                  self.tests, {}, 3)
        self.assertEqual(renamed["proposed_test"], original["proposed_test"])
        self.assertEqual((self.factors, self.tests), before)
        self.assertEqual(list(inspect.signature(choose_factor_diagnostic_action).parameters),
                         ["factors", "tests", "observations", "remaining_budget"])

    def test_invalid_models_do_not_infer_independence_or_accept_nonboolean_observations(self) -> None:
        cases = [
            ({}, {"t": 1}, {}, 1),
            ({"f": "t"}, {}, {}, 1),
            ([], {"t": 1}, {}, 1),
            ({"f": "t"}, [], {}, 1),
            ({"f": "t"}, {"t": 1}, [], 1),
            ({"": "t"}, {"t": 1}, {}, 1),
            ({"f": "t"}, {"": 1}, {}, 1),
            ({"f": "missing"}, {"t": 1}, {}, 1),
            ({"f": ["t"]}, {"t": 1}, {}, 1),
            ({"f": "t", "alias": "t"}, {"t": 1}, {}, 1),
            ({"f": "t"}, {"t": 1}, {"unknown": True}, 1),
        ]
        for invalid in (0, 1, "true", None, [], {}):
            cases.append(({"f": "t"}, {"t": 1}, {"t": invalid}, 1))
        for invalid in (True, False, -1, 0, 1.0, "1", None):
            cases.append(({"f": "t"}, {"t": invalid}, {}, 1))
        for invalid in (True, False, -1, 1.0, "1", None):
            cases.append(({"f": "t"}, {"t": 1}, {}, invalid))
        for case in cases:
            with self.subTest(case=case), self.assertRaises(PipelineError):
                choose_factor_diagnostic_action(*case)


if __name__ == "__main__":
    unittest.main()
