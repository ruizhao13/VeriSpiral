from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verispiral.pipeline import repository_root, run_demo


def relative_files(root: Path) -> list[Path]:
    return sorted(
        relative
        for path in root.rglob("*")
        if path.is_file()
        for relative in (path.relative_to(root),)
        # Each sibling demo has its own byte-exact golden test.
        if relative.parts[0] not in {
            "minimax", "evolution", "research-specification", "diagnosis", "path-trial", "workflow",
        }
    )


class GoldenRunTests(unittest.TestCase):
    def test_tracked_golden_run_is_byte_exact(self) -> None:
        root = repository_root()
        expected = root / "examples" / "expected"
        with tempfile.TemporaryDirectory() as temporary:
            actual = Path(temporary) / "actual"
            run_demo(root / "examples" / "candidate.json", actual, root)
            self.assertEqual(relative_files(actual), relative_files(expected))
            for relative in relative_files(expected):
                self.assertEqual(
                    (actual / relative).read_bytes(),
                    (expected / relative).read_bytes(),
                    f"golden artifact is stale: {relative}",
                )


if __name__ == "__main__":
    unittest.main()
