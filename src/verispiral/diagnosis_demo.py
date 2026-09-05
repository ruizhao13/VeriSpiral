"""Finite public loss-table adapter for diagnostic experiment selection.

All tables, costs and check-factor mappings are constructed fixtures. The
controller receives only declared checks and paid observations, never labels.
Separate indicators permit simultaneous failed checks without a single-cause prior.
This module does not run an LLM or claim to simulate a real scientific domain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from pathlib import Path

from .diagnosis import choose_factor_diagnostic_action
from .pipeline import file_digest, object_digest, write_json


TEST_COSTS = {
    "implementation_match": 1,
    "cheap_matches_exact": 1,
    "repeat_stable": 2,
    "metric_rank_stable": 2,
    "search_has_support": 3,
    "fresh_suite_transfer": 4,
    "setup_transfers": 5,
}
FAULT_TEST = {
    "algorithm": "search_has_support",
    "verifier": "cheap_matches_exact",
    "setup": "setup_transfers",
    "goal": "metric_rank_stable",
    "implementation": "implementation_match",
    "noise": "repeat_stable",
    "gaming": "fresh_suite_transfer",
    "no_detected_fault": None,
}
HYPOTHESES = {
    fault: {test: test != failed_test for test in TEST_COSTS}
    for fault, failed_test in FAULT_TEST.items()
}
FACTORS = {
    "algorithm_dominated": "search_has_support",
    "verifier_disagreement": "cheap_matches_exact",
    "setup_mean_disagreement": "setup_transfers",
    "goal_rank_disagreement": "metric_rank_stable",
    "implementation_disagreement": "implementation_match",
    "replicate_disagreement": "repeat_stable",
    "fresh_mean_disagreement": "fresh_suite_transfer",
}
NEXT_ACTION = {
    "algorithm_dominated": "continue_algorithm_search",
    "verifier_disagreement": "propose_verifier_revision",
    "setup_mean_disagreement": "propose_setup_revision",
    "goal_rank_disagreement": "request_goal_metric_review",
    "implementation_disagreement": "repair_and_recompute_implementation",
    "replicate_disagreement": "collect_replicates_and_quantify_uncertainty",
    "fresh_mean_disagreement": "red_team_verifier_and_refresh_exposed_suite",
}


@dataclass(frozen=True)
class FiniteCase:
    setup: tuple[int, ...] = (2, 2, 2, 2)
    reference: tuple[int, ...] = (2, 2, 2, 2)
    fresh: tuple[int, ...] = (2, 2, 2, 2)
    comparator: tuple[int, ...] = (4, 4, 4, 4)
    cheap_indices: tuple[int, ...] = (0, 1, 2, 3)
    reported_offset: int = 0
    replicate_offsets: tuple[int, ...] = (0, 0)


def mean(values: tuple[int, ...]) -> Fraction:
    return Fraction(sum(values), len(values))


def cheap(case: FiniteCase, values: tuple[int, ...]) -> Fraction:
    return mean(tuple(values[index] for index in case.cheap_indices))


def observe(case: FiniteCase, test: str) -> dict:
    """Compute one paid test; no planted diagnosis is an input."""
    exact = mean(case.setup)
    if test == "implementation_match":
        values = (exact + case.reported_offset, exact)
    elif test == "cheap_matches_exact":
        values = (cheap(case, case.setup), exact)
    elif test == "repeat_stable":
        values = tuple(exact + offset for offset in case.replicate_offsets)
    elif test == "metric_rank_stable":
        values = (
            exact <= mean(case.comparator),
            max(case.setup) <= max(case.comparator),
        )
    elif test == "fresh_suite_transfer":
        values = (exact, mean(case.fresh))
    elif test == "setup_transfers":
        values = (exact, mean(case.reference))
    elif test == "search_has_support":
        dominated = (
            cheap(case, case.setup) > cheap(case, case.comparator)
            and exact > mean(case.comparator)
            and mean(case.reference) > mean(case.comparator)
        )
        return {"passed": not dominated, "unanimously_dominated": dominated}
    else:
        raise ValueError(f"unknown finite-adapter test: {test}")
    return {"passed": all(value == values[0] for value in values),
            "compared_values": [str(value) for value in values]}


def public_cases() -> list[tuple[str, tuple[str, ...], FiniteCase]]:
    base = FiniteCase()
    tail = (0, 0, 0, 12)
    weak = (8, 8, 8, 8)
    zero = (0, 0, 0, 0)
    # Labels are used only by the evaluation harness after a diagnosis stops.
    return [
        ("case_01", ("algorithm_dominated",), replace(base, setup=weak, reference=weak, fresh=weak)),
        ("case_02", ("verifier_disagreement",), replace(base, setup=tail, reference=tail, fresh=tail,
                                                     comparator=(2, 2, 2, 2), cheap_indices=(0, 1))),
        ("case_03", ("setup_mean_disagreement",), replace(base, setup=zero, fresh=zero, reference=weak)),
        ("case_04", ("goal_rank_disagreement",), replace(base, setup=tail, reference=tail, fresh=tail)),
        ("case_05", ("implementation_disagreement",), replace(base, reported_offset=-1)),
        ("case_06", ("replicate_disagreement",), replace(base, replicate_offsets=(0, 1))),
        ("case_07", ("fresh_mean_disagreement",), replace(base, setup=zero, reference=zero, fresh=weak)),
        ("case_08", (), base),
        ("case_09", ("implementation_disagreement", "replicate_disagreement"),
         replace(base, reported_offset=-1, replicate_offsets=(0, 1))),
        ("case_10", ("fresh_mean_disagreement", "verifier_disagreement"),
         replace(base, setup=tail, reference=tail, fresh=weak,
                 comparator=(2, 2, 2, 2), cheap_indices=(0, 1))),
    ]

def diagnose_case(case: FiniteCase, budget: int = 18) -> dict:
    observations: dict[str, bool] = {}
    trace = []
    remaining = budget
    while True:
        decision = choose_factor_diagnostic_action(FACTORS, TEST_COSTS, observations, remaining)
        if decision["status"] != "test_proposed":
            break
        test = decision["proposed_test"]
        result = observe(case, test)
        remaining -= decision["cost"]
        observations[test] = result["passed"]
        trace.append({"test": test, "selection": decision, "result": result,
                      "remaining_budget": remaining})
    supported = decision["supported_factors"]
    actions = [NEXT_ACTION[factor] for factor in supported]
    if decision["status"] != "diagnosis_supported":
        actions.append("collect_evidence_for_pending_checks")
    elif not actions:
        actions.append("report_scoped_checks_only")
    return {
        "case_digest": object_digest(asdict(case)),
        "trace": trace, "decision": decision, "budget_spent": budget - remaining,
        "next_action_proposals": actions, "revision_applied": False,
        "scientific_claim_accepted": False,
    }


def verifier_comparison() -> dict:
    """Compare two prewritten verifier mechanisms on a fixed finite candidate set."""
    candidates = {"stable": (2, 2, 2, 2), "tail_failure": (0, 0, 0, 12),
                  "weak": (8, 8, 8, 8)}
    gold = {name: mean(values) for name, values in candidates.items()}
    acceptable = {name for name, score in gold.items() if score <= 2}
    rows = []
    for name, indices, build_cost in (("prefix_screen", (0, 1), 1),
                                      ("exact_enumeration", (0, 1, 2, 3), 6)):
        scores = {key: mean(tuple(values[i] for i in indices))
                  for key, values in candidates.items()}
        selected = min(scores, key=lambda key: (scores[key], key))
        accepted = {key for key, score in scores.items() if score <= 2}
        rows.append({
            "verifier": name, "selected_candidate": selected,
            "scores": {key: str(score) for key, score in scores.items()},
            "reference_regret_of_selected": str(gold[selected] - min(gold.values())),
            "false_promotions": sorted(accepted - acceptable),
            "false_rejections": sorted(acceptable - accepted),
            "build_cost_units": build_cost, "call_cost_units": len(indices),
            "planned_calls": 100,
            "amortized_cost_units": str(Fraction(build_cost, 100) + len(indices)),
        })
    return {"candidate_losses": candidates, "acceptance_threshold": 2,
            "reference_scores": {key: str(score) for key, score in gold.items()},
            "cost_basis": "declared illustrative units, not measured runtime",
            "call_definition": "one candidate evaluation; 100 planned calls, not 100 executed trials",
            "comparison_boundary": "exact verifier equals the reference by construction; not an equal-budget study",
            "construction_status": "two prewritten mechanisms; no verifier synthesis executed",
            "rows": rows}


def run_diagnosis_demo(output: str | Path) -> Path:
    results = []
    for case_id, labels, case in public_cases():
        result = diagnose_case(case)
        result.update({"case_id": case_id, "fixture": asdict(case),
                       "planted_factors_for_scoring_only": sorted(labels),
                       "matches_planted_factors": result["decision"]["supported_factors"] == sorted(labels)})
        results.append(result)
    report = {
        "artifact_type": "finite_diagnosis_report", "schema_version": "2.0",
        "scope": "public finite loss tables and separately observable failed-check indicators",
        "limitations": [
            "Not real-world validation, causal identification, or learned resource allocation.",
            "All cases and tests are public; there is no hidden or independent final holdout.",
            "Indicators support simultaneous observed check failures, not their causes or interactions.",
            "Unknown or mean-preserving faults invisible to these checks may remain after coverage.",
            "Equality checks and fixed replicate offsets do not quantify sampling uncertainty.",
            "The reference is an exact finite-table average, not a real scientific oracle.",
        ],
        "factor_checks": FACTORS, "test_cost_units": TEST_COSTS,
        "selection_rule": "least-cost unobserved check, then identifier; all registered checks required",
        "legacy_single_fault_predictions": HYPOTHESES,
        "diagnostic_cases": results,
        "budget_limited_case": diagnose_case(public_cases()[0][2], budget=1),
        "verifier_comparison": verifier_comparison(),
    }
    output = Path(output)
    path = output / "diagnosis_report.json"
    write_json(path, report)
    write_json(output / "manifest.json", {
        "artifact_type": "finite_diagnosis_manifest", "schema_version": "2.0",
        "artifacts": {path.name: file_digest(path)},
        "sources": {name: file_digest(Path(__file__).with_name(name))
                    for name in ("diagnosis.py", "diagnosis_demo.py")},
        "scientific_claim_accepted": False,
    })
    return path
