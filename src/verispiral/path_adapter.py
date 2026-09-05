"""Bounded path adapter for the connected, human-approved research loop.

``propose`` validates the supported mathematical setup. Other operations consume
that approved setup; they never approve a proposal or change a specification.
Costs count edge operations of the invoked solver, reference, scorer and checker,
including their graph validation and indexing. Proposal/schema handling, node
operations and serialization are outside this metric; it is not elapsed time.
"""

from __future__ import annotations

from copy import deepcopy

from .path_reference import exact_shortest_path, submitted_path_cost
from .path_workflow import check, solve, validate_graph


FACTORS = {
    "candidate_infeasible": "path_feasible",
    "candidate_not_optimal": "path_optimal",
    "certificate_invalid": "certificate_valid",
    "screen_disagreement": "screen_agrees_with_reference",
}
METHODS = ("greedy_edge", "topological_exact")
VERIFIERS = ("all_edges_certificate", "path_edges_only", "feasibility_only")
_ACCEPTED = {"certified_optimal", "accepted_by_weak_gate"}
_GENERATION_COUNTERS = (
    "graph_scan_edges", "indexing_edge_visits", "solver_edge_visits", "witness_edge_visits",
)


def _setup_fields(setup: dict) -> tuple[int, list]:
    if not isinstance(setup, dict) or set(setup) != {"node_count", "edges"}:
        raise ValueError("setup must contain exactly node_count and edges")
    n, edges = setup["node_count"], setup["edges"]
    if type(n) is not int or not 2 <= n <= 12 or not isinstance(edges, list):
        raise ValueError("expected node_count 2..12 and an edges list")
    return n, edges


def _spec_fields(spec: dict) -> tuple[int, list, str]:
    if not isinstance(spec, dict):
        raise ValueError("expected a validated path specification")
    n, edges = _setup_fields(spec.get("setup"))
    screen = spec.get("screen_verifier")
    if screen not in VERIFIERS:
        raise ValueError("unknown screen verifier")
    return n, edges, screen


def propose(setup: dict) -> dict:
    """Propose an explicit finite path goal without inventing human acceptance."""
    n, edges = _setup_fields(setup)
    weights = validate_graph(n, edges)
    outgoing = [[] for _ in range(n)]
    for u, v in weights:
        outgoing[u].append(v)
    reachable = {0}
    for u in range(n):
        if u in reachable:
            reachable.update(outgoing[u])
    if len(reachable) != n:
        raise ValueError("unsupported setup: every node must be reachable from source 0")
    return {
        "goal": {
            "objective": "minimum_path_weight",
            "source": 0,
            "target": n - 1,
            "acceptance": "feasible path with an all-edges optimality certificate",
        },
        "setup": deepcopy(setup),
        "verifier_frontier": [
            {"id": variant,
             "role": "certification_gate" if index == 0 else "diagnostic_only_screen",
             "recommended": index == 0}
            for index, variant in enumerate(VERIFIERS)
        ],
        "algorithm_frontier": list(METHODS),
        "scope": "Numbered DAGs with 2..12 nodes, integer edge weights, no parallel edges, "
                 "and every node reachable from source 0; the supplied graph is the full model. "
                 "No claim about omitted edges or real-world route validity.",
    }


def generate(spec: dict, method: str) -> dict:
    """Run one declared producer and charge all its reported edge work."""
    n, edges, _ = _spec_fields(spec)
    if method not in METHODS:
        raise ValueError("unknown adapter algorithm")
    candidate = solve(n, edges, method)
    return {"candidate": candidate,
            "cost": sum(candidate[field] for field in _GENERATION_COUNTERS)}


def _path_length(candidate: dict) -> int:
    path = candidate.get("path") if isinstance(candidate, dict) else None
    return max(0, len(path) - 1) if isinstance(path, (list, tuple)) else 0


def test_costs(spec: dict, candidate: dict) -> dict:
    """Conservative positive edge-work reservations, with no outcome evaluation."""
    n, edges, _ = _spec_fields(spec)
    m, length = len(edges), _path_length(candidate)
    dfs_bound = 2 ** (n - 1) - 1
    return {
        "path_feasible": max(1, m + length),
        "path_optimal": max(1, 3 * m + dfs_bound + length),
        "certificate_valid": max(1, 2 * m + length),
        "screen_agrees_with_reference": max(1, 4 * m + dfs_bound + (m + length) + length),
    }


