"""Concrete public shortest-path workflow trial; no model or live research runtime.

The two weak verifiers below are explicit development comparators, never
registered authority. All arithmetic is exact on bounded integer DAGs.
"""

from __future__ import annotations

from pathlib import Path

from .path_reference import exact_shortest_path, submitted_path_cost
from .pipeline import file_digest, object_digest, read_json, repository_root, write_json


def validate_graph(n: int, edges: list) -> dict[tuple[int, int], int]:
    if type(n) is not int or not 2 <= n <= 12 or not isinstance(edges, (list, tuple)):
        raise ValueError("expected a DAG with 2..12 nodes and an edge sequence")
    weights = {}
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 3:
            raise ValueError("edges must be integer triples")
        u, v, w = edge
        if any(type(x) is not int for x in edge) or not 0 <= u < v < n:
            raise ValueError("edges require integer weights and 0 <= u < v < n")
        if (u, v) in weights:
            raise ValueError("parallel edges are ambiguous for node-path witnesses")
        weights[u, v] = w
    return weights


def solve(n: int, edges: list, method: str) -> dict:
    if method == "greedy_with_potentials":
        candidate = solve(n, edges, "greedy_edge")
        witness = solve(n, edges, "topological_exact")
        return {**candidate, "potentials": witness["potentials"],
                "graph_scan_edges": candidate["graph_scan_edges"] + witness["graph_scan_edges"],
                "indexing_edge_visits": candidate["indexing_edge_visits"] + witness["indexing_edge_visits"],
                "witness_edge_visits": candidate["witness_edge_visits"]
                + witness["solver_edge_visits"] + witness["witness_edge_visits"]}
    weights = validate_graph(n, edges)
    outgoing = {u: [] for u in range(n)}
    for (u, v), w in weights.items():
        outgoing[u].append((v, w))
    visits = 0
    if method == "greedy_edge":
        path, potentials = [0], [0] * n
        while path[-1] != n - 1:
            u = path[-1]
            visits += len(outgoing[u])
            if not outgoing[u]:
                return {"path": [], "potentials": None, "solver_edge_visits": visits,
                        "witness_edge_visits": 0, "graph_scan_edges": len(edges),
                        "indexing_edge_visits": len(edges)}
            v, w = min(outgoing[u], key=lambda item: (item[1], item[0]))
            potentials[v] = potentials[u] + w
            path.append(v)
        # Path-prefix sums are an untrusted proposed witness, not a dual solution.
        witness_visits = len(path) - 1
    elif method == "topological_exact":
        distances, paths = [None] * n, [None] * n
        distances[0], paths[0] = 0, [0]
        for u in range(n):
            if distances[u] is None:
                continue
            for v, w in outgoing[u]:
                visits += 1
                candidate = (distances[u] + w, paths[u] + [v])
                if distances[v] is None or candidate < (distances[v], paths[v]):
                    distances[v], paths[v] = candidate
        path = paths[-1] or []
        potentials = distances if all(d is not None for d in distances) else None
        # The direct solver already computes all reachable distances. Its work is
        # charged in solver_edge_visits, not declared a free certificate oracle.
        witness_visits = 0
    else:
        raise ValueError(f"unknown solver: {method}")
    return {"path": path, "potentials": potentials, "solver_edge_visits": visits,
            "witness_edge_visits": witness_visits, "graph_scan_edges": len(edges),
            "indexing_edge_visits": len(edges)}


