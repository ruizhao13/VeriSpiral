"""Deterministic, human-gated evolution proposals from explicit feedback.

This module verifies provenance and authorization boundaries, then emits a
proposal and an unapplied patch decision.  It never edits the target prompt,
skill, schema, verifier, or registry, and it never converts preference feedback
into a scientific conclusion.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .pipeline import (
    PipelineError,
    TRUSTED_EXECUTABLE_VERIFIERS,
    build_decision_packet,
    evaluate_candidate,
    file_digest,
    object_digest,
    repository_root,
    validate_artifact,
    write_json,
)


TRUST_REGISTRY_PATH = "examples/evolution/registry.json"
POLICY_ACTIONS = {
    "require_registered_control_receipt_replay": (
        "Before any manual application, replay the registered executable control "
        "verifier and revalidate the bound packet, receipt, and manifest hashes; "
        "reject the proposal if any binding changes."
    )
}
REQUIRED_CONTROL_GATES = (
    "schema",
    "evidence_integrity",
    "assumption_audit",
    "comparison_scope",
    "falsifiability",
    "induction_readiness",
    "semantic_verification",
    "human_acceptance",
    "candidate_lifecycle",
)
REQUIRED_CONTROL_GATE_VERDICTS = (
    "pass",
    "pass",
    "pass",
    "pass",
    "pass",
    "pass",
    "pass",
    "pending",
    "pass",
)
REQUIRED_CONTROL_STAGE_STATUS = {
    "structural_validation": "pass",
    "evidence_integrity": "pass",
    "semantic_verification": "verified",
    "human_acceptance": "pending",
    "candidate_lifecycle": "ready_for_verification",
}
CONTROL_SOURCE_TYPE = "bound_executable_verification_control"
CONTROL_SOURCE_USE = "process_only_unapplied_policy_proposal"
PASSED_SOURCE_REVALIDATION = {
    "candidate_registry_binding": "pass",
    "current_evidence_hashes": "pass",
    "registered_verifier_artifact": "pass",
    "executable_verifier_replay": "pass",
    "recomputed_packet_identity": "pass",
}
ACCEPTANCE_EXPECTATIONS = {
    "source_linkage": (
        "The registered decision packet, executable verification receipt, and manifest "
        "retain their recorded SHA-256 values."
    ),
    "target_hash_unchanged": (
        "The target remains at version 1.0.0 and its registered hash before any "
        "manual application."
    ),
    "deterministic_replay": (
        "Two runs from the same registered inputs produce byte-identical proposal artifacts."
    ),
    "manual_content_check": (
        "After approval and manual application, exactly one instruction is appended "
        "under the feedback gate."
    ),
}
ROLLBACK_TRIGGER = (
    "Any declared acceptance check fails after a human-approved manual application."
)
ROLLBACK_ACTION = (
    "Restore the registered target bytes and replay the bound executable control "
    "verifier before reconsideration."
)
REQUIRED_NON_GOALS = (
    "Do not create or strengthen any scientific claim from this preference event.",
    "Do not bypass, disable, or weaken any verifier or evidence gate.",
    "Do not modify a prompt, skill, schema, verifier, or registry automatically.",
    "Do not treat a bound control receipt as scientific success or human acceptance.",
)
REQUIRED_ACCEPTANCE_TYPES = {
    "source_linkage",
    "target_hash_unchanged",
    "deterministic_replay",
    "manual_content_check",
}
GOVERNED_OUTPUT_ROOTS = {"prompts", "skills", "schemas", "src"}
PROHIBITED_CHANGE_PATTERNS = (
    re.compile(
        r"\b(?:bypass|disable|skip|ignore|remove|weaken)\s+(?:the\s+)?"
        r"(?:verifier|verification|evidence\s+gate)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:theorem|scientific\s+claim)\s+(?:is|has\s+been)\s+"
        r"(?:proved|proven|verified|true)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bminimax[- ]optimal\b", re.IGNORECASE),
    re.compile(r"(?:绕过|跳过|关闭|削弱).{0,12}(?:验证|verifier)", re.IGNORECASE),
    re.compile(r"(?:定理|科学结论).{0,12}(?:已证明|成立|已验证)", re.IGNORECASE),
)


class EvolutionError(PipelineError):
    """Raised when a feedback-derived proposal violates a hard boundary."""


@dataclass(frozen=True)
class EvolutionRunResult:
    output_dir: Path
    proposal: Path
    patch: Path
    manifest: Path
    decision_status: str
    apply_status: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvolutionError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _load_strict_object(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise EvolutionError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise EvolutionError(f"{label} must be a JSON object: {path}")
    return value


def _require_schema(
    value: Mapping[str, Any], kind: str, root: Path, label: str
) -> None:
    issues = validate_artifact(value, kind, root)
    if issues:
        raise EvolutionError(
            f"invalid {label}: " + "; ".join(str(issue) for issue in issues)
        )


def _require_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise EvolutionError(f"{label} must be unique")


def _repo_file(root: Path, locator: str, label: str) -> Path:
    if not isinstance(locator, str) or not locator:
        raise EvolutionError(f"{label} must be a non-empty repository-local path")
    if "\\" in locator:
        raise EvolutionError(f"{label} must use repository-local POSIX syntax")
    relative = PurePosixPath(locator)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or relative.as_posix() != locator
    ):
        raise EvolutionError(f"{label} escapes or is not canonical within the repository")
    resolved = (root / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise EvolutionError(f"{label} escapes the repository") from exc
    if not resolved.is_file():
        raise EvolutionError(f"{label} does not resolve to a file: {locator}")
    return resolved


def _manifest_file(
    root: Path, manifest_path: Path, locator: str, label: str
) -> Path:
    if not isinstance(locator, str) or not locator or "\\" in locator:
        raise EvolutionError(f"{label} must be a canonical relative path")
    relative = PurePosixPath(locator)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
        or relative.as_posix() != locator
    ):
        raise EvolutionError(f"{label} escapes its manifest directory")
    resolved = (manifest_path.parent / Path(*relative.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise EvolutionError(f"{label} escapes the repository") from exc
    if not resolved.is_file():
        raise EvolutionError(f"{label} does not resolve to a file: {locator}")
    return resolved


def _semver(value: str, label: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", value)
    if match is None:
        raise EvolutionError(f"{label} must be major.minor.patch")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _validate_manifest_linkage(
    root: Path,
    manifest_path: Path,
    packet_path: Path,
    receipt_path: Path,
    packet: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> None:
    manifest = _load_strict_object(manifest_path, "source manifest")
    required = {
        "schema_version",
        "run_id",
        "decision",
        "candidate_sha256",
        "artifacts",
    }
    if set(manifest) != required:
        raise EvolutionError("source manifest has an unexpected shape")
    if manifest["schema_version"] != "1.0" or manifest["decision"] != "await_human_acceptance":
        raise EvolutionError("source manifest is not an awaiting-human control run")
    artifacts = manifest["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        raise EvolutionError("source manifest must bind exactly one decision packet")

    resolved_artifacts: dict[Path, Mapping[str, Any]] = {}
    artifact_names: list[str] = []
    for index, item in enumerate(artifacts):
        if not isinstance(item, Mapping) or set(item) != {"path", "sha256"}:
            raise EvolutionError(f"source manifest artifact {index} has an unexpected shape")
        locator = item["path"]
        sha256 = item["sha256"]
        if not isinstance(locator, str) or not re.fullmatch(r"[a-f0-9]{64}", str(sha256)):
            raise EvolutionError(f"source manifest artifact {index} is malformed")
        artifact_path = _manifest_file(
            root, manifest_path, locator, f"source manifest artifact {index}"
        )
        if artifact_path in resolved_artifacts:
            raise EvolutionError("source manifest resolves multiple entries to one file")
        if file_digest(artifact_path) != sha256:
            raise EvolutionError(f"source manifest artifact hash drift: {locator}")
        resolved_artifacts[artifact_path] = item
        artifact_names.append(locator)
    _require_unique(artifact_names, "source manifest artifact paths")

    if packet_path not in resolved_artifacts or packet_path.name != "decision_packet.json":
        raise EvolutionError("source manifest must bind exactly one decision packet")
    if resolved_artifacts[packet_path]["sha256"] != file_digest(packet_path):
        raise EvolutionError("source manifest does not bind the exact decision packet")

    packet_receipt = packet["verification_receipts"][0]
    resolved_receipt = _repo_file(
        root, packet_receipt["locator"], "packet verification receipt"
    )
    if resolved_receipt != receipt_path:
        raise EvolutionError("decision packet binds a different verification receipt")
    receipt_sha256 = file_digest(receipt_path)
    if packet_receipt["sha256"] != receipt_sha256:
        raise EvolutionError("decision packet verification receipt hash drift")
    _validate_bound_control_chain(manifest, receipt, packet, receipt_sha256)


def _validate_bound_control_chain(
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    packet: Mapping[str, Any],
    receipt_sha256: str,
) -> None:
    """Require a bound control receipt without upgrading it to scientific success."""

    if packet["decision"] != "await_human_acceptance":
        raise EvolutionError("control source must remain awaiting human acceptance")
    if packet["stage_status"] != REQUIRED_CONTROL_STAGE_STATUS:
        raise EvolutionError("control source stage status is not the exact pending-human state")
    if packet["human_acceptance_records"] != []:
        raise EvolutionError("control source must not contain a human acceptance record")
    if len(packet["verification_receipts"]) != 1:
        raise EvolutionError("control source must bind exactly one verification receipt")

    gates = packet["gate_results"]
    gate_names = [gate["gate"] for gate in gates]
    gate_verdicts = [gate["verdict"] for gate in gates]
    if (
        tuple(gate_names) != REQUIRED_CONTROL_GATES
        or tuple(gate_verdicts) != REQUIRED_CONTROL_GATE_VERDICTS
    ):
        raise EvolutionError("control source does not contain the exact bounded gate state")
    if manifest["run_id"] != packet["packet_id"]:
        raise EvolutionError("source manifest run_id does not match the decision packet")
    if manifest["candidate_sha256"] != packet["candidate_sha256"]:
        raise EvolutionError("source manifest candidate hash does not match the decision packet")

    packet_receipt = packet["verification_receipts"][0]
    if packet_receipt["receipt_id"] != receipt["receipt_id"]:
        raise EvolutionError("decision packet references a different receipt id")
    if packet_receipt["sha256"] != receipt_sha256:
        raise EvolutionError("decision packet receipt hash does not verify")
    if packet_receipt["semantic_sha256"] != receipt["semantic_sha256"]:
        raise EvolutionError("receipt semantic subject binding does not verify")
    if receipt["candidate_id"] != packet["candidate_id"]:
        raise EvolutionError("receipt candidate id does not match the decision packet")
    if (
        packet_receipt["method"] != "executable_check"
        or packet_receipt["result"] != "passed"
        or receipt["method"] != "executable_check"
        or receipt["result"]["status"] != "passed"
    ):
        raise EvolutionError("control receipt is not a passed executable verification")
    if packet_receipt["verifier_id"] != receipt["verifier"]["id"]:
        raise EvolutionError("receipt verifier identity does not match the decision packet")


def _revalidate_executable_control_source(
    candidate: Mapping[str, Any],
    packet: Mapping[str, Any],
    receipt: Mapping[str, Any],
    root: Path,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Replay current evidence and verifier state, not only recorded JSON hashes."""

    candidate_evidence = candidate["evidence"]
    evidence_ids = [item["id"] for item in candidate_evidence]
    binding_ids = [item["id"] for item in receipt["evidence_bindings"]]
    if evidence_ids != binding_ids or len(binding_ids) != len(set(binding_ids)):
        raise EvolutionError(
            "current evidence set does not exactly match the verification receipt"
        )
    binding_by_id = {item["id"]: item for item in receipt["evidence_bindings"]}
    for item in candidate_evidence:
        evidence_path = _repo_file(
            root, item["locator"], f"candidate evidence {item['id']}"
        )
        if file_digest(evidence_path) != binding_by_id[item["id"]]["sha256"]:
            raise EvolutionError(
                f"current evidence hash drift blocks evolution: {item['id']}"
            )

    verifier = receipt["verifier"]
    registration = TRUSTED_EXECUTABLE_VERIFIERS.get(verifier["id"])
    if registration is None:
        raise EvolutionError("receipt verifier is not currently registered")
    registered_identity = {
        "artifact_locator": registration["artifact_locator"],
        "artifact_sha256": registration["artifact_sha256"],
        "command": registration["command"],
    }
    receipt_identity = {
        "artifact_locator": verifier["artifact_locator"],
        "artifact_sha256": verifier["artifact_sha256"],
        "command": verifier["command"],
    }
    if receipt_identity != registered_identity:
        raise EvolutionError(
            "verification receipt does not match the currently registered verifier"
        )
    verifier_path = _repo_file(
        root, verifier["artifact_locator"], "registered verifier artifact"
    )
    if file_digest(verifier_path) != registration["artifact_sha256"]:
        raise EvolutionError("registered verifier artifact hash drift blocks evolution")

    gates, evidence_manifest, verification_manifest, human_manifest = evaluate_candidate(
        candidate, root
    )
    gates_by_name = {gate.gate: gate for gate in gates}
    evidence_gate = gates_by_name["evidence_integrity"]
    if evidence_gate.verdict != "pass":
        raise EvolutionError(
            "current evidence integrity replay failed: " + evidence_gate.summary
        )
    semantic_gate = gates_by_name["semantic_verification"]
    if semantic_gate.verdict != "pass" or verification_manifest is None:
        summary = semantic_gate.summary
        if "verifier artifact" in summary or "trusted registration" in summary:
            raise EvolutionError(
                "registered verifier artifact revalidation failed: " + summary
            )
        if "registered verifier replay" in summary:
            raise EvolutionError("executable verifier replay failed: " + summary)
        if "evidence" in summary:
            raise EvolutionError("current evidence revalidation failed: " + summary)
        raise EvolutionError("semantic control-source replay failed: " + summary)
    if gates_by_name["human_acceptance"].verdict != "pending":
        raise EvolutionError(
            "control-source replay must remain pending explicit human acceptance"
        )

    replayed_packet = build_decision_packet(
        candidate,
        gates,
        evidence_manifest,
        verification_manifest,
        human_manifest,
    )
    if replayed_packet != dict(packet):
        raise EvolutionError(
            "recomputed decision packet does not match the registered control source"
        )

    checks = [
        {
            "check": "candidate_registry_binding",
            "status": "pass",
            "detail": "Candidate bytes and canonical object digest match the registry and decision packet.",
        },
        {
            "check": "current_evidence_hash_revalidation",
            "status": "pass",
            "detail": "Every current repository-local evidence artifact matches its receipt-bound SHA-256.",
        },
        {
            "check": "registered_verifier_artifact_revalidation",
            "status": "pass",
            "detail": "Verifier identity, command, artifact path, and current artifact hash match the trusted registration.",
        },
        {
            "check": "executable_verifier_replay",
            "status": "pass",
            "detail": "The currently registered executable verifier passed over the bound candidate and reproduced the receipt output.",
        },
        {
            "check": "decision_packet_recomputation",
            "status": "pass",
            "detail": "A fresh evaluation reproduced the complete registered decision packet while human acceptance remained pending.",
        },
    ]
    return dict(PASSED_SOURCE_REVALIDATION), checks


