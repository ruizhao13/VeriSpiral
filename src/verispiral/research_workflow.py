"""Connect problem intake, specification decisions, checks and bounded repairs.

The implemented adapter is a small integer DAG problem. Prose is source material
for user review, never silently parsed into an authoritative scientific goal.
Decision files record authorization but cannot authenticate a human identity.
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path

from . import path_adapter
from .diagnosis import choose_factor_diagnostic_action
from .pipeline import file_digest, object_digest, read_json, repository_root, write_json


IMPLEMENTATION = ("research_workflow.py", "path_adapter.py", "path_workflow.py",
                  "path_reference.py", "diagnosis.py", "pipeline.py", "schema.py")


def _implementation() -> dict:
    return {name: file_digest(Path(__file__).with_name(name)) for name in IMPLEMENTATION}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _public_output_guard(inputs: list[Path], output: Path, root: Path) -> None:
    if _inside(output, root):
        if any(not _inside(path, root / "examples" / "workflow") for path in inputs):
            raise ValueError("private or unregistered inputs require an output workspace outside the public repository")
        if any(_inside(output, root / name) for name in ("src", "schemas", "prompts", ".git")):
            raise ValueError("workflow outputs cannot overwrite governed source directories")


def _binding(path: Path, directory: Path) -> dict:
    root = repository_root()
    locator = ("repo:" + path.resolve().relative_to(root.resolve()).as_posix()
               if _inside(path, root / "examples/workflow")
               else os.path.relpath(path.resolve(), directory.resolve()))
    return {"locator": locator, "sha256": file_digest(path)}


def _resolve(binding: dict, directory: Path) -> Path:
    if not isinstance(binding, dict) or set(binding) != {"locator", "sha256"}:
        raise ValueError("invalid input binding")
    locator = binding["locator"]
    if not isinstance(locator, str):
        raise ValueError("input locator must be text")
    path = ((repository_root() / locator[5:]).resolve() if locator.startswith("repo:")
            else (directory / locator).resolve())
    if file_digest(path) != binding["sha256"]:
        raise ValueError("input or parent artifact hash drift")
    return path


def _save(path: Path, value: dict) -> None:
    if path.exists() and read_json(path) != value:
        raise ValueError(f"immutable output conflict: {path.name}; choose a new output directory")
    write_json(path, value)


def _build_proposal(problem: Path, setup: Path | None, directory: Path) -> dict:
    if problem.suffix.lower() not in {".md", ".txt"} or problem.stat().st_size > 100_000:
        raise ValueError("problem input must be a small UTF-8 Markdown or text document")
    text = problem.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("problem document is empty")
    proposal, issues = None, []
    if setup is None:
        issues.append("Provide typed setup data for the supported shortest_path_dag adapter.")
    else:
        try:
            proposal = path_adapter.propose(read_json(setup))
        except ValueError as error:
            issues.append(str(error))
    return {
        "kind": "research_workflow_proposal", "schema_version": "1.0", "version": 1,
        "status": "needs_input" if issues else "awaiting_decision", "parent": None,
        "inputs": {"problem": _binding(problem, directory),
                   "setup": _binding(setup, directory) if setup else None},
        "implementation": _implementation(), "adapter": "shortest_path_dag",
        "charter": {
            "explicit": [{"source": "problem document", "sha256": file_digest(problem),
                          "characters": len(text), "interpretation": "Original prose remains the source of truth."}],
            "inferred": [],
            "assumed": ["The proposed finite graph is the complete model; it has no omitted-environment guarantee."],
            "unknown": issues + ["User must confirm that this adapter goal and setup match the source document."],
            "semantic_extraction": "not_implemented; adapter proposals require explicit review",
        },
        "adapter_proposal": proposal, "issues": issues,
        "permission_boundary": "Only a matching accepted decision freezes the proposed goal, setup and screen.",
    }


def prepare_workflow(problem_path, setup_path, output_dir, root=None) -> Path:
    root, directory = Path(root or repository_root()), Path(output_dir).resolve()
    problem = Path(problem_path).resolve()
    setup = Path(setup_path).resolve() if setup_path else None
    _public_output_guard([problem] + ([setup] if setup else []), directory, root)
    proposal = _build_proposal(problem, setup, directory)
    path = directory / "proposal.json"
    _save(path, proposal)
    _save(directory / "decision_template.json", {
        "action": "pending", "proposal_sha256": file_digest(path), "actor": "user_record",
        "selection": {"screen_verifier": "all_edges_certificate", "initial_algorithm": "greedy_edge"},
        "budget_edge_operations": 1000, "max_rounds": 3,
    })
    return path


def _validated_proposal(path: Path, root: Path) -> tuple[dict, list[Path], dict | None]:
    proposal = read_json(path)
    if proposal.get("implementation") != _implementation():
        raise ValueError("workflow implementation hash drift; prepare a new proposal")
    if proposal.get("status") != "awaiting_decision":
        raise ValueError("proposal needs input before it can be accepted")
    problem = _resolve(proposal["inputs"]["problem"], path.parent)
    setup = _resolve(proposal["inputs"]["setup"], path.parent)
    fresh = _build_proposal(problem, setup, path.parent)
    retained = None
    if proposal.get("parent") is not None:
        parent_path = _resolve(proposal["parent"], path.parent)
        parent = read_json(parent_path)
        if parent.get("status") != "awaiting_verifier_decision":
            raise ValueError("parent did not request a verifier revision")
        base = parent["specification"]
        if (base["goal"] != fresh["adapter_proposal"]["goal"]
                or base["setup"] != fresh["adapter_proposal"]["setup"]
                or base["source_sha256"] != fresh["inputs"]["problem"]["sha256"]
                or parent["specification_sha256"] != object_digest(base)
                or type(base["version"]) is not int or base["version"] < 1
                or base["implementation"] != _implementation()):
            raise ValueError("verifier successor cannot change the goal, setup or executing implementation")
        fresh.update({"version": base["version"] + 1, "parent": proposal["parent"],
                      "base_specification_sha256": object_digest(base),
                      "required_screen": "all_edges_certificate"})
        retained = deepcopy(parent["rounds"][-1]["candidate"])
        if object_digest(retained["value"]) != retained["content_sha256"]:
            raise ValueError("parent candidate identity mismatch")
    if proposal != fresh:
        raise ValueError("proposal content does not match its bound inputs and supported contract")
    return proposal, [problem, setup], retained


def _decision(path: Path, proposal_path: Path, proposal: dict) -> dict:
    value = read_json(path)
    expected = {"action", "proposal_sha256", "actor", "selection", "budget_edge_operations", "max_rounds"}
    if set(value) != expected or value["action"] not in {"accept", "reject"}:
        raise ValueError("decision must explicitly accept or reject with the complete decision contract")
    if value["proposal_sha256"] != file_digest(proposal_path):
        raise ValueError("decision is bound to a different proposal")
    if value["actor"] not in {"user_record", "synthetic_fixture"}:
        raise ValueError("decision actor must state user_record or synthetic_fixture")
    choice = value["selection"]
    if (not isinstance(choice, dict) or set(choice) != {"screen_verifier", "initial_algorithm"}
            or choice["screen_verifier"] not in path_adapter.VERIFIERS
            or choice["initial_algorithm"] not in path_adapter.METHODS):
        raise ValueError("decision selects unsupported methods")
    if proposal.get("required_screen") and choice["screen_verifier"] != proposal["required_screen"]:
        raise ValueError("this verifier successor requires the proposed complete screen")
    if type(value["budget_edge_operations"]) is not int or not 0 <= value["budget_edge_operations"] <= 1_000_000:
        raise ValueError("edge budget must be an integer from 0 to 1000000")
    if type(value["max_rounds"]) is not int or not 1 <= value["max_rounds"] <= 8:
        raise ValueError("max_rounds must be an integer from 1 to 8")
    return value


def execute_workflow(proposal_path, decision_path, output_dir, root=None) -> Path:
    root, directory = Path(root or repository_root()), Path(output_dir).resolve()
    proposal_path, decision_path = Path(proposal_path).resolve(), Path(decision_path).resolve()
    proposal, inputs, retained = _validated_proposal(proposal_path, root)
    _public_output_guard(inputs, directory, root)
    decision = _decision(decision_path, proposal_path, proposal)
    if decision["action"] == "reject":
        path = directory / "workflow_report.json"
        _save(path, {"status": "rejected_by_recorded_decision", "budget_spent": 0,
                     "proposal_sha256": file_digest(proposal_path), "decision_sha256": file_digest(decision_path),
                     "human_identity_authenticated": False, "rounds": []})
        return path
    adapter = proposal["adapter_proposal"]
    spec = {"version": proposal["version"], "goal": adapter["goal"], "setup": adapter["setup"],
            "screen_verifier": decision["selection"]["screen_verifier"],
            "initial_algorithm": decision["selection"]["initial_algorithm"],
            "source_sha256": proposal["inputs"]["problem"]["sha256"],
            "implementation": _implementation(),
            "target_lineage": object_digest({"goal": adapter["goal"], "setup": adapter["setup"]}),
            "proposal_sha256": file_digest(proposal_path), "decision_sha256": file_digest(decision_path)}
    spec_sha = object_digest(spec)
    remaining, ledger, rounds = decision["budget_edge_operations"], [], []

    def spend(kind: str, bound: int, operation) -> dict | None:
        nonlocal remaining
        if bound > remaining:
            return None
        result = operation()
        if type(result.get("cost")) is not int or not 0 <= result["cost"] <= bound:
            raise ValueError("adapter exceeded reservation; result cannot be published")
        remaining -= result["cost"]
        ledger.append({"kind": kind, "reservation": bound, "actual_cost": result["cost"],
                       "remaining": remaining})
        return result

    n, m = adapter["setup"]["node_count"], len(adapter["setup"]["edges"])
    if retained:
        candidate = retained["value"]
        origin = "retained_requires_recheck"
    else:
        generated = spend("candidate_generation", 3 * m + n,
                          lambda: path_adapter.generate(spec, spec["initial_algorithm"]))
        candidate = generated["candidate"] if generated else None
        origin = "generated"
    status, weak_screen_exposed = "budget_exhausted", False
    for index in range(decision["max_rounds"] if candidate is not None else 0):
        identity = {"content_sha256": object_digest(candidate), "specification_sha256": spec_sha,
                    "value": deepcopy(candidate), "origin": origin}
        observations, receipts = {}, []
        costs = path_adapter.test_costs(spec, candidate)
        while True:
            diagnosis = choose_factor_diagnostic_action(path_adapter.FACTORS, costs, observations, remaining)
            if diagnosis["status"] != "test_proposed":
                break
            test = diagnosis["proposed_test"]
            result = spend(test, diagnosis["cost"], lambda: path_adapter.observe(spec, candidate, test))
            if result is None:
                raise ValueError("controller proposed an unaffordable test")
            observations[test] = result["passed"]
            receipt = {"test": test, "result": result, "candidate_sha256": identity["content_sha256"],
                       "specification_sha256": spec_sha, "remaining_budget": remaining}
            receipt["receipt_sha256"] = object_digest(receipt)
            receipts.append(receipt)
        round_result = {"round": index + 1, "candidate": identity, "observations": observations,
                        "receipts": receipts, "diagnosis": diagnosis}
        rounds.append(round_result)
        factors = diagnosis["supported_factors"]
        weak_screen_exposed |= "screen_disagreement" in factors and spec["screen_verifier"] != "all_edges_certificate"
        if not diagnosis["coverage_checked"]:
            status = "budget_exhausted"
            break
        if not factors:
            status = "awaiting_verifier_decision" if weak_screen_exposed else "candidate_ready_for_human_acceptance"
            break
        if index + 1 == decision["max_rounds"]:
            status = "max_rounds_exhausted"
            break
        if not set(factors).intersection({"candidate_infeasible", "candidate_not_optimal", "certificate_invalid"}):
            status = "awaiting_verifier_decision" if weak_screen_exposed else "inconclusive"
            break
        repair = spend("solution_repair", 3 * m, lambda: path_adapter.repair(spec, candidate, factors))
        if repair is None:
            status = "budget_exhausted"
            break
        candidate, origin = repair["candidate"], repair["kind"]
        round_result["repair"] = {"kind": origin, "cost": repair["cost"], "next_content_sha256": object_digest(candidate)}
    report = {
        "kind": "connected_research_workflow", "schema_version": "1.0", "status": status,
        "specification": spec, "specification_sha256": spec_sha,
        "stages": ["ingest", "charter", "adapter_frontier", "recorded_specification_decision", "freeze",
                   "candidate_execution", "budgeted_checks", "multiple_factor_diagnosis", "repair_or_stop"],
        "rounds": rounds, "cost_ledger": ledger, "budget_limit": decision["budget_edge_operations"],
        "budget_spent": decision["budget_edge_operations"] - remaining, "remaining_budget": remaining,
        "retained_candidate_status": "rechecked_under_successor" if retained and rounds and rounds[-1]["diagnosis"]["coverage_checked"] else "requires_recheck" if retained else "not_applicable",
        "prior_evidence_applicable": False if retained else None,
        "human_acceptance": "pending", "human_identity_authenticated": False,
        "scientific_claim_accepted": False,
        "limitations": ["One explicit small-DAG adapter; no general prose understanding or LLM-generated algorithms.",
                        "Failed checks are concurrent scoped indicators, not exhaustive causal diagnoses.",
                        "The budget counts declared edge operations; parsing, I/O, node work and controller time are excluded.",
                        "Separate implementations share model authorship; public fixtures are not hidden final tests."],
    }
    path = directory / "workflow_report.json"
    _save(path, report)
    _save(directory / "decision_packet.json", {"status": status, "report_sha256": file_digest(path),
          "specification_sha256": spec_sha, "supported_factors": rounds[-1]["diagnosis"]["supported_factors"] if rounds else [],
          "unresolved_factors": rounds[-1]["diagnosis"]["unresolved_factors"] if rounds else sorted(path_adapter.FACTORS),
          "all_observed_factors": sorted({factor for row in rounds for factor in row["diagnosis"]["supported_factors"]}),
          "next_action": "review_candidate" if status == "candidate_ready_for_human_acceptance" else status,
          "human_acceptance": "pending", "scientific_claim_accepted": False})
    if status == "awaiting_verifier_decision":
        successor = _build_proposal(inputs[0], inputs[1], directory)
        successor.update({"version": spec["version"] + 1, "parent": _binding(path, directory),
                          "base_specification_sha256": spec_sha, "required_screen": "all_edges_certificate"})
        _save(directory / "revision_proposal.json", successor)
    _save(directory / "manifest.json", {"report_sha256": file_digest(path), "implementation": _implementation(),
          "decision_packet_sha256": file_digest(directory / "decision_packet.json")})
    return path


def run_workflow_demo(output_dir, root=None) -> Path:
    root, output = Path(root or repository_root()), Path(output_dir)
    proposal = prepare_workflow(root / "examples/workflow/problem.md", root / "examples/workflow/setup.json",
                                output / "proposal", root)

    def fixture_decision(proposed: Path, path: Path, screen: str) -> Path:
        _save(path, {"action": "accept", "proposal_sha256": file_digest(proposed), "actor": "synthetic_fixture",
                    "selection": {"screen_verifier": screen, "initial_algorithm": "greedy_edge"},
                    "budget_edge_operations": 1000, "max_rounds": 3})
        return path

    first_decision = fixture_decision(proposal, output / "first_decision.json", "path_edges_only")
    first = execute_workflow(proposal, first_decision, output / "initial_run", root)
    revision = first.parent / "revision_proposal.json"
    second_decision = fixture_decision(revision, output / "successor_decision.json", "all_edges_certificate")
    second = execute_workflow(revision, second_decision, output / "successor_run", root)
    initial, successor = read_json(first), read_json(second)
    path = output / "demo_summary.json"
    _save(path, {"scope": "Public connected workflow with synthetic specification decisions; no live human identity claim.",
                "initial_status": initial["status"], "initial_rounds": len(initial["rounds"]),
                "first_round_factors": initial["rounds"][0]["diagnosis"]["supported_factors"],
                "successor_status": successor["status"], "successor_version": successor["specification"]["version"],
                "target_lineage_preserved": initial["specification"]["target_lineage"] == successor["specification"]["target_lineage"],
                "successor_recheck": successor["retained_candidate_status"],
                "initial_report_sha256": file_digest(first), "successor_report_sha256": file_digest(second),
                "scientific_claim_accepted": False})
    return path
