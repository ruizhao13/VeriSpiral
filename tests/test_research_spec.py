from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from verispiral.pipeline import file_digest, object_digest
from verispiral.research_spec import (
    ResearchSpecError,
    run_research_specification_loop,
    verify_trace_integrity,
)
from verispiral.schema import load_schema, validate


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = (
    ROOT / "examples" / "research_spec" / "minimax_coevolution_scenario.json"
)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_scenario(path: Path, value: dict[str, object]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def reseal_trace_events(trace: dict[str, object]) -> None:
    previous = "0" * 64
    sealed: dict[str, dict[str, object]] = {}
    for event in trace["events"]:
        event["previous_event_sha256"] = previous
        for consumption in event["consumes"]:
            consumption["event_sha256"] = sealed[consumption["event_id"]][
                "event_sha256"
            ]
        body = {key: value for key, value in event.items() if key != "event_sha256"}
        event["event_sha256"] = object_digest(body)
        sealed[event["event_id"]] = event
        previous = event["event_sha256"]
    trace["event_chain_head_sha256"] = previous


class ResearchSpecificationLoopTests(unittest.TestCase):
    def _run_scenario(self, scenario: dict[str, object]):
        temporary = tempfile.TemporaryDirectory()
        base = Path(temporary.name)
        scenario_path = base / "scenario.json"
        write_scenario(scenario_path, scenario)
        result = run_research_specification_loop(
            scenario_path, base / "output", ROOT
        )
        return temporary, result

    def _expect_error(self, mutate) -> ResearchSpecError:
        scenario = copy.deepcopy(read_json(SCENARIO_PATH))
        mutate(scenario)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            scenario_path = base / "scenario.json"
            write_scenario(scenario_path, scenario)
            with self.assertRaises(ResearchSpecError) as caught:
                run_research_specification_loop(scenario_path, base / "output", ROOT)
        return caught.exception

    def test_public_loop_is_connected_human_gated_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = run_research_specification_loop(
                SCENARIO_PATH, base / "first", ROOT
            )
            second = run_research_specification_loop(
                SCENARIO_PATH, base / "second", ROOT
            )
            self.assertEqual(first.trace.read_bytes(), second.trace.read_bytes())
            self.assertEqual(first.manifest.read_bytes(), second.manifest.read_bytes())
            trace = read_json(first.trace)

        self.assertEqual(
            [item["outcome"] for item in trace["rounds"]],
            [
                "target_compatible_control_pass",
                "revision_accepted_as_immutable_successor",
                "failed_control_checks",
                "revision_created_separate_branch",
                "target_compatible_control_pass",
            ],
        )
        self.assertEqual(
            [item["consumed_preceding_terminal_event_id"] for item in trace["rounds"]],
            [
                "specification.registered",
                "round-01.human-solution-judgment",
                "round-02.human-spec-decision",
                "round-03.diagnosis",
                "round-04.human-spec-decision",
            ],
        )
        branches = {item["branch_id"]: item for item in trace["branches"]}
        parent = branches["unknown-horizon-target"]
        verifier_child = branches["unknown-horizon-target-verifier-v2"]
        model_child = branches["known-horizon-exploration"]
        self.assertEqual(parent["specification_version"], "1.0.0")
        self.assertEqual(parent["status"], "superseded")
        self.assertEqual(verifier_child["specification_version"], "1.1.0")
        self.assertEqual(model_child["specification_version"], "1.2.0")
        self.assertEqual(verifier_child["parent_branch_id"], parent["branch_id"])
        self.assertEqual(model_child["parent_branch_id"], verifier_child["branch_id"])
        self.assertFalse(verifier_child["parent_progress_credit"])
        self.assertFalse(model_child["parent_progress_credit"])
        self.assertEqual(
            verifier_child["target_lineage_id"], parent["target_lineage_id"]
        )
        self.assertNotEqual(
            model_child["target_lineage_id"], parent["target_lineage_id"]
        )
        self.assertEqual(verifier_child["lineage_relation"], "accepted_successor")
        self.assertEqual(model_child["lineage_relation"], "separate_model_branch")
        self.assertTrue(trace["invariants"]["initial_specification_preserved"])
        self.assertFalse(trace["invariants"]["ai_changed_specification"])
        self.assertFalse(trace["invariants"]["superseded_specification_reused"])
        self.assertEqual(
            trace["final_status"],
            "target_compatible_candidate_awaiting_semantic_verification",
        )
        self.assertEqual(
            trace["scientific_claim_status"], "not_established_by_control_loop"
        )
        self.assertEqual(
            trace["candidates"][-1]["human_judgment_event_id"],
            "round-05.human-solution-judgment",
        )
        self.assertEqual(
            trace["candidates"][-1]["scientific_claim_status"], "not_established"
        )
        first, replay = trace["candidates"][:2]
        self.assertEqual(first["control_status"], "target_compatible_control_pass")
        self.assertNotIn(
            "information_interface_exact_match",
            [item["type"] for item in first["verifier_results"]],
        )
        interface_result = next(
            item
            for item in replay["verifier_results"]
            if item["type"] == "information_interface_exact_match"
        )
        self.assertEqual(replay["control_status"], "failed_control_checks")
        self.assertEqual(interface_result["diagnostic_code"], "information_interface_mismatch")
        self.assertEqual(
            trace["candidates"][-1]["branch_id"],
            "unknown-horizon-target-verifier-v2",
        )
        self.assertEqual(len(trace["candidates"][-1]["verifier_results"]), 3)
        events_after_accept = [
            event for event in trace["events"] if event["event_index"] > 5
        ]
        self.assertNotIn(
            "minimax-unknown-horizon-v1",
            [event["specification_id"] for event in events_after_accept],
        )

    def test_public_inputs_and_outputs_conform_to_independent_schemas(self) -> None:
        scenario = read_json(SCENARIO_PATH)
        self.assertEqual(
            validate(
                scenario,
                load_schema(ROOT / "schemas" / "research_coevolution_scenario.schema.json"),
            ),
            [],
        )
        spec_schema = load_schema(ROOT / "schemas" / "research_specification.schema.json")
        for entry in scenario["specification_registry"]:
            self.assertEqual(validate(read_json(ROOT / entry["path"]), spec_schema), [])
        with tempfile.TemporaryDirectory() as temporary:
            result = run_research_specification_loop(
                SCENARIO_PATH, Path(temporary) / "output", ROOT
            )
            self.assertEqual(
                validate(
                    read_json(result.trace),
                    load_schema(ROOT / "schemas" / "research_coevolution_trace.schema.json"),
                ),
                [],
            )
            self.assertEqual(
                validate(
                    read_json(result.manifest),
                    load_schema(ROOT / "schemas" / "research_coevolution_manifest.schema.json"),
                ),
                [],
            )
            self.assertEqual(read_json(result.manifest)["trace_sha256"], file_digest(result.trace))

    def test_event_hash_chain_and_consumption_hashes_detect_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_research_specification_loop(
                SCENARIO_PATH, Path(temporary) / "output", ROOT
            )
            trace = read_json(result.trace)
        scenario = read_json(SCENARIO_PATH)
        verify_trace_integrity(trace, ROOT, scenario)
        trace["events"][2]["details"]["summary"] = "Tampered diagnosis summary that is long enough for schema validation."
        with self.assertRaises(ResearchSpecError) as caught:
            verify_trace_integrity(trace, ROOT, scenario)
        self.assertIn("event hash mismatch", str(caught.exception))

    def test_resealed_source_payload_hash_must_match_scenario_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_research_specification_loop(
                SCENARIO_PATH, Path(temporary) / "output", ROOT
            )
            trace = read_json(result.trace)
        trace["events"][1]["source_payload_sha256"] = "0" * 64
        reseal_trace_events(trace)
        with self.assertRaises(ResearchSpecError) as caught:
            verify_trace_integrity(trace, ROOT, read_json(SCENARIO_PATH))
        self.assertIn("source payload hash mismatch", str(caught.exception))

    def test_top_level_derived_state_must_match_canonical_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_research_specification_loop(
                SCENARIO_PATH, Path(temporary) / "output", ROOT
            )
            original = read_json(result.trace)
        scenario = read_json(SCENARIO_PATH)

        wrong_final = copy.deepcopy(original)
        wrong_final["final_status"] = "no_target_compatible_candidate"
        with self.assertRaises(ResearchSpecError) as final_error:
            verify_trace_integrity(wrong_final, ROOT, scenario)
        self.assertIn("final_status", str(final_error.exception))

        revived_parent = copy.deepcopy(original)
        parent = next(
            item
            for item in revived_parent["branches"]
            if item["branch_id"] == "unknown-horizon-target"
        )
        parent["status"] = "researching"
        with self.assertRaises(ResearchSpecError) as branch_error:
            verify_trace_integrity(revived_parent, ROOT, scenario)
        self.assertIn("branches", str(branch_error.exception))

    def test_next_round_must_consume_preceding_diagnosis(self) -> None:
        error = self._expect_error(
            lambda scenario: scenario["rounds"][1]["submission"].update(
                {
                    "consumes": [
                        {
                            "event_id": "specification.registered",
                            "response_code": "begin_research_under_registered_specification",
                        }
                    ]
                }
            )
        )
        self.assertIn("must consume the preceding", str(error))

    def test_consumed_response_code_must_have_been_emitted(self) -> None:
        error = self._expect_error(
            lambda scenario: scenario["rounds"][1]["submission"]["consumes"][0].update(
                {"response_code": "invented_response"}
            )
        )
        self.assertIn("did not emit response code", str(error))

    def test_ai_revision_discussion_cannot_apply_without_human_decision(self) -> None:
        error = self._expect_error(
            lambda scenario: scenario["rounds"][1].update(
                {"human_spec_decision": None}
            )
        )
        self.assertIn("requires a human decision", str(error))

    def test_superseded_v1_verifier_cannot_receive_later_research(self) -> None:
        error = self._expect_error(
            lambda scenario: scenario["rounds"][2].update(
                {"branch_id": "unknown-horizon-target"}
            )
        )
        self.assertIn("is not ready for another research round", str(error))

    def test_human_rejection_preserves_parent_and_creates_no_branch(self) -> None:
        scenario = copy.deepcopy(read_json(SCENARIO_PATH))
        decision = scenario["rounds"][1]["human_spec_decision"]
        decision.update(
            {
                "action": "reject",
                "child_branch_id": None,
                "selected_specification_id": None,
                "selected_revision_kind": None,
                "decision_note": "Reject the model revision and continue research under the unchanged parent specification.",
            }
        )
        scenario["rounds"] = scenario["rounds"][:2]
        temporary, result = self._run_scenario(scenario)
        try:
            trace = read_json(result.trace)
        finally:
            temporary.cleanup()
        self.assertEqual(len(trace["branches"]), 1)
        self.assertEqual(trace["branches"][0]["specification_version"], "1.0.0")
        self.assertEqual(
            trace["rounds"][1]["outcome"], "revision_rejected_parent_preserved"
        )

    def test_human_modify_selects_a_distinct_registered_specification(self) -> None:
        scenario = copy.deepcopy(read_json(SCENARIO_PATH))
        decision = scenario["rounds"][1]["human_spec_decision"]
        decision.update(
            {
                "action": "modify",
                "child_branch_id": "human-modified-verifier-successor",
                "selected_specification_id": "minimax-unknown-horizon-human-modified-verifier-v3",
                "selected_revision_kind": "verifier_revision",
                "decision_note": "Use the human-modified verifier wording and create a versioned child branch without parent credit.",
            }
        )
        scenario["rounds"] = scenario["rounds"][:2]
        temporary, result = self._run_scenario(scenario)
        try:
            trace = read_json(result.trace)
        finally:
            temporary.cleanup()
        branch = next(
            item for item in trace["branches"] if item["branch_id"] == "human-modified-verifier-successor"
        )
        self.assertEqual(branch["specification_version"], "1.2.0")
        self.assertFalse(branch["parent_progress_credit"])

    def test_child_solution_never_counts_as_parent_target_progress(self) -> None:
        scenario = copy.deepcopy(read_json(SCENARIO_PATH))
        final_round = scenario["rounds"][4]
        final_round["branch_id"] = "known-horizon-exploration"
        final_round["submission"]["solution_candidate"]["assumptions"][
            "horizon_knowledge"
        ] = "known"
        final_round["submission"]["solution_candidate"]["information_interface"][
            "horizon_knowledge"
        ] = "known"
        temporary, result = self._run_scenario(scenario)
        try:
            trace = read_json(result.trace)
        finally:
            temporary.cleanup()
        self.assertEqual(trace["candidates"][-1]["control_status"], "target_compatible_control_pass")
        self.assertEqual(trace["candidates"][-1]["branch_id"], "known-horizon-exploration")
        self.assertFalse(trace["candidates"][-1]["parent_progress_credit"])
        self.assertEqual(trace["final_status"], "no_target_compatible_candidate")

    def test_registry_hash_drift_and_wrong_revision_class_are_rejected(self) -> None:
        hash_error = self._expect_error(
            lambda scenario: scenario["specification_registry"][0].update(
                {"specification_sha256": "0" * 64}
            )
        )
        self.assertIn("object hash drift", str(hash_error))
        class_error = self._expect_error(
            lambda scenario: scenario["rounds"][1]["submission"][
                "revision_discussion"
            ].update({"revision_kind": "model_revision"})
        )
        self.assertIn("does not match changed fields", str(class_error))

    def test_human_modify_cannot_cross_the_ai_discussion_revision_kind(self) -> None:
        def mutate(scenario):
            decision = scenario["rounds"][3]["human_spec_decision"]
            decision.update(
                {
                    "action": "modify",
                    "child_branch_id": "cross-kind-attack",
                    "selected_specification_id": "minimax-unknown-horizon-human-modified-verifier-v3",
                    "selected_revision_kind": "verifier_revision",
                }
            )

        error = self._expect_error(mutate)
        self.assertIn("must preserve the AI discussion revision_kind", str(error))

    def test_problem_identity_effect_is_strictly_bound_to_revision_kind(self) -> None:
        verifier_error = self._expect_error(
            lambda scenario: scenario["rounds"][1]["submission"][
                "revision_discussion"
            ].update({"problem_identity_effect": "creates_new_target_lineage"})
        )
        self.assertIn("verifier_revision requires", str(verifier_error))
        model_error = self._expect_error(
            lambda scenario: scenario["rounds"][3]["submission"][
                "revision_discussion"
            ].update({"problem_identity_effect": "preserves_problem"})
        )
        self.assertIn("model_revision requires", str(model_error))

    def test_duplicate_json_keys_are_rejected(self) -> None:
        source = SCENARIO_PATH.read_text(encoding="utf-8")
        duplicated = source.replace(
            '  "schema_version": "1.0",',
            '  "schema_version": "1.0",\n  "schema_version": "1.0",',
            1,
        )
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            path = base / "scenario.json"
            path.write_text(duplicated, encoding="utf-8")
            with self.assertRaises(ResearchSpecError) as caught:
                run_research_specification_loop(path, base / "output", ROOT)
        self.assertIn("duplicate JSON object key", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