def check(n: int, edges: list, candidate: dict, variant: str) -> dict:
    if variant not in {"feasibility_only", "path_edges_only", "all_edges_certificate"}:
        raise ValueError(f"unknown verifier: {variant}")
    weights = validate_graph(n, edges)
    path = candidate.get("path") if isinstance(candidate, dict) else None
    result = {"status": "invalid_witness", "cost": None, "edge_checks": 0,
              "graph_scan_edges": len(edges), "violated_edge": None}
    if (not isinstance(path, list) or not 2 <= len(path) <= n
            or any(type(v) is not int for v in path) or path[0] != 0 or path[-1] != n - 1):
        return result
    cost = 0
    for edge in zip(path, path[1:]):
        result["edge_checks"] += 1
        if edge not in weights:
            return result
        cost += weights[edge]
    result["cost"] = cost
    if variant == "feasibility_only":
        # This baseline deliberately misuses feasibility as an optimality gate.
        result["status"] = "accepted_by_weak_gate"
        return result
    potentials = candidate.get("potentials")
    if (not isinstance(potentials, list) or len(potentials) != n
            or any(type(value) is not int for value in potentials) or potentials[0] != 0):
        result["status"] = "unverified"
        return result
    tested_edges = list(zip(path, path[1:])) if variant == "path_edges_only" else weights
    for u, v in tested_edges:
        result["edge_checks"] += 1
        if potentials[v] > potentials[u] + weights[u, v]:
            result["status"] = "unverified"
            result["violated_edge"] = [u, v, weights[u, v]]
            return result
    if potentials[-1] != cost:
        result["status"] = "unverified"
        return result
    result["status"] = "certified_optimal" if variant == "all_edges_certificate" else "accepted_by_weak_gate"
    return result


def public_graphs(plan: dict) -> list[dict]:
    if plan["regression_cases"]["edge_rule"] != "Complete DAG; weight(u,v,k) = ((u+1)*17 + (v+1)*11 + k*7) % 19 - 6.":
        raise ValueError("unimplemented graph generation rule")
    graphs = [
        {"id": "greedy_trap", "group": "development", "n": 4,
         "edges": [(0, 1, 1), (1, 3, 9), (0, 2, 2), (2, 3, 1)]},
        {"id": "negative_edge", "group": "development", "n": 4,
         "edges": [(0, 1, 2), (0, 2, 4), (1, 3, 2), (2, 3, -5)]},
    ]
    for n in plan["regression_cases"]["node_counts"]:
        for k in range(plan["regression_cases"]["instances_per_size"]):
            edges = [(u, v, ((u + 1) * 17 + (v + 1) * 11 + k * 7) % 19 - 6)
                     for u in range(n) for v in range(u + 1, n)]
            graphs.append({"id": f"complete-{n}-{k}", "group": "public_regression",
                           "n": n, "edges": edges})
    return graphs


def evaluate_graph(graph: dict, plan: dict) -> dict:
    n, edges = graph["n"], graph["edges"]
    reference = exact_shortest_path(n, edges)
    if reference["status"] != "optimal":
        raise ValueError("trial requires a reachable target")
    rows, candidates = [], {}
    for solver in plan["candidate_pool"]:
        candidate = solve(n, edges, solver)
        candidates[solver] = candidate
        actual_cost = submitted_path_cost(n, edges, candidate["path"])
        for variant in plan["verifier_variants"]:
            result = check(n, edges, candidate, variant)
            regret = None if actual_cost is None else actual_cost - reference["cost"]
            accepted = result["status"] in {"accepted_by_weak_gate", "certified_optimal"}
            rows.append({"solver": solver, "verifier": variant, "result": result,
                         "independently_scored_cost": actual_cost,
                         "regret": regret, "false_accept": accepted and regret != 0,
                         "false_reject": result["status"] == "invalid_witness" and regret == 0,
                         "unverified_optimal": not accepted and regret == 0,
                         "supported_findings": (["algorithm_suboptimal"] if regret is not None and regret > 0 else [])
                         + (["verifier_false_acceptance"] if accepted and regret != 0 else [])})
    return {"graph": graph, "graph_digest": object_digest(graph), "reference": reference,
            "candidates": candidates,
            "reference_graph_validation_and_index_edges": len(edges),
            "reference_indexing_edge_visits": len(edges),
            "independent_scoring_graph_edges": len(edges) * len(candidates),
            "independent_scoring_path_edges": sum(max(0, len(candidate["path"]) - 1) for candidate in candidates.values()),
            "independent_candidate_scoring": "one graph validation/index plus path traversal per candidate; separate evaluation overhead",
            "evaluations": rows}