class _ScoringPath(list):
    """Meter the unchanged reference scorer's path-edge loop, including exits."""

    def __init__(self, path: list | tuple) -> None:
        super().__init__(path)
        self.edge_visits = 0

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if isinstance(key, slice) and key == slice(1, None, None):
            def count_edges():
                for node in value:
                    self.edge_visits += 1
                    yield node
            return count_edges()
        return value


def _score(n: int, edges: list, candidate: dict) -> tuple[int | None, dict]:
    path = candidate.get("path") if isinstance(candidate, dict) else None
    counted = _ScoringPath(path) if isinstance(path, (list, tuple)) else path
    cost = submitted_path_cost(n, edges, counted)
    return cost, {
        "scoring_graph_validation_edges": len(edges),
        "scoring_path_edges": counted.edge_visits if isinstance(counted, _ScoringPath) else 0,
    }


def observe(spec: dict, candidate: dict, test_id: str) -> dict:
    """Run only the requested observation; a failure supports one narrow factor.

    Certificate rejection does not establish suboptimality. An optimal path can
    still have a bad witness, and several observations may fail simultaneously.
    Weak screen acceptance is diagnostic evidence and never certification.
    """
    n, edges, screen = _spec_fields(spec)
    if test_id not in FACTORS.values():
        raise ValueError("unknown path diagnostic test")
    evidence = {"test_id": test_id,
                "supported_factor_on_failure": next(factor for factor, test in FACTORS.items()
                                                    if test == test_id),
                "interpretation": "This observation is not an exclusive root-cause claim."}
    counts = {}
    if test_id in {"path_feasible", "path_optimal", "screen_agrees_with_reference"}:
        actual, scoring_counts = _score(n, edges, candidate)
        counts.update(scoring_counts)
        evidence["actual_cost"] = actual
        evidence["path_feasible"] = actual is not None
        passed = actual is not None
    if test_id in {"path_optimal", "screen_agrees_with_reference"}:
        reference = exact_shortest_path(n, edges)
        counts.update({"reference_graph_validation_edges": len(edges),
                       "reference_indexing_edges": len(edges),
                       "reference_dfs_edge_visits": reference["edge_visits"]})
        regret = None if actual is None or reference["cost"] is None else actual - reference["cost"]
        optimal = actual is not None and reference["status"] == "optimal" and regret == 0
        evidence.update({"reference_cost": reference["cost"], "reference_path": reference["path"],
                         "regret": regret, "path_optimal": optimal})
        passed = optimal
    if test_id in {"certificate_valid", "screen_agrees_with_reference"}:
        variant = "all_edges_certificate" if test_id == "certificate_valid" else screen
        result = check(n, edges, candidate, variant)
        counts.update({"checker_graph_validation_edges": result["graph_scan_edges"],
                       "checker_edge_checks": result["edge_checks"]})
        accepted = result["status"] in _ACCEPTED
        evidence.update({"verifier": variant, "check_status": result["status"],
                         "check_cost": result["cost"], "violated_edge": result["violated_edge"],
                         "screen_accepted": accepted,
                         "certified": result["status"] == "certified_optimal"})
        passed = result["status"] == "certified_optimal" if test_id == "certificate_valid" else accepted == optimal
    evidence["operation_counts"] = counts
    return {"passed": passed, "cost": sum(counts.values()), "evidence": evidence}


def repair(spec: dict, candidate: dict, supported_factors: list) -> dict | None:
    """Apply a declared candidate/witness producer; screen changes need a proposal."""
    _spec_fields(spec)
    if not isinstance(supported_factors, list) or any(factor not in FACTORS for factor in supported_factors):
        raise ValueError("unsupported diagnostic factor")
    if {"candidate_infeasible", "candidate_not_optimal"}.intersection(supported_factors):
        return {**generate(spec, "topological_exact"), "kind": "candidate_replacement"}
    if "certificate_invalid" in supported_factors:
        if not isinstance(candidate, dict):
            raise ValueError("witness repair requires a candidate mapping")
        producer = generate(spec, "topological_exact")
        repaired = deepcopy(candidate)
        repaired["potentials"] = producer["candidate"]["potentials"]
        return {"candidate": repaired, "cost": producer["cost"], "kind": "witness_only"}
    return None
