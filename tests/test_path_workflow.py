from __future__ import annotations

import itertools
import json
from pathlib import Path
import unittest

from verispiral.path_reference import exact_shortest_path, submitted_path_cost
from verispiral.path_workflow import check, public_graphs, solve, validate_graph


TRAP = [(0, 1, 1), (0, 2, 2), (1, 3, 9), (2, 3, 1)]
COMPLETE = "all_edges_certificate"


class PathWorkflowTests(unittest.TestCase):
    def test_off_path_edge_defeats_both_weak_gates(self) -> None:
        forged = {"path": [0, 1, 3], "potentials": [0, 1, 2, 10]}
        for variant in ("feasibility_only", "path_edges_only"):
            result = check(4, TRAP, forged, variant)
            self.assertEqual(result["status"], "accepted_by_weak_gate")
            self.assertEqual(result["cost"], 10)
        result = check(4, TRAP, forged, COMPLETE)
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["violated_edge"], [2, 3, 1])
        self.assertEqual(exact_shortest_path(4, TRAP)["cost"], 3)

    def test_source_anchor_cannot_be_shifted(self) -> None:
        # These shifted potentials satisfy every edge inequality and p[t]=10.
        forged = {"path": [0, 1, 3], "potentials": [7, 8, 9, 10]}
        self.assertEqual(check(4, TRAP, forged, COMPLETE)["status"], "unverified")

    def test_non_integer_and_malformed_potentials_are_unverified(self) -> None:
        malformed = [None, (), [0, 1, 2], [0, 1, 2, 3, 4],
                     [0, 1, float("nan"), 10], [0, True, 2, 3],
                     [0, 1, 2.0, 3], [0, 1, float("inf"), 3]]
        for potentials in malformed:
            with self.subTest(potentials=potentials):
                result = check(4, TRAP, {"path": [0, 2, 3],
                                        "potentials": potentials}, COMPLETE)
                self.assertEqual(result["status"], "unverified")
                self.assertEqual(result["cost"], 3)

    def test_bad_paths_are_invalid_witnesses(self) -> None:
        paths = [None, (), [], [0], [1, 3], [0, 2], [0, 3], [0, 1, 2, 3],
                 [0, True, 3], [0, 2.0, 3], [0, -1, 3], [0, 4, 3],
                 [0, 1, 1, 3], [0, 1, 2, 1, 3]]
        for path in paths:
            with self.subTest(path=path):
                result = check(4, TRAP, {"path": path,
                                        "potentials": [0, 1, 2, 3]}, COMPLETE)
                self.assertEqual(result["status"], "invalid_witness")
        self.assertEqual(check(4, TRAP, None, COMPLETE)["status"], "invalid_witness")

    def test_invalid_graphs_fail_closed(self) -> None:
        graphs = [TRAP + [(0, 1, 99)], [(0, 1, True)], [(0, 1, 2.0)],
                  [(False, 1, 2)], [(1, 0, 2)], [(0, 4, 2)], [(0, 1)]]
        for edges in graphs:
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                check(4, edges, {"path": [0, 2, 3], "potentials": [0, 1, 2, 3]}, COMPLETE)
        for n in (True, 2.0, 1, 13):
            with self.subTest(n=n), self.assertRaises(ValueError):
                validate_graph(n, [])

    def test_optimal_path_with_corrupt_witness_remains_unverified(self) -> None:
        for potentials in ([0, 1, 2, 2], [0, 1, 1, 3], None):
            candidate = {"path": [0, 2, 3], "potentials": potentials}
            result = check(4, TRAP, candidate, COMPLETE)
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(result["cost"], exact_shortest_path(4, TRAP)["cost"])

    def test_recomputes_cost_with_exact_large_integer_arithmetic(self) -> None:
        large = 2 ** 53
        edges = [(0, 1, large), (1, 2, 1), (0, 2, large)]
        forged = {"path": [0, 1, 2], "potentials": [0, large, large],
                  "cost": large}
        result = check(3, edges, forged, COMPLETE)
        self.assertEqual(result["cost"], large + 1)
        self.assertEqual(result["status"], "unverified")

    def test_bounded_exhaustive_certificate_soundness(self) -> None:
        # 27 graphs, both possible paths, and 121 proposed potential vectors.
        # This finite check complements the telescoping proof, not all inputs.
        certified = 0
        for weights in itertools.product((-2, 0, 3), repeat=3):
            edges = [(0, 1, weights[0]), (0, 2, weights[1]), (1, 2, weights[2])]
            optimum = exact_shortest_path(3, edges)["cost"]
            self.assertEqual(optimum, min(weights[1], weights[0] + weights[2]))
            for path in ([0, 2], [0, 1, 2]):
                for p1, p2 in itertools.product(range(-4, 7), repeat=2):
                    result = check(3, edges, {"path": path,
                                             "potentials": [0, p1, p2]}, COMPLETE)
                    if result["status"] == "certified_optimal":
                        certified += 1
                        self.assertEqual(result["cost"], optimum,
                                         (edges, path, p1, p2))
        self.assertGreater(certified, 0)

    def test_exact_solver_agrees_with_reference_on_all_public_cases(self) -> None:
        plan_path = Path(__file__).resolve().parents[1] / "examples/path/experiment_plan.json"
        plan = json.loads(plan_path.read_text())
        cases = public_graphs(plan)
        self.assertTrue(any(w < 0 for case in cases for _, _, w in case["edges"]))
        for case in cases:
            with self.subTest(case=case["id"]):
                n, edges = case["n"], case["edges"]
                candidate = solve(n, edges, "topological_exact")
                reference = exact_shortest_path(n, edges)
                result = check(n, edges, candidate, COMPLETE)
                self.assertEqual(candidate["path"], reference["path"])
                self.assertEqual(result["cost"], reference["cost"])
                self.assertEqual(result["status"], "certified_optimal")

    def test_edge_counters_account_for_solver_and_checker_work(self) -> None:
        # Operation counts only: no wall-time or equal-total-budget assertion.
        greedy = solve(4, TRAP, "greedy_edge")
        exact = solve(4, TRAP, "topological_exact")
        self.assertEqual(greedy["solver_edge_visits"], 3)
        self.assertEqual(greedy["witness_edge_visits"], 2)
        self.assertEqual(exact["solver_edge_visits"], 4)
        self.assertEqual(exact["witness_edge_visits"], 0)
        self.assertEqual(exact["graph_scan_edges"], 4)
        result = check(4, TRAP, exact, COMPLETE)
        self.assertEqual(result["edge_checks"], 6)  # Two path edges plus all four edges.
        self.assertEqual(result["graph_scan_edges"], 4)

    def test_exact_solver_leaves_unreachable_node_certificate_unverified(self) -> None:
        edges = [(0, 2, -1)]
        candidate = solve(3, edges, "topological_exact")
        self.assertEqual(candidate["path"], [0, 2])
        self.assertIsNone(candidate["potentials"])
        self.assertEqual(check(3, edges, candidate, COMPLETE)["status"], "unverified")

    def assert_witness_repair(self, n: int, edges: list) -> None:
        greedy = solve(n, edges, "greedy_edge")
        repaired = solve(n, edges, "greedy_with_potentials")
        direct = solve(n, edges, "topological_exact")
        self.assertEqual(repaired["path"], greedy["path"])
        optimum = exact_shortest_path(n, edges)["cost"]
        actual = submitted_path_cost(n, edges, repaired["path"])
        result = check(n, edges, repaired, COMPLETE)
        expected = "certified_optimal" if actual == optimum else "unverified"
        self.assertEqual(result["status"], expected)
        self.assertEqual(repaired["solver_edge_visits"], greedy["solver_edge_visits"])
        self.assertGreaterEqual(repaired["witness_edge_visits"],
                                greedy["witness_edge_visits"] + direct["solver_edge_visits"])
        for component in ("graph_scan_edges", "indexing_edge_visits"):
            self.assertGreaterEqual(repaired[component], greedy[component] + direct[component])
        self.assertGreaterEqual(repaired["solver_edge_visits"] + repaired["witness_edge_visits"],
                                direct["solver_edge_visits"] + direct["witness_edge_visits"])

    def test_witness_repair_preserves_public_paths_and_charges_production(self) -> None:
        plan_path = Path(__file__).resolve().parents[1] / "examples/path/experiment_plan.json"
        for case in public_graphs(json.loads(plan_path.read_text())):
            with self.subTest(case=case["id"]):
                self.assert_witness_repair(case["n"], case["edges"])
        self.assert_witness_repair(3, [(0, 1, 2), (0, 2, 1), (1, 2, -3)])

    def test_witness_repair_on_all_27_complete_three_node_weight_assignments(self) -> None:
        for a, b, c in itertools.product((-2, 0, 3), repeat=3):
            with self.subTest(weights=(a, b, c)):
                self.assert_witness_repair(3, [(0, 1, a), (0, 2, b), (1, 2, c)])


if __name__ == "__main__":
    unittest.main()
