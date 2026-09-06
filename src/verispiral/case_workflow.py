"""Problem-first workflow driven by submitted agent work and actual execution.

The host invokes agents; this module manages one local development case. It
does not generate model replies, authenticate their authors, sandbox supplied
programs, or provide hidden final evaluation. Programs are explicitly selected
local Python components, not imports from the legacy candidate-to-Skill flow.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil

from .case_execution import digest_json, read_json_object, run_program


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _available_hash(path: Path) -> str | None:
    try:
        return _hash(path)
    except OSError:
        return None


def _write(path: Path, value: dict) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + ".new")
    with temporary.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    os.replace(temporary, path)


def _component(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("component must be a relative case-local path")
    path = (directory / name).resolve()
    if not path.is_relative_to(directory) or not path.is_file() or path.suffix != ".py":
        raise ValueError("component must resolve to a Python file inside this case")
    return path


def _producer(value: dict) -> dict:
    if (not isinstance(value, dict)
            or any(not isinstance(value.get(k), str) or not value[k].strip()
                   for k in ("role", "id", "version"))
            or value.get("kind") not in {"live_agent", "external", "public_fixture"}):
        raise ValueError("producer needs role, id, version and live_agent/external/public_fixture kind")
    return deepcopy(value)


def _load(directory: Path) -> dict:
    state = read_json_object(directory / "case.json")
    if _hash(directory / "problem.md") != state["problem_sha256"]:
        raise ValueError("original problem changed; start a new case")
    if _hash(directory / "reference.py") != state["reference"]["sha256"]:
        raise ValueError("reference implementation changed; start a newly scoped case")
    for event in state["events"]:
        path = directory / event["file"]
        if not path.resolve().is_relative_to(directory) or _hash(path) != event["sha256"]:
            raise ValueError("recorded event identity changed")
    return state


@contextmanager
def _locked(case_dir):
    directory = Path(case_dir).resolve()
    lock = directory / ".case.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("case already has a writer; inspect an interrupted run before removing its lock") from error
    os.close(descriptor)
    try:
        yield directory, _load(directory)
    finally:
        lock.unlink()


def _event(directory: Path, state: dict, kind: str, payload: dict) -> dict:
    name = f"events/{len(state['events']) + 1:04d}-{kind}.json"
    path = directory / name
    if path.exists():
        raise ValueError("event already exists; inspect the interrupted write")
    _write(path, {"kind": kind, "payload": payload,
                 "runtime": {"python": platform.python_version(),
                             "workflow_sha256": _hash(Path(__file__)),
                             "executor_sha256": _hash(Path(__file__).with_name("case_execution.py"))}})
    binding = {"file": name, "sha256": _hash(path)}
    state["events"].append(binding)
    _write(directory / "case.json", state)
    return binding


def _require(state: dict, *statuses: str) -> None:
    if state["status"] not in statuses:
        raise ValueError(f"operation unavailable at {state['status']}; expected {', '.join(statuses)}")


def create_case(problem, case_dir, reference, reference_scope: str, *,
                call_budget: int = 20, max_rounds: int = 4, timeout_seconds: float = 10) -> Path:
    """Keep a source document and separately selected reference outside Git."""
    directory, source, anchor = Path(case_dir).resolve(), Path(problem).resolve(), Path(reference).resolve()
    if directory.exists():
        raise ValueError("case directory already exists; choose a new case")
    if any((parent / ".git").exists() for parent in (directory, *directory.parents)):
        raise ValueError("live case inputs and outputs belong outside Git repositories")
    if source.suffix.lower() not in {".md", ".txt"} or source.stat().st_size > 100_000:
        raise ValueError("problem must be a UTF-8 Markdown/text document of at most 100000 bytes")
    if not source.read_text(encoding="utf-8").strip() or anchor.suffix != ".py" or not anchor.is_file():
        raise ValueError("nonempty problem and explicit Python reference are required")
    if not isinstance(reference_scope, str) or not reference_scope.strip():
        raise ValueError("reference scope must be explicit")
    if type(call_budget) is not int or not 0 <= call_budget <= 10000:
        raise ValueError("call budget must be an integer in 0..10000")
    if type(max_rounds) is not int or not 1 <= max_rounds <= 100:
        raise ValueError("max rounds must be an integer in 1..100")
    if type(timeout_seconds) not in {int, float} or not 0 < timeout_seconds <= 300:
        raise ValueError("per-program timeout must be in (0, 300]")
    directory.mkdir(parents=True)
    (directory / "events").mkdir()
    (directory / "components").mkdir()
    shutil.copyfile(source, directory / "problem.md")
    shutil.copyfile(anchor, directory / "reference.py")
    state = {
        "schema_version": "1.0", "status": "awaiting_design", "problem_sha256": _hash(directory / "problem.md"),
        "reference": {"sha256": _hash(directory / "reference.py"), "scope": reference_scope,
                      "selection": "explicitly supplied by case host; not authenticated or proved by this runner"},
        "call_budget": call_budget, "calls_used": 0, "max_rounds": max_rounds,
        "timeout_seconds": timeout_seconds, "round_count": 0, "design_version": 0,
        "design": None, "specification": None, "last_run": None, "events": [],
        "evaluation_use": "development", "scientific_claim_accepted": False,
        "model_usage": "host-managed; not measured by this runner",
    }
    _write(directory / "case.json", state)
    return directory / "case.json"


def submit_design(case_dir, proposal_path) -> dict:
    proposal = read_json_object(Path(proposal_path))
    with _locked(case_dir) as (directory, state):
        _require(state, "awaiting_design", "needs_input", "awaiting_review")
        for key in ("goal", "setup", "verifier"):
            if not isinstance(proposal.get(key), dict) or not proposal[key]:
                raise ValueError(f"design requires a nonempty {key} object")
        if not isinstance(proposal.get("unknowns"), list) or not isinstance(proposal.get("assumptions"), list):
            raise ValueError("design must distinguish assumptions and material unknowns")
        _producer(proposal.get("producer"))
        checker = proposal["verifier"]
        for key in ("meaning", "mechanism"):
            if not isinstance(checker.get(key), str) or not checker[key].strip():
                raise ValueError(f"verifier requires {key}")
        if not isinstance(checker.get("limitations"), list):
            raise ValueError("verifier limitations must be stated")
        program = _component(directory, checker.get("program"))
        proposal = deepcopy(proposal)
        proposal["verifier"]["program_sha256"] = _hash(program)
        previous = state["design"]
        if previous and state.get("revision_requested") == "revise_verifier":
            if any(previous[k] != proposal[k] for k in ("goal", "setup", "assumptions")):
                raise ValueError("verifier revision cannot change goal, setup or assumptions")
        state["design_version"] += 1
        state["design"] = proposal
        state["design_sha256"] = digest_json(proposal)
        state["status"] = "needs_input" if proposal["unknowns"] else "awaiting_review"
        state["review"] = None
        state["specification"] = None
        _event(directory, state, "design", {"version": state["design_version"], "proposal": proposal,
                                          "design_sha256": state["design_sha256"]})
        return deepcopy(state)


def _execute(directory: Path, state: dict, label: str, program: Path, request: dict,
             expected_sha256: str | None = None) -> dict:
    if state["calls_used"] >= state["call_budget"]:
        raise ValueError("program call budget exhausted")
    state["calls_used"] += 1
    # Charge before launch, including failed or interrupted attempts.
    current_hash = _available_hash(program)
    _event(directory, state, "reservation", {"label": label, "call": state["calls_used"],
                                            "request_sha256": digest_json(request), "program_sha256": current_hash})
    if current_hash is None or (expected_sha256 is not None and current_hash != expected_sha256):
        receipt = {"status": "error", "program_sha256": current_hash,
                   "request_sha256": digest_json(request), "output": None, "output_sha256": None,
                   "error": "component unavailable or frozen identity changed before execution", "elapsed_seconds": 0.0}
    else:
        receipt = run_program(program, request, timeout_seconds=state["timeout_seconds"])
    if (expected_sha256 is not None and receipt["status"] == "ok"
            and receipt["program_sha256"] != expected_sha256):
        receipt.update(status="error", output=None, output_sha256=None,
                       error="executed component does not match the frozen identity")
    receipt["component"] = label
    receipt["call"] = state["calls_used"]
    receipt["evaluation_use"] = "development"
    _event(directory, state, "execution", receipt)
    return receipt


def _check_design(directory: Path, state: dict) -> Path:
    checker = _component(directory, state["design"]["verifier"]["program"])
    if _hash(checker) != state["design"]["verifier"]["program_sha256"]:
        raise ValueError("checker changed; submit and review a new design before execution")
    return checker


def audit_design(case_dir, program: str, producer: dict) -> dict:
    with _locked(case_dir) as (directory, state):
        _require(state, "awaiting_review")
        checker = _check_design(directory, state)
        identity = _producer(producer)
        audit = _component(directory, program)
        # Provide the contract and implementation, not the designer's rationale.
        request = {"goal": state["design"]["goal"], "setup": state["design"]["setup"],
                   "assumptions": state["design"]["assumptions"],
                   "verifier_contract": state["design"]["verifier"],
                   "verifier_meaning": state["design"]["verifier"]["meaning"],
                   "checker_path": str(checker), "reference_scope": state["reference"]["scope"]}
        receipt = _execute(directory, state, "red_team", audit, request)
        output = receipt["output"] if receipt["status"] == "ok" else None
        ready = isinstance(output, dict) and output.get("verdict") == "ready" and isinstance(output.get("findings"), list)
        state["review"] = {"producer": identity, "receipt": receipt, "design_sha256": state["design_sha256"]}
        state["status"] = "awaiting_decision" if ready else "awaiting_review"
        _event(directory, state, "review", state["review"])
        return deepcopy(state)


def record_decision(case_dir, decision_path) -> dict:
    decision = read_json_object(Path(decision_path))
    with _locked(case_dir) as (directory, state):
        _require(state, "awaiting_decision")
        _check_design(directory, state)
        if decision.get("design_sha256") != state["design_sha256"]:
            raise ValueError("decision is not bound to the current reviewed design")
        if decision.get("actor") not in {"user_record", "synthetic_fixture"} or decision.get("action") not in {"accept", "reject"}:
            raise ValueError("decision must explicitly accept/reject and identify user_record or synthetic_fixture")
        if decision["action"] == "accept":
            state["specification"] = {
                "version": state["design_version"], "design_sha256": state["design_sha256"],
                "problem_sha256": state["problem_sha256"], "reference": deepcopy(state["reference"]),
                "target_lineage": digest_json({k: state["design"][k] for k in ("goal", "setup", "assumptions")}),
                "decision": deepcopy(decision), "human_identity_authenticated": False,
            }
            state["specification_sha256"] = digest_json(state["specification"])
            state["status"] = "ready_to_run"
        else:
            state["status"] = "stopped"
        _event(directory, state, "decision", decision)
        return deepcopy(state)


def _verdict(receipt: dict | None) -> str:
    if not receipt or receipt["status"] != "ok":
        return "inconclusive"
    value = receipt["output"].get("verdict")
    return value if isinstance(value, str) and value in {"pass", "fail", "inconclusive"} else "inconclusive"


def execute_round(case_dir, solver: str | None, producer: dict, *, recheck: bool = False) -> dict:
    with _locked(case_dir) as (directory, state):
        _require(state, "ready_to_run")
        checker = _check_design(directory, state)
        identity = _producer(producer)
        previous = state["last_run"]
        required = 2 if recheck else 3
        if recheck and (not previous or previous["candidate"] is None
                        or previous["target_lineage"] != state["specification"]["target_lineage"]):
            raise ValueError("recheck requires a retained candidate under the same goal and setup")
        if state["round_count"] >= state["max_rounds"] or state["call_budget"] - state["calls_used"] < required:
            state["status"] = "budget_or_round_limit"
            _event(directory, state, "stop", {"reason": state["status"], "required_calls": required})
            return deepcopy(state)
        problem = {"goal": state["design"]["goal"], "setup": state["design"]["setup"]}
        production = None
        if recheck:
            candidate = deepcopy(previous["candidate"])
            candidate_origin = {"retained_from_run": state["last_run_sha256"]}
        else:
            program = _component(directory, solver)
            production = _execute(directory, state, "solver", program, problem)
            value = production["output"] if production["status"] == "ok" else None
            candidate = value.get("candidate") if isinstance(value, dict) else None
            if not isinstance(candidate, dict):
                candidate = None
            candidate_origin = {"producer": identity, "program": solver, "execution": production}
        screened = reference = None
        if candidate is not None:
            request = {**problem, "candidate": candidate}
            screened = _execute(directory, state, "checker", checker, request,
                                state["design"]["verifier"]["program_sha256"])
            reference = _execute(directory, state, "reference", directory / "reference.py", request,
                                 state["reference"]["sha256"])
        screen_verdict, reference_verdict = _verdict(screened), _verdict(reference)
        observations = []
        if candidate is None:
            observations.append("solver_did_not_return_an_executable_candidate")
        if screened and screened["status"] != "ok":
            observations.append("checker_execution_error")
        if reference and reference["status"] != "ok":
            observations.append("reference_execution_error")
        if reference_verdict == "fail":
            observations.append("candidate_failed_reference")
        if screen_verdict == "pass" and reference_verdict == "fail":
            observations.append("screen_accepted_reference_rejected")
        if screen_verdict == "fail" and reference_verdict == "pass":
            observations.append("screen_rejected_reference_accepted")
        identities_intact = (_available_hash(checker) == state["design"]["verifier"]["program_sha256"]
                             and _available_hash(directory / "reference.py") == state["reference"]["sha256"])
        if not identities_intact:
            observations.append("frozen_component_changed_during_round")
        complete = screen_verdict == reference_verdict == "pass" and identities_intact
        state["round_count"] += 1
        run = {
            "round": state["round_count"], "specification_sha256": state["specification_sha256"],
            "target_lineage": state["specification"]["target_lineage"],
            "candidate": candidate, "candidate_sha256": digest_json(candidate) if candidate is not None else None,
            "candidate_origin": candidate_origin, "checker": screened, "reference": reference,
            "screen_verdict": screen_verdict, "reference_verdict": reference_verdict,
            "observations": observations, "all_declared_checks_passed": complete,
            "evaluation_use": "development", "is_hidden_final_evaluation": False,
            "scientific_claim_accepted": False, "calls_used": state["calls_used"],
            "candidate_rechecked": recheck, "prior_pass_reused": False,
            "limitations": ["Reference correctness and scope require external justification.",
                            "Reported component costs are declarations; only calls and timeout are enforced.",
                            "Host/model work, dependency closure and private context access are not measured."],
        }
        state["last_run"] = run
        state["last_run_sha256"] = digest_json(run)
        state["status"] = "ready_for_review" if complete else "needs_diagnosis"
        _event(directory, state, "round", run)
        return deepcopy(state)


def submit_diagnosis(case_dir, diagnosis_path) -> dict:
    diagnosis = read_json_object(Path(diagnosis_path))
    with _locked(case_dir) as (directory, state):
        _require(state, "needs_diagnosis", "ready_for_review")
        if diagnosis.get("run_sha256") != state["last_run_sha256"]:
            raise ValueError("diagnosis must consume the current actual run")
        _producer(diagnosis.get("producer"))
        action = diagnosis.get("next_action")
        if action not in {"continue_search", "revise_verifier", "revise_setup", "revise_goal", "stop"}:
            raise ValueError("unsupported next research action")
        if not isinstance(diagnosis.get("hypotheses"), list) or not diagnosis["hypotheses"]:
            raise ValueError("diagnosis must preserve explicit competing hypotheses or unknowns")
        if not isinstance(diagnosis.get("experiment"), dict) or not diagnosis["experiment"]:
            raise ValueError("diagnosis needs a distinguishing experiment or a scoped stop reason")
        state["revision_requested"] = action
        state["status"] = ("ready_to_run" if action == "continue_search" else
                           "stopped" if action == "stop" else "awaiting_design")
        _event(directory, state, "diagnosis", diagnosis)
        return deepcopy(state)


def inspect_case(case_dir) -> dict:
    """Return the evidence ledger and a host-facing next action, never an LLM reply."""
    directory = Path(case_dir).resolve()
    state = _load(directory)
    actions = {
        "awaiting_design": ("goal_setup_designer / verifier_synthesizer", "Submit a grounded goal/setup and executable verifier proposal."),
        "needs_input": ("goal_setup_designer / user", "Resolve material unknowns against the original problem; submit an updated design."),
        "awaiting_review": ("verifier_red_team", "Audit the contract and checker with executable counterexamples."),
        "awaiting_decision": ("user", "Use an existing applicable authorization or record a concrete design decision."),
        "ready_to_run": ("solver", "Submit an executable candidate producer, or recheck a retained candidate."),
        "needs_diagnosis": ("research_controller", "Read actual receipts; propose a distinguishing experiment and the next action."),
        "ready_for_review": ("user / research_controller", "Review scoped results or propose further research; no scientific claim is auto-accepted."),
        "budget_or_round_limit": ("user", "Budget or round limit reached; retain partial evidence."),
        "stopped": ("none", "This bounded case is stopped."),
    }
    role, instruction = actions[state["status"]]
    return {"status": state["status"], "next_role": role, "instruction": instruction,
            "case": state, "runtime": "host-driven agents; runner executes submitted Python components"}
