from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verispiral.minimax import run_minimax_scenario
from verispiral.pipeline import read_json, validate_artifact


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "examples" / "minimax_scenario.json"
EXPECTED = ROOT / "examples" / "expected" / "minimax"
ARTIFACTS = (
    ("evolution_trace.json", "minimax_evolution"),
    ("assumption_branches.json", "assumption_branches"),
    ("insight_ledger.json", "insight_ledger"),
    ("manifest.json", None),
)


class MinimaxGoldenTests(unittest.TestCase):
    def test_public_scenario_and_tracked_trace_are_valid_and_byte_exact(self) -> None:
        self.assertEqual(
            validate_artifact(read_json(SCENARIO), "minimax_scenario", ROOT), []
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "minimax"
            result = run_minimax_scenario(SCENARIO, output)
            self.assertEqual(result.final_status, "minimax_rate_match")
            for filename, kind in ARTIFACTS:
                generated = output / filename
                tracked = EXPECTED / filename
                self.assertEqual(generated.read_bytes(), tracked.read_bytes(), filename)
                if kind is not None:
                    self.assertEqual(
                        validate_artifact(read_json(generated), kind, ROOT), [], filename
                    )


if __name__ == "__main__":
    unittest.main()
