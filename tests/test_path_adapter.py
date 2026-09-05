from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from verispiral import path_adapter as adapter
from verispiral.path_reference import exact_shortest_path
from verispiral.path_workflow import public_graphs


TRAP = {"node_count": 4, "edges": [[0, 1, 1], [0, 2, 2], [1, 3, 9], [2, 3, 1]]}


def specification(setup=None, screen="path_edges_only"):
    return {"setup": adapter.propose(setup or TRAP)["setup"], "screen_verifier": screen}


class PathAdapterTests(unittest.TestCase):
    def test_proposal_is_explicit_and_has_no_approval_or_evaluation(self):
        with patch.object(adapter, "solve", side_effect=AssertionError("no generation")), \
             patch.object(adapter, "check", side_effect=AssertionError("no checking")), \
             patch.object(adapter, "exact_shortest_path", side_effect=AssertionError("no oracle")):
            proposal = adapter.propose(TRAP)
        self.assertEqual(proposal["goal"]["source"], 0)
        self.assertEqual(proposal["goal"]["target"], 3)
        self.assertEqual(proposal["algorithm_frontier"], ["greedy_edge", "topological_exact"])
        self.assertNotIn("approval", proposal)
        frontier = proposal["verifier_frontier"]
        self.assertEqual(frontier[0], {"id": "all_edges_certificate", "recommended": True,
                                       "role": "certification_gate"})
        self.assertTrue(all(entry["role"] == "diagnostic_only_screen" for entry in frontier[1:]))
        self.assertIn("2..12", proposal["scope"])

    def test_setup_rejects_unsupported_and_malformed_graphs(self):
        malformed = [None, {}, {**TRAP, "private_field": "unsupported"},
                     {"node_count": True, "edges": []},
                     {"node_count": 13, "edges": []},
                     {"node_count": 4, "edges": tuple(TRAP["edges"])},
                     {"node_count": 3, "edges": [[0, 2, 1]]},
                     {"node_count": 3, "edges": [[0, 1, 1]]},
                     {"node_count": 2, "edges": [[1, 0, 1]]},
                     {"node_count": 2, "edges": [[0, 1, 1], [0, 1, 2]]},
                     {"node_count": 2, "edges": [[0, 1, True]]},
                     {"node_count": 2, "edges": [[0, 1]]}]
        for setup in malformed:
            with self.subTest(setup=setup), self.assertRaises(ValueError):
                adapter.propose(setup)
        with self.assertRaisesRegex(ValueError, "every node must be reachable"):
            adapter.propose({"node_count": 3, "edges": [[0, 2, 1]]})

    def test_reachability_accepts_unsorted_edge_input(self):
        setup = {"node_count": 4, "edges": [[2, 3, -1], [1, 2, 3], [0, 1, 2]]}
        self.assertEqual(adapter.propose(setup)["setup"], setup)

    def test_generation_does_not_rerun_witness_producer(self):
        spec = specification()
        original_solve = adapter.solve
        with patch.object(adapter, "solve", wraps=original_solve) as solver:
            result = adapter.generate(spec, "greedy_edge")
        solver.assert_called_once_with(4, spec["setup"]["edges"], "greedy_edge")
        self.assertEqual(result["candidate"]["path"], [0, 1, 3])
        self.assertEqual(result["cost"], 4 + 4 + 3 + 2)

    def test_reservations_do_not_compute_test_outcomes(self):
        with patch.object(adapter, "check", side_effect=AssertionError("no checking")), \
             patch.object(adapter, "submitted_path_cost", side_effect=AssertionError("no scoring")), \
             patch.object(adapter, "exact_shortest_path", side_effect=AssertionError("no oracle")):
            costs = adapter.test_costs(specification(), {"path": [0, 1, 3]})
        self.assertEqual(costs, {"path_feasible": 6, "path_optimal": 21,
                                 "certificate_valid": 10, "screen_agrees_with_reference": 31})

    def test_feasibility_test_does_not_consult_checker_or_oracle(self):
        candidate = {"path": [0, 1, 3], "cost": -999, "potentials": None}
        with patch.object(adapter, "check", side_effect=AssertionError("no checking")), \
             patch.object(adapter, "exact_shortest_path", side_effect=AssertionError("no oracle")):
            result = adapter.observe(specification(), candidate, "path_feasible")
        self.assertTrue(result["passed"])
        self.assertEqual(result["evidence"]["actual_cost"], 10)
        self.assertEqual(result["cost"], 6)
        self.assertNotIn("reference_cost", result["evidence"])

    def test_optimality_independently_scores_path_ignoring_submitted_cost(self):
        candidate = {"path": [0, 1, 3], "cost": 3, "potentials": [0, 1, 2, 10]}
        with patch.object(adapter, "check", side_effect=AssertionError("no certificate test")):
            result = adapter.observe(specification(), candidate, "path_optimal")
        self.assertFalse(result["passed"])
        self.assertEqual(result["evidence"]["actual_cost"], 10)
        self.assertEqual(result["evidence"]["reference_cost"], 3)
        self.assertEqual(result["evidence"]["reference_path"], [0, 2, 3])
        self.assertEqual(result["evidence"]["regret"], 7)
        self.assertEqual(result["cost"], 4 + 2 + 4 + 4 + 4)

    def test_certificate_test_always_uses_full_gate_without_reference(self):
        spec = specification(screen="feasibility_only")
        candidate = adapter.generate(spec, "greedy_edge")["candidate"]
        with patch.object(adapter, "submitted_path_cost", side_effect=AssertionError("no scoring")), \
             patch.object(adapter, "exact_shortest_path", side_effect=AssertionError("no oracle")):
            result = adapter.observe(spec, candidate, "certificate_valid")
        self.assertFalse(result["passed"])
        self.assertEqual(result["evidence"]["verifier"], "all_edges_certificate")
        self.assertNotIn("reference_cost", result["evidence"])

    def test_compound_factors_are_reportable_for_the_same_candidate(self):
        spec = specification()
        candidate = adapter.generate(spec, "greedy_edge")["candidate"]
        supported = [factor for factor, test_id in adapter.FACTORS.items()
                     if not adapter.observe(spec, candidate, test_id)["passed"]]
        self.assertEqual(supported, ["candidate_not_optimal", "certificate_invalid", "screen_disagreement"])
        screen = adapter.observe(spec, candidate, "screen_agrees_with_reference")
        self.assertTrue(screen["evidence"]["screen_accepted"])
        self.assertFalse(screen["evidence"]["certified"])

    def test_optimal_path_with_bad_witness_has_separate_failures(self):
        spec = specification(screen="all_edges_certificate")
        candidate = {"path": [0, 2, 3], "potentials": None}
        self.assertTrue(adapter.observe(spec, candidate, "path_optimal")["passed"])
        self.assertFalse(adapter.observe(spec, candidate, "certificate_valid")["passed"])
        self.assertFalse(adapter.observe(spec, candidate, "screen_agrees_with_reference")["passed"])

    def test_witness_repair_preserves_path_and_metadata_and_charges_full_producer(self):
        spec = specification()
        candidate = {"path": [0, 2, 3], "potentials": None, "solver_edge_visits": 19,
                     "custom_metadata": {"proposal": "fixture"}}
        before = deepcopy(candidate)
        repaired = adapter.repair(spec, candidate, ["certificate_invalid"])
        self.assertEqual(repaired["kind"], "witness_only")
        self.assertEqual(repaired["cost"], adapter.generate(spec, "topological_exact")["cost"])
        self.assertEqual({k: v for k, v in repaired["candidate"].items() if k != "potentials"},
                         {k: v for k, v in candidate.items() if k != "potentials"})
        self.assertEqual(candidate, before)
        self.assertTrue(adapter.observe(spec, repaired["candidate"], "certificate_valid")["passed"])

    def test_candidate_repair_addresses_compound_failure_but_does_not_edit_spec(self):
        spec = specification()
        before = deepcopy(spec)
        candidate = adapter.generate(spec, "greedy_edge")["candidate"]
        repaired = adapter.repair(spec, candidate, ["certificate_invalid", "candidate_not_optimal"])
        self.assertEqual(repaired["kind"], "candidate_replacement")
        self.assertEqual(repaired["candidate"]["path"], [0, 2, 3])
        self.assertTrue(adapter.observe(spec, repaired["candidate"], "certificate_valid")["passed"])
        self.assertEqual(spec, before)
        self.assertIsNone(adapter.repair(spec, candidate, ["screen_disagreement"]))
        self.assertIsNone(adapter.repair(spec, candidate, []))

    def test_actual_scoring_counts_include_early_exit(self):
        spec = specification()
        for path, expected_visits in [(None, 0), ([], 0), ([1, 3], 0),
                                      ([0, True, 3], 0), ([0, 3], 1),
                                      ([0, 1, 2, 3], 2), ([0, 1, 3, 1, 3], 3)]:
            with self.subTest(path=path):
                result = adapter.observe(spec, {"path": path}, "path_feasible")
                self.assertFalse(result["passed"])
                self.assertEqual(result["cost"], 4 + expected_visits)
                self.assertEqual(result["evidence"]["operation_counts"]["scoring_path_edges"], expected_visits)

    def test_all_public_cases_fit_reserved_costs_and_direct_results_match_reference(self):
        plan = json.loads((Path(__file__).resolve().parents[1] / "examples/path/experiment_plan.json").read_text())
        cases = public_graphs(plan)
        self.assertEqual(len(cases), 26)
        for case in cases:
            setup = {"node_count": case["n"], "edges": case["edges"]}
            for screen in adapter.VERIFIERS:
                spec = specification(setup, screen)
                for method in adapter.METHODS:
                    candidate = adapter.generate(spec, method)["candidate"]
                    costs = adapter.test_costs(spec, candidate)
                    for test_id, bound in costs.items():
                        with self.subTest(case=case["id"], method=method, screen=screen, test=test_id):
                            result = adapter.observe(spec, candidate, test_id)
                            self.assertIs(type(bound), int)
                            self.assertGreater(bound, 0)
                            self.assertLessEqual(result["cost"], bound)
                            self.assertEqual(result["cost"], sum(result["evidence"]["operation_counts"].values()))
                    if method == "topological_exact":
                        self.assertEqual(candidate["path"], exact_shortest_path(case["n"], case["edges"])["path"])
                        self.assertTrue(adapter.observe(spec, candidate, "certificate_valid")["passed"])

    def test_operations_leave_inputs_unchanged_and_reject_unknown_actions(self):
        setup = deepcopy(TRAP)
        before = deepcopy(setup)
        proposal = adapter.propose(setup)
        proposal["setup"]["edges"][0][2] = -999
        self.assertEqual(setup, before)
        spec = specification(setup)
        candidate = adapter.generate(spec, "greedy_edge")["candidate"]
        snapshots = deepcopy((spec, candidate))
        for test_id in adapter.FACTORS.values():
            adapter.observe(spec, candidate, test_id)
        adapter.repair(spec, candidate, ["certificate_invalid"])
        self.assertEqual((spec, candidate), snapshots)
        with self.assertRaises(ValueError):
            adapter.generate(spec, "greedy_with_potentials")
        with self.assertRaises(ValueError):
            adapter.observe(spec, candidate, "invented_test")
        with self.assertRaises(ValueError):
            adapter.repair(spec, candidate, ["invented_factor"])


if __name__ == "__main__":
    unittest.main()