def _trusted_source(
    feedback: Mapping[str, Any], registry: Mapping[str, Any], root: Path
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, str]]:
    source = feedback["control_source"]
    candidate_ref = source["candidate"]
    packet_ref = source["decision_packet"]
    receipt_ref = source["verification_receipt"]
    manifest_ref = source["manifest"]

    candidate_path = _repo_file(root, candidate_ref["path"], "feedback candidate")
    packet_path = _repo_file(root, packet_ref["path"], "feedback decision packet")
    receipt_path = _repo_file(
        root, receipt_ref["path"], "feedback verification receipt"
    )
    manifest_path = _repo_file(root, manifest_ref["path"], "feedback source manifest")

    entries = [
        item
        for item in registry["control_sources"]
        if item["source_id"] == source["source_id"]
    ]
    if len(entries) != 1:
        raise EvolutionError("feedback source_id is not uniquely registered")
    registered = entries[0]
    expected = {
        "source_id": source["source_id"],
        "source_type": source["source_type"],
        "allowed_use": source["allowed_use"],
        "human_acceptance_status": source["human_acceptance_status"],
        "scientific_conclusion_allowed": source["scientific_conclusion_allowed"],
        "candidate_path": candidate_ref["path"],
        "candidate_file_sha256": candidate_ref["file_sha256"],
        "candidate_object_sha256": candidate_ref["object_sha256"],
        "candidate_id": candidate_ref["candidate_id"],
        "decision_packet_path": packet_ref["path"],
        "decision_packet_sha256": packet_ref["sha256"],
        "packet_id": packet_ref["packet_id"],
        "verification_receipt_path": receipt_ref["path"],
        "verification_receipt_sha256": receipt_ref["sha256"],
        "receipt_id": receipt_ref["receipt_id"],
        "manifest_path": manifest_ref["path"],
        "manifest_sha256": manifest_ref["sha256"],
    }
    if expected != dict(registered):
        raise EvolutionError("feedback control source does not match the trust registry")
    if (
        expected["source_type"] != CONTROL_SOURCE_TYPE
        or expected["allowed_use"] != CONTROL_SOURCE_USE
        or expected["human_acceptance_status"] != "pending"
        or expected["scientific_conclusion_allowed"] is not False
    ):
        raise EvolutionError("registered control source exceeds its process-only authority")
    if file_digest(candidate_path) != registered["candidate_file_sha256"]:
        raise EvolutionError("registered candidate file hash drift")
    if file_digest(packet_path) != registered["decision_packet_sha256"]:
        raise EvolutionError("registered decision packet hash drift")
    if file_digest(receipt_path) != registered["verification_receipt_sha256"]:
        raise EvolutionError("registered verification receipt hash drift")
    if file_digest(manifest_path) != registered["manifest_sha256"]:
        raise EvolutionError("registered source manifest hash drift")

    candidate = _load_strict_object(candidate_path, "registered candidate")
    packet = _load_strict_object(packet_path, "registered decision packet")
    receipt = _load_strict_object(receipt_path, "registered verification receipt")
    _require_schema(candidate, "candidate", root, "registered candidate")
    _require_schema(packet, "decision_packet", root, "registered decision packet")
    _require_schema(receipt, "verification_receipt", root, "registered verification receipt")
    if packet["packet_id"] != registered["packet_id"]:
        raise EvolutionError("registered decision packet identity does not match")
    candidate_sha256 = object_digest(candidate)
    if (
        candidate["id"] != registered["candidate_id"]
        or candidate_sha256 != registered["candidate_object_sha256"]
        or candidate_sha256 != packet["candidate_sha256"]
        or candidate["id"] != packet["candidate_id"]
    ):
        raise EvolutionError(
            "registered candidate identity does not match the decision packet"
        )
    if receipt["receipt_id"] != registered["receipt_id"]:
        raise EvolutionError("registered verification receipt identity does not match")
    _validate_manifest_linkage(
        root, manifest_path, packet_path, receipt_path, packet, receipt
    )
    revalidation, replay_checks = _revalidate_executable_control_source(
        candidate, packet, receipt, root
    )

    checks = [
        {
            "check": "control_source_registry_match",
            "status": "pass",
            "detail": "Packet, receipt, manifest identities and hashes match the control-source registry.",
        },
        {
            "check": "repository_local_control_source",
            "status": "pass",
            "detail": "The decision packet, executable receipt, and manifest resolve within the repository.",
        },
        {
            "check": "packet_receipt_manifest_binding",
            "status": "pass",
            "detail": "The manifest binds the packet and the packet binds the exact replayed executable receipt.",
        },
        {
            "check": "bounded_control_stage",
            "status": "pass",
            "detail": "Structural, integrity, and executable verification passed while human acceptance remains pending.",
        },
        {
            "check": "process_only_authority",
            "status": "pass",
            "detail": "The source authorizes only an unapplied process proposal and no scientific conclusion.",
        },
    ]
    return expected, checks + replay_checks, revalidation


