"""Trusted executable verifier for the public pipeline-policy candidate.

The verifier reads one candidate JSON object from standard input and emits one
deterministic JSON result.  It verifies only the declared pipeline promotion
contract.  It does not establish the truth of an arbitrary scientific claim.
"""

from __future__ import annotations

import copy
import json
import sys

from verispiral.pipeline import (
    GateResult,
    PipelineError,
    SEMANTIC_SUBJECT_FIELDS,
    build_decision_packet,
    build_success_trace,
    semantic_subject_digest,
    skill_blueprint_digest,
)


VERIFIER_ID = "verispiral.pipeline-contract"
EXPECTED_BLUEPRINT_SHA256 = "0bdb31138cfb81e08b190f124921cd6351cca8aaba481113fa69de0d1d150906"
EXPECTED_STATEMENT = (
    "The pipeline blocks success traces and activatable skills unless structural "
    "validation, evidence integrity, a bound semantic verification receipt, explicit "
    "human acceptance, and ready lifecycle status all pass."
)
EXPECTED_KILL_CONDITIONS = {
    "A success trace or activatable skill is emitted without a bound verification receipt.",
    "A success trace or activatable skill is emitted without explicit human acceptance.",
    "A parked candidate is promoted or emits a success trace or activatable skill.",
}
CHECKS = [
    "claim_matches_pipeline_policy",
    "success_trace_rejects_missing_receipt",
    "success_trace_rejects_missing_human_acceptance",
    "parked_candidate_cannot_promote",
    "skill_blueprint_matches_reviewed_contract",
    "skill_blueprint_preserves_gate_and_human_boundaries",
]


def _rejects_trace(candidate: dict[str, object], missing: str) -> bool:
    packet = {
        "decision": "promote_to_prototype",
        "stage_status": {
            "structural_validation": "pass",
            "evidence_integrity": "pass",
            "semantic_verification": "verified",
            "human_acceptance": "accepted",
            "candidate_lifecycle": "ready_for_verification",
        },
        "verification_receipts": [
            {
                "receipt_id": "receipt-probe",
                "sha256": "0" * 64,
                "semantic_sha256": "1" * 64,
                "skill_blueprint_sha256": skill_blueprint_digest(candidate),
                "method": "executable_check",
                "verifier_id": VERIFIER_ID,
            }
        ],
        "human_acceptance_records": [
            {
                "acceptance_id": "acceptance-probe",
                "sha256": "2" * 64,
                "scope": "prototype_skill_activation",
                "reviewer_role": "human_reviewer",
                "skill_blueprint_sha256": skill_blueprint_digest(candidate),
            }
        ],
        "gate_results": [{"gate": "probe", "verdict": "pass"}],
        "packet_id": "packet-" + "0" * 12,
    }
    if missing == "receipt":
        packet["verification_receipts"] = []
    else:
        packet["human_acceptance_records"] = []
    try:
        build_success_trace(candidate, packet)
    except PipelineError:
        return True
    return False


def _parked_cannot_promote(candidate: dict[str, object]) -> bool:
    parked = copy.deepcopy(candidate)
    parked["status"] = "parked"
    pass_names = (
        "schema",
        "evidence_integrity",
        "assumption_audit",
        "comparison_scope",
        "falsifiability",
        "induction_readiness",
        "semantic_verification",
        "human_acceptance",
    )
    gates = [GateResult(name, "pass", "behavioral verifier probe passed") for name in pass_names]
    gates.append(
        GateResult(
            "candidate_lifecycle",
            "blocked",
            "candidate is parked; promotion is intentionally disabled",
        )
    )
    packet = build_decision_packet(
        parked,
        gates,
        [],
        {
            "receipt_id": "receipt-probe",
            "locator": "probe",
            "sha256": "0" * 64,
            "semantic_sha256": semantic_subject_digest(parked),
            "skill_blueprint_sha256": skill_blueprint_digest(parked),
            "method": "executable_check",
            "verifier_id": VERIFIER_ID,
            "verifier_artifact_locator": "probe",
            "verifier_artifact_sha256": "1" * 64,
            "result": "passed",
        },
        {
            "acceptance_id": "acceptance-probe",
            "locator": "probe",
            "sha256": "2" * 64,
            "semantic_sha256": semantic_subject_digest(parked),
            "skill_blueprint_sha256": skill_blueprint_digest(parked),
            "receipt_id": "receipt-probe",
            "receipt_sha256": "0" * 64,
            "decision": "accepted",
            "scope": "prototype_skill_activation",
            "reviewer_role": "human_reviewer",
        },
    )
    return packet["decision"] == "parked" and packet["gate_recommendation"] == "keep_parked"


def main() -> int:
    candidate = json.load(sys.stdin)
    semantic_sha = semantic_subject_digest(candidate)
    blueprint_sha = skill_blueprint_digest(candidate)
    checks_pass = (
        tuple(SEMANTIC_SUBJECT_FIELDS)
        == (
            "id",
            "research_question",
            "claim",
            "assumptions",
            "proof_route",
            "novelty",
            "comparators",
            "expected_value",
            "risks",
            "limitations",
            "skill_blueprint",
        )
        and candidate["claim"]["statement"] == EXPECTED_STATEMENT
        and set(candidate["claim"]["kill_conditions"]) == EXPECTED_KILL_CONDITIONS
        and blueprint_sha == EXPECTED_BLUEPRINT_SHA256
        and all(
            phrase not in " ".join(candidate["skill_blueprint"]["workflow"]).lower()
            for phrase in ("bypass", "skip verification", "ignore gate", "disable gate")
        )
        and _rejects_trace(candidate, "receipt")
        and _rejects_trace(candidate, "human")
        and _parked_cannot_promote(candidate)
    )
    result = {
        "status": "passed" if checks_pass else "failed",
        "verifier_id": VERIFIER_ID,
        "semantic_sha256": semantic_sha,
        "skill_blueprint_sha256": blueprint_sha,
        "checks": CHECKS,
    }
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sys.stdout.write(encoded + "\n")
    return 0 if checks_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
