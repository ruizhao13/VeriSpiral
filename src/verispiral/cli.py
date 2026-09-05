"""Command-line interface for VeriSpiral."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .pipeline import (
    CandidateValidationError,
    PipelineError,
    read_json,
    repository_root,
    run_demo,
    validate_artifact,
)
from .minimax import run_minimax_scenario
from .evolution import run_evolution_feedback
from .public_audit import audit_tree
from .research_spec import run_research_specification_loop
from .diagnosis_demo import run_diagnosis_demo
from .path_workflow import run_path_trial
from .research_workflow import prepare_workflow, execute_workflow, run_workflow_demo


def _resolve_from_root(value: str, root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _resolve_from_cwd(value: str) -> Path:
    """Resolve user-owned Minimax inputs without assuming a source checkout."""

    path = Path(value).expanduser()
    return path if path.is_absolute() else Path.cwd() / path


def cmd_validate(args: argparse.Namespace) -> int:
    root = repository_root()
    path = _resolve_from_cwd(args.input)
    value = read_json(path)
    issues = validate_artifact(value, args.kind, root)
    if issues:
        print(f"INVALID {args.kind}: {path}")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print(f"VALID {args.kind}: {path}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    root = repository_root()
    candidate = _resolve_from_root(args.candidate, root)
    output = _resolve_from_cwd(args.output)
    result = run_demo(candidate, output, root)
    packet = read_json(result.decision_packet)
    gates = packet["gate_results"]
    stages = packet["stage_status"]
    print(f"[1/5] VALID candidate structure: {packet['candidate_id']}")
    print(f"      {len(gates)} scoped gates evaluated")
    print(
        "[2/5] STAGES: "
        f"structure={stages['structural_validation']}, "
        f"evidence={stages['evidence_integrity']}, "
        f"semantic={stages['semantic_verification']}, "
        f"human={stages['human_acceptance']}, "
        f"lifecycle={stages['candidate_lifecycle']}"
    )
    print(f"[3/5] {result.decision.upper()}: {result.decision_packet}")
    if result.success_trace and result.induced_skill:
        print(f"[4/5] RECORDED accepted success trace: {result.success_trace}")
        print(f"[5/5] EMITTED activation-eligible skill: {result.induced_skill}")
        print(f"Manifest: {result.manifest}")
        return 0
    print("[4/5] NO success trace: semantic verification or human acceptance is incomplete")
    print("[5/5] NO activation-eligible skill")
    print(f"Manifest: {result.manifest}")
    # The checked-in public fixture intentionally stops at human review.  That
    # is a successful demonstration of the boundary, not a failed command.
    return 0 if result.decision == "await_human_acceptance" else 2


def cmd_audit(args: argparse.Namespace) -> int:
    target = _resolve_from_cwd(args.path)
    findings = audit_tree(target, max_file_bytes=args.max_bytes)
    if findings:
        print(f"PUBLIC-RELEASE AUDIT FAILED: {len(findings)} finding(s)")
        for finding in findings:
            print(f"- {finding.render()}")
        print("Potential credential values are intentionally redacted.")
        return 1
    print(f"PUBLIC-RELEASE AUDIT PASSED: {target}")
    return 0


def cmd_minimax(args: argparse.Namespace) -> int:
    if args.scenario is None:
        scenario = repository_root() / "examples" / "minimax_scenario.json"
    else:
        scenario = _resolve_from_cwd(args.scenario)
    output = _resolve_from_cwd(args.output)
    result = run_minimax_scenario(scenario, output)
    trace = read_json(result.evolution_trace)
    for round_result in trace["rounds"]:
        print(
            f"[round {round_result['round_index']}] "
            f"{round_result['candidate_id']}: {round_result['status']} "
            f"(rate={round_result['rate_check']['status']}, "
            f"assumptions={round_result['assumption_check']['status']}, "
            f"branch={round_result['assumption_branch_id']})"
        )
    print(f"Evolution trace: {result.evolution_trace}")
    print(f"Assumption branches: {result.assumption_branches}")
    print(f"Insight ledger: {result.insight_ledger}")
    print(f"Manifest: {result.manifest}")
    print(
        f"FINAL certificate-rate status: {result.final_status} | "
        "human review required | source text and proofs not checked"
    )
    return 0


def cmd_evolve(args: argparse.Namespace) -> int:
    root = repository_root()
    feedback = _resolve_from_root(args.feedback, root)
    output = _resolve_from_cwd(args.output)
    result = run_evolution_feedback(feedback, output, root)
    print("[1/3] VALIDATED explicit feedback and bound control-source linkage")
    print(f"[2/3] PROPOSED patch for human review: {result.patch}")
    print(f"[3/3] NOT APPLIED; target component remains unchanged")
    print(f"Proposal: {result.proposal}")
    print(f"Manifest: {result.manifest}")
    print(
        "FINAL evolution status: proposed_for_human_review | "
        "human review required | no scientific conclusion generated"
    )
    return 0


def cmd_research_loop(args: argparse.Namespace) -> int:
    root = repository_root()
    scenario = _resolve_from_root(args.scenario, root)
    output = _resolve_from_cwd(args.output)
    result = run_research_specification_loop(scenario, output, root)
    trace = read_json(result.trace)
    print(
        f"[1/4] REGISTERED human-owned research specification: "
        f"{trace['initial_specification_id']}"
    )
    print(
        f"[2/4] REPLAYED {len(trace['rounds'])} linked research rounds with "
        "explicit diagnosis/decision consumption"
    )
    print(
        f"[3/4] PRESERVED {len(trace['branches'])} immutable specification "
        "states; the accepted verifier successor stayed on target, while the "
        "model branch received no parent-target credit"
    )
    print(f"[4/4] {result.final_status.upper()}: {result.trace}")
    print(f"Manifest: {result.manifest}")
    print(
        "CONTROL-PLANE RESULT ONLY | human decisions are checked-in fixtures | "
        "scientific claim not established"
    )
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    path = run_diagnosis_demo(_resolve_from_cwd(args.output))
    report = read_json(path)
    for case in report["diagnostic_cases"]:
        decision = case["decision"]
        factors = ', '.join(decision['supported_factors']) or '(no registered indicator failed)'
        print(f"{case['case_id']}: {factors} "
              f"| cost={case['budget_spent']} | {', '.join(case['next_action_proposals'])}")
    print(f"Report: {path}")
    print("FINITE SYNTHETIC DIAGNOSIS | multiple observed indicators | no revision applied")
    return 0


def cmd_path_trial(args: argparse.Namespace) -> int:
    path = run_path_trial(_resolve_from_cwd(args.output))
    report = read_json(path)
    for verifier, result in report["verifier_summary"].items():
        print(
            f"{verifier}: accepted={result['accepted_count']}/"
            f"{result['candidate_evaluations']} | "
            f"false_accept={result['false_accept_count']} | "
            f"false_reject={result['false_reject_count']} | "
            f"optimal_unverified={result['unverified_optimal_count']}"
        )
    print(f"Scope: {report['scope']}")
    repair = report["witness_repair"]["summary"]
    print(f"Witness repair: paths_preserved={repair['paths_preserved']} | "
          f"certified={repair['certified_optimal_count']} | "
          f"false_accept={repair['false_accept_count']} | "
          f"optimal_unverified={repair['unverified_optimal_count']}")
    print(f"Report: {path}")
    return 0


def cmd_workflow_prepare(args: argparse.Namespace) -> int:
    path = prepare_workflow(
        _resolve_from_cwd(args.problem),
        _resolve_from_cwd(args.setup) if args.setup else None,
        _resolve_from_cwd(args.output),
    )
    proposal = read_json(path)
    print(f"Workflow proposal: {proposal['status']}")
    for issue in proposal["issues"]:
        print(f"- {issue}")
    print(f"Proposal: {path}")
    print(f"Pending decision template: {path.parent / 'decision_template.json'}")
    return 0


def cmd_workflow_run(args: argparse.Namespace) -> int:
    path = execute_workflow(
        _resolve_from_cwd(args.proposal),
        _resolve_from_cwd(args.decision),
        _resolve_from_cwd(args.output),
    )
    report = read_json(path)
    factors = sorted({factor for row in report["rounds"]
                      for factor in row["diagnosis"]["supported_factors"]})
    print(f"Workflow: {report['status']} | edge_operations={report['budget_spent']}")
    print(f"Observed factors: {', '.join(factors) or '(none observed)'}")
    print(f"Report: {path}")
    return 0


def cmd_workflow_demo(args: argparse.Namespace) -> int:
    path = run_workflow_demo(_resolve_from_cwd(args.output))
    summary = read_json(path)
    print(f"Initial workflow: {summary['initial_status']} | rounds={summary['initial_rounds']}")
    print(f"Concurrent factors: {', '.join(summary['first_round_factors'])}")
    print(f"Successor workflow: {summary['successor_status']} | version={summary['successor_version']}")
    print(f"Target lineage preserved: {summary['target_lineage_preserved']} | {summary['successor_recheck']}")
    print(f"Scope: {summary['scope']}")
    print(f"Summary: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verispiral",
        description=(
            "Run VeriSpiral's deterministic, verifier-guided research-agent "
            "workflow."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate a JSON artifact")
    validate_parser.add_argument(
        "--kind",
        required=True,
        choices=(
            "candidate",
            "decision_packet",
            "verification_receipt",
            "human_acceptance",
            "acceptance_registry",
            "success_trace",
            "induced_skill",
            "minimax_scenario",
            "minimax_evolution",
            "assumption_branches",
            "insight_ledger",
            "evolution_registry",
            "feedback_event",
            "evolution_proposal",
            "evolution_patch",
            "evolution_manifest",
            "research_specification",
            "research_coevolution_scenario",
            "research_coevolution_trace",
            "research_coevolution_manifest",
        ),
    )
    validate_parser.add_argument("--input", required=True)
    validate_parser.set_defaults(handler=cmd_validate)

    demo_parser = subparsers.add_parser("demo", help="run candidate-to-skill demo")
    demo_parser.add_argument("--candidate", default="examples/candidate.json")
    demo_parser.add_argument("--output", default="demo/output")
    demo_parser.set_defaults(handler=cmd_demo)

    minimax_parser = subparsers.add_parser(
        "minimax", help="verify registered minimax certificate evolution"
    )
    minimax_parser.add_argument(
        "--scenario",
        default=None,
        help="scenario JSON (defaults to the packaged public fixture)",
    )
    minimax_parser.add_argument("--output", default="demo/minimax-output")
    minimax_parser.set_defaults(handler=cmd_minimax)

    evolve_parser = subparsers.add_parser(
        "evolve", help="propose an unapplied evolution patch from explicit feedback"
    )
    evolve_parser.add_argument(
        "--feedback", default="examples/evolution/feedback_event.json"
    )
    evolve_parser.add_argument("--output", default="demo/output/evolution")
    evolve_parser.set_defaults(handler=cmd_evolve)

    research_loop_parser = subparsers.add_parser(
        "research-loop",
        help="replay a human-governed model/verifier/solution-search loop",
    )
    research_loop_parser.add_argument(
        "--scenario",
        default="examples/research_spec/minimax_coevolution_scenario.json",
    )
    research_loop_parser.add_argument(
        "--output", default="demo/output/research-specification"
    )
    research_loop_parser.set_defaults(handler=cmd_research_loop)

    diagnose_parser = subparsers.add_parser(
        "diagnose", help="run finite synthetic diagnostic experiment selection"
    )
    diagnose_parser.add_argument("--output", default="demo/output/diagnosis")
    diagnose_parser.set_defaults(handler=cmd_diagnose)

    path_trial_parser = subparsers.add_parser(
        "path-trial", help="check public DAG path candidates against an exhaustive reference"
    )
    path_trial_parser.add_argument("--output", default="demo/output/path-trial")
    path_trial_parser.set_defaults(handler=cmd_path_trial)

    workflow_prepare_parser = subparsers.add_parser(
        "workflow-prepare", help="prepare a reviewable specification from a problem document and typed setup"
    )
    workflow_prepare_parser.add_argument("--problem", required=True)
    workflow_prepare_parser.add_argument("--setup")
    workflow_prepare_parser.add_argument("--output", required=True)
    workflow_prepare_parser.set_defaults(handler=cmd_workflow_prepare)

    workflow_run_parser = subparsers.add_parser(
        "workflow-run", help="execute a specification with its explicit recorded decision"
    )
    workflow_run_parser.add_argument("--proposal", required=True)
    workflow_run_parser.add_argument("--decision", required=True)
    workflow_run_parser.add_argument("--output", required=True)
    workflow_run_parser.set_defaults(handler=cmd_workflow_run)

    workflow_demo_parser = subparsers.add_parser(
        "workflow-demo", help="run the public connected workflow with synthetic specification decisions"
    )
    workflow_demo_parser.add_argument("--output", default="demo/output/workflow")
    workflow_demo_parser.set_defaults(handler=cmd_workflow_demo)

    audit_parser = subparsers.add_parser("audit", help="audit a public release tree")
    audit_parser.add_argument("path", nargs="?", default=".")
    audit_parser.add_argument("--max-bytes", type=int, default=20 * 1024 * 1024)
    audit_parser.set_defaults(handler=cmd_audit)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except CandidateValidationError as exc:
        print("INVALID candidate:", file=sys.stderr)
        for issue in exc.issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    except (OSError, ValueError, PipelineError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