def _trusted_component(
    feedback: Mapping[str, Any], registry: Mapping[str, Any], root: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    target = feedback["target_component"]
    target_path = _repo_file(root, target["path"], "target component path")
    entries = [
        item
        for item in registry["components"]
        if item["component_id"] == target["component_id"]
    ]
    if len(entries) != 1:
        raise EvolutionError("target component_id is not uniquely registered")
    registered = dict(entries[0])
    if dict(target) != registered:
        raise EvolutionError("target path, type, version, or hash does not match the registry")
    if file_digest(target_path) != target["current_sha256"]:
        raise EvolutionError("target component hash drift")

    target_text = target_path.read_text(encoding="utf-8")
    version_marker = f"Version: {target['current_version']}"
    if target["component_type"] in {"prompt", "skill"} and target_text.count(version_marker) != 1:
        raise EvolutionError("target component does not carry its registered version marker")

    change = feedback["single_change"]
    proposed_value = POLICY_ACTIONS.get(change["policy_action"])
    if proposed_value is None:
        raise EvolutionError("feedback requests an unregistered policy action")
    if target_text.count(change["target_location"]) != 1:
        raise EvolutionError("single change must resolve to exactly one target location")
    if proposed_value in target_text:
        raise EvolutionError("proposed instruction is already present in the target")

    current_version = _semver(target["current_version"], "target current_version")
    proposed_version = _semver(change["proposed_version"], "proposed_version")
    expected_version = (current_version[0], current_version[1], current_version[2] + 1)
    if proposed_version != expected_version:
        raise EvolutionError(
            "a single process instruction must propose exactly one patch-version increment"
        )

    rollback = feedback["rollback_rule"]
    if (
        rollback["trigger"] != ROLLBACK_TRIGGER
        or rollback["action"] != ROLLBACK_ACTION
        or rollback["restore_version"] != target["current_version"]
        or rollback["restore_sha256"] != target["current_sha256"]
    ):
        raise EvolutionError("rollback rule must match the trusted exact-restore template")

    checks = feedback["acceptance_checks"]
    check_ids = [item["check_id"] for item in checks]
    check_types = [item["check_type"] for item in checks]
    _require_unique(check_ids, "acceptance check ids")
    _require_unique(check_types, "acceptance check types")
    if set(check_types) != REQUIRED_ACCEPTANCE_TYPES:
        raise EvolutionError(
            "acceptance checks must cover source linkage, target hash, "
            "deterministic replay, and manual content"
        )
    if any(
        item["expected"] != ACCEPTANCE_EXPECTATIONS[item["check_type"]]
        for item in checks
    ):
        raise EvolutionError("acceptance checks must match the trusted policy templates")
    if tuple(feedback["non_goals"]) != REQUIRED_NON_GOALS:
        raise EvolutionError("non-goals must match the trusted safety template")

    checks_out = [
        {
            "check": "target_registry_match",
            "status": "pass",
            "detail": "Target path, type, current version, and SHA-256 match the registry.",
        },
        {
            "check": "single_change_scope",
            "status": "pass",
            "detail": "One process-only instruction targets one location and one patch version.",
        },
        {
            "check": "rollback_and_acceptance_contract",
            "status": "pass",
            "detail": "Required acceptance checks and exact rollback bytes are declared.",
        },
    ]
    return registered, checks_out


def _validate_authorization_and_claim_boundary(feedback: Mapping[str, Any]) -> None:
    boundary = feedback["authorization_boundary"]
    expected = {
        "requires_human_approval": True,
        "human_review_status": "required",
        "apply_status": "not_applied",
        "automatic_application": False,
        "verifier_bypass_allowed": False,
        "scientific_conclusion_allowed": False,
        "source_authority": CONTROL_SOURCE_USE,
        "source_human_acceptance_status": "pending",
    }
    if dict(boundary) != expected:
        raise EvolutionError("feedback authorization boundary is not human-gated")
    searchable = " ".join(
        (
            feedback["feedback_summary"],
            feedback["single_change"]["rationale"],
        )
    )
    for pattern in PROHIBITED_CHANGE_PATTERNS:
        if pattern.search(searchable):
            raise EvolutionError(
                "preference feedback cannot bypass verification or assert a scientific conclusion"
            )


def _output_boundary(root: Path, destination: Path) -> None:
    resolved = destination.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return
    if relative.parts and relative.parts[0] in GOVERNED_OUTPUT_ROOTS:
        raise EvolutionError(
            "evolution artifacts cannot be written inside prompt, skill, schema, "
            "or verifier source roots"
        )


def _build_proposal(
    feedback: Mapping[str, Any],
    feedback_sha256: str,
    registry_sha256: str,
    source: Mapping[str, Any],
    source_revalidation: Mapping[str, str],
    target: Mapping[str, Any],
    provenance_checks: list[dict[str, str]],
) -> dict[str, Any]:
    identity = {
        "feedback": feedback,
        "feedback_file_sha256": feedback_sha256,
        "registry_sha256": registry_sha256,
        "source": source,
        "source_revalidation": source_revalidation,
        "target": target,
    }
    proposal_id = f"proposal-{object_digest(identity)[:12]}"
    requested_change = feedback["single_change"]
    change = {
        "operation": requested_change["operation"],
        "target_location": requested_change["target_location"],
        "policy_action": requested_change["policy_action"],
        "proposed_value": POLICY_ACTIONS[requested_change["policy_action"]],
        "proposed_version": requested_change["proposed_version"],
        "rationale": requested_change["rationale"],
        "requested_effect": requested_change["requested_effect"],
    }
    change["change_sha256"] = object_digest(change)
    acceptance_checks = [dict(item, status="not_run") for item in feedback["acceptance_checks"]]
    return {
        "schema_version": "1.0",
        "proposal_id": proposal_id,
        "feedback_id": feedback["feedback_id"],
        "feedback_sha256": feedback_sha256,
        "actor": feedback["actor"],
        "signal_type": feedback["signal_type"],
        "feedback_summary": feedback["feedback_summary"],
        "control_source": dict(source),
        "source_revalidation": dict(source_revalidation),
        "target_component": dict(target),
        "single_change": change,
        "acceptance_checks": acceptance_checks,
        "acceptance_status": "not_run_patch_not_applied",
        "rollback_rule": dict(feedback["rollback_rule"]),
        "rollback_status": "not_needed_patch_not_applied",
        "non_goals": list(feedback["non_goals"]),
        "provenance_checks": provenance_checks,
        "authorization_boundary": {
            "requires_human_approval": True,
            "human_review_status": "required",
            "apply_status": "not_applied",
            "automatic_application": False,
            "verifier_bypass_allowed": False,
            "scientific_conclusion_status": "no_scientific_conclusion_generated",
            "single_feedback_scope": "workflow_preference_only",
            "source_authority": CONTROL_SOURCE_USE,
            "source_human_acceptance_status": "pending",
        },
    }


def _build_patch(proposal: Mapping[str, Any]) -> dict[str, Any]:
    patch_id = f"patch-{object_digest(proposal)[:12]}"
    rollback = dict(proposal["rollback_rule"])
    rollback["status"] = "not_needed_patch_not_applied"
    return {
        "schema_version": "1.0",
        "patch_id": patch_id,
        "proposal_id": proposal["proposal_id"],
        "feedback_id": proposal["feedback_id"],
        "feedback_sha256": proposal["feedback_sha256"],
        "actor": proposal["actor"],
        "signal_type": proposal["signal_type"],
        "decision_status": "proposed_for_human_review",
        "target_component": dict(proposal["target_component"]),
        "single_change": dict(proposal["single_change"]),
        "acceptance_checks": [dict(item) for item in proposal["acceptance_checks"]],
        "rollback_rule": rollback,
        "non_goals": list(proposal["non_goals"]),
        "bound_control_provenance": dict(proposal["control_source"]),
        "source_revalidation": dict(proposal["source_revalidation"]),
        "authorization_boundary": {
            "requires_human_approval": True,
            "human_review_status": "required",
            "apply_status": "not_applied",
            "automatic_application": False,
            "verifier_bypass_allowed": False,
            "scientific_conclusion_status": "no_scientific_conclusion_generated",
            "source_authority": CONTROL_SOURCE_USE,
            "source_human_acceptance_status": "pending",
        },
    }


def run_evolution_feedback(
    feedback_path: str | Path,
    output_dir: str | Path,
    repo_root: str | Path | None = None,
) -> EvolutionRunResult:
    """Verify one explicit feedback event and emit an unapplied patch proposal."""

    root = Path(repo_root).resolve() if repo_root else repository_root().resolve()
    feedback_file = Path(feedback_path).resolve()
    feedback = _load_strict_object(feedback_file, "feedback event")
    _require_schema(feedback, "feedback_event", root, "feedback event")

    registry_path = _repo_file(root, TRUST_REGISTRY_PATH, "evolution trust registry")
    registry = _load_strict_object(registry_path, "evolution trust registry")
    _require_schema(registry, "evolution_registry", root, "evolution trust registry")
    _require_unique(
        [item["source_id"] for item in registry["control_sources"]],
        "registry source ids",
    )
    _require_unique(
        [item["component_id"] for item in registry["components"]],
        "registry component ids",
    )

    _validate_authorization_and_claim_boundary(feedback)
    source, source_checks, source_revalidation = _trusted_source(
        feedback, registry, root
    )
    target, target_checks = _trusted_component(feedback, registry, root)

    destination = Path(output_dir)
    _output_boundary(root, destination)
    feedback_sha256 = file_digest(feedback_file)
    registry_sha256 = file_digest(registry_path)
    proposal = _build_proposal(
        feedback,
        feedback_sha256,
        registry_sha256,
        source,
        source_revalidation,
        target,
        source_checks + target_checks,
    )
    patch = _build_patch(proposal)
    _require_schema(proposal, "evolution_proposal", root, "generated evolution proposal")
    _require_schema(patch, "evolution_patch", root, "generated evolution patch")

    target_path = _repo_file(root, target["path"], "target component path")
    if file_digest(target_path) != target["current_sha256"]:
        raise EvolutionError("target component changed during proposal generation")

    destination.mkdir(parents=True, exist_ok=True)
    proposal_path = destination / "evolution_proposal.json"
    patch_path = destination / "evolution_patch.json"
    manifest_path = destination / "manifest.json"
    write_json(proposal_path, proposal)
    write_json(patch_path, patch)
    manifest = {
        "schema_version": "1.0",
        "run_id": proposal["proposal_id"],
        "registry_id": registry["registry_id"],
        "registry_sha256": registry_sha256,
        "input_feedback_sha256": feedback_sha256,
        "decision_status": "proposed_for_human_review",
        "apply_status": "not_applied",
        "human_review_status": "required",
        "source_id": source["source_id"],
        "source_type": CONTROL_SOURCE_TYPE,
        "source_use": CONTROL_SOURCE_USE,
        "source_human_acceptance_status": "pending",
        "scientific_conclusion_status": "no_scientific_conclusion_generated",
        "source_revalidation": dict(source_revalidation),
        "artifacts": [
            {"path": proposal_path.name, "sha256": file_digest(proposal_path)},
            {"path": patch_path.name, "sha256": file_digest(patch_path)},
        ],
    }
    _require_schema(manifest, "evolution_manifest", root, "generated evolution manifest")
    write_json(manifest_path, manifest)
    return EvolutionRunResult(
        output_dir=destination,
        proposal=proposal_path,
        patch=patch_path,
        manifest=manifest_path,
        decision_status="proposed_for_human_review",
        apply_status="not_applied",
    )
