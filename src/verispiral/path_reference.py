"""Exhaustive reference for the small public directed-path fixtures.

This implementation deliberately enumerates paths instead of using a shortest-
path algorithm or checking certificates. Its exact answers apply only to the
validated, at-most-twelve-node directed acyclic graphs accepted here.
"""

from __future__ import annotations


def _validated_edges(
    node_count: int, edges: list[tuple[int, int, int]]
) -> dict[tuple[int, int], int]:
    if type(node_count) is not int or not 2 <= node_count <= 12:
        raise ValueError("node_count must be an integer from 2 through 12")
    if not isinstance(edges, (list, tuple)):
        raise ValueError("edges must be a list or tuple of triples")
    if len(edges) > node_count * (node_count - 1) // 2:
        raise ValueError("too many edges for a simple ordered acyclic graph")

    weights: dict[tuple[int, int], int] = {}
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 3:
            raise ValueError("each edge must be a source, target, weight triple")
        source, target, weight = edge
        if any(type(value) is not int for value in edge):
            raise ValueError("edge endpoints and weights must be integers")
        if not 0 <= source < target < node_count:
            raise ValueError("edges must satisfy 0 <= source < target < node_count")
        if (source, target) in weights:
            raise ValueError("duplicate directed edge")
        weights[source, target] = weight
    return weights


def exact_shortest_path(
    node_count: int, edges: list[tuple[int, int, int]]
) -> dict:
    """Enumerate source-to-target paths and return the cheapest one.

    Nodes are ``0 .. node_count - 1``, source is zero, and target is the last
    node. Each edge must point from a smaller node to a larger node. Negative
    integer weights are allowed. Ties use the lexicographically smallest node
    path. ``edge_visits`` counts actual DFS edge traversals, including dead ends
    and repeated traversals reached through different path prefixes; it is not
    a timing estimate or a count of distinct edges.

    Malformed input raises ``ValueError``. Lists and tuples are accepted for
    the edge sequence and triples, allowing fixtures loaded from JSON.
    """
    weights = _validated_edges(node_count, edges)
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(node_count)]
    for (source, target), weight in weights.items():
        adjacency[source].append((target, weight))

    best_cost: int | None = None
    best_path: list[int] = []
    edge_visits = 0

    def visit(node: int, cost: int, path: list[int]) -> None:
        nonlocal best_cost, best_path, edge_visits
        if node == node_count - 1:
            if best_cost is None or (cost, path) < (best_cost, best_path):
                best_cost, best_path = cost, path.copy()
            return
        for target, weight in adjacency[node]:
            edge_visits += 1
            path.append(target)
            visit(target, cost + weight, path)
            path.pop()

    visit(0, 0, [0])
    return {
        "status": "unreachable" if best_cost is None else "optimal",
        "cost": best_cost,
        "path": best_path,
        "edge_visits": edge_visits,
    }


def submitted_path_cost(
    node_count: int, edges: list[tuple[int, int, int]], path: list[int]
) -> int | None:
    """Score a submitted path without trusting solver or verifier costs.

    The graph has the same contract as ``exact_shortest_path`` and malformed
    graphs raise ``ValueError``. A malformed or infeasible submitted path
    returns ``None``. This checks feasibility and sums actual edge weights;
    it does not run the exhaustive oracle or establish optimality.
    """
    weights = _validated_edges(node_count, edges)
    if not isinstance(path, (list, tuple)) or len(path) < 2:
        return None
    if any(type(node) is not int or not 0 <= node < node_count for node in path):
        return None
    if path[0] != 0 or path[-1] != node_count - 1:
        return None
    cost = 0
    for source, target in zip(path, path[1:]):
        if (source, target) not in weights:
            return None
        cost += weights[source, target]
    return cost
