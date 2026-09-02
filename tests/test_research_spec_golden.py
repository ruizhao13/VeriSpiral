from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verispiral.pipeline import repository_root
from verispiral.research_spec import run_research_specification_loop


def relative_files(root: Path) -> list[Path]:
    return sorted(
        path.relative_to(root) for path in root.rglob("*") if path.is_file()
    )


class ResearchSpecificationGoldenTests(unittest.TestCase):
    def test_tracked_research_loop_is_byte_exact(self) -> None:
        root = repository_root()
        expected = root / "examples" / "expected" / "research-specification"
        scenario = root / "examples" / "research_spec" / "minimax_coevolution_scenario.json"
        with tempfile.TemporaryDirectory() as temporary:
            actual = Path(temporary) / "actual"
            run_research_specification_loop(scenario, actual, root)
            self.assertEqual(relative_files(actual), relative_files(expected))
            for relative in relative_files(expected):
                self.assertEqual(
                    (actual / relative).read_bytes(),
                    (expected / relative).read_bytes(),
                    f"research-specification golden artifact is stale: {relative}",
                )


if __name__ == "__main__":
    unittest.main()
