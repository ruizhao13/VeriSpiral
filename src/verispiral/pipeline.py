"""Deterministic candidate-to-skill pipeline used by VeriSpiral."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import ValidationIssue, load_schema, validate


SCHEMA_FILES = {
    "candidate": "candidate.schema.json",
    "decision_packet": "decision_packet.schema.json",
    "verification_receipt": "verification_receipt.schema.json",
    "human_acceptance": "human_acceptance.schema.json",
    "acceptance_registry": "acceptance_registry.schema.json",
    "success_trace": "success_trace.schema.json",
    "induced_skill": "induced_skill.schema.json",
    "minimax_scenario": "minimax_scenario.schema.json",
    "minimax_evolution": "minimax_evolution.schema.json",
    "assumption_branches": "assumption_branches.schema.json",
    "insight_ledger": "insight_ledger.schema.json",
    "evolution_registry": "evolution_registry.schema.json",
    "feedback_event": "feedback_event.schema.json",
    "evolution_proposal": "evolution_proposal.schema.json",
    "evolution_patch": "evolution_patch.schema.json",
    "evolution_manifest": "evolution_manifest.schema.json",
    "research_specification": "research_specification.schema.json",
    "research_coevolution_scenario": "research_coevolution_scenario.schema.json",
    "research_coevolution_trace": "research_coevolution_trace.schema.json",
    "research_coevolution_manifest": "research_coevolution_manifest.schema.json",
}

SEMANTIC_SUBJECT_FIELDS = (
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

STRUCTURAL_GATES = (
    "schema",
    "assumption_audit",
    "comparison_scope",
    "falsifiability",
    "induction_readiness",
)

TRUSTED_EXECUTABLE_VERIFIERS = {
    "verispiral.pipeline-contract": {
        "artifact_locator": "examples/verifiers/pipeline_contract.py",
        "artifact_sha256": "d7083fdacfef609907181797613a79d3bb69019d3de6f2b3e47275a072f3ccc3",
        "command": "python -B examples/verifiers/pipeline_contract.py",
    }
}

TRUSTED_ACCEPTANCE_REGISTRY = {
    "locator": "examples/verification/acceptance_registry.json",
    "sha256": "bdb7ecb055d07fff860ff86bb4a0fc4502b0ca93ffa8edd0d8df067477f8dacf",
}


class PipelineError(RuntimeError):
    """Raised when a generated artifact violates a repository invariant."""


class CandidateValidationError(PipelineError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("candidate validation failed: " + "; ".join(map(str, self.issues)))


@dataclass(frozen=True)
class GateResult:
    gate: str
    verdict: str
    summary: str
    evidence_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "verdict": self.verdict,
            "summary": self.summary,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class RunResult:
    decision: str
    output_dir: Path
    decision_packet: Path
    success_trace: Path | None
    induced_skill: Path | None
    manifest: Path


def repository_root() -> Path:
    """Locate the public checkout in source and installed-CLI workflows.

    Editable and wheel installs place ``verispiral`` outside the repository data
    files.  Prefer the current working directory when it carries the public
    schemas and example fixture, then fall back to the source-tree layout.
    """

    source_checkout = Path(__file__).resolve().parents[2]
    installed_data = (
        Path(sysconfig.get_path("data")).resolve() / "share" / "verispiral"
    )
    for candidate in (Path.cwd().resolve(), source_checkout, installed_data):
        if (
            (candidate / "schemas" / "candidate.schema.json").is_file()
            and (candidate / "examples" / "candidate.json").is_file()
        ):
            return candidate
    return source_checkout


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise PipelineError(f"duplicate JSON object key: {key!r}")
        value[key] = item
    return value


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(value, dict):
        raise PipelineError(f"expected a JSON object: {path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def object_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def semantic_subject_digest(candidate: Mapping[str, Any]) -> str:
    """Bind receipts to the scientific/research content, not mutable workflow state."""

    return object_digest({field: candidate[field] for field in SEMANTIC_SUBJECT_FIELDS})


def skill_blueprint_digest(candidate: Mapping[str, Any]) -> str:
    """Bind the exact activatable Skill payload independently of surrounding prose."""

    return object_digest(candidate["skill_blueprint"])


def file_digest(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_artifact(value: Mapping[str, Any], kind: str, repo_root: Path) -> list[ValidationIssue]:
    try:
        filename = SCHEMA_FILES[kind]
    except KeyError as exc:
        raise PipelineError(f"unknown artifact kind: {kind}") from exc
    schema = load_schema(repo_root / "schemas" / filename)
    return validate(value, schema)


def _safe_evidence_path(repo_root: Path, locator: str) -> Path | None:
    candidate = Path(locator)
    if candidate.is_absolute():
        return None
    resolved = (repo_root / candidate).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return resolved


def _evidence_gate(
    candidate: Mapping[str, Any], repo_root: Path
) -> tuple[GateResult, list[dict[str, str]]]:
    evidence = candidate["evidence"]
    ids = [item["id"] for item in evidence]
    problems: list[str] = []
    manifest: list[dict[str, str]] = []
    if len(ids) != len(set(ids)):
        problems.append("evidence identifiers are not unique")

    for item in evidence:
        locator = item["locator"]
        path = _safe_evidence_path(repo_root, locator)
        if path is None:
            problems.append(f"{item['id']} has a locator outside the repository")
            continue
        if not path.is_file():
            problems.append(f"{item['id']} does not resolve to a file")
            continue
        manifest.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "locator": locator,
                "sha256": file_digest(path),
            }
        )

    if problems:
        return (
            GateResult(
                "evidence_integrity",
                "fail",
                "; ".join(problems),
                tuple(ids),
            ),
            manifest,
        )
    return (
        GateResult(
            "evidence_integrity",
            "pass",
            f"resolved and hashed {len(manifest)} repository-local evidence artifacts",
            tuple(ids),
        ),
        manifest,
    )


def _semantic_verification_gate(
    candidate: Mapping[str, Any],
    repo_root: Path,
    evidence_manifest: list[dict[str, str]],
) -> tuple[GateResult, dict[str, Any] | None]:
    declaration = candidate["semantic_verification"]
    if declaration["status"] != "receipt_attached":
        return (
            GateResult(
                "semantic_verification",
                "pending",
                "no passed verification receipt is attached to the semantic subject",
            ),
            None,
        )

    locator = declaration["receipt_locator"]
    receipt_path = _safe_evidence_path(repo_root, locator)
    if receipt_path is None or not receipt_path.is_file():
        return (
            GateResult(
                "semantic_verification",
                "fail",
                "verification receipt does not resolve to a repository-local file",
            ),
            None,
        )

    try:
        receipt = read_json(receipt_path)
    except (OSError, ValueError, PipelineError) as exc:
        return (
            GateResult(
                "semantic_verification",
                "fail",
                f"verification receipt cannot be read: {exc}",
            ),
            None,
        )

    issues = validate_artifact(receipt, "verification_receipt", repo_root)
    if issues:
        return (
            GateResult(
                "semantic_verification",
                "fail",
                "verification receipt violates its schema: "
                + "; ".join(map(str, issues)),
            ),
            None,
        )

    problems: list[str] = []
    semantic_sha = semantic_subject_digest(candidate)
    blueprint_sha = skill_blueprint_digest(candidate)
    if receipt["candidate_id"] != candidate["id"]:
        problems.append("receipt candidate_id does not match")
    if receipt["semantic_sha256"] != semantic_sha:
        problems.append("receipt is not bound to the current semantic subject")
    if receipt["skill_blueprint_sha256"] != blueprint_sha:
        problems.append("receipt is not bound to the current Skill blueprint")
    if tuple(receipt["subject_fields"]) != SEMANTIC_SUBJECT_FIELDS:
        problems.append("receipt does not cover the complete semantic subject")

    verifier = receipt["verifier"]
    verifier_path = _safe_evidence_path(repo_root, verifier["artifact_locator"])
    if verifier_path is None or not verifier_path.is_file():
        problems.append("verifier artifact is not a repository-local file")
    elif file_digest(verifier_path) != verifier["artifact_sha256"]:
        problems.append("verifier artifact hash does not match the receipt")

    evidence_by_id = {item["id"]: item for item in evidence_manifest}
    binding_ids = [item["id"] for item in receipt["evidence_bindings"]]
    if len(binding_ids) != len(set(binding_ids)):
        problems.append("receipt evidence bindings are not unique")
    for binding in receipt["evidence_bindings"]:
        current = evidence_by_id.get(binding["id"])
        if current is None:
            problems.append(f"receipt evidence {binding['id']} is not resolved")
        elif current["sha256"] != binding["sha256"]:
            problems.append(f"receipt evidence hash drift: {binding['id']}")

    if receipt["result"]["status"] != "passed":
        problems.append("receipt does not record a passed result")

    registration = TRUSTED_EXECUTABLE_VERIFIERS.get(verifier["id"])
    if receipt["method"] != "executable_check" or registration is None:
        problems.append("receipt verifier is not registered for safe executable replay")
    elif (
        verifier["artifact_locator"] != registration["artifact_locator"]
        or verifier["artifact_sha256"] != registration["artifact_sha256"]
        or verifier["command"] != registration["command"]
    ):
        problems.append("receipt verifier does not match its trusted registration")
    elif verifier_path is not None and verifier_path.is_file():
        replay_environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(repo_root / "src"),
            "PYTHONIOENCODING": "utf-8",
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-B", str(verifier_path)],
                input=canonical_bytes(candidate),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=repo_root,
                env=replay_environment,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            problems.append(f"registered verifier replay failed: {exc}")
        else:
            output_sha = hashlib.sha256(completed.stdout).hexdigest()
            if completed.returncode != 0:
                problems.append("registered verifier replay returned a nonzero exit code")
            if output_sha != receipt["result"]["output_sha256"]:
                problems.append("registered verifier replay output does not match the receipt")
            try:
                replay_result = json.loads(completed.stdout.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                problems.append("registered verifier replay did not emit valid JSON")
            else:
                expected_result = {
                    "status": "passed",
                    "verifier_id": verifier["id"],
                    "semantic_sha256": semantic_sha,
                    "skill_blueprint_sha256": blueprint_sha,
                    "checks": receipt["result"]["checks"],
                }
                if replay_result != expected_result:
                    problems.append("registered verifier replay result does not match the receipt")
    if problems:
        return (
            GateResult(
                "semantic_verification",
                "fail",
                "; ".join(problems),
                tuple(binding_ids),
            ),
            None,
        )

    receipt_sha = file_digest(receipt_path)
    manifest = {
        "receipt_id": receipt["receipt_id"],
        "locator": locator,
        "sha256": receipt_sha,
        "semantic_sha256": semantic_sha,
        "skill_blueprint_sha256": blueprint_sha,
        "method": receipt["method"],
        "verifier_id": verifier["id"],
        "verifier_artifact_locator": verifier["artifact_locator"],
        "verifier_artifact_sha256": verifier["artifact_sha256"],
        "result": "passed",
    }
    return (
        GateResult(
            "semantic_verification",
            "pass",
            "replayed a registered executable verifier and bound its passed receipt to the complete semantic subject",
            tuple(binding_ids),
        ),
        manifest,
    )


def _human_acceptance_gate(
    candidate: Mapping[str, Any],
    repo_root: Path,
    verification_manifest: Mapping[str, Any] | None,
) -> tuple[GateResult, dict[str, Any] | None]:
    declaration = candidate["human_acceptance"]
    if declaration["status"] == "pending":
        return (
            GateResult(
                "human_acceptance",
                "pending",
                "human acceptance remains pending",
            ),
            None,
        )
    if declaration["status"] == "rejected":
        return (
            GateResult(
                "human_acceptance",
                "fail",
                "human reviewer rejected prototype skill activation",
            ),
            None,
        )
    if verification_manifest is None:
        return (
            GateResult(
                "human_acceptance",
                "fail",
                "human acceptance cannot bind an invalid or missing verification receipt",
            ),
            None,
        )

    locator = declaration["record_locator"]
    record_path = _safe_evidence_path(repo_root, locator)
    if record_path is None or not record_path.is_file():
        return (
            GateResult(
                "human_acceptance",
                "fail",
                "human acceptance record does not resolve to a repository-local file",
            ),
            None,
        )
    try:
        record = read_json(record_path)
    except (OSError, ValueError, PipelineError) as exc:
        return (
            GateResult(
                "human_acceptance",
                "fail",
                f"human acceptance record cannot be read: {exc}",
            ),
            None,
        )
    issues = validate_artifact(record, "human_acceptance", repo_root)
    if issues:
        return (
            GateResult(
                "human_acceptance",
                "fail",
                "human acceptance record violates its schema: "
                + "; ".join(map(str, issues)),
            ),
            None,
        )

    problems: list[str] = []
    if record["candidate_id"] != candidate["id"]:
        problems.append("acceptance candidate_id does not match")
    if record["semantic_sha256"] != verification_manifest["semantic_sha256"]:
        problems.append("acceptance is not bound to the verified semantic subject")
    if record["skill_blueprint_sha256"] != verification_manifest["skill_blueprint_sha256"]:
        problems.append("acceptance is not bound to the verified Skill blueprint")
    receipt_ref = record["verification_receipt"]
    if receipt_ref["receipt_id"] != verification_manifest["receipt_id"]:
        problems.append("acceptance references a different verification receipt")
    if receipt_ref["sha256"] != verification_manifest["sha256"]:
        problems.append("acceptance verification receipt hash does not match")
    if record["decision"] != "accepted":
        problems.append("acceptance record does not authorize prototype skill activation")

    record_sha = file_digest(record_path)
    registry_path = _safe_evidence_path(
        repo_root, TRUSTED_ACCEPTANCE_REGISTRY["locator"]
    )
    registry: dict[str, Any] | None = None
    if registry_path is None or not registry_path.is_file():
        problems.append("trusted acceptance registry is unavailable")
    elif file_digest(registry_path) != TRUSTED_ACCEPTANCE_REGISTRY["sha256"]:
        problems.append("trusted acceptance registry hash drift")
    else:
        try:
            registry = read_json(registry_path)
        except (OSError, ValueError, PipelineError) as exc:
            problems.append(f"trusted acceptance registry cannot be read: {exc}")
        else:
            registry_issues = validate_artifact(
                registry, "acceptance_registry", repo_root
            )
            if registry_issues:
                problems.append(
                    "trusted acceptance registry violates its schema: "
                    + "; ".join(map(str, registry_issues))
                )
            else:
                expected_registration = {
                    "acceptance_id": record["acceptance_id"],
                    "record_locator": locator,
                    "record_sha256": record_sha,
                    "candidate_id": candidate["id"],
                    "semantic_sha256": verification_manifest["semantic_sha256"],
                    "skill_blueprint_sha256": verification_manifest[
                        "skill_blueprint_sha256"
                    ],
                    "receipt_id": verification_manifest["receipt_id"],
                    "receipt_sha256": verification_manifest["sha256"],
                }
                matches = [
                    item
                    for item in registry["accepted_records"]
                    if item["acceptance_id"] == record["acceptance_id"]
                ]
                if len(matches) != 1 or dict(matches[0]) != expected_registration:
                    problems.append(
                        "human acceptance is not registered by the trusted attestation boundary"
                    )
    if problems:
        return (
            GateResult("human_acceptance", "fail", "; ".join(problems)),
            None,
        )

    assert registry is not None
    manifest = {
        "acceptance_id": record["acceptance_id"],
        "locator": locator,
        "sha256": record_sha,
        "semantic_sha256": record["semantic_sha256"],
        "skill_blueprint_sha256": record["skill_blueprint_sha256"],
        "receipt_id": receipt_ref["receipt_id"],
        "receipt_sha256": receipt_ref["sha256"],
        "decision": "accepted",
        "scope": record["scope"],
        "reviewer_role": record["reviewer_role"],
        "acceptance_registry_id": registry["registry_id"],
        "acceptance_registry_sha256": TRUSTED_ACCEPTANCE_REGISTRY["sha256"],
    }
    return (
        GateResult(
            "human_acceptance",
            "pass",
            "bound registered human acceptance to the exact semantic subject, Skill blueprint, and receipt",
        ),
        manifest,
    )


def _lifecycle_gate(candidate: Mapping[str, Any]) -> GateResult:
    if candidate["status"] == "parked":
        return GateResult(
            "candidate_lifecycle",
            "blocked",
            "candidate is parked; promotion is intentionally disabled",
        )
    return GateResult(
        "candidate_lifecycle",
        "pass",
        "candidate is explicitly ready for verification and promotion review",
    )


def _assumption_gate(candidate: Mapping[str, Any]) -> GateResult:
    allowed = {"structural", "measurement", "computational", "scope", "engineering"}
    unsupported = sorted(
        assumption["id"]
        for assumption in candidate["assumptions"]
        if assumption["classification"] not in allowed
    )
    if unsupported:
        return GateResult(
            "assumption_audit",
            "fail",
            "unclassified assumptions: " + ", ".join(unsupported),
        )
    return GateResult(
        "assumption_audit",
        "pass",
        f"classified cost and weakening route for {len(candidate['assumptions'])} assumptions",
    )


def _comparison_gate(candidate: Mapping[str, Any]) -> GateResult:
    novelty = candidate["novelty"]
    literature_evidence = [item for item in candidate["evidence"] if item["kind"] == "literature"]
    if novelty["scope"] == "field_level" and len(literature_evidence) < 3:
        return GateResult(
            "comparison_scope",
            "fail",
            "field-level novelty requires at least three literature evidence artifacts",
        )
    if len(candidate["comparators"]) < 2:
        return GateResult(
            "comparison_scope", "fail", "at least two explicit comparators are required"
        )
    return GateResult(
        "comparison_scope",
        "pass",
        f"scoped novelty as {novelty['scope']} against {len(candidate['comparators'])} comparators",
        tuple(item["id"] for item in literature_evidence),
    )


def _falsifiability_gate(candidate: Mapping[str, Any]) -> GateResult:
    claim = candidate["claim"]
    if not claim["measurable_target"] or not claim["kill_conditions"]:
        return GateResult(
            "falsifiability", "fail", "claim needs a measurable target and kill conditions"
        )
    if not candidate["risks"] or not candidate["limitations"]:
        return GateResult(
            "falsifiability", "fail", "candidate needs explicit risks and limitations"
        )
    return GateResult(
        "falsifiability",
        "pass",
        f"recorded {len(claim['kill_conditions'])} kill conditions and {len(candidate['risks'])} risks",
    )


def _induction_gate(candidate: Mapping[str, Any]) -> GateResult:
    blueprint = candidate["skill_blueprint"]
    name = blueprint["name"]
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) is None:
        return GateResult("induction_readiness", "fail", "skill name is not a lowercase slug")
    required_lists = ("inputs", "workflow", "outputs", "validation", "failure_modes")
    empty = [field for field in required_lists if not blueprint[field]]
    if empty:
        return GateResult(
            "induction_readiness", "fail", "empty blueprint fields: " + ", ".join(empty)
        )
    return GateResult(
        "induction_readiness",
        "pass",
        "skill blueprint has trigger, workflow, outputs, validation, and failure modes",
    )


def evaluate_candidate(
    candidate: Mapping[str, Any], repo_root: Path
) -> tuple[
    list[GateResult],
    list[dict[str, str]],
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    evidence_gate, evidence_manifest = _evidence_gate(candidate, repo_root)
    verification_gate, verification_manifest = _semantic_verification_gate(
        candidate, repo_root, evidence_manifest
    )
    human_gate, human_manifest = _human_acceptance_gate(
        candidate, repo_root, verification_manifest
    )
    gates = [
        GateResult("schema", "pass", "candidate conforms to candidate.schema.json"),
        evidence_gate,
        _assumption_gate(candidate),
        _comparison_gate(candidate),
        _falsifiability_gate(candidate),
        _induction_gate(candidate),
        verification_gate,
        human_gate,
        _lifecycle_gate(candidate),
    ]
    return gates, evidence_manifest, verification_manifest, human_manifest


def build_decision_packet(
    candidate: Mapping[str, Any],
    gates: list[GateResult],
    evidence_manifest: list[dict[str, str]],
    verification_manifest: Mapping[str, Any] | None,
    human_manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    candidate_sha = object_digest(candidate)
    gates_by_name = {gate.gate: gate for gate in gates}
    structural_pass = all(gates_by_name[name].verdict == "pass" for name in STRUCTURAL_GATES)
    evidence_pass = gates_by_name["evidence_integrity"].verdict == "pass"
    semantic_pass = gates_by_name["semantic_verification"].verdict == "pass"
    human_pass = gates_by_name["human_acceptance"].verdict == "pass"
    lifecycle_pass = gates_by_name["candidate_lifecycle"].verdict == "pass"
    promote = (
        structural_pass
        and evidence_pass
        and semantic_pass
        and human_pass
        and lifecycle_pass
    )
    if candidate["status"] == "parked":
        decision = "parked"
        recommendation = "keep_parked"
    elif not structural_pass or not evidence_pass:
        decision = "revise"
        recommendation = "revise"
    elif not semantic_pass:
        decision = "await_semantic_verification"
        recommendation = "await_semantic_verification"
    elif not human_pass and candidate["human_acceptance"]["status"] == "pending":
        decision = "await_human_acceptance"
        recommendation = "await_human_acceptance"
    else:
        decision = "promote_to_prototype" if promote else "revise"
        recommendation = "promote_to_prototype" if promote else "revise"

    semantic_status = (
        "verified"
        if semantic_pass
        else ("pending" if candidate["semantic_verification"]["status"] == "pending" else "invalid")
    )
    human_status = (
        "accepted"
        if human_pass
        else (
            candidate["human_acceptance"]["status"]
            if candidate["human_acceptance"]["status"] in {"pending", "rejected"}
            else "invalid"
        )
    )
    packet: dict[str, Any] = {
        "schema_version": "1.0",
        "packet_id": f"packet-{candidate_sha[:12]}",
        "candidate_id": candidate["id"],
        "candidate_sha256": candidate_sha,
        "claim": candidate["claim"],
        "assumptions": candidate["assumptions"],
        "proof_route": candidate["proof_route"],
        "novelty": candidate["novelty"],
        "comparators": candidate["comparators"],
        "expected_value": candidate["expected_value"],
        "risks": candidate["risks"],
        "limitations": candidate["limitations"],
        "evidence_manifest": evidence_manifest,
        "verification_receipts": [dict(verification_manifest)]
        if verification_manifest is not None
        else [],
        "human_acceptance_records": [dict(human_manifest)]
        if human_manifest is not None
        else [],
        "gate_results": [gate.as_dict() for gate in gates],
        "stage_status": {
            "structural_validation": "pass" if structural_pass else "fail",
            "evidence_integrity": "pass" if evidence_pass else "fail",
            "semantic_verification": semantic_status,
            "human_acceptance": human_status,
            "candidate_lifecycle": candidate["status"],
        },
        "decision": decision,
        "gate_recommendation": recommendation,
        "human_review_boundary": "Structural and integrity checks are not semantic proof. Activation requires a bound verification receipt and explicit human acceptance.",
        "semantic_verification_boundary": "Only a repository-registered executable verifier is replayed automatically, and its result applies only to the scope and limitations recorded in the bound receipt.",
        "reward_questions": candidate["reward_questions"],
    }
    return packet


def build_success_trace(
    candidate: Mapping[str, Any], packet: Mapping[str, Any]
) -> dict[str, Any]:
    required_stage_status = {
        "structural_validation": "pass",
        "evidence_integrity": "pass",
        "semantic_verification": "verified",
        "human_acceptance": "accepted",
        "candidate_lifecycle": "ready_for_verification",
    }
    blueprint_sha = skill_blueprint_digest(candidate)
    if (
        packet["decision"] != "promote_to_prototype"
        or packet["stage_status"] != required_stage_status
        or len(packet["verification_receipts"]) != 1
        or len(packet["human_acceptance_records"]) != 1
        or packet["verification_receipts"][0]["skill_blueprint_sha256"]
        != blueprint_sha
        or packet["human_acceptance_records"][0]["skill_blueprint_sha256"]
        != blueprint_sha
        or any(gate["verdict"] != "pass" for gate in packet["gate_results"])
    ):
        raise PipelineError(
            "success trace requires structural validity, evidence integrity, "
            "a bound verification receipt, explicit human acceptance, and a ready candidate"
        )

    packet_sha = object_digest(packet)
    blueprint = candidate["skill_blueprint"]
    receipt = packet["verification_receipts"][0]
    acceptance = packet["human_acceptance_records"][0]
    return {
        "schema_version": "1.0",
        "trace_id": f"trace-{packet_sha[:12]}",
        "source_candidate_id": candidate["id"],
        "source_packet_id": packet["packet_id"],
        "source_packet_sha256": packet_sha,
        "outcome": "verified_success",
        "reward_signal": {
            "type": "bound_verification_and_human_acceptance",
            "value": 1,
            "basis": [
                gate["gate"] for gate in packet["gate_results"] if gate["verdict"] == "pass"
            ],
        },
        "verification_receipt": {
            "receipt_id": receipt["receipt_id"],
            "sha256": receipt["sha256"],
            "semantic_sha256": receipt["semantic_sha256"],
            "skill_blueprint_sha256": receipt["skill_blueprint_sha256"],
            "method": receipt["method"],
            "verifier_id": receipt["verifier_id"],
        },
        "human_acceptance": {
            "acceptance_id": acceptance["acceptance_id"],
            "sha256": acceptance["sha256"],
            "scope": acceptance["scope"],
            "reviewer_role": acceptance["reviewer_role"],
            "skill_blueprint_sha256": acceptance["skill_blueprint_sha256"],
            "acceptance_registry_id": acceptance["acceptance_registry_id"],
            "acceptance_registry_sha256": acceptance["acceptance_registry_sha256"],
        },
        "skill_name": blueprint["name"],
        "trigger": blueprint["trigger"],
        "workflow": blueprint["workflow"],
        "validation": blueprint["validation"],
        "failure_modes": blueprint["failure_modes"],
    }


def build_induced_skill(
    candidate: Mapping[str, Any], trace: Mapping[str, Any]
) -> dict[str, Any]:
    blueprint = candidate["skill_blueprint"]
    return {
        "schema_version": "1.0",
        "name": blueprint["name"],
        "description": blueprint["description"],
        "trigger": blueprint["trigger"],
        "inputs": blueprint["inputs"],
        "workflow": blueprint["workflow"],
        "outputs": blueprint["outputs"],
        "validation": blueprint["validation"],
        "failure_modes": blueprint["failure_modes"],
        "activation_status": "eligible_for_activation",
        "provenance": {
            "trace_id": trace["trace_id"],
            "source_packet_id": trace["source_packet_id"],
            "reward_signal": trace["reward_signal"]["type"],
            "verification_receipt_id": trace["verification_receipt"]["receipt_id"],
            "verification_receipt_sha256": trace["verification_receipt"]["sha256"],
            "skill_blueprint_sha256": trace["verification_receipt"][
                "skill_blueprint_sha256"
            ],
            "human_acceptance_id": trace["human_acceptance"]["acceptance_id"],
            "human_acceptance_sha256": trace["human_acceptance"]["sha256"],
            "acceptance_registry_id": trace["human_acceptance"][
                "acceptance_registry_id"
            ],
            "acceptance_registry_sha256": trace["human_acceptance"][
                "acceptance_registry_sha256"
            ],
        },
    }


def render_skill_markdown(skill: Mapping[str, Any]) -> str:
    def section(title: str, values: list[str]) -> str:
        return f"## {title}\n\n" + "\n".join(f"{index}. {value}" for index, value in enumerate(values, 1))

    description = json.dumps(skill["description"], ensure_ascii=False)
    parts = [
        "---",
        f"name: {skill['name']}",
        f"description: {description}",
        "---",
        "",
        f"# {skill['name']}",
        "",
        f"Use when {skill['trigger'][0].lower() + skill['trigger'][1:]}",
        "",
        section("Inputs", skill["inputs"]),
        "",
        section("Workflow", skill["workflow"]),
        "",
        section("Outputs", skill["outputs"]),
        "",
        section("Validation", skill["validation"]),
        "",
        section("Failure modes", skill["failure_modes"]),
        "",
        "## Provenance",
        "",
        f"Eligible for activation from trace `{skill['provenance']['trace_id']}` after bound verification receipt `{skill['provenance']['verification_receipt_id']}` and human acceptance `{skill['provenance']['human_acceptance_id']}`.",
        "",
    ]
    return "\n".join(parts)


def _require_valid(value: Mapping[str, Any], kind: str, repo_root: Path) -> None:
    issues = validate_artifact(value, kind, repo_root)
    if issues:
        raise PipelineError(f"generated {kind} is invalid: " + "; ".join(map(str, issues)))


def _relative_artifact(output_dir: Path, path: Path) -> str:
    return path.relative_to(output_dir).as_posix()


def run_demo(
    candidate_path: str | Path,
    output_dir: str | Path,
    repo_root: str | Path | None = None,
) -> RunResult:
    root = Path(repo_root).resolve() if repo_root else repository_root().resolve()
    candidate = read_json(candidate_path)
    issues = validate_artifact(candidate, "candidate", root)
    if issues:
        raise CandidateValidationError(issues)

    (
        gates,
        evidence_manifest,
        verification_manifest,
        human_manifest,
    ) = evaluate_candidate(candidate, root)
    packet = build_decision_packet(
        candidate,
        gates,
        evidence_manifest,
        verification_manifest,
        human_manifest,
    )
    _require_valid(packet, "decision_packet", root)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    packet_path = destination / "decision_packet.json"
    trace_path = destination / "success_trace.json"
    skill_json_path = destination / "induced_skill" / "skill.json"
    skill_md_path = destination / "induced_skill" / "SKILL.md"
    manifest_path = destination / "manifest.json"
    write_json(packet_path, packet)

    artifacts = [packet_path]
    emitted_trace: Path | None = None
    emitted_skill: Path | None = None
    if packet["decision"] == "promote_to_prototype":
        trace = build_success_trace(candidate, packet)
        _require_valid(trace, "success_trace", root)
        skill = build_induced_skill(candidate, trace)
        _require_valid(skill, "induced_skill", root)
        write_json(trace_path, trace)
        write_json(skill_json_path, skill)
        skill_md_path.parent.mkdir(parents=True, exist_ok=True)
        skill_md_path.write_text(render_skill_markdown(skill), encoding="utf-8")
        artifacts.extend([trace_path, skill_json_path, skill_md_path])
        emitted_trace = trace_path
        emitted_skill = skill_md_path
    else:
        for stale in (trace_path, skill_json_path, skill_md_path):
            stale.unlink(missing_ok=True)

    manifest = {
        "schema_version": "1.0",
        "run_id": packet["packet_id"],
        "decision": packet["decision"],
        "candidate_sha256": packet["candidate_sha256"],
        "artifacts": [
            {
                "path": _relative_artifact(destination, artifact),
                "sha256": file_digest(artifact),
            }
            for artifact in artifacts
        ],
    }
    write_json(manifest_path, manifest)
    return RunResult(
        decision=packet["decision"],
        output_dir=destination,
        decision_packet=packet_path,
        success_trace=emitted_trace,
        induced_skill=emitted_skill,
        manifest=manifest_path,
    )
