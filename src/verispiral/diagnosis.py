"""Select checks in explicit finite signature or independent indicator models.

Hypotheses are supplied predictions, not evidence or calibrated probabilities.
The controller sees observed check outcomes but never a fixture's hidden cause.
Even a uniquely supported hypothesis is conditional on the supplied signatures;
it does not establish a causal explanation outside that model.
"""

from __future__ import annotations

from fractions import Fraction

from .pipeline import PipelineError


def _require_named_dict(value: object, label: str, *, nonempty: bool) -> None:
    if not isinstance(value, dict) or (nonempty and not value):
        qualifier = "nonempty " if nonempty else ""
        raise PipelineError(f"{label} must be a {qualifier}dictionary")
    if any(not isinstance(key, str) or not key for key in value):
        raise PipelineError(f"{label} identifiers must be nonempty strings")


def choose_diagnostic_action(
    hypotheses: dict[str, dict[str, bool]],
    tests: dict[str, int],
    observations: dict[str, bool],
    remaining_budget: int,
) -> dict:
    """Propose an affordable check or return an explicit stopping condition.

    Each hypothesis must predict every test's boolean outcome. Observations
    filter inconsistent hypotheses; identical signatures are allowed and can
    leave the diagnosis inconclusive. With equal weights on the survivors, a
    check's score is its expected number of eliminations divided by its cost:
    ``(n - sum(bucket_size ** 2) / n) / cost``. The ``information_gain`` output
    is that exact rational score, not Shannon information or a learned posterior.
    Ties prefer lower cost, then lexicographically smaller test identifiers.

    The caller executes the proposal and accounts for its cost before calling
    again. This pure function neither spends budget nor changes its inputs.
    ``diagnosis_supported`` requires every registered check to have been observed
    and exactly one consistent survivor. A singleton still needs coverage checks;
    zero-score checks can disconfirm the model even when they cannot split it.
    Invalid inputs raise :class:`PipelineError`.
    """
    _require_named_dict(hypotheses, "hypotheses", nonempty=True)
    _require_named_dict(tests, "tests", nonempty=True)
    _require_named_dict(observations, "observations", nonempty=False)
    if type(remaining_budget) is not int or remaining_budget < 0:
        raise PipelineError("remaining_budget must be a nonnegative integer")
    if any(type(cost) is not int or cost <= 0 for cost in tests.values()):
        raise PipelineError("test costs must be positive integers")
    for hypothesis_id, predictions in hypotheses.items():
        _require_named_dict(predictions, f"hypothesis {hypothesis_id}", nonempty=True)
        if predictions.keys() != tests.keys():
            raise PipelineError(f"hypothesis {hypothesis_id} must predict every test exactly")
        if any(type(outcome) is not bool for outcome in predictions.values()):
            raise PipelineError(f"hypothesis {hypothesis_id} predictions must be booleans")
    if not observations.keys() <= tests.keys():
        raise PipelineError("observations contain unknown tests")
    if any(type(outcome) is not bool for outcome in observations.values()):
        raise PipelineError("observations must be booleans")

    remaining = sorted(
        hypothesis_id
        for hypothesis_id, predictions in hypotheses.items()
        if all(predictions[test_id] == outcome for test_id, outcome in observations.items())
    )

    pending = sorted(tests.keys() - observations.keys())

    def result(status: str, test_id: str | None = None, score: Fraction = Fraction(0)) -> dict:
        return {
            "status": status,
            "remaining_hypotheses": remaining,
            "pending_tests": pending,
            "coverage_checked": not pending,
            "proposed_test": test_id,
            "information_gain": str(score),
            "cost": tests[test_id] if test_id is not None else 0,
        }

    if not remaining:
        return result("model_mismatch")
    if not pending:
        return result("diagnosis_supported" if len(remaining) == 1 else "inconclusive")

    candidates: list[tuple[Fraction, int, str]] = []
    n = len(remaining)
    for test_id, cost in tests.items():
        if test_id in observations:
            continue
        positives = sum(hypotheses[hypothesis_id][test_id] for hypothesis_id in remaining)
        negatives = n - positives
        score = Fraction(2 * positives * negatives, n * cost)
        if cost <= remaining_budget:
            candidates.append((-score, cost, test_id))

    if not candidates:
        return result("budget_exhausted")
    negative_score, _, proposed_test = min(candidates)
    return result("test_proposed", proposed_test, -negative_score)


FACTOR_LIMITATIONS = [
    "Supported factors are explicit failed-check indicators, not identified causes.",
    "Coverage is limited to registered checks; unknown or check-invisible faults may remain.",
    "No joint outcome signature or interaction is inferred from individual factors.",
]


def choose_factor_diagnostic_action(
    factors: dict[str, str],
    tests: dict[str, int],
    observations: dict[str, bool],
    remaining_budget: int,
) -> dict:
    """Observe separately registered failure indicators without a single-cause prior.

    Each factor names a distinct check: an observed ``False`` supports that
    narrow indicator, ``True`` clears it for this observation, and an unobserved
    check leaves it unresolved. These are separately observable predicates, not
    an assumption of statistical independence or causal superposition. The caller
    must supply complete joint signatures to ``choose_diagnostic_action`` if
    factors predict interactions or depend on combinations of check outcomes.

    Choose the cheapest affordable unobserved check, breaking ties by identifier.
    Extra registered checks are allowed and must also be observed for completion.
    This pure function does not execute checks or consume budget.
    """
    _require_named_dict(factors, "factors", nonempty=True)
    _require_named_dict(tests, "tests", nonempty=True)
    _require_named_dict(observations, "observations", nonempty=False)
    if type(remaining_budget) is not int or remaining_budget < 0:
        raise PipelineError("remaining_budget must be a nonnegative integer")
    if any(type(cost) is not int or cost <= 0 for cost in tests.values()):
        raise PipelineError("test costs must be positive integers")
    if any(not isinstance(test, str) or test not in tests for test in factors.values()):
        raise PipelineError("each factor must map to a registered test")
    if len(set(factors.values())) != len(factors):
        raise PipelineError("each factor must map to a distinct test")
    if not observations.keys() <= tests.keys():
        raise PipelineError("observations contain unknown tests")
    if any(type(outcome) is not bool for outcome in observations.values()):
        raise PipelineError("observations must be booleans")

    pending = sorted(tests.keys() - observations.keys())
    affordable = [(tests[test], test) for test in pending if tests[test] <= remaining_budget]
    proposed = min(affordable)[1] if affordable else None
    status = ("diagnosis_supported" if not pending else
              "test_proposed" if proposed is not None else "budget_exhausted")
    return {
        "status": status,
        "supported_factors": sorted(factor for factor, test in factors.items()
                                    if observations.get(test) is False),
        "cleared_factors": sorted(factor for factor, test in factors.items()
                                  if observations.get(test) is True),
        "unresolved_factors": sorted(factor for factor, test in factors.items()
                                     if test not in observations),
        "pending_tests": pending,
        "coverage_checked": not pending,
        "proposed_test": proposed,
        "cost": tests[proposed] if proposed is not None else 0,
        "selection_reason": "least_cost_unobserved_check" if proposed is not None else None,
        "limitations": list(FACTOR_LIMITATIONS),
    }
