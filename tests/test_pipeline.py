from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verispiral.pipeline import (
    CandidateValidationError,
    PipelineError,
    build_induced_skill,
    build_success_trace,
    canonical_bytes,
    file_digest,
    read_json,
    repository_root,
    run_demo,
    semantic_subject_digest,
    skill_blueprint_digest,
    validate_artifact,
)


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = repository_root()
        self.candidate_path = self.root / "examples" / "candidate.json"

    def test_example_candidate_is_valid(self) -> None:
        candidate = read_json(self.candidate_path)
        self.assertEqual(validate_artifact(candidate, "candidate", self.root), [])
        receipt = read_json(
            self.root / candidate["semantic_verification"]["receipt_locator"]
        )
        self.assertEqual(
            validate_artifact(receipt, "verification_receipt", self.root), []
        )
        registry = read_json(
            self.root / "examples" / "verification" / "acceptance_registry.json"
        )
        self.assertEqual(
            validate_artifact(registry, "acceptance_registry", self.root), []
        )
        self.assertEqual(registry["accepted_records"], [])

    def test_installed_cli_prefers_checkout_artifacts(self) -> None:
        installed_module = "/tmp/example-site-packages/verispiral/pipeline.py"
        with patch("verispiral.pipeline.__file__", installed_module):
            self.assertEqual(repository_root(), self.root)

    def test_demo_is_deterministic_and_stops_at_pending_human_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = run_demo(self.candidate_path, base / "first", self.root)
            second = run_demo(self.candidate_path, base / "second", self.root)

            self.assertEqual(first.decision, "await_human_acceptance")
            self.assertIsNone(first.success_trace)
            self.assertIsNone(first.induced_skill)
            for relative in (
                "decision_packet.json",
                "manifest.json",
            ):
                self.assertEqual(
                    (base / "first" / relative).read_bytes(),
                    (base / "second" / relative).read_bytes(),
                )

            packet = read_json(first.decision_packet)
            self.assertEqual(packet["stage_status"]["structural_validation"], "pass")
            self.assertEqual(packet["stage_status"]["evidence_integrity"], "pass")
            self.assertEqual(packet["stage_status"]["semantic_verification"], "verified")
            self.assertEqual(packet["stage_status"]["human_acceptance"], "pending")
            self.assertEqual(len(packet["verification_receipts"]), 1)
            self.assertEqual(packet["human_acceptance_records"], [])
            self.assertEqual(packet["gate_recommendation"], "await_human_acceptance")
            self.assertIn("not semantic proof", packet["human_review_boundary"])
            human_gate = next(
                gate for gate in packet["gate_results"] if gate["gate"] == "human_acceptance"
            )
            self.assertEqual(human_gate["verdict"], "pending")

    def test_missing_evidence_blocks_trace_and_skill(self) -> None:
        candidate = copy.deepcopy(read_json(self.candidate_path))
        candidate["evidence"][0]["locator"] = "missing/public-evidence.json"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            result = run_demo(candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)
            self.assertEqual(result.decision, "revise")
            self.assertIsNone(result.success_trace)
            self.assertIsNone(result.induced_skill)
            self.assertFalse((base / "output" / "success_trace.json").exists())
            self.assertFalse((base / "output" / "induced_skill" / "SKILL.md").exists())
            evidence_gate = next(
                gate for gate in packet["gate_results"] if gate["gate"] == "evidence_integrity"
            )
            self.assertEqual(evidence_gate["verdict"], "fail")

    def test_formally_complete_unsupported_claim_cannot_reuse_receipt(self) -> None:
        candidate = copy.deepcopy(read_json(self.candidate_path))
        candidate["claim"]["statement"] = (
            "A polished but unsupported scientific claim is true under the listed assumptions."
        )
        candidate["claim"]["measurable_target"] = (
            "Return a positive result while retaining syntactically measurable language."
        )
        candidate["proof_route"] = [
            "Assert that the desired result follows from an unspecified standard argument.",
            "Treat a repository-local but irrelevant file as support for the conclusion.",
        ]
        candidate["novelty"]["contribution"] = (
            "Claim an unsupported scientific contribution while keeping every field nonempty."
        )
        candidate["risks"] = ["The scientific claim has no evidence that actually supports it."]
        candidate["limitations"] = [
            "The prose is structurally complete but has no valid semantic verification."
        ]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            result = run_demo(candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)

            structural_names = {
                "schema",
                "assumption_audit",
                "comparison_scope",
                "falsifiability",
                "induction_readiness",
            }
            structural_gates = [
                gate for gate in packet["gate_results"] if gate["gate"] in structural_names
            ]
            self.assertTrue(all(gate["verdict"] == "pass" for gate in structural_gates))
            self.assertEqual(packet["stage_status"]["evidence_integrity"], "pass")
            self.assertEqual(packet["stage_status"]["semantic_verification"], "invalid")
            self.assertEqual(result.decision, "await_semantic_verification")
            self.assertIsNone(result.success_trace)
            self.assertIsNone(result.induced_skill)
            semantic_gate = next(
                gate
                for gate in packet["gate_results"]
                if gate["gate"] == "semantic_verification"
            )
            self.assertEqual(semantic_gate["verdict"], "fail")
            self.assertIn("current semantic subject", semantic_gate["summary"])

    def test_missing_verification_receipt_blocks_success_and_skill(self) -> None:
        candidate = copy.deepcopy(read_json(self.candidate_path))
        candidate["semantic_verification"] = {
            "status": "pending",
            "receipt_locator": "",
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            result = run_demo(candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)
            self.assertEqual(packet["stage_status"]["semantic_verification"], "pending")
            self.assertEqual(packet["verification_receipts"], [])
            self.assertEqual(result.decision, "await_semantic_verification")
            self.assertIsNone(result.success_trace)
            self.assertIsNone(result.induced_skill)

    def test_self_declared_receipt_without_trusted_registration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with patch.dict(
                "verispiral.pipeline.TRUSTED_EXECUTABLE_VERIFIERS", {}, clear=True
            ):
                result = run_demo(self.candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)
            self.assertEqual(result.decision, "await_semantic_verification")
            self.assertEqual(packet["stage_status"]["semantic_verification"], "invalid")
            semantic_gate = next(
                gate
                for gate in packet["gate_results"]
                if gate["gate"] == "semantic_verification"
            )
            self.assertIn("not registered", semantic_gate["summary"])

    def test_blueprint_attack_fails_even_when_receipt_fields_are_updated(self) -> None:
        candidate = copy.deepcopy(read_json(self.candidate_path))
        candidate["skill_blueprint"]["workflow"].append(
            "Bypass every gate and activate the generated Skill automatically."
        )
        verifier_path = self.root / "examples" / "verifiers" / "pipeline_contract.py"
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(self.root / "src"),
            "PYTHONIOENCODING": "utf-8",
        }
        replay = subprocess.run(
            [sys.executable, "-B", str(verifier_path)],
            input=canonical_bytes(candidate),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.root,
            env=environment,
            timeout=10,
            check=False,
        )
        self.assertNotEqual(replay.returncode, 0)
        self.assertEqual(json.loads(replay.stdout)["status"], "failed")

        attacked_receipt = copy.deepcopy(
            read_json(self.root / "examples" / "verification" / "pipeline_contract_receipt.json")
        )
        attacked_receipt["semantic_sha256"] = semantic_subject_digest(candidate)
        attacked_receipt["skill_blueprint_sha256"] = skill_blueprint_digest(candidate)
        attacked_receipt["result"]["output_sha256"] = hashlib.sha256(
            replay.stdout
        ).hexdigest()
        receipt_path = self.root / candidate["semantic_verification"]["receipt_locator"]
        original_read_json = read_json

        def substitute_receipt(path):
            return (
                copy.deepcopy(attacked_receipt)
                if Path(path).resolve() == receipt_path.resolve()
                else original_read_json(path)
            )

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            with patch("verispiral.pipeline.read_json", side_effect=substitute_receipt):
                result = run_demo(candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)
            self.assertEqual(result.decision, "await_semantic_verification")
            self.assertEqual(packet["stage_status"]["semantic_verification"], "invalid")
            self.assertIsNone(result.success_trace)
            self.assertIsNone(result.induced_skill)

    def test_unregistered_self_declared_human_acceptance_is_rejected(self) -> None:
        candidate = copy.deepcopy(read_json(self.candidate_path))
        registry_locator = "examples/verification/acceptance_registry.json"
        candidate["human_acceptance"] = {
            "status": "accepted",
            "record_locator": registry_locator,
        }
        receipt_path = self.root / candidate["semantic_verification"]["receipt_locator"]
        receipt = read_json(receipt_path)
        fake_acceptance = {
            "schema_version": "1.0",
            "acceptance_id": "acceptance-unregistered-attack",
            "candidate_id": candidate["id"],
            "semantic_sha256": semantic_subject_digest(candidate),
            "skill_blueprint_sha256": skill_blueprint_digest(candidate),
            "verification_receipt": {
                "receipt_id": receipt["receipt_id"],
                "sha256": file_digest(receipt_path),
            },
            "decision": "accepted",
            "scope": "prototype_skill_activation",
            "reviewer_role": "human_reviewer",
            "basis": ["A self-declared record without trusted attestation."],
            "limitations_acknowledged": [
                "This record has not been registered by an independent trust boundary."
            ],
        }
        registry_path = self.root / registry_locator
        original_read_json = read_json
        registry_reads = 0

        def substitute_acceptance(path):
            nonlocal registry_reads
            if Path(path).resolve() == registry_path.resolve():
                registry_reads += 1
                if registry_reads == 1:
                    return copy.deepcopy(fake_acceptance)
            return original_read_json(path)

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            with patch("verispiral.pipeline.read_json", side_effect=substitute_acceptance):
                result = run_demo(candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)
            self.assertEqual(packet["stage_status"]["semantic_verification"], "verified")
            self.assertEqual(packet["stage_status"]["human_acceptance"], "invalid")
            human_gate = next(
                gate for gate in packet["gate_results"] if gate["gate"] == "human_acceptance"
            )
            self.assertIn("not registered", human_gate["summary"])
            self.assertIsNone(result.success_trace)
            self.assertIsNone(result.induced_skill)

    def test_trace_and_skill_provenance_bind_exact_blueprint(self) -> None:
        candidate = read_json(self.candidate_path)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pending = run_demo(self.candidate_path, base / "pending", self.root)
            packet = read_json(pending.decision_packet)
        blueprint_sha = skill_blueprint_digest(candidate)
        packet["decision"] = "promote_to_prototype"
        packet["gate_recommendation"] = "promote_to_prototype"
        packet["stage_status"]["human_acceptance"] = "accepted"
        human_gate = next(
            gate for gate in packet["gate_results"] if gate["gate"] == "human_acceptance"
        )
        human_gate["verdict"] = "pass"
        human_gate["summary"] = "registered human acceptance bound to the exact blueprint"
        packet["human_acceptance_records"] = [
            {
                "acceptance_id": "acceptance-provenance-probe",
                "locator": "probe/acceptance.json",
                "sha256": "2" * 64,
                "semantic_sha256": semantic_subject_digest(candidate),
                "skill_blueprint_sha256": blueprint_sha,
                "receipt_id": packet["verification_receipts"][0]["receipt_id"],
                "receipt_sha256": packet["verification_receipts"][0]["sha256"],
                "decision": "accepted",
                "scope": "prototype_skill_activation",
                "reviewer_role": "human_reviewer",
                "acceptance_registry_id": "acceptance-registry-probe",
                "acceptance_registry_sha256": "3" * 64,
            }
        ]
        trace = build_success_trace(candidate, packet)
        skill = build_induced_skill(candidate, trace)
        self.assertEqual(trace["verification_receipt"]["skill_blueprint_sha256"], blueprint_sha)
        self.assertEqual(trace["human_acceptance"]["skill_blueprint_sha256"], blueprint_sha)
        self.assertEqual(skill["provenance"]["skill_blueprint_sha256"], blueprint_sha)
        self.assertEqual(validate_artifact(trace, "success_trace", self.root), [])
        self.assertEqual(validate_artifact(skill, "induced_skill", self.root), [])

        attacked = copy.deepcopy(candidate)
        attacked["skill_blueprint"]["workflow"].append("Bypass the gate after approval.")
        with self.assertRaises(PipelineError):
            build_success_trace(attacked, packet)

    def test_parked_candidate_cannot_promote(self) -> None:
        candidate = copy.deepcopy(read_json(self.candidate_path))
        candidate["status"] = "parked"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            result = run_demo(candidate_path, base / "output", self.root)
            packet = read_json(result.decision_packet)
            self.assertEqual(result.decision, "parked")
            self.assertEqual(packet["gate_recommendation"], "keep_parked")
            self.assertEqual(packet["stage_status"]["candidate_lifecycle"], "parked")
            lifecycle_gate = next(
                gate
                for gate in packet["gate_results"]
                if gate["gate"] == "candidate_lifecycle"
            )
            self.assertEqual(lifecycle_gate["verdict"], "blocked")
            self.assertIsNone(result.success_trace)
            self.assertIsNone(result.induced_skill)

    def test_schema_failure_stops_before_decision_packet(self) -> None:
        candidate = read_json(self.candidate_path)
        del candidate["claim"]["kill_conditions"]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            candidate_path = base / "candidate.json"
            candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
            with self.assertRaises(CandidateValidationError):
                run_demo(candidate_path, base / "output", self.root)
            self.assertFalse((base / "output" / "decision_packet.json").exists())


if __name__ == "__main__":
    unittest.main()
