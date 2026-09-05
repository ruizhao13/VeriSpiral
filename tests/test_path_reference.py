from __future__ import annotations

import copy
import itertools
import unittest

from verispiral.path_reference import exact_shortest_path, submitted_path_cost


class ExhaustivePathReferenceTests(unittest.TestCase):
    def test_two_node_path(self) -> None:
        self.assertEqual(exact_shortest_path(2, [(0, 1, 7)]), {
            "status": "optimal", "cost": 7, "path": [0, 1], "edge_visits": 1,
        })

    def test_negative_edge_defeats_locally_cheapest_first_edge(self) -> None:
        self.assertEqual(exact_shortest_path(4, [
            (0, 1, 1), (1, 3, 8), (0, 2, 6), (2, 3, -10), (0, 3, 3),
        ]), {
            "status": "optimal", "cost": -4, "path": [0, 2, 3], "edge_visits": 5,
        })

    def test_does_not_prune_expensive_prefix(self) -> None:
        self.assertEqual(exact_shortest_path(3, [
            (0, 2, 0), (0, 1, 100), (1, 2, -101),
        ]), {
            "status": "optimal", "cost": -1, "path": [0, 1, 2], "edge_visits": 3,
        })

    def test_ties_are_lexicographic_and_edge_order_invariant(self) -> None:
        edges = [(0, 3, 2), (0, 1, 1), (1, 3, 1), (1, 2, 0), (2, 3, 1)]
        expected = {
            "status": "optimal", "cost": 2, "path": [0, 1, 2, 3], "edge_visits": 5,
        }
        for permutation in itertools.permutations(edges):
            with self.subTest(edges=permutation):
                self.assertEqual(exact_shortest_path(4, list(permutation)), expected)

    def test_shared_suffix_and_dead_end_are_counted_on_every_visit(self) -> None:
        # 0-1-3-5 and 0-2-3-5 traverse 3-5 twice; 0-4 is a dead end.
        self.assertEqual(exact_shortest_path(6, [
            (0, 1, 1), (0, 2, 1), (1, 3, 1), (2, 3, 1),
            (3, 5, 1), (0, 4, 0),
        ]), {
            "status": "optimal", "cost": 3, "path": [0, 1, 3, 5], "edge_visits": 7,
        })

    def test_unreachable_and_unvisited_edges(self) -> None:
        self.assertEqual(exact_shortest_path(5, [(0, 1, 2), (2, 4, -3)]), {
            "status": "unreachable", "cost": None, "path": [], "edge_visits": 1,
        })
        self.assertEqual(exact_shortest_path(2, []), {
            "status": "unreachable", "cost": None, "path": [], "edge_visits": 0,
        })

    def test_full_graph_at_size_limit_visits_every_nonempty_prefix(self) -> None:
        # Every increasing subset of nodes 1..11 is one traversed prefix.
        edges = [(u, v, 0) for u in range(12) for v in range(u + 1, 12)]
        self.assertEqual(exact_shortest_path(12, edges), {
            "status": "optimal", "cost": 0, "path": list(range(12)),
            "edge_visits": 2 ** 11 - 1,
        })

    def test_json_triples_and_inputs_are_not_mutated(self) -> None:
        edges = [[0, 2, 5], [0, 1, -2], [1, 2, 1]]
        original = copy.deepcopy(edges)
        result = exact_shortest_path(3, edges)
        self.assertEqual(result["cost"], -1)
        self.assertEqual(edges, original)
        result["path"].append(100)
        self.assertEqual(exact_shortest_path(3, edges)["path"], [0, 1, 2])

    def test_invalid_node_count(self) -> None:
        for node_count in (None, True, False, 2.0, "3", -1, 0, 1, 13):
            with self.subTest(node_count=node_count), self.assertRaises(ValueError):
                exact_shortest_path(node_count, [])

    def test_invalid_edge_shapes_and_values(self) -> None:
        malformed = [
            None, "edges", {"0": 1}, [None], ["012"], [(0, 1)],
            [(0, 1, 2, 3)], [(0, 1, True)], [(False, 1, 2)],
            [(0, True, 2)], [(0.0, 1, 2)], [(0, 1.0, 2)],
            [(0, 1, 2.0)], [(0, 1, "2")], [(0, 1, None)],
            [(-1, 1, 2)], [(0, 3, 2)], [(1, 1, 2)], [(2, 1, 2)],
            [(0, 1, 2), (0, 1, 3)], [(0, 1, 2)] * 4,
        ]
        for edges in malformed:
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                exact_shortest_path(3, edges)


class SubmittedPathCostTests(unittest.TestCase):
    def test_sums_actual_weights_for_optimal_and_suboptimal_paths(self) -> None:
        edges = [(0, 1, 10), (1, 3, -20), (0, 2, 1), (2, 3, 2), (0, 3, 0)]
        self.assertEqual(submitted_path_cost(4, edges, [0, 1, 3]), -10)
        self.assertEqual(submitted_path_cost(4, edges, [0, 2, 3]), 3)
        self.assertEqual(submitted_path_cost(4, edges, (0, 3)), 0)

    def test_rejects_malformed_and_infeasible_paths(self) -> None:
        edges = [(0, 1, 2), (1, 3, 3), (0, 3, 8)]
        for path in (
            None, {}, "013", [], [0], [0, 1], [1, 3], [0, 2, 3],
            [0, 1, 1, 3], [0, 3, 1, 3], [0, 1, 4, 3], [0, -1, 3],
            [False, 1, 3], [0, True, 3], [0, 1, 3.0], [0, "1", 3],
            [0, None, 3], [0, [], 3],
        ):
            with self.subTest(path=path):
                self.assertIsNone(submitted_path_cost(4, edges, path))

    def test_graph_validation_is_not_skipped_for_invalid_path(self) -> None:
        for node_count, edges in (
            (True, []), (13, []), (3, [(0, 1, True)]),
            (3, [(0, 1, 2), (0, 1, 3)]), (3, [(2, 1, 1)]),
        ):
            with self.subTest(node_count=node_count, edges=edges):
                with self.assertRaises(ValueError):
                    submitted_path_cost(node_count, edges, [])

    def test_inputs_remain_unchanged(self) -> None:
        edges = [[0, 1, -2], [1, 2, 4]]
        path = [0, 1, 2]
        before = copy.deepcopy((edges, path))
        self.assertEqual(submitted_path_cost(3, edges, path), 2)
        self.assertEqual((edges, path), before)


if __name__ == "__main__":
    unittest.main()
