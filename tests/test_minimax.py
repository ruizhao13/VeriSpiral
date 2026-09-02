from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from verispiral.cli import main
from verispiral.minimax import MinimaxScenarioError, run_minimax_scenario
from verispiral.pipeline import validate_artifact


ROOT = Path(__file__).resolve().parents[1]


def signature() -> dict[str, str]:
    return {
        "observation_model": "stochastic_k_armed_bandit",
        "parameter_class": "bounded_mean_vectors",
        "loss": "expected_pseudo_regret",
        "algorithm_class": "nonanticipating_policy",
        "regime": "gap_independent_finite_horizon",
    }


def assumptions(horizon_knowledge: str) -> dict[str, object]:
    return {
        "arms_known": True,
        "horizon_knowledge": horizon_knowledge,
        "reward_support": "unit_interval",
    }


def rate(log_horizon: str = "0", horizon: str = "1/2") -> dict[str, object]:
    return {
        "polynomial_exponents": {"arms": "1/2", "horizon": horizon},
        "log_exponents": {"horizon": log_horizon},
    }


def source_registry() -> list[dict[str, str]]:
    return [
        {
            "source_id": source_id,
            "title": title,
            "url": f"https://example.invalid/{source_id}",
            "locator": f"synthetic public fixture for {source_id}",
            "registration_status": "registered_public_extract",
            "proof_status": "cited_not_reproved",
        }
        for source_id, title in (
            ("source-lower", "Synthetic lower certificate source"),
            ("source-ucb", "Synthetic UCB-like certificate source"),
            ("source-moss", "Synthetic horizon-tuned certificate source"),
            ("source-anytime", "Synthetic anytime certificate source"),
        )
    ]


def certificate(
    certificate_id: str,
    kind: str,
    source_id: str,
    horizon_knowledge: str,
    certificate_rate: dict[str, object],
) -> dict[str, object]:
    return {
        "certificate_id": certificate_id,
        "kind": kind,
        "registered": True,
        "source_id": source_id,
        "theorem_locator": f"{source_id}:theorem-fixture",
        "extraction_note": "Synthetic certificate fields registered for verifier tests.",
        "problem_signature": signature(),
        "assumptions": assumptions(horizon_knowledge),
        "rate": certificate_rate,
    }


def three_round_scenario() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "scenario_id": "public-bandit-minimax-evolution",
        "problem_signature": signature(),
        "target_assumptions": assumptions("unknown"),
        "source_registry": source_registry(),
        "assumption_order": {"horizon_knowledge": ["unknown", "known"]},
        "lower_certificate": certificate(
            "registered-lower-v1", "lower", "source-lower", "unknown", rate()
        ),
        "rounds": [
            {
                "round_index": 1,
                "candidate_id": "ucb-like-v1",
                "candidate_label": "UCB-like registered upper certificate",
                "algorithm_change": "Use the synthetic UCB-like fixture algorithm.",
                "search_hypothesis": "The synthetic baseline retains a logarithmic rate gap.",
                "upper_certificate": certificate(
                    "registered-upper-ucb-v1",
                    "upper",
                    "source-ucb",
                    "unknown",
                    rate("1/2"),
                ),
            },
            {
                "round_index": 2,
                "candidate_id": "horizon-tuned-moss-v1",
                "candidate_label": "Horizon-tuned MOSS registered upper certificate",
                "algorithm_change": "Use the synthetic horizon-tuned fixture algorithm.",
                "search_hypothesis": "Known horizon closes the rate gap on a separate branch.",
                "upper_certificate": certificate(
                    "registered-upper-moss-v1",
                    "upper",
                    "source-moss",
                    "known",
                    rate(),
                ),
            },
            {
                "round_index": 3,
                "candidate_id": "anytime-minimax-v1",
                "candidate_label": "Anytime minimax registered upper certificate",
                "algorithm_change": "Use the synthetic anytime minimax fixture algorithm.",
                "search_hypothesis": "Anytime calibration restores the target assumption scope.",
                "upper_certificate": certificate(
                    "registered-upper-anytime-v1",
                    "upper",
                    "source-anytime",
                    "unknown",
                    rate(),
                ),
            },
        ],
    }


