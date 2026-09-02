from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verispiral.cli import build_parser
from verispiral.pipeline import PipelineError, read_json


class CliValidationTests(unittest.TestCase):
    def test_pipeline_json_reader_rejects_duplicate_object_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"candidate":"first","candidate":"second"}\n', encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "duplicate JSON object key"):
                read_json(path)

    def test_validate_command_exposes_control_artifact_schemas(self) -> None:
        parser = build_parser()
        for kind in (
            "verification_receipt",
            "human_acceptance",
            "acceptance_registry",
        ):
            with self.subTest(kind=kind):
                args = parser.parse_args(
                    ["validate", "--kind", kind, "--input", "unused.json"]
                )
                self.assertEqual(args.kind, kind)


if __name__ == "__main__":
    unittest.main()
