"""Deterministic scope and rate-algebra checks for registered theory certificates.

This module does not prove an upper or lower bound.  It checks whether supplied
certificates describe the same problem, whether their registered assumptions
match a fixed target, and whether their declared monomial/log-rate exponents
are algebraically compatible.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence


SIGNATURE_FIELDS = (
    "observation_model",
    "parameter_class",
    "loss",
    "algorithm_class",
    "regime",
)
VERIFICATION_SCOPE = (
    "Checks registered certificate scope, assumptions, and polynomial/log-rate "
    "algebra only; it does not re-prove either theorem."
)
SOURCE_VERIFICATION_BOUNDARY = (
    "Source metadata and certificate extracts are registered public-demo records; "
    "source text and proofs are not fetched or verified by this program, and human "
    "review remains required."
)


class MinimaxScenarioError(ValueError):
    """Raised when a scenario is malformed or internally ambiguous."""


@dataclass(frozen=True)
class MinimaxRunResult:
    output_dir: Path
    evolution_trace: Path
    assumption_branches: Path
    insight_ledger: Path
    manifest: Path
    final_status: str


def _reject_duplicate_object_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MinimaxScenarioError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MinimaxScenarioError(f"{label} must be an object")
    return dict(value)


def _string(value: Any, label: str, min_length: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < min_length:
        raise MinimaxScenarioError(
            f"{label} must be a string with at least {min_length} characters"
        )
    return value


def _require_exact_keys(
    value: Mapping[str, Any], required: set[str], label: str
) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing or extra:
        raise MinimaxScenarioError(
            f"{label} must contain exactly {sorted(required)}; "
            f"missing={missing}, extra={extra}"
        )


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return result or "minimax-scenario"


def _signature(value: Any, label: str) -> dict[str, str]:
    raw = _mapping(value, label)
    missing = sorted(set(SIGNATURE_FIELDS) - set(raw))
    extra = sorted(set(raw) - set(SIGNATURE_FIELDS))
    if missing or extra:
        raise MinimaxScenarioError(
            f"{label} must contain exactly {SIGNATURE_FIELDS}; "
            f"missing={missing}, extra={extra}"
        )
    return {
        field: _string(raw[field], f"{label}.{field}", 3)
        for field in SIGNATURE_FIELDS
    }


def _assumptions(value: Any, label: str) -> dict[str, Any]:
    raw = _mapping(value, label)
    if not raw:
        raise MinimaxScenarioError(f"{label} must not be empty")
    normalized: dict[str, Any] = {}
    for key, item in raw.items():
        if not isinstance(key, str) or not key:
            raise MinimaxScenarioError(f"{label} has an invalid key")
        if not isinstance(item, (str, int, bool)) or isinstance(item, float):
            raise MinimaxScenarioError(
                f"{label}.{key} must be a string, integer, or boolean"
            )
        normalized[key] = item
    return dict(sorted(normalized.items()))


def _fraction(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise MinimaxScenarioError(f"{label} must be an integer or rational string")
    if isinstance(value, str) and re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?", value) is None:
        raise MinimaxScenarioError(
            f"{label} must use canonical integer or numerator/denominator syntax"
        )
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise MinimaxScenarioError(f"{label} is not a valid rational exponent") from exc
    return result


def _rate(value: Any, label: str) -> dict[str, dict[str, Fraction]]:
    raw = _mapping(value, label)
    required = {"polynomial_exponents", "log_exponents"}
    _require_exact_keys(raw, required, label)
    result: dict[str, dict[str, Fraction]] = {}
    for family in ("polynomial_exponents", "log_exponents"):
        exponents = _mapping(raw[family], f"{label}.{family}")
        parsed: dict[str, Fraction] = {}
        for variable, exponent in exponents.items():
            if (
                not isinstance(variable, str)
                or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", variable) is None
            ):
                raise MinimaxScenarioError(f"{label}.{family} has an invalid variable")
            parsed[variable] = _fraction(exponent, f"{label}.{family}.{variable}")
        result[family] = dict(sorted(parsed.items()))
    if not result["polynomial_exponents"]:
        raise MinimaxScenarioError(f"{label}.polynomial_exponents must not be empty")
    return result


def _source_registry(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise MinimaxScenarioError("scenario.source_registry must be a non-empty list")
    required = {
        "source_id",
        "title",
        "url",
        "locator",
        "registration_status",
        "proof_status",
    }
    registry: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        label = f"scenario.source_registry[{index}]"
        raw = _mapping(item, label)
        _require_exact_keys(raw, required, label)
        source_id = _string(raw["source_id"], f"{label}.source_id", 3)
        if source_id in seen:
            raise MinimaxScenarioError(f"duplicate source_id: {source_id}")
        seen.add(source_id)
        if raw["registration_status"] != "registered_public_extract":
            raise MinimaxScenarioError(
                f"{label}.registration_status must be 'registered_public_extract'"
            )
        if raw["proof_status"] != "cited_not_reproved":
            raise MinimaxScenarioError(
                f"{label}.proof_status must be 'cited_not_reproved'"
            )
        url = _string(raw["url"], f"{label}.url", 8)
        if not url.startswith("https://"):
            raise MinimaxScenarioError(f"{label}.url must use https")
        registry.append(
            {
                "source_id": source_id,
                "title": _string(raw["title"], f"{label}.title", 8),
                "url": url,
                "locator": _string(raw["locator"], f"{label}.locator", 3),
                "registration_status": "registered_public_extract",
                "proof_status": "cited_not_reproved",
            }
        )
    return sorted(registry, key=lambda item: item["source_id"])


def _certificate(
    value: Any,
    expected_kind: str,
    label: str,
    registered_source_ids: set[str],
) -> dict[str, Any]:
    raw = _mapping(value, label)
    required = {
        "certificate_id",
        "kind",
        "registered",
        "source_id",
        "theorem_locator",
        "extraction_note",
        "problem_signature",
        "assumptions",
        "rate",
    }
    _require_exact_keys(raw, required, label)
    kind = _string(raw["kind"], f"{label}.kind")
    if kind != expected_kind:
        raise MinimaxScenarioError(f"{label}.kind must be {expected_kind!r}")
    if raw["registered"] is not True:
        raise MinimaxScenarioError(
            f"{label} must be explicitly registered before algebraic verification"
        )
    source_id = _string(raw["source_id"], f"{label}.source_id", 3)
    if source_id not in registered_source_ids:
        raise MinimaxScenarioError(
            f"{label}.source_id references unknown source_id {source_id!r}"
        )
    return {
        "certificate_id": _string(
            raw["certificate_id"], f"{label}.certificate_id", 3
        ),
        "kind": kind,
        "registered": True,
        "source_id": source_id,
        "theorem_locator": _string(
            raw["theorem_locator"], f"{label}.theorem_locator", 3
        ),
        "extraction_note": _string(
            raw["extraction_note"], f"{label}.extraction_note", 12
        ),
        "problem_signature": _signature(
            raw["problem_signature"], f"{label}.problem_signature"
        ),
        "assumptions": _assumptions(raw["assumptions"], f"{label}.assumptions"),
        "rate": _rate(raw["rate"], f"{label}.rate"),
    }


def _assumption_order(value: Any) -> dict[str, tuple[Any, ...]]:
    raw = _mapping(value, "assumption_order")
    if not raw:
        raise MinimaxScenarioError("assumption_order must not be empty")
    result: dict[str, tuple[Any, ...]] = {}
    for key, ordered_values in raw.items():
        if not isinstance(key, str) or not key:
            raise MinimaxScenarioError("assumption_order has an invalid key")
        if not isinstance(ordered_values, list) or len(ordered_values) < 2:
            raise MinimaxScenarioError(
                f"assumption_order.{key} must be a list with at least two values"
            )
        if any(
            not isinstance(item, (str, int, bool)) or isinstance(item, float)
            for item in ordered_values
        ):
            raise MinimaxScenarioError(
                f"assumption_order.{key} values must be strings, integers, or booleans"
            )
        encoded = [json.dumps(item, sort_keys=True) for item in ordered_values]
        if len(encoded) != len(set(encoded)):
            raise MinimaxScenarioError(f"assumption_order.{key} contains duplicates")
        result[key] = tuple(ordered_values)
    return dict(sorted(result.items()))


def _load_scenario(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            raw = json.load(handle, object_pairs_hook=_reject_duplicate_object_keys)
    except json.JSONDecodeError as exc:
        raise MinimaxScenarioError(f"invalid scenario JSON: {exc}") from exc
    scenario = _mapping(raw, "scenario")
    required = {
        "schema_version",
        "scenario_id",
        "problem_signature",
        "target_assumptions",
        "assumption_order",
        "source_registry",
        "lower_certificate",
        "rounds",
    }
    _require_exact_keys(scenario, required, "scenario")
    if scenario["schema_version"] != "1.0":
        raise MinimaxScenarioError("scenario.schema_version must be '1.0'")

    source_registry = _source_registry(scenario["source_registry"])
    registered_source_ids = {item["source_id"] for item in source_registry}

    rounds_raw = scenario["rounds"]
    if not isinstance(rounds_raw, list) or not rounds_raw:
        raise MinimaxScenarioError("scenario.rounds must be a non-empty list")
    rounds: list[dict[str, Any]] = []
    for expected_index, value in enumerate(rounds_raw, start=1):
        item = _mapping(value, f"rounds[{expected_index - 1}]")
        round_required = {
            "round_index",
            "candidate_id",
            "candidate_label",
            "algorithm_change",
            "search_hypothesis",
            "upper_certificate",
        }
        _require_exact_keys(item, round_required, f"rounds[{expected_index - 1}]")
        round_index = item["round_index"]
        if (
            isinstance(round_index, bool)
            or not isinstance(round_index, int)
            or round_index != expected_index
        ):
            raise MinimaxScenarioError(
                "round_index values must be consecutive integers starting at 1"
            )
        rounds.append(
            {
                "round_index": expected_index,
                "candidate_id": _string(
                    item["candidate_id"],
                    f"rounds[{expected_index - 1}].candidate_id",
                    3,
                ),
                "candidate_label": _string(
                    item["candidate_label"],
                    f"rounds[{expected_index - 1}].candidate_label",
                    3,
                ),
                "algorithm_change": _string(
                    item["algorithm_change"],
                    f"rounds[{expected_index - 1}].algorithm_change",
                    8,
                ),
                "search_hypothesis": _string(
                    item["search_hypothesis"],
                    f"rounds[{expected_index - 1}].search_hypothesis",
                    8,
                ),
                "upper_certificate": _certificate(
                    item["upper_certificate"],
                    "upper",
                    f"rounds[{expected_index - 1}].upper_certificate",
                    registered_source_ids,
                ),
            }
        )

    return {
        "schema_version": "1.0",
        "scenario_id": _string(
            scenario["scenario_id"], "scenario.scenario_id", 3
        ),
        "problem_signature": _signature(
            scenario["problem_signature"], "scenario.problem_signature"
        ),
        "target_assumptions": _assumptions(
            scenario["target_assumptions"], "scenario.target_assumptions"
        ),
        "source_registry": source_registry,
        "assumption_order": _assumption_order(scenario["assumption_order"]),
        "lower_certificate": _certificate(
            scenario["lower_certificate"],
            "lower",
            "scenario.lower_certificate",
            registered_source_ids,
        ),
        "rounds": rounds,
    }


def _mapping_diff(
    expected: Mapping[str, Any], actual: Mapping[str, Any], value_labels: tuple[str, str]
) -> list[dict[str, Any]]:
    left_label, right_label = value_labels
    differences: list[dict[str, Any]] = []
    for key in sorted(set(expected) | set(actual)):
        left_present = key in expected
        right_present = key in actual
        left = expected.get(key)
        right = actual.get(key)
        if left_present != right_present or left != right:
            differences.append(
                {
                    "field": key,
                    f"{left_label}_present": left_present,
                    f"{left_label}_value": left,
                    f"{right_label}_present": right_present,
                    f"{right_label}_value": right,
                }
            )
    return differences


def _fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _rate_json(rate: Mapping[str, Mapping[str, Fraction]]) -> dict[str, dict[str, str]]:
    return {
        family: {variable: _fraction_text(exponent) for variable, exponent in values.items()}
        for family, values in rate.items()
    }


def compare_rate_algebra(
    upper: Mapping[str, Mapping[str, Fraction]],
    lower: Mapping[str, Mapping[str, Fraction]],
) -> dict[str, Any]:
    """Compare registered monomial/log exponents using exact rational arithmetic."""

    deltas: dict[str, dict[str, Fraction]] = {}
    for family in ("polynomial_exponents", "log_exponents"):
        variables = sorted(set(upper[family]) | set(lower[family]))
        deltas[family] = {
            variable: upper[family].get(variable, Fraction(0))
            - lower[family].get(variable, Fraction(0))
            for variable in variables
        }

    variables = sorted(
        set(deltas["polynomial_exponents"]) | set(deltas["log_exponents"])
    )
    coordinate_signs: dict[str, int] = {}
    for variable in variables:
        polynomial_delta = deltas["polynomial_exponents"].get(
            variable, Fraction(0)
        )
        log_delta = deltas["log_exponents"].get(variable, Fraction(0))
        decisive_delta = polynomial_delta if polynomial_delta else log_delta
        coordinate_signs[variable] = (decisive_delta > 0) - (decisive_delta < 0)

    has_negative = any(value < 0 for value in coordinate_signs.values())
    has_positive = any(value > 0 for value in coordinate_signs.values())
    has_positive_polynomial = any(
        deltas["polynomial_exponents"].get(variable, Fraction(0)) > 0
        for variable, sign in coordinate_signs.items()
        if sign > 0
    )

    if has_negative and has_positive:
        status = "not_comparable"
        reason = (
            "registered rate factors have mixed coordinatewise upper-minus-lower "
            "directions, so neither rate dominates without a joint growth regime"
        )
    elif has_negative:
        status = "certificate_conflict"
        reason = (
            "registered upper rate is coordinatewise below the lower certificate"
        )
    elif has_positive_polynomial:
        status = "polynomial_gap"
        reason = "registered upper certificate has an excess polynomial factor"
    elif has_positive:
        status = "log_gap"
        reason = "polynomial exponents match but the upper certificate has an excess log factor"
    else:
        status = "minimax_rate_match"
        reason = "registered upper and lower polynomial/log exponents match exactly"

    return {
        "status": status,
        "reason": reason,
        "upper": _rate_json(upper),
        "lower": _rate_json(lower),
        "delta_upper_minus_lower": {
            family: {
                variable: _fraction_text(exponent)
                for variable, exponent in values.items()
            }
            for family, values in deltas.items()
        },
    }


def _classify_assumption_change(
    key: str,
    old: Any,
    new: Any,
    orders: Mapping[str, Sequence[Any]],
) -> str:
    order = orders.get(key)
    if order is None or old not in order or new not in order:
        return "unclassified_change"
    old_index = order.index(old)
    new_index = order.index(new)
    if new_index > old_index:
        return "strengthening"
    if new_index < old_index:
        return "weakening"
    return "unchanged"


def _canonical_default(value: Any) -> str:
    if isinstance(value, Fraction):
        return _fraction_text(value)
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_canonical_default,
    ).encode("utf-8")


def _object_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _insight_for_round(round_result: Mapping[str, Any]) -> tuple[str, str, str]:
    status = round_result["status"]
    rate_status = round_result["rate_check"]["status"]
    assumption_status = round_result["assumption_check"]["status"]
    if status == "certificate_conflict":
        return (
            "certificate_conflict",
            "Registered same-scope certificates conflict in exact rate algebra; no minimax conclusion is recorded.",
            "Repair or withdraw the conflicting certificate before proposing another algorithm change.",
        )
    if assumption_status == "assumption_mismatch" and rate_status == "minimax_rate_match":
        return (
            "rate_match_on_incompatible_assumption_branch",
            "Rate exponents match algebraically only on a non-target assumption branch; the target remains unchanged.",
            "Keep the restricted branch separate and search for a registered upper certificate that restores the target assumptions.",
        )
    if status == "log_gap":
        return (
            "registered_log_gap",
            "Registered polynomial exponents match while an excess logarithmic exponent remains.",
            "Search for an algorithmic mechanism that removes the positive log exponent without changing the target signature or assumptions.",
        )
    if status == "minimax_rate_match":
        return (
            "target_scope_rate_match",
            "Registered upper and lower rate exponents match on the original target signature and assumptions.",
            "Freeze the rate-match packet and request human review of the certificate extraction, constants, and omitted lower-order terms.",
        )
    if status == "polynomial_gap":
        return (
            "registered_polynomial_gap",
            "The registered upper certificate retains an excess polynomial exponent.",
            "Identify which algorithmic term creates the polynomial gap before changing the target assumptions.",
        )
    if rate_status == "not_comparable" and assumption_status == "match":
        return (
            "not_comparable",
            "Mixed exponent directions prevent a coordinatewise rate ordering on the registered target scope.",
            "Register a joint asymptotic regime or another comparison rule before drawing a rate conclusion.",
        )
    return (
        "not_comparable",
        "The registered certificate scope is not comparable with the fixed target.",
        "Resolve the first scope mismatch or create an explicitly separate research branch.",
    )


def evaluate_minimax_scenario(scenario: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scenario_id = scenario["scenario_id"]
    scenario_slug = _slug(scenario_id)
    target_signature = scenario["problem_signature"]
    target_assumptions = scenario["target_assumptions"]
    lower = scenario["lower_certificate"]
    orders = scenario["assumption_order"]

    certificates = [lower] + [item["upper_certificate"] for item in scenario["rounds"]]
    certificate_ids = [certificate["certificate_id"] for certificate in certificates]
    if len(certificate_ids) != len(set(certificate_ids)):
        duplicates = sorted(
            certificate_id
            for certificate_id in set(certificate_ids)
            if certificate_ids.count(certificate_id) > 1
        )
        raise MinimaxScenarioError(f"duplicate certificate_id values: {duplicates}")
    certificate_inventory = [
        {
            "certificate_id": certificate["certificate_id"],
            "kind": certificate["kind"],
            "source_id": certificate["source_id"],
            "theorem_locator": certificate["theorem_locator"],
            "extraction_note": certificate["extraction_note"],
        }
        for certificate in certificates
    ]

    target_branch_id = f"{scenario_slug}-target-v1"
    branches: list[dict[str, Any]] = [
        {
            "branch_id": target_branch_id,
            "version": 1,
            "kind": "target",
            "parent_branch_id": None,
            "assumptions": target_assumptions,
            "active_target": True,
            "merge_status": "authoritative_target",
        }
    ]
    patches: list[dict[str, Any]] = []
    round_results: list[dict[str, Any]] = []
    previous_branch_id = target_branch_id

    lower_target_signature_diff = _mapping_diff(
        target_signature, lower["problem_signature"], ("target", "lower")
    )
    lower_target_assumption_diff = _mapping_diff(
        target_assumptions, lower["assumptions"], ("target", "lower")
    )

    for item in scenario["rounds"]:
        upper = item["upper_certificate"]
        target_upper_signature_diff = _mapping_diff(
            target_signature, upper["problem_signature"], ("target", "upper")
        )
        upper_lower_signature_diff = _mapping_diff(
            lower["problem_signature"], upper["problem_signature"], ("lower", "upper")
        )
        target_upper_assumption_diff = _mapping_diff(
            target_assumptions, upper["assumptions"], ("target", "upper")
        )
        upper_lower_assumption_diff = _mapping_diff(
            lower["assumptions"], upper["assumptions"], ("lower", "upper")
        )

        signatures_match_target = not (
            lower_target_signature_diff or target_upper_signature_diff
        )
        assumptions_match_target = not (
            lower_target_assumption_diff or target_upper_assumption_diff
        )
        signature_check = {
            "status": "match" if signatures_match_target else "signature_mismatch",
            "target_vs_lower": lower_target_signature_diff,
            "target_vs_upper": target_upper_signature_diff,
            "lower_vs_upper": upper_lower_signature_diff,
        }
        assumption_check = {
            "status": "match" if assumptions_match_target else "assumption_mismatch",
            "target_vs_lower": lower_target_assumption_diff,
            "target_vs_upper": target_upper_assumption_diff,
            "lower_vs_upper": upper_lower_assumption_diff,
        }

        if upper_lower_signature_diff:
            rate_check = {
                "status": "not_comparable",
                "reason": "upper and lower certificates have different problem signatures",
                "upper": _rate_json(upper["rate"]),
                "lower": _rate_json(lower["rate"]),
                "delta_upper_minus_lower": {},
            }
            certificate_status = "scope_incompatible"
        else:
            rate_check = compare_rate_algebra(upper["rate"], lower["rate"])
            if upper_lower_assumption_diff:
                certificate_status = "scope_incompatible"
            elif rate_check["status"] == "certificate_conflict":
                certificate_status = "certificate_conflict"
            elif rate_check["status"] == "not_comparable":
                certificate_status = "rate_incomparable"
            else:
                certificate_status = "consistent"

        scope_comparability = (
            "comparable"
            if signatures_match_target and assumptions_match_target
            else "not_comparable"
        )
        comparability = (
            "not_comparable"
            if rate_check["status"] == "not_comparable"
            else scope_comparability
        )
        if certificate_status == "certificate_conflict":
            overall_status = "certificate_conflict"
        elif comparability == "not_comparable" or rate_check["status"] == "not_comparable":
            overall_status = "not_comparable"
        else:
            overall_status = rate_check["status"]

        branch_id = target_branch_id
        patch_id: str | None = None
        if target_upper_assumption_diff:
            patch_version = len(patches) + 1
            patch_id = f"{scenario_slug}-assumption-patch-v{patch_version}"
            branch_id = f"{scenario_slug}-candidate-assumptions-v{patch_version}"
            changes: list[dict[str, Any]] = []
            for difference in target_upper_assumption_diff:
                key = difference["field"]
                old = difference["target_value"]
                new = difference["upper_value"]
                changes.append(
                    {
                        "field": key,
                        "from_present": difference["target_present"],
                        "from_value": old,
                        "to_present": difference["upper_present"],
                        "to_value": new,
                        "relation": _classify_assumption_change(key, old, new, orders),
                    }
                )
            relations = {change["relation"] for change in changes}
            classification = next(iter(relations)) if len(relations) == 1 else "mixed_change"
            patch = {
                "patch_id": patch_id,
                "version": patch_version,
                "operation": "create_candidate_branch",
                "classification": classification,
                "round_index": item["round_index"],
                "candidate_id": item["candidate_id"],
                "base_branch_id": target_branch_id,
                "new_branch_id": branch_id,
                "changes": changes,
                "unchanged_assumptions": {
                    key: value
                    for key, value in target_assumptions.items()
                    if key in upper["assumptions"]
                    and upper["assumptions"][key] == value
                },
                "candidate_certificate_sha256": _object_digest(upper),
                "invalidated_target_conclusions": [
                    "A rate match on this branch cannot certify minimax rate matching for the authoritative target."
                ],
                "new_obligations": [
                    "Supply a target-compatible upper certificate before any target-branch promotion; bridge inputs are outside this public runner."
                ],
                "human_review_required": True,
                "target_mutated": False,
                "merge_status": "not_merged",
            }
            patches.append(patch)
            branches.append(
                {
                    "branch_id": branch_id,
                    "version": patch_version,
                    "kind": "candidate_assumption_branch",
                    "parent_branch_id": target_branch_id,
                    "assumptions": upper["assumptions"],
                    "active_target": False,
                    "merge_status": "not_merged",
                    "created_by_patch": patch_id,
                    "round_index": item["round_index"],
                }
            )

        if branch_id != target_branch_id:
            branch_transition = "branched_without_target_mutation"
        elif previous_branch_id != target_branch_id:
            branch_transition = "returned_to_target"
        else:
            branch_transition = "stayed_on_target"
        previous_branch_id = branch_id

        round_result = {
            "round_index": item["round_index"],
            "candidate_id": item["candidate_id"],
            "candidate_label": item["candidate_label"],
            "algorithm_change": item["algorithm_change"],
            "search_hypothesis": item["search_hypothesis"],
            "upper_certificate_id": upper["certificate_id"],
            "lower_certificate_id": lower["certificate_id"],
            "signature_check": signature_check,
            "assumption_check": assumption_check,
            "certificate_status": certificate_status,
            "comparability": comparability,
            "rate_check": rate_check,
            "rate_algebra_applicable_to_target": comparability == "comparable",
            "assumption_branch_id": branch_id,
            "assumption_patch_id": patch_id,
            "branch_transition": branch_transition,
            "status": overall_status,
        }
        round_results.append(round_result)

    final_round = round_results[-1]
    if final_round["status"] == "minimax_rate_match":
        final_claim_boundary = (
            "Rate match under registered certificates; theorem proofs, source extraction, "
            "constants, and omitted lower-order terms are not machine-verified."
        )
    else:
        final_claim_boundary = (
            f"No target-scope minimax rate match is recorded; final verifier status is "
            f"{final_round['status']}. Theorem proofs and source extraction are not "
            "machine-verified."
        )

    evolution_trace = {
        "schema_version": "1.0",
        "trace_id": f"{scenario_slug}-evolution-trace-v1",
        "scenario_id": scenario_id,
        "verification_scope": VERIFICATION_SCOPE,
        "source_verification_boundary": SOURCE_VERIFICATION_BOUNDARY,
        "source_review_status": "human_review_required",
        "source_registry": scenario["source_registry"],
        "certificate_inventory": certificate_inventory,
        "problem_signature": target_signature,
        "target_assumptions": target_assumptions,
        "lower_certificate_id": lower["certificate_id"],
        "rounds": round_results,
        "final": {
            "round_index": final_round["round_index"],
            "candidate_id": final_round["candidate_id"],
            "status": final_round["status"],
            "assumption_branch_id": final_round["assumption_branch_id"],
            "original_target_preserved": True,
            "human_review_required": True,
            "claim_boundary": final_claim_boundary,
        },
    }
    assumption_branches = {
        "schema_version": "1.0",
        "scenario_id": scenario_id,
        "verification_scope": VERIFICATION_SCOPE,
        "target_branch_id": target_branch_id,
        "branches": branches,
        "patches": patches,
        "invariants": {
            "target_mutated": False,
            "strengthening_requires_new_branch": True,
            "candidate_branch_auto_merged": False,
        },
    }

    entries: list[dict[str, Any]] = []
    for index, round_result in enumerate(round_results, start=1):
        kind, summary, next_search_action = _insight_for_round(round_result)
        entries.append(
            {
                "sequence": index,
                "insight_id": f"{scenario_slug}-insight-{index:03d}",
                "round_index": round_result["round_index"],
                "candidate_id": round_result["candidate_id"],
                "kind": kind,
                "status": round_result["status"],
                "rate_status": round_result["rate_check"]["status"],
                "assumption_status": round_result["assumption_check"]["status"],
                "assumption_branch_id": round_result["assumption_branch_id"],
                "algorithm_change": round_result["algorithm_change"],
                "search_hypothesis": round_result["search_hypothesis"],
                "summary": summary,
                "next_search_action": next_search_action,
                "claim_status": "verifier_diagnosis_not_a_new_theorem",
            }
        )
    insight_ledger = {
        "schema_version": "1.0",
        "ledger_id": f"{scenario_slug}-insight-ledger-v1",
        "scenario_id": scenario_id,
        "verification_scope": VERIFICATION_SCOPE,
        "append_only": True,
        "entries": entries,
    }
    return evolution_trace, assumption_branches, insight_ledger


def run_minimax_scenario(
    scenario_path: str | Path, output_dir: str | Path
) -> MinimaxRunResult:
    scenario = _load_scenario(scenario_path)
    evolution_trace, assumption_branches, insight_ledger = evaluate_minimax_scenario(
        scenario
    )
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    trace_path = destination / "evolution_trace.json"
    branches_path = destination / "assumption_branches.json"
    ledger_path = destination / "insight_ledger.json"
    manifest_path = destination / "manifest.json"

    _write_json(trace_path, evolution_trace)
    _write_json(branches_path, assumption_branches)
    _write_json(ledger_path, insight_ledger)
    artifacts = (trace_path, branches_path, ledger_path)
    manifest = {
        "schema_version": "1.0",
        "scenario_id": scenario["scenario_id"],
        "scenario_sha256": _object_digest(scenario),
        "verification_scope": VERIFICATION_SCOPE,
        "final_status": evolution_trace["final"]["status"],
        "artifacts": [
            {
                "path": artifact.relative_to(destination).as_posix(),
                "sha256": _file_digest(artifact),
            }
            for artifact in artifacts
        ],
    }
    _write_json(manifest_path, manifest)
    return MinimaxRunResult(
        output_dir=destination,
        evolution_trace=trace_path,
        assumption_branches=branches_path,
        insight_ledger=ledger_path,
        manifest=manifest_path,
        final_status=evolution_trace["final"]["status"],
    )