def write_scenario(path: Path, scenario: dict[str, object]) -> None:
    path.write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class MinimaxVerifierTests(unittest.TestCase):
    def test_three_round_evolution_preserves_target_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, three_round_scenario())
            result = run_minimax_scenario(scenario_path, root / "output")

            trace = read_json(result.evolution_trace)
            rounds = trace["rounds"]
            self.assertEqual(
                [item["status"] for item in rounds],
                ["log_gap", "not_comparable", "minimax_rate_match"],
            )
            self.assertEqual(
                [item["rate_check"]["status"] for item in rounds],
                ["log_gap", "minimax_rate_match", "minimax_rate_match"],
            )
            self.assertEqual(rounds[1]["assumption_check"]["status"], "assumption_mismatch")
            self.assertEqual(rounds[1]["comparability"], "not_comparable")
            self.assertFalse(rounds[1]["rate_algebra_applicable_to_target"])
            self.assertEqual(rounds[1]["branch_transition"], "branched_without_target_mutation")
            self.assertEqual(rounds[2]["branch_transition"], "returned_to_target")
            self.assertTrue(trace["final"]["original_target_preserved"])
            self.assertEqual(result.final_status, "minimax_rate_match")
            self.assertEqual(trace["source_review_status"], "human_review_required")
            self.assertIn("not fetched or verified", trace["source_verification_boundary"])
            self.assertEqual(len(trace["source_registry"]), 4)
            self.assertEqual(
                [item["kind"] for item in trace["certificate_inventory"]],
                ["lower", "upper", "upper", "upper"],
            )
            self.assertEqual(
                set(trace["certificate_inventory"][0]),
                {
                    "certificate_id",
                    "kind",
                    "source_id",
                    "theorem_locator",
                    "extraction_note",
                },
            )

            branches = read_json(result.assumption_branches)
            self.assertEqual(len(branches["patches"]), 1)
            patch = branches["patches"][0]
            self.assertEqual(patch["classification"], "strengthening")
            self.assertEqual(patch["operation"], "create_candidate_branch")
            self.assertFalse(patch["target_mutated"])
            self.assertEqual(patch["merge_status"], "not_merged")
            self.assertFalse(branches["invariants"]["target_mutated"])

            ledger = read_json(result.insight_ledger)
            self.assertEqual(
                [entry["kind"] for entry in ledger["entries"]],
                [
                    "registered_log_gap",
                    "rate_match_on_incompatible_assumption_branch",
                    "target_scope_rate_match",
                ],
            )

    def test_fraction_algebra_is_canonical_and_deterministic(self) -> None:
        scenario = three_round_scenario()
        scenario["rounds"][0]["upper_certificate"]["rate"]["polynomial_exponents"][
            "horizon"
        ] = "2/4"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            first = run_minimax_scenario(scenario_path, root / "first")
            second = run_minimax_scenario(scenario_path, root / "second")
            for name in (
                "evolution_trace.json",
                "assumption_branches.json",
                "insight_ledger.json",
                "manifest.json",
            ):
                self.assertEqual(
                    (first.output_dir / name).read_bytes(),
                    (second.output_dir / name).read_bytes(),
                )
            trace = read_json(first.evolution_trace)
            self.assertEqual(
                trace["rounds"][0]["rate_check"]["upper"]["polynomial_exponents"][
                    "horizon"
                ],
                "1/2",
            )

    def test_strict_signature_mismatch_is_not_comparable(self) -> None:
        scenario = three_round_scenario()
        scenario["rounds"] = [copy.deepcopy(scenario["rounds"][0])]
        scenario["rounds"][0]["upper_certificate"]["problem_signature"]["loss"] = (
            "simple_regret"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            result = run_minimax_scenario(scenario_path, root / "output")
            round_result = read_json(result.evolution_trace)["rounds"][0]
            self.assertEqual(round_result["signature_check"]["status"], "signature_mismatch")
            self.assertEqual(round_result["comparability"], "not_comparable")
            self.assertEqual(round_result["rate_check"]["status"], "not_comparable")
            self.assertEqual(round_result["certificate_status"], "scope_incompatible")
            self.assertEqual(round_result["status"], "not_comparable")
            trace = read_json(result.evolution_trace)
            self.assertIn(
                "No target-scope minimax rate match", trace["final"]["claim_boundary"]
            )
            self.assertEqual(
                validate_artifact(trace, "minimax_evolution", ROOT), []
            )

    def test_mixed_polynomial_exponent_signs_are_not_comparable(self) -> None:
        scenario = three_round_scenario()
        scenario["rounds"] = [copy.deepcopy(scenario["rounds"][2])]
        scenario["rounds"][0]["round_index"] = 1
        scenario["rounds"][0]["upper_certificate"]["rate"] = {
            "polynomial_exponents": {"arms": "2/3", "horizon": "1/3"},
            "log_exponents": {"horizon": "0"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            result = run_minimax_scenario(scenario_path, root / "output")
            round_result = read_json(result.evolution_trace)["rounds"][0]
            self.assertEqual(round_result["rate_check"]["status"], "not_comparable")
            self.assertIn("mixed", round_result["rate_check"]["reason"])
            self.assertEqual(round_result["certificate_status"], "rate_incomparable")
            self.assertEqual(round_result["comparability"], "not_comparable")
            self.assertFalse(round_result["rate_algebra_applicable_to_target"])
            self.assertEqual(round_result["status"], "not_comparable")
            trace = read_json(result.evolution_trace)
            self.assertEqual(
                validate_artifact(trace, "minimax_evolution", ROOT), []
            )

    def test_cross_family_coordinate_directions_are_not_comparable(self) -> None:
        scenario = three_round_scenario()
        scenario["rounds"] = [copy.deepcopy(scenario["rounds"][2])]
        scenario["rounds"][0]["round_index"] = 1
        scenario["rounds"][0]["upper_certificate"]["rate"] = {
            "polynomial_exponents": {"arms": "2/3", "horizon": "1/2"},
            "log_exponents": {"arms": "0", "horizon": "-1"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            result = run_minimax_scenario(scenario_path, root / "output")
            round_result = read_json(result.evolution_trace)["rounds"][0]
            self.assertEqual(round_result["rate_check"]["status"], "not_comparable")
            self.assertIn("joint growth regime", round_result["rate_check"]["reason"])
            self.assertEqual(round_result["certificate_status"], "rate_incomparable")
            self.assertEqual(round_result["status"], "not_comparable")

    def test_upper_rate_below_same_scope_lower_is_certificate_conflict(self) -> None:
        scenario = three_round_scenario()
        scenario["rounds"] = [copy.deepcopy(scenario["rounds"][2])]
        scenario["rounds"][0]["round_index"] = 1
        scenario["rounds"][0]["upper_certificate"]["rate"] = rate(horizon="1/3")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            result = run_minimax_scenario(scenario_path, root / "output")
            round_result = read_json(result.evolution_trace)["rounds"][0]
            self.assertEqual(round_result["comparability"], "comparable")
            self.assertEqual(round_result["rate_check"]["status"], "certificate_conflict")
            self.assertEqual(round_result["status"], "certificate_conflict")

    def test_registered_order_distinguishes_weakening_from_strengthening(self) -> None:
        scenario = three_round_scenario()
        scenario["target_assumptions"] = assumptions("known")
        scenario["lower_certificate"]["assumptions"] = assumptions("known")
        scenario["rounds"] = [copy.deepcopy(scenario["rounds"][0])]
        scenario["rounds"][0]["upper_certificate"]["assumptions"] = assumptions(
            "unknown"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            result = run_minimax_scenario(scenario_path, root / "output")
            branches = read_json(result.assumption_branches)
            self.assertEqual(branches["patches"][0]["classification"], "weakening")

    def test_unregistered_certificate_is_rejected_without_theory_claim(self) -> None:
        scenario = three_round_scenario()
        scenario["lower_certificate"]["registered"] = False
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            with self.assertRaises(MinimaxScenarioError):
                run_minimax_scenario(scenario_path, root / "output")

    def test_unknown_certificate_source_is_rejected(self) -> None:
        scenario = three_round_scenario()
        scenario["rounds"][0]["upper_certificate"]["source_id"] = "source-not-registered"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            with self.assertRaisesRegex(MinimaxScenarioError, "unknown source_id"):
                run_minimax_scenario(scenario_path, root / "output")

    def test_source_registration_and_proof_status_are_strict(self) -> None:
        cases = (
            ("registration_status", "unreviewed_extract"),
            ("proof_status", "proof_checked"),
        )
        for field, invalid_value in cases:
            with self.subTest(field=field):
                scenario = three_round_scenario()
                scenario["source_registry"][0][field] = invalid_value
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    scenario_path = root / "scenario.json"
                    write_scenario(scenario_path, scenario)
                    with self.assertRaises(MinimaxScenarioError):
                        run_minimax_scenario(scenario_path, root / "output")

    def test_normalized_scenario_digest_includes_source_registry(self) -> None:
        first_scenario = three_round_scenario()
        second_scenario = copy.deepcopy(first_scenario)
        second_scenario["source_registry"][0]["title"] = "Changed registered title"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_path = root / "first.json"
            second_path = root / "second.json"
            write_scenario(first_path, first_scenario)
            write_scenario(second_path, second_scenario)
            first = run_minimax_scenario(first_path, root / "first-output")
            second = run_minimax_scenario(second_path, root / "second-output")
            first_manifest = read_json(first.manifest)
            second_manifest = read_json(second.manifest)
            self.assertNotEqual(
                first_manifest["scenario_sha256"], second_manifest["scenario_sha256"]
            )

    def test_normalized_scenario_digest_binds_semantically_unused_valid_fields(self) -> None:
        first_scenario = three_round_scenario()
        second_scenario = copy.deepcopy(first_scenario)
        second_scenario["assumption_order"]["reward_support"] = [
            "unit_interval",
            "bounded_real",
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_path = root / "first.json"
            second_path = root / "second.json"
            write_scenario(first_path, first_scenario)
            write_scenario(second_path, second_scenario)
            first = run_minimax_scenario(first_path, root / "first-output")
            second = run_minimax_scenario(second_path, root / "second-output")
            self.assertNotEqual(
                read_json(first.manifest)["scenario_sha256"],
                read_json(second.manifest)["scenario_sha256"],
            )

    def test_runner_rejects_missing_schema_required_fields(self) -> None:
        mutations = (
            ("assumption_order", lambda value: value.pop("assumption_order")),
            (
                "round_algorithm_change",
                lambda value: value["rounds"][0].pop("algorithm_change"),
            ),
            (
                "round_search_hypothesis",
                lambda value: value["rounds"][0].pop("search_hypothesis"),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                scenario = three_round_scenario()
                mutate(scenario)
                root = Path(temporary)
                scenario_path = root / "scenario.json"
                write_scenario(scenario_path, scenario)
                self.assertTrue(
                    validate_artifact(scenario, "minimax_scenario", ROOT),
                    "schema should reject the same missing field",
                )
                with self.assertRaises(MinimaxScenarioError):
                    run_minimax_scenario(scenario_path, root / "output")

    def test_runner_rejects_non_integer_round_index(self) -> None:
        for invalid_index in (True, 1.0):
            with (
                self.subTest(invalid_index=invalid_index),
                tempfile.TemporaryDirectory() as temporary,
            ):
                scenario = three_round_scenario()
                scenario["rounds"][0]["round_index"] = invalid_index
                root = Path(temporary)
                scenario_path = root / "scenario.json"
                write_scenario(scenario_path, scenario)
                self.assertTrue(
                    validate_artifact(scenario, "minimax_scenario", ROOT),
                    "schema should reject the same non-integer index",
                )
                with self.assertRaises(MinimaxScenarioError):
                    run_minimax_scenario(scenario_path, root / "output")

    def test_runner_rejects_duplicate_json_object_keys(self) -> None:
        scenario_text = json.dumps(three_round_scenario(), ensure_ascii=False)
        original = (
            '"polynomial_exponents": {"arms": "1/2", "horizon": "1/2"}'
        )
        duplicate = (
            '"polynomial_exponents": {"arms": "1/2", '
            '"horizon": "1/3", "horizon": "1/2"}'
        )
        self.assertIn(original, scenario_text)
        scenario_text = scenario_text.replace(original, duplicate, 1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            scenario_path.write_text(scenario_text, encoding="utf-8")
            with self.assertRaisesRegex(
                MinimaxScenarioError, "duplicate JSON object key"
            ):
                run_minimax_scenario(scenario_path, root / "output")

    def test_runner_and_schema_reject_noncanonical_rate_variable_names(self) -> None:
        scenario = three_round_scenario()
        exponents = scenario["rounds"][0]["upper_certificate"]["rate"][
            "polynomial_exponents"
        ]
        exponents[" horizon"] = exponents.pop("horizon")
        self.assertTrue(validate_artifact(scenario, "minimax_scenario", ROOT))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, scenario)
            with self.assertRaisesRegex(MinimaxScenarioError, "invalid variable"):
                run_minimax_scenario(scenario_path, root / "output")

    def test_runner_rejects_extra_fields_at_every_structural_level(self) -> None:
        mutations = (
            ("root", lambda value: value.__setitem__("ignored", "not allowed")),
            (
                "source",
                lambda value: value["source_registry"][0].__setitem__(
                    "ignored", "not allowed"
                ),
            ),
            (
                "certificate",
                lambda value: value["lower_certificate"].__setitem__(
                    "ignored", "not allowed"
                ),
            ),
            (
                "signature",
                lambda value: value["lower_certificate"]["problem_signature"].__setitem__(
                    "ignored", "not allowed"
                ),
            ),
            (
                "rate",
                lambda value: value["lower_certificate"]["rate"].__setitem__(
                    "ignored", {}
                ),
            ),
            (
                "round",
                lambda value: value["rounds"][0].__setitem__(
                    "ignored", "not allowed"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                scenario = three_round_scenario()
                mutate(scenario)
                root = Path(temporary)
                scenario_path = root / "scenario.json"
                write_scenario(scenario_path, scenario)
                self.assertTrue(
                    validate_artifact(scenario, "minimax_scenario", ROOT),
                    "schema should reject the same extra field",
                )
                with self.assertRaises(MinimaxScenarioError):
                    run_minimax_scenario(scenario_path, root / "output")

    def test_valid_fixture_satisfies_public_input_schema(self) -> None:
        self.assertEqual(
            validate_artifact(three_round_scenario(), "minimax_scenario", ROOT), []
        )

    def test_output_schemas_reject_extra_and_invalid_key_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            write_scenario(scenario_path, three_round_scenario())
            result = run_minimax_scenario(scenario_path, root / "output")

            trace = read_json(result.evolution_trace)
            trace["rounds"][0]["ignored"] = "not allowed"
            trace["rounds"][1]["certificate_status"] = "unchecked"
            self.assertTrue(validate_artifact(trace, "minimax_evolution", ROOT))

            branches = read_json(result.assumption_branches)
            branches["patches"][0]["ignored"] = "not allowed"
            self.assertTrue(validate_artifact(branches, "assumption_branches", ROOT))

            ledger = read_json(result.insight_ledger)
            ledger["entries"][0]["rate_status"] = "unchecked"
            self.assertTrue(validate_artifact(ledger, "insight_ledger", ROOT))

    def test_cli_minimax_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scenario_path = root / "scenario.json"
            output = root / "cli-output"
            write_scenario(scenario_path, three_round_scenario())
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "minimax",
                        "--scenario",
                        str(scenario_path),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("[round 1] ucb-like-v1: log_gap", stdout.getvalue())
            self.assertIn(
                "FINAL certificate-rate status: minimax_rate_match", stdout.getvalue()
            )
            self.assertIn("human review required", stdout.getvalue())
            self.assertIn("proofs not checked", stdout.getvalue())
            self.assertEqual(
                stdout.getvalue().splitlines()[-1],
                "FINAL certificate-rate status: minimax_rate_match | "
                "human review required | source text and proofs not checked",
            )
            self.assertTrue((output / "manifest.json").is_file())

    def test_cli_minimax_uses_packaged_default_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stdout = io.StringIO()
            with (
                patch("verispiral.cli.Path.cwd", return_value=root),
                redirect_stdout(stdout),
            ):
                exit_code = main(["minimax"])
            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "demo" / "minimax-output" / "manifest.json").is_file())
            self.assertIn(
                "FINAL certificate-rate status: minimax_rate_match", stdout.getvalue()
            )

    def test_cli_minimax_resolves_relative_paths_from_invocation_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_scenario(root / "scenario.json", three_round_scenario())
            stdout = io.StringIO()
            with (
                patch("verispiral.cli.Path.cwd", return_value=root),
                patch(
                    "verispiral.cli.repository_root",
                    side_effect=AssertionError("minimax must not require a checkout"),
                ),
                redirect_stdout(stdout),
            ):
                exit_code = main(["minimax", "--scenario", "scenario.json"])
            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "demo" / "minimax-output" / "manifest.json").is_file())
            self.assertIn("proofs not checked", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
