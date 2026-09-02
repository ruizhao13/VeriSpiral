"""Human-governed co-evolution of research specifications and solution search.

This module implements a deliberately small control-plane state machine.  It
does not generate algorithms and it does not prove scientific claims.  An AI
submission may either propose a solution under the current specification or
open a discussion about revising the model/verifier.  Only an explicit human
decision can create a versioned specification branch; an existing branch is
never mutated and work on a child branch never counts as progress on its
parent.

The public fixture is deterministic so that the authorization and provenance
semantics can be reviewed independently from any model provider.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .pipeline import file_digest, object_digest, repository_root, write_json
from .schema import load_schema, validate


SPEC_SCHEMA = "research_specification.schema.json"
SCENARIO_SCHEMA = "research_coevolution_scenario.schema.json"
TRACE_SCHEMA = "research_coevolution_trace.schema.json"
MANIFEST_SCHEMA = "research_coevolution_manifest.schema.json"
ZERO_SHA256 = "0" * 64
SUPPORTED_VERIFIERS = {
    "assumption_exact_match",
    "information_interface_exact_match",
    "rate_signature_exact_match",
}
REQUIRED_BASE_VERIFIERS = {
    "assumption_exact_match",
    "rate_signature_exact_match",
}
SPEC_FIELDS = {
    "model",
    "target",
    "assumptions",
    "verifier_suite",
    "human_judgment_boundary",
    "version",
}


class ResearchSpecError(RuntimeError):
    """Raised when a scenario violates a specification-governance invariant."""


@dataclass(frozen=True)
class ResearchSpecRunResult:
    output_dir: Path
    trace: Path
    manifest: Path
    final_status: str


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ResearchSpecError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _load_strict_object(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise ResearchSpecError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ResearchSpecError(f"{label} must be a JSON object: {path}")
    return value


def _require_schema(
    value: Mapping[str, Any], schema_name: str, root: Path, label: str
) -> None:
    issues = validate(value, load_schema(root / "schemas" / schema_name))
    if issues:
        raise ResearchSpecError(
            f"invalid {label}: " + "; ".join(str(issue) for issue in issues)
        )


def _safe_repo_file(root: Path, locator: str, label: str) -> Path:
    if not locator or "\\" in locator:
        raise ResearchSpecError(f"{label} must be a canonical repository-local path")
    relative = Path(locator)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ResearchSpecError(f"{label} escapes or is not canonical within the repository")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ResearchSpecError(f"{label} escapes the repository") from exc
    if not resolved.is_file():
        raise ResearchSpecError(f"{label} does not resolve to a file: {locator}")
    return resolved


def _semver(value: str, label: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    if match is None:
        raise ResearchSpecError(f"{label} must be a canonical major.minor.patch version")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _validate_specification(spec: Mapping[str, Any], root: Path, label: str) -> None:
    _require_schema(spec, SPEC_SCHEMA, root, label)
    _semver(str(spec["version"]), f"{label} version")
    verifier_ids = [item["verifier_id"] for item in spec["verifier_suite"]]
    if len(verifier_ids) != len(set(verifier_ids)):
        raise ResearchSpecError(f"{label} verifier identifiers must be unique")
    verifier_types = {item["type"] for item in spec["verifier_suite"]}
    unsupported = verifier_types - SUPPORTED_VERIFIERS
    if unsupported:
        raise ResearchSpecError(
            f"{label} uses unsupported deterministic verifier types: {sorted(unsupported)}"
        )
    missing = REQUIRED_BASE_VERIFIERS - verifier_types
    if missing:
        raise ResearchSpecError(
            f"{label} is missing required control verifiers: {sorted(missing)}"
        )


def _load_spec_registry(
    scenario: Mapping[str, Any], root: Path
) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    resolved_paths: set[Path] = set()
    for entry in scenario["specification_registry"]:
        spec_id = entry["specification_id"]
        if spec_id in registry:
            raise ResearchSpecError(f"duplicate specification id: {spec_id}")
        path = _safe_repo_file(root, entry["path"], f"specification {spec_id}")
        if path in resolved_paths:
            raise ResearchSpecError("multiple specification ids resolve to the same file")
        resolved_paths.add(path)
        if file_digest(path) != entry["file_sha256"]:
            raise ResearchSpecError(f"registered file hash drift for specification {spec_id}")
        spec = _load_strict_object(path, f"specification {spec_id}")
        _validate_specification(spec, root, f"specification {spec_id}")
        digest = object_digest(spec)
        if digest != entry["specification_sha256"]:
            raise ResearchSpecError(f"registered object hash drift for specification {spec_id}")
        registry[spec_id] = {
            "specification": spec,
            "specification_sha256": digest,
            "file_sha256": entry["file_sha256"],
            "path": entry["path"],
        }
    return registry


def _changed_spec_fields(
    base: Mapping[str, Any], proposed: Mapping[str, Any]
) -> list[str]:
    return sorted(field for field in SPEC_FIELDS if base[field] != proposed[field])


def _validate_revision(
    base: Mapping[str, Any],
    proposed: Mapping[str, Any],
    declared_kind: str,
) -> list[str]:
    changed = _changed_spec_fields(base, proposed)
    substantive = [field for field in changed if field != "version"]
    if not substantive:
        raise ResearchSpecError("a specification revision must change more than its version")
    if "version" not in changed:
        raise ResearchSpecError("a specification revision must change its version")
    if _semver(str(proposed["version"]), "proposed version") <= _semver(
        str(base["version"]), "base version"
    ):
        raise ResearchSpecError("a proposed specification version must increase")

    model_fields = {"model", "target", "assumptions"}
    verifier_fields = {"verifier_suite", "human_judgment_boundary"}
    touches_model = bool(set(substantive) & model_fields)
    touches_verifier = bool(set(substantive) & verifier_fields)
    actual_kind = (
        "model_and_verifier_revision"
        if touches_model and touches_verifier
        else "model_revision"
        if touches_model
        else "verifier_revision"
    )
    if declared_kind != actual_kind:
        raise ResearchSpecError(
            f"declared revision kind {declared_kind!r} does not match changed fields "
            f"{substantive!r} ({actual_kind})"
        )
    return changed


def _validate_problem_identity_effect(revision_kind: str, effect: str) -> None:
    expected = (
        "preserves_problem"
        if revision_kind == "verifier_revision"
        else "creates_new_target_lineage"
    )
    if effect != expected:
        raise ResearchSpecError(
            f"{revision_kind} requires problem_identity_effect={expected!r}; "
            f"received {effect!r}"
        )


def _resolve_consumptions(
    declarations: list[Mapping[str, str]],
    events_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    resolved: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for declaration in declarations:
        event_id = declaration["event_id"]
        response_code = declaration["response_code"]
        key = (event_id, response_code)
        if key in seen:
            raise ResearchSpecError(f"duplicate consumption edge: {event_id}/{response_code}")
        seen.add(key)
        try:
            source = events_by_id[event_id]
        except KeyError as exc:
            raise ResearchSpecError(f"consumption references unknown event: {event_id}") from exc
        if response_code not in source["emits"]:
            raise ResearchSpecError(
                f"event {event_id} did not emit response code {response_code!r}"
            )
        resolved.append(
            {
                "event_id": event_id,
                "event_sha256": source["event_sha256"],
                "response_code": response_code,
            }
        )
    return resolved


def _seal_event(
    events: list[dict[str, Any]],
    events_by_id: dict[str, dict[str, Any]],
    *,
    event_id: str,
    actor: str,
    event_type: str,
    round_id: str,
    branch_id: str,
    specification_id: str,
    specification_sha256: str,
    consumption_declarations: list[Mapping[str, str]],
    emits: list[str],
    source_payload: Mapping[str, Any],
    subject_id: str,
    status: str,
    summary: str,
    authorization: str,
    parent_progress_credit: bool,
) -> dict[str, Any]:
    if event_id in events_by_id:
        raise ResearchSpecError(f"duplicate event id: {event_id}")
    if len(emits) != len(set(emits)):
        raise ResearchSpecError(f"event {event_id} emits duplicate response codes")
    event = {
        "event_id": event_id,
        "event_index": len(events),
        "actor": actor,
        "event_type": event_type,
        "round_id": round_id,
        "branch_id": branch_id,
        "specification_id": specification_id,
        "specification_sha256": specification_sha256,
        "previous_event_sha256": events[-1]["event_sha256"] if events else ZERO_SHA256,
        "consumes": _resolve_consumptions(consumption_declarations, events_by_id),
        "emits": emits,
        "source_payload_sha256": object_digest(source_payload),
        "details": {
            "subject_id": subject_id,
            "status": status,
            "summary": summary,
            "authorization": authorization,
            "parent_progress_credit": parent_progress_credit,
        },
    }
    event["event_sha256"] = object_digest(event)
    events.append(event)
    events_by_id[event_id] = event
    return event


def _required_consumption(
    declarations: list[Mapping[str, str]], terminal_event: Mapping[str, Any]
) -> None:
    if not any(item["event_id"] == terminal_event["event_id"] for item in declarations):
        raise ResearchSpecError(
            "each research round must consume the preceding round's verifier diagnosis "
            "or human decision"
        )


def _evaluate_solution(
    candidate: Mapping[str, Any], specification: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], str, str, str]:
    results: list[dict[str, Any]] = []
    for verifier in specification["verifier_suite"]:
        verifier_type = verifier["type"]
        if verifier_type == "assumption_exact_match":
            passed = candidate["assumptions"] == specification["assumptions"]
            code = "assumption_scope_match" if passed else "assumption_scope_mismatch"
        elif verifier_type == "information_interface_exact_match":
            passed = (
                candidate["information_interface"]["horizon_knowledge"]
                == specification["assumptions"].get("horizon_knowledge")
            )
            code = (
                "information_interface_match"
                if passed
                else "information_interface_mismatch"
            )
        elif verifier_type == "rate_signature_exact_match":
            passed = (
                candidate["rate_signature"]
                == specification["target"]["required_rate_signature"]
            )
            code = "target_rate_signature_match" if passed else "target_rate_signature_gap"
        else:  # guarded when loading the specification
            raise ResearchSpecError(f"unsupported verifier type: {verifier_type}")
        results.append(
            {
                "verifier_id": verifier["verifier_id"],
                "type": verifier_type,
                "status": "pass" if passed else "fail",
                "diagnostic_code": code,
                "semantic_scope": verifier["semantic_scope"],
                "limitation": verifier["limitation"],
            }
        )

    failures = [result for result in results if result["status"] == "fail"]
    if not failures:
        return (
            results,
            "target_compatible_control_pass",
            "present_target_compatible_candidate_for_human_judgment",
            "The candidate matches the registered assumptions and target rate signature; "
            "semantic truth remains outside this control check.",
        )
    codes = {result["diagnostic_code"] for result in failures}
    if codes & {"assumption_scope_mismatch", "information_interface_mismatch"}:
        response = "preserve_target_or_request_model_branch"
        summary = (
            "The candidate changes the declared assumption scope and cannot count as "
            "progress on this branch."
        )
    else:
        response = "close_rate_gap_without_changing_target"
        summary = "The candidate preserves the target assumptions but misses the target rate signature."
    return results, "failed_control_checks", response, summary


def _decision_consumption(
    event: Mapping[str, Any], response_code: str
) -> list[dict[str, str]]:
    return [{"event_id": event["event_id"], "response_code": response_code}]


def _branch_record(
    branch_id: str,
    parent_branch_id: str | None,
    specification_id: str,
    registry_entry: Mapping[str, Any],
    created_by_event_id: str,
    target_lineage_id: str,
    lineage_relation: str,
) -> dict[str, Any]:
    return {
        "branch_id": branch_id,
        "parent_branch_id": parent_branch_id,
        "specification_id": specification_id,
        "specification_sha256": registry_entry["specification_sha256"],
        "specification_version": registry_entry["specification"]["version"],
        "created_by_event_id": created_by_event_id,
        "target_lineage_id": target_lineage_id,
        "lineage_relation": lineage_relation,
        "status": "researching",
        "parent_progress_credit": False,
    }


def _expected_source_payload_hashes(
    scenario: Mapping[str, Any], registry: Mapping[str, Mapping[str, Any]]
) -> dict[str, str]:
    """Replay source selection so event payload hashes bind to the scenario."""

    initial = scenario["initial_state"]
    branch_specs: dict[str, str] = {
        initial["branch_id"]: initial["specification_id"]
    }
    payloads: dict[str, Mapping[str, Any]] = {
        "specification.registered": initial
    }
    for round_input in scenario["rounds"]:
        round_id = round_input["round_id"]
        branch_id = round_input["branch_id"]
        try:
            specification_id = branch_specs[branch_id]
            specification = registry[specification_id]["specification"]
        except KeyError as exc:
            raise ResearchSpecError(
                f"scenario source replay references an unknown branch: {branch_id}"
            ) from exc
        submission = round_input["submission"]
        if submission["kind"] == "solution_candidate":
            candidate = submission["solution_candidate"]
            payloads[f"{round_id}.submission"] = candidate
            results, status, _, _ = _evaluate_solution(candidate, specification)
            payloads[f"{round_id}.diagnosis"] = {
                "candidate_id": candidate["candidate_id"],
                "results": results,
                "status": status,
                "scientific_claim_status": "not_semantically_verified",
            }
            judgment = round_input["human_solution_judgment"]
            if judgment is not None:
                payloads[f"{round_id}.human-solution-judgment"] = judgment
        else:
            discussion = submission["revision_discussion"]
            proposed = registry[discussion["proposed_specification_id"]]["specification"]
            discussion_payload = dict(discussion)
            discussion_payload["changed_fields"] = _validate_revision(
                specification, proposed, discussion["revision_kind"]
            )
            _validate_problem_identity_effect(
                discussion["revision_kind"], discussion["problem_identity_effect"]
            )
            payloads[f"{round_id}.submission"] = discussion_payload
            decision = round_input["human_spec_decision"]
            payloads[f"{round_id}.human-spec-decision"] = decision
            if decision["action"] != "reject":
                if decision["selected_revision_kind"] != discussion["revision_kind"]:
                    raise ResearchSpecError(
                        "human decision crosses the AI discussion revision_kind"
                    )
                selected = registry[decision["selected_specification_id"]][
                    "specification"
                ]
                _validate_revision(
                    specification, selected, decision["selected_revision_kind"]
                )
                branch_specs[decision["child_branch_id"]] = decision[
                    "selected_specification_id"
                ]
    return {event_id: object_digest(payload) for event_id, payload in payloads.items()}


def verify_trace_integrity(
    trace: Mapping[str, Any],
    root: Path | None = None,
    scenario: Mapping[str, Any] | str | Path | None = None,
) -> None:
    """Verify event chaining and bind every source payload to a scenario replay."""

    repo = (root or repository_root()).resolve()
    _require_schema(trace, TRACE_SCHEMA, repo, "research co-evolution trace")
    if scenario is None:
        raise ResearchSpecError(
            "scenario is required to bind source_payload_sha256 values"
        )
    scenario_value = (
        _load_strict_object(Path(scenario), "research co-evolution scenario")
        if isinstance(scenario, (str, Path))
        else scenario
    )
    _require_schema(
        scenario_value, SCENARIO_SCHEMA, repo, "research co-evolution scenario"
    )
    if object_digest(scenario_value) != trace["scenario_sha256"]:
        raise ResearchSpecError("trace is not bound to the supplied scenario object")
    registry = _load_spec_registry(scenario_value, repo)
    expected_payload_hashes = _expected_source_payload_hashes(
        scenario_value, registry
    )
    previous = ZERO_SHA256
    seen: dict[str, Mapping[str, Any]] = {}
    for expected_index, event in enumerate(trace["events"]):
        if event["event_index"] != expected_index:
            raise ResearchSpecError("event indices are not contiguous")
        if event["event_id"] in seen:
            raise ResearchSpecError(f"duplicate event id in trace: {event['event_id']}")
        if event["previous_event_sha256"] != previous:
            raise ResearchSpecError(f"event chain break at {event['event_id']}")
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        if object_digest(body) != event["event_sha256"]:
            raise ResearchSpecError(f"event hash mismatch at {event['event_id']}")
        expected_payload_hash = expected_payload_hashes.get(event["event_id"])
        if expected_payload_hash is None:
            raise ResearchSpecError(
                f"trace event is not produced by the supplied scenario: {event['event_id']}"
            )
        if event["source_payload_sha256"] != expected_payload_hash:
            raise ResearchSpecError(
                f"source payload hash mismatch at {event['event_id']}"
            )
        for consumption in event["consumes"]:
            source = seen.get(consumption["event_id"])
            if source is None:
                raise ResearchSpecError(
                    f"event {event['event_id']} consumes a future or missing event"
                )
            if source["event_sha256"] != consumption["event_sha256"]:
                raise ResearchSpecError(
                    f"consumption hash mismatch at {event['event_id']}"
                )
            if consumption["response_code"] not in source["emits"]:
                raise ResearchSpecError(
                    f"consumption response mismatch at {event['event_id']}"
                )
        seen[event["event_id"]] = event
        previous = event["event_sha256"]
    if set(seen) != set(expected_payload_hashes):
        raise ResearchSpecError("trace omits one or more scenario-produced events")
    if trace["event_chain_head_sha256"] != previous:
        raise ResearchSpecError("trace event-chain head does not match the final event")

    with tempfile.TemporaryDirectory() as temporary:
        replay_root = Path(temporary)
        replay_scenario_path = replay_root / "scenario.json"
        write_json(replay_scenario_path, scenario_value)
        replay_result = run_research_specification_loop(
            replay_scenario_path,
            replay_root / "output",
            repo,
            _skip_trace_verification=True,
        )
        expected_trace = _load_strict_object(
            replay_result.trace, "canonical replay trace"
        )
    if trace != expected_trace:
        differing = sorted(
            key
            for key in set(trace) | set(expected_trace)
            if trace.get(key) != expected_trace.get(key)
        )
        raise ResearchSpecError(
            "trace differs from canonical scenario replay at top-level fields: "
            + ", ".join(differing)
        )


def run_research_specification_loop(
    scenario_path: str | Path,
    output_dir: str | Path,
    root: str | Path | None = None,
    *,
    _skip_trace_verification: bool = False,
) -> ResearchSpecRunResult:
    """Execute a deterministic, human-gated research-specification scenario."""

    repo = Path(root).resolve() if root is not None else repository_root().resolve()
    scenario_file = Path(scenario_path).resolve()
    scenario = _load_strict_object(scenario_file, "research co-evolution scenario")
    _require_schema(scenario, SCENARIO_SCHEMA, repo, "research co-evolution scenario")
    registry = _load_spec_registry(scenario, repo)

    initial = scenario["initial_state"]
    try:
        initial_entry = registry[initial["specification_id"]]
    except KeyError as exc:
        raise ResearchSpecError("initial specification is not registered") from exc

    branches: dict[str, dict[str, Any]] = {
        initial["branch_id"]: _branch_record(
            initial["branch_id"],
            None,
            initial["specification_id"],
            initial_entry,
            "specification.registered",
            f"{initial['branch_id']}:target-lineage",
            "root",
        )
    }
    events: list[dict[str, Any]] = []
    events_by_id: dict[str, dict[str, Any]] = {}
    genesis = _seal_event(
        events,
        events_by_id,
        event_id="specification.registered",
        actor="human",
        event_type="specification_registered",
        round_id="setup",
        branch_id=initial["branch_id"],
        specification_id=initial["specification_id"],
        specification_sha256=initial_entry["specification_sha256"],
        consumption_declarations=[],
        emits=["begin_research_under_registered_specification"],
        source_payload=initial,
        subject_id=initial["specification_id"],
        status="active",
        summary="The human registered the initial model, target, assumptions, and verifier suite.",
        authorization="human_specification_authority",
        parent_progress_credit=False,
    )
    previous_terminal: Mapping[str, Any] = genesis
    round_records: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []

    rounds = scenario["rounds"]
    if [item["round_index"] for item in rounds] != list(range(1, len(rounds) + 1)):
        raise ResearchSpecError("round indices must be contiguous and start at 1")

    for round_input in rounds:
        round_id = round_input["round_id"]
        branch_id = round_input["branch_id"]
        try:
            branch = branches[branch_id]
        except KeyError as exc:
            raise ResearchSpecError(f"round references unknown branch: {branch_id}") from exc
        if branch["status"] != "researching":
            raise ResearchSpecError(f"branch {branch_id} is not ready for another research round")
        entry = registry[branch["specification_id"]]
        specification = entry["specification"]
        submission = round_input["submission"]
        declarations = submission["consumes"]
        _required_consumption(declarations, previous_terminal)
        submission_event_id = f"{round_id}.submission"

        solution = submission["solution_candidate"]
        discussion = submission["revision_discussion"]
        if submission["kind"] == "solution_candidate":
            if solution is None or discussion is not None:
                raise ResearchSpecError("a solution submission must contain only solution_candidate")
            if round_input["human_spec_decision"] is not None:
                raise ResearchSpecError("a solution round cannot carry a specification decision")
            submit_event = _seal_event(
                events,
                events_by_id,
                event_id=submission_event_id,
                actor="ai",
                event_type="ai_solution_submission",
                round_id=round_id,
                branch_id=branch_id,
                specification_id=branch["specification_id"],
                specification_sha256=branch["specification_sha256"],
                consumption_declarations=declarations,
                emits=["run_registered_control_verifiers"],
                source_payload=solution,
                subject_id=solution["candidate_id"],
                status="proposal_received",
                summary=solution["proposal_summary"],
                authorization="ai_proposal_only_not_evidence",
                parent_progress_credit=False,
            )
            verifier_results, status, response_code, diagnosis_summary = _evaluate_solution(
                solution, specification
            )
            diagnosis_payload = {
                "candidate_id": solution["candidate_id"],
                "results": verifier_results,
                "status": status,
                "scientific_claim_status": "not_semantically_verified",
            }
            diagnosis_event = _seal_event(
                events,
                events_by_id,
                event_id=f"{round_id}.diagnosis",
                actor="system",
                event_type="control_verifier_diagnosis",
                round_id=round_id,
                branch_id=branch_id,
                specification_id=branch["specification_id"],
                specification_sha256=branch["specification_sha256"],
                consumption_declarations=_decision_consumption(
                    submit_event, "run_registered_control_verifiers"
                ),
                emits=[response_code],
                source_payload=diagnosis_payload,
                subject_id=solution["candidate_id"],
                status=status,
                summary=diagnosis_summary,
                authorization="control_check_only_not_scientific_verification",
                parent_progress_credit=False,
            )
            judgment_input = round_input["human_solution_judgment"]
            terminal: Mapping[str, Any] = diagnosis_event
            judgment_event: Mapping[str, Any] | None = None
            if status == "target_compatible_control_pass":
                if judgment_input is None:
                    raise ResearchSpecError(
                        "a target-compatible candidate requires an explicit human judgment"
                    )
                if judgment_input["diagnosis_event_id"] != diagnosis_event["event_id"]:
                    raise ResearchSpecError("human judgment does not reference this diagnosis")
                judgment_status = {
                    "accept_for_semantic_review": "candidate_ready_for_semantic_review",
                    "reject_candidate": "candidate_rejected_by_human",
                    "request_revision": "candidate_revision_requested",
                }[judgment_input["action"]]
                judgment_event = _seal_event(
                    events,
                    events_by_id,
                    event_id=f"{round_id}.human-solution-judgment",
                    actor="human",
                    event_type="human_solution_judgment",
                    round_id=round_id,
                    branch_id=branch_id,
                    specification_id=branch["specification_id"],
                    specification_sha256=branch["specification_sha256"],
                    consumption_declarations=_decision_consumption(
                        diagnosis_event,
                        "present_target_compatible_candidate_for_human_judgment",
                    ),
                    emits=[judgment_status],
                    source_payload=judgment_input,
                    subject_id=solution["candidate_id"],
                    status=judgment_status,
                    summary=judgment_input["judgment_note"],
                    authorization="human_judgment_without_theorem_acceptance",
                    parent_progress_credit=False,
                )
                terminal = judgment_event
                if judgment_input["action"] == "accept_for_semantic_review":
                    branch["status"] = "candidate_ready_for_semantic_review"
            elif judgment_input is not None:
                raise ResearchSpecError(
                    "a failed control diagnosis cannot be promoted by a human-solution judgment"
                )

            candidate_records.append(
                {
                    "candidate_id": solution["candidate_id"],
                    "branch_id": branch_id,
                    "specification_id": branch["specification_id"],
                    "specification_sha256": branch["specification_sha256"],
                    "target_lineage_id": branch["target_lineage_id"],
                    "control_status": status,
                    "verifier_results": verifier_results,
                    "diagnosis_event_id": diagnosis_event["event_id"],
                    "human_judgment_event_id": (
                        judgment_event["event_id"] if judgment_event is not None else None
                    ),
                    "parent_progress_credit": False,
                    "scientific_claim_status": "not_established",
                }
            )
            round_records.append(
                {
                    "round_index": round_input["round_index"],
                    "round_id": round_id,
                    "branch_id": branch_id,
                    "submission_kind": "solution_candidate",
                    "submission_event_id": submit_event["event_id"],
                    "terminal_event_id": terminal["event_id"],
                    "consumed_preceding_terminal_event_id": previous_terminal["event_id"],
                    "outcome": status,
                }
            )
            previous_terminal = terminal

        elif submission["kind"] == "revision_discussion":
            if discussion is None or solution is not None:
                raise ResearchSpecError("a discussion submission must contain only revision_discussion")
            if round_input["human_solution_judgment"] is not None:
                raise ResearchSpecError("a discussion round cannot carry a solution judgment")
            if discussion["base_specification_id"] != branch["specification_id"]:
                raise ResearchSpecError("discussion base specification does not match its branch")
            if discussion["base_specification_sha256"] != branch["specification_sha256"]:
                raise ResearchSpecError("discussion base specification hash does not match its branch")
            try:
                proposed_entry = registry[discussion["proposed_specification_id"]]
            except KeyError as exc:
                raise ResearchSpecError("discussion proposes an unregistered specification") from exc
            changed_fields = _validate_revision(
                specification,
                proposed_entry["specification"],
                discussion["revision_kind"],
            )
            _validate_problem_identity_effect(
                discussion["revision_kind"], discussion["problem_identity_effect"]
            )
            discussion_payload = dict(discussion)
            discussion_payload["changed_fields"] = changed_fields
            discussion_event = _seal_event(
                events,
                events_by_id,
                event_id=submission_event_id,
                actor="ai",
                event_type="ai_spec_revision_discussion",
                round_id=round_id,
                branch_id=branch_id,
                specification_id=branch["specification_id"],
                specification_sha256=branch["specification_sha256"],
                consumption_declarations=declarations,
                emits=["human_spec_decision_required"],
                source_payload=discussion_payload,
                subject_id=discussion["discussion_id"],
                status="proposal_not_applied",
                summary=discussion["question_for_human"],
                authorization="ai_may_discuss_but_cannot_change_specification",
                parent_progress_credit=False,
            )
            decision = round_input["human_spec_decision"]
            if decision is None:
                raise ResearchSpecError("a revision discussion requires a human decision")
            if decision["discussion_event_id"] != discussion_event["event_id"]:
                raise ResearchSpecError("human decision references the wrong discussion event")
            if decision["proposed_specification_id"] != discussion["proposed_specification_id"]:
                raise ResearchSpecError("human decision references the wrong proposed specification")
            if (
                decision["proposed_specification_sha256"]
                != proposed_entry["specification_sha256"]
            ):
                raise ResearchSpecError("human decision does not bind the proposed specification hash")

            action = decision["action"]
            child_branch_id = decision["child_branch_id"]
            selected_spec_id = decision["selected_specification_id"]
            if action == "reject":
                if child_branch_id is not None or selected_spec_id is not None:
                    raise ResearchSpecError("a rejected revision cannot create a branch")
                decision_status = "revision_rejected_parent_preserved"
            else:
                if not child_branch_id or not selected_spec_id:
                    raise ResearchSpecError("an approved revision must name a child branch and specification")
                if child_branch_id in branches:
                    raise ResearchSpecError(f"duplicate branch id: {child_branch_id}")
                if action in {"accept", "branch"} and selected_spec_id != discussion[
                    "proposed_specification_id"
                ]:
                    raise ResearchSpecError(
                        f"{action} must select the exact AI-proposed specification"
                    )
                if action == "modify" and selected_spec_id == discussion[
                    "proposed_specification_id"
                ]:
                    raise ResearchSpecError("modify must select a distinct human-modified specification")
                try:
                    selected_entry = registry[selected_spec_id]
                except KeyError as exc:
                    raise ResearchSpecError("human decision selects an unregistered specification") from exc
                if decision["selected_revision_kind"] != discussion["revision_kind"]:
                    raise ResearchSpecError(
                        "human accept/modify/branch must preserve the AI discussion revision_kind; "
                        "a cross-kind change requires a new AI proposal and discussion"
                    )
                _validate_revision(
                    specification,
                    selected_entry["specification"],
                    decision["selected_revision_kind"],
                )
                if action in {"accept", "modify"}:
                    if decision["selected_revision_kind"] != "verifier_revision":
                        raise ResearchSpecError(
                            "accept or modify can supersede a target-lineage branch only "
                            "for a verifier-only revision; model revisions require branch"
                        )
                    decision_status = "revision_accepted_as_immutable_successor"
                else:
                    decision_status = "revision_created_separate_branch"

            decision_event = _seal_event(
                events,
                events_by_id,
                event_id=f"{round_id}.human-spec-decision",
                actor="human",
                event_type="human_spec_decision",
                round_id=round_id,
                branch_id=branch_id,
                specification_id=branch["specification_id"],
                specification_sha256=branch["specification_sha256"],
                consumption_declarations=_decision_consumption(
                    discussion_event, "human_spec_decision_required"
                ),
                emits=[decision["continuation_response_code"]],
                source_payload=decision,
                subject_id=discussion["discussion_id"],
                status=decision_status,
                summary=decision["decision_note"],
                authorization="human_specification_authority",
                parent_progress_credit=False,
            )
            if action != "reject":
                selected_entry = registry[selected_spec_id]
                if action in {"accept", "modify"}:
                    target_lineage_id = branch["target_lineage_id"]
                    lineage_relation = "accepted_successor"
                    branch["status"] = "superseded"
                else:
                    target_lineage_id = f"{child_branch_id}:target-lineage"
                    lineage_relation = "separate_model_branch"
                branches[child_branch_id] = _branch_record(
                    child_branch_id,
                    branch_id,
                    selected_spec_id,
                    selected_entry,
                    decision_event["event_id"],
                    target_lineage_id,
                    lineage_relation,
                )

            round_records.append(
                {
                    "round_index": round_input["round_index"],
                    "round_id": round_id,
                    "branch_id": branch_id,
                    "submission_kind": "revision_discussion",
                    "submission_event_id": discussion_event["event_id"],
                    "terminal_event_id": decision_event["event_id"],
                    "consumed_preceding_terminal_event_id": previous_terminal["event_id"],
                    "outcome": decision_status,
                }
            )
            previous_terminal = decision_event
        else:
            raise ResearchSpecError(f"unsupported AI submission kind: {submission['kind']}")

    initial_branch = branches[initial["branch_id"]]
    initial_target_lineage_id = initial_branch["target_lineage_id"]
    active_target_branches = [
        item
        for item in branches.values()
        if item["target_lineage_id"] == initial_target_lineage_id
        and item["status"] != "superseded"
    ]
    trace = {
        "schema_version": "1.0",
        "scenario_id": scenario["scenario_id"],
        "scenario_sha256": object_digest(scenario),
        "initial_branch_id": initial["branch_id"],
        "initial_specification_id": initial["specification_id"],
        "initial_specification_sha256": initial_entry["specification_sha256"],
        "events": events,
        "event_chain_head_sha256": events[-1]["event_sha256"],
        "rounds": round_records,
        "branches": sorted(branches.values(), key=lambda item: item["branch_id"]),
        "candidates": candidate_records,
        "invariants": {
            "ai_changed_specification": False,
            "all_specification_changes_human_authorized": True,
            "all_specification_changes_created_new_branches": True,
            "parent_progress_inherited_from_child": False,
            "initial_specification_preserved": (
                initial_branch["specification_sha256"]
                == initial_entry["specification_sha256"]
            ),
            "every_later_round_consumed_preceding_terminal_event": True,
            "superseded_specification_reused": False,
        },
        "scientific_claim_status": "not_established_by_control_loop",
        "final_status": (
            "target_compatible_candidate_awaiting_semantic_verification"
            if any(
                item["status"] == "candidate_ready_for_semantic_review"
                for item in active_target_branches
            )
            else "no_target_compatible_candidate"
        ),
    }
    _require_schema(trace, TRACE_SCHEMA, repo, "generated research co-evolution trace")
    if not _skip_trace_verification:
        verify_trace_integrity(trace, repo, scenario)

    destination = Path(output_dir).resolve()
    trace_path = destination / "research_coevolution_trace.json"
    manifest_path = destination / "manifest.json"
    write_json(trace_path, trace)
    manifest = {
        "schema_version": "1.0",
        "scenario_id": scenario["scenario_id"],
        "scenario_file_sha256": file_digest(scenario_file),
        "scenario_object_sha256": object_digest(scenario),
        "initial_specification_sha256": initial_entry["specification_sha256"],
        "event_chain_head_sha256": trace["event_chain_head_sha256"],
        "trace_sha256": file_digest(trace_path),
        "final_status": trace["final_status"],
        "scientific_claim_status": trace["scientific_claim_status"],
    }
    _require_schema(manifest, MANIFEST_SCHEMA, repo, "generated research co-evolution manifest")
    write_json(manifest_path, manifest)
    return ResearchSpecRunResult(
        output_dir=destination,
        trace=trace_path,
        manifest=manifest_path,
        final_status=trace["final_status"],
    )


__all__ = [
    "ResearchSpecError",
    "ResearchSpecRunResult",
    "run_research_specification_loop",
    "verify_trace_integrity",
]
