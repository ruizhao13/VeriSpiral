from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verispiral.evolution import run_evolution_feedback
from verispiral.pipeline import read_json, validate_artifact


ROOT = Path(__file__).resolve().parents[1]
FEEDBACK = ROOT / "examples" / "evolution" / "feedback_event.json"
EXPECTED = ROOT / "examples" / "expected" / "evolution"
ARTIFACTS = (
    ("evolution_proposal.json", "evolution_proposal"),
    ("evolution_patch.json", "evolution_patch"),
    ("manifest.json", "evolution_manifest"),
)


class EvolutionGoldenTests(unittest.TestCase):
    def test_feedback_run_is_schema_valid_and_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evolution"
            result = run_evolution_feedback(FEEDBACK, output, ROOT)
            self.assertEqual(result.decision_status, "proposed_for_human_review")
            self.assertEqual(result.apply_status, "not_applied")
            for filename, kind in ARTIFACTS:
                generated = output / filename
                tracked = EXPECTED / filename
                self.assertEqual(generated.read_bytes(), tracked.read_bytes(), filename)
                self.assertEqual(
                    validate_artifact(read_json(generated), kind, ROOT), [], filename
                )


if __name__ == "__main__":
    unittest.main()