def run_path_trial(output: str | Path, root: Path | None = None) -> Path:
    root = root or repository_root()
    plan_path = root / "examples" / "path" / "experiment_plan.json"
    plan = read_json(plan_path)
    rows = [evaluate_graph(graph, plan) for graph in public_graphs(plan)]
    summary = {}
    for variant in plan["verifier_variants"]:
        evaluations = [value for row in rows for value in row["evaluations"]
                       if value["verifier"] == variant]
        accepted = [value for value in evaluations if value["result"]["status"] in
                    {"accepted_by_weak_gate", "certified_optimal"}]
        summary[variant] = {
            "candidate_evaluations": len(evaluations), "accepted_count": len(accepted),
            "false_accept_count": sum(value["false_accept"] for value in evaluations),
            "false_reject_count": sum(value["false_reject"] for value in evaluations),
            "unverified_optimal_count": sum(value["unverified_optimal"] for value in evaluations),
            "max_accepted_regret": max((value["regret"] for value in accepted), default=None),
        }
    repair_plan_path = root / "examples" / "path" / "witness_repair_plan.json"
    repair_plan = read_json(repair_plan_path)
    if repair_plan["baseline_summary_sha256"] != object_digest(summary):
        raise ValueError("baseline changed; the follow-up repair plan must be reconsidered")
    repairs = []
    for row in rows:
        graph = row["graph"]
        repaired = solve(graph["n"], graph["edges"], "greedy_with_potentials")
        checked = check(graph["n"], graph["edges"], repaired, "all_edges_certificate")
        actual_cost = submitted_path_cost(graph["n"], graph["edges"], repaired["path"])
        repairs.append({"graph_id": graph["id"], "candidate": repaired, "result": checked,
                        "independent_scoring_graph_edges": len(graph["edges"]),
                        "independent_scoring_path_edges": len(repaired["path"]) - 1,
                        "path_preserved": repaired["path"] == row["candidates"]["greedy_edge"]["path"],
                        "reference_regret": actual_cost - row["reference"]["cost"]})
    repair_summary = {
        "candidate_evaluations": len(repairs),
        "paths_preserved": sum(row["path_preserved"] for row in repairs),
        "certified_optimal_count": sum(row["result"]["status"] == "certified_optimal" for row in repairs),
        "false_accept_count": sum(row["result"]["status"] == "certified_optimal" and row["reference_regret"] != 0 for row in repairs),
        "unverified_optimal_count": sum(row["result"]["status"] != "certified_optimal" and row["reference_regret"] == 0 for row in repairs),
    }
    report = {
        "artifact_type": "public_path_workflow_trial", "plan_sha256": file_digest(plan_path),
        "scope": f"{len(rows)} public DAGs, two initial solvers and a witness-only follow-up; development evidence only",
        "verifier_summary": summary, "cases": rows,
        "witness_repair": {"plan_sha256": file_digest(repair_plan_path),
                           "summary": repair_summary, "cases": repairs,
                           "cost_result": "Potential generation runs the direct exact solver; this fixes certificate coverage but does not make greedy paths better or beat that solver's work."},
        "cost_boundary": "Edge counters are a cost vector; validation, indexing, candidate generation and witness production are not free. No wall-time or equal-budget effectiveness claim.",
        "iteration_result": "All-edge checks repair demonstrated weak-gate false acceptance; no efficiency benefit over direct DAG shortest-path solving is established.",
        "limitations": ["No LLM-generated algorithm or automatic verifier revision was executed.",
                        "All cases are exposed development/regression inputs, not hidden final tests.",
                        "The reference was separately authored by the same model family; this is implementation cross-checking, not fully independent evidence.",
                        "A rejected or missing certificate leaves optimality unverified; it does not prove suboptimality.",
                        "Graph omissions and real-world route validity are outside this finite mathematical goal."],
    }
    output = Path(output)
    path = output / "path_trial_report.json"
    write_json(path, report)
    write_json(output / "manifest.json", {
        "artifact_sha256": file_digest(path), "plan_sha256": file_digest(plan_path),
        "source_sha256": {name: file_digest(Path(__file__).with_name(name))
                          for name in ("path_workflow.py", "path_reference.py")},
        "repair_plan_sha256": file_digest(repair_plan_path),
        "human_acceptance": "not_requested_development_trial", "revision_applied": False,
    })
    return path
