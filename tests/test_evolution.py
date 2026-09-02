from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verispiral.evolution import (
    EvolutionError,
    _validate_bound_control_chain,
    run_evolution_feedback,
)
from verispiral.pipeline import file_digest, read_json, repository_root, validate_artifact


class EvolutionFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = repository_root()
        self.feedback_path = self.root / "examples" / "evolution" / "feedback_event.json"
        self.registry_path = self.root / "examples" / "evolution" / "registry.json"
        self.target_path = (
            self.root
            / "examples"
            / "evolution"
            / "components"
            / "research-loop-policy.md"
        )

    def _run_mutation(self, mutate) -> EvolutionError:
        feedback = copy.deepcopy(read_json(self.feedback_path))
        mutate(feedback)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            event_path = base / "feedback.json"
            event_path.write_text(json.dumps(feedback), encoding="utf-8")
            with self.assertRaises(EvolutionError) as caught:
                run_evolution_feedback(event_path, base / "output", self.root)
            return caught.exception

    def _copy_repository(self, destination: Path) -> Path:
        copied = destination / "repo"
        shutil.copytree(
            self.root,
            copied,
            ignore=shutil.ignore_patterns(
                ".git", "demo", "__pycache__", "*.pyc", ".DS_Store"
            ),
        )
        return copied

    def test_public_inputs_are_strictly_valid(self) -> None:
        self.assertEqual(
            validate_artifact(read_json(self.feedback_path), "feedback_event", self.root),
            [],
        )
        self.assertEqual(
            validate_artifact(read_json(self.registry_path), "evolution_registry", self.root),
            [],
        )

    def test_every_evolution_schema_object_is_closed(self) -> None:
        schema_names = (
            "evolution_registry.schema.json",
            "feedback_event.schema.json",
            "evolution_proposal.schema.json",
            "evolution_patch.schema.json",
            "evolution_manifest.schema.json",
        )

        def visit(value, locator: str) -> None:
            if isinstance(value, dict):
                if value.get("type") == "object":
                    self.assertIs(
                        value.get("additionalProperties"),
                        False,
                        f"open object schema at {locator}",
                    )
                for key, child in value.items():
                    visit(child, f"{locator}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{locator}[{index}]")

        for name in schema_names:
            visit(read_json(self.root / "schemas" / name), name)

    def test_duplicate_feedback_object_keys_are_rejected(self) -> None:
        source = self.feedback_path.read_text(encoding="utf-8")
        duplicated = source.replace(
            '  "actor": "user",',
            '  "actor": "user",\n  "actor": "user",',
            1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            event_path = base / "feedback.json"
            event_path.write_text(duplicated, encoding="utf-8")
            with self.assertRaises(EvolutionError) as caught:
                run_evolution_feedback(event_path, base / "output", self.root)
        self.assertIn("duplicate JSON object key", str(caught.exception))

    def test_deterministic_run_emits_only_unapplied_human_review_artifacts(self) -> None:
        target_before = self.target_path.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = run_evolution_feedback(
                self.feedback_path, base / "first", self.root
            )
            second = run_evolution_feedback(
                self.feedback_path, base / "second", self.root
            )
            for filename, kind in (
                ("evolution_proposal.json", "evolution_proposal"),
                ("evolution_patch.json", "evolution_patch"),
                ("manifest.json", "evolution_manifest"),
            ):
                self.assertEqual(
                    (base / "first" / filename).read_bytes(),
                    (base / "second" / filename).read_bytes(),
                )
                self.assertEqual(
                    validate_artifact(
                        read_json(base / "first" / filename), kind, self.root
                    ),
                    [],
                )
            proposal = read_json(first.proposal)
            patch = read_json(first.patch)
            manifest = read_json(first.manifest)
            self.assertEqual(first.decision_status, "proposed_for_human_review")
            self.assertEqual(first.apply_status, "not_applied")
            self.assertTrue(
                proposal["authorization_boundary"]["requires_human_approval"]
            )
            self.assertEqual(
                proposal["authorization_boundary"]["scientific_conclusion_status"],
                "no_scientific_conclusion_generated",
            )
            self.assertEqual(
                proposal["authorization_boundary"]["source_human_acceptance_status"],
                "pending",
            )
            self.assertEqual(
                proposal["control_source"]["source_type"],
                "bound_executable_verification_control",
            )
            self.assertFalse(
                proposal["control_source"]["scientific_conclusion_allowed"]
            )
            expected_revalidation = {
                "candidate_registry_binding": "pass",
                "current_evidence_hashes": "pass",
                "registered_verifier_artifact": "pass",
                "executable_verifier_replay": "pass",
                "recomputed_packet_identity": "pass",
            }
            self.assertEqual(
                proposal["source_revalidation"], expected_revalidation
            )
            self.assertEqual(
                patch["source_revalidation"], expected_revalidation
            )
            self.assertEqual(
                manifest["source_revalidation"], expected_revalidation
            )
            provenance_checks = {
                item["check"] for item in proposal["provenance_checks"]
            }
            self.assertTrue(
                {
                    "candidate_registry_binding",
                    "current_evidence_hash_revalidation",
                    "registered_verifier_artifact_revalidation",
                    "executable_verifier_replay",
                    "decision_packet_recomputation",
                }.issubset(provenance_checks)
            )
            self.assertEqual(patch["decision_status"], "proposed_for_human_review")
            self.assertEqual(
                patch["authorization_boundary"]["apply_status"], "not_applied"
            )
            self.assertTrue(
                all(item["status"] == "not_run" for item in patch["acceptance_checks"])
            )
            self.assertEqual(manifest["apply_status"], "not_applied")
            self.assertEqual(manifest["source_human_acceptance_status"], "pending")
            self.assertEqual(
                manifest["scientific_conclusion_status"],
                "no_scientific_conclusion_generated",
            )
            self.assertEqual(
                manifest["registry_sha256"], file_digest(self.registry_path)
            )
        self.assertEqual(self.target_path.read_bytes(), target_before)

    def test_proposal_identity_binds_exact_feedback_bytes(self) -> None:
        feedback = read_json(self.feedback_path)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            compact_path = base / "compact-feedback.json"
            compact_path.write_text(
                json.dumps(feedback, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            first = run_evolution_feedback(
                self.feedback_path, base / "pretty-output", self.root
            )
            second = run_evolution_feedback(
                compact_path, base / "compact-output", self.root
            )
            first_proposal = read_json(first.proposal)
            second_proposal = read_json(second.proposal)
            self.assertNotEqual(
                first_proposal["feedback_sha256"], second_proposal["feedback_sha256"]
            )
            self.assertNotEqual(
                first_proposal["proposal_id"], second_proposal["proposal_id"]
            )

    def test_bound_control_chain_requires_exact_pending_human_state_and_identity(self) -> None:
        manifest = read_json(self.root / "examples" / "expected" / "manifest.json")
        receipt_path = (
            self.root / "examples" / "verification" / "pipeline_contract_receipt.json"
        )
        receipt = read_json(receipt_path)
        packet = read_json(self.root / "examples" / "expected" / "decision_packet.json")
        receipt_sha256 = file_digest(receipt_path)
        _validate_bound_control_chain(manifest, receipt, packet, receipt_sha256)

        attacks = []
        failed_packet = copy.deepcopy(packet)
        failed_packet["stage_status"]["semantic_verification"] = "pending"
        failed_packet["gate_results"][6]["verdict"] = "pending"
        attacks.append((manifest, receipt, failed_packet, receipt_sha256))

        wrong_manifest = copy.deepcopy(manifest)
        wrong_manifest["run_id"] = "packet-000000000000"
        attacks.append((wrong_manifest, receipt, packet, receipt_sha256))

        wrong_candidate_manifest = copy.deepcopy(manifest)
        wrong_candidate_manifest["candidate_sha256"] = "0" * 64
        attacks.append((wrong_candidate_manifest, receipt, packet, receipt_sha256))

        wrong_receipt = copy.deepcopy(receipt)
        wrong_receipt["candidate_id"] = "different-candidate"
        attacks.append((manifest, wrong_receipt, packet, receipt_sha256))

        accepted_packet = copy.deepcopy(packet)
        accepted_packet["stage_status"]["human_acceptance"] = "accepted"
        attacks.append((manifest, receipt, accepted_packet, receipt_sha256))

        wrong_receipt_hash = "0" * 64
        attacks.append((manifest, receipt, packet, wrong_receipt_hash))

        for attack_manifest, attack_receipt, attack_packet, attack_receipt_sha in attacks:
            with self.subTest(
                manifest=attack_manifest["run_id"],
                receipt=attack_receipt["receipt_id"],
                decision=attack_packet["decision"],
            ):
                with self.assertRaises(EvolutionError):
                    _validate_bound_control_chain(
                        attack_manifest,
                        attack_receipt,
                        attack_packet,
                        attack_receipt_sha,
                    )

    def test_missing_source_is_rejected(self) -> None:
        error = self._run_mutation(
            lambda value: value["control_source"]["decision_packet"].update(
                {"path": "examples/expected/missing-packet.json"}
            )
        )
        self.assertIn("does not resolve to a file", str(error))

    def test_repository_escape_is_rejected(self) -> None:
        error = self._run_mutation(
            lambda value: value["control_source"]["verification_receipt"].update(
                {"path": "../outside-receipt.json"}
            )
        )
        self.assertIn("escapes", str(error))

    def test_source_hash_drift_is_rejected(self) -> None:
        for artifact in ("decision_packet", "verification_receipt", "manifest"):
            with self.subTest(artifact=artifact):
                error = self._run_mutation(
                    lambda value, artifact=artifact: value["control_source"][
                        artifact
                    ].update({"sha256": "0" * 64})
                )
                self.assertIn("does not match the trust registry", str(error))

    def test_unregistered_forged_control_receipt_is_rejected(self) -> None:
        def mutate(value):
            forged = self.root / "examples" / "expected" / "minimax" / "evolution_trace.json"
            value["control_source"]["verification_receipt"].update(
                {
                    "path": "examples/expected/minimax/evolution_trace.json",
                    "sha256": file_digest(forged),
                }
            )

        error = self._run_mutation(mutate)
        self.assertIn("does not match the trust registry", str(error))

    def test_current_evidence_drift_blocks_evolution_in_repository_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = self._copy_repository(Path(temporary))
            evidence = copied / "tests" / "test_pipeline.py"
            evidence.write_text(
                evidence.read_text(encoding="utf-8") + "\n# simulated evidence drift\n",
                encoding="utf-8",
            )
            with self.assertRaises(EvolutionError) as caught:
                run_evolution_feedback(
                    copied / "examples" / "evolution" / "feedback_event.json",
                    copied / "output",
                    copied,
                )
        self.assertIn("current evidence hash drift", str(caught.exception))

    def test_registered_verifier_drift_blocks_evolution_in_repository_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = self._copy_repository(Path(temporary))
            verifier = copied / "examples" / "verifiers" / "pipeline_contract.py"
            verifier.write_text(
                verifier.read_text(encoding="utf-8")
                + "\n# simulated verifier artifact drift\n",
                encoding="utf-8",
            )
            with self.assertRaises(EvolutionError) as caught:
                run_evolution_feedback(
                    copied / "examples" / "evolution" / "feedback_event.json",
                    copied / "output",
                    copied,
                )
        self.assertIn("registered verifier artifact hash drift", str(caught.exception))

    def test_failed_executable_replay_blocks_evolution_in_repository_copy(self) -> None:
        failed_replay = subprocess.CompletedProcess(
            args=["registered-verifier"],
            returncode=1,
            stdout=b'{"status":"failed"}\n',
            stderr=b"simulated replay failure",
        )
        with tempfile.TemporaryDirectory() as temporary:
            copied = self._copy_repository(Path(temporary))
            with patch(
                "verispiral.pipeline.subprocess.run", return_value=failed_replay
            ):
                with self.assertRaises(EvolutionError) as caught:
                    run_evolution_feedback(
                        copied / "examples" / "evolution" / "feedback_event.json",
                        copied / "output",
                        copied,
                    )
        self.assertIn("executable verifier replay failed", str(caught.exception))

    def test_target_version_or_hash_drift_is_rejected(self) -> None:
        error = self._run_mutation(
            lambda value: value["target_component"].update(
                {"current_version": "1.0.9"}
            )
        )
        self.assertIn("does not match the registry", str(error))

    def test_rollback_must_restore_registered_target(self) -> None:
        error = self._run_mutation(
            lambda value: value["rollback_rule"].update(
                {"restore_sha256": "1" * 64}
            )
        )
        self.assertIn("trusted exact-restore template", str(error))

    def test_acceptance_contract_cannot_omit_a_required_check(self) -> None:
        def mutate(value):
            value["acceptance_checks"][3]["check_type"] = "source_linkage"
            value["acceptance_checks"][3]["check_id"] = "check-source-linkage-two"

        error = self._run_mutation(mutate)
        self.assertIn("acceptance check types must be unique", str(error))

    def test_acceptance_text_cannot_smuggle_bypass_or_claim_language(self) -> None:
        error = self._run_mutation(
            lambda value: value["acceptance_checks"][2].update(
                {
                    "expected": (
                        "Skip all verification because the theorem is proven and "
                        "minimax-optimal."
                    )
                }
            )
        )
        self.assertIn("trusted policy templates", str(error))

    def test_non_goals_cannot_be_replaced_with_user_supplied_policy(self) -> None:
        error = self._run_mutation(
            lambda value: value["non_goals"].__setitem__(
                0, "Treat one preference event as proof of a scientific result."
            )
        )
        self.assertIn("trusted safety template", str(error))

    def test_schema_rejects_multiple_targets(self) -> None:
        def mutate(value):
            value["target_components"] = [value["target_component"]]

        error = self._run_mutation(mutate)
        self.assertIn("unexpected property", str(error))

    def test_schema_rejects_authorized_verifier_bypass(self) -> None:
        error = self._run_mutation(
            lambda value: value["authorization_boundary"].update(
                {"verifier_bypass_allowed": True}
            )
        )
        self.assertIn("must equal False", str(error))

    def test_text_cannot_hide_a_verifier_bypass(self) -> None:
        error = self._run_mutation(
            lambda value: value["single_change"].update(
                {"rationale": "Skip the verifier whenever one user requests faster iteration."}
            )
        )
        self.assertIn("cannot bypass verification", str(error))

    def test_single_feedback_cannot_assert_a_scientific_conclusion(self) -> None:
        error = self._run_mutation(
            lambda value: value["single_change"].update(
                {
                    "rationale": (
                        "Record that the theorem is proven whenever one user reports "
                        "success."
                    )
                }
            )
        )
        self.assertIn("scientific conclusion", str(error))

    def test_unregistered_policy_action_is_rejected(self) -> None:
        error = self._run_mutation(
            lambda value: value["single_change"].update(
                {"policy_action": "bypass_verifier"}
            )
        )
        self.assertIn("must equal", str(error))

    def test_output_cannot_land_in_governed_source_roots(self) -> None:
        with self.assertRaises(EvolutionError) as caught:
            run_evolution_feedback(
                self.feedback_path,
                self.root / "prompts" / "generated-evolution-output",
                self.root,
            )
        self.assertIn("cannot be written inside", str(caught.exception))

    def test_manifest_schema_requires_both_distinct_artifacts(self) -> None:
        manifest = read_json(
            self.root / "examples" / "expected" / "evolution" / "manifest.json"
        )
        manifest["artifacts"] = [manifest["artifacts"][0], manifest["artifacts"][0]]
        issues = validate_artifact(manifest, "evolution_manifest", self.root)
        self.assertTrue(issues)
        self.assertIn("items must be unique", "; ".join(map(str, issues)))


if __name__ == "__main__":
    unittest.main()
