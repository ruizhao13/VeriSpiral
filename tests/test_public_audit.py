from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from verispiral.public_audit import audit_tree


class PublicAuditTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "safe.txt").write_text("portable public text\n", encoding="utf-8")
            self.assertEqual(audit_tree(root), [])

    def test_sensitive_values_are_classified_without_echoing_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = "sk-" + "z" * 24
            local_path = "/" + "Users/example/private/file"
            (root / "notes.txt").write_text(
                f"path={local_path}\napi_key='{secret}'\n",
                encoding="utf-8",
            )
            findings = audit_tree(root)
            rendered = "\n".join(item.render() for item in findings)
            self.assertIn("local-absolute-path", rendered)
            self.assertIn("openai-style-key", rendered)
            self.assertIn("assigned-secret", rendered)
            self.assertNotIn(secret, rendered)

    def test_large_file_and_forbidden_extension_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "weights.pkl").write_bytes(b"12345")
            rules = {finding.rule for finding in audit_tree(root, max_file_bytes=4)}
            self.assertEqual(rules, {"forbidden-extension", "large-file"})

    def test_allowed_large_text_is_still_scanned_for_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            secret = "sk-" + "z" * 24
            payload = "public text\n" * 200_000 + f"token={secret}\n"
            (root / "large-notes.txt").write_text(payload, encoding="utf-8")

            findings = audit_tree(root)
            rendered = "\n".join(item.render() for item in findings)

            self.assertIn("openai-style-key", rendered)
            self.assertNotIn(secret, rendered)

    def test_release_exclusions_are_case_insensitive_and_pruned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("ProJecTs", "DATA", "DataSets", "RAW", "Tmp", ".VENV-review"):
                (root / name).mkdir()
            findings = audit_tree(root)
            self.assertEqual(
                {finding.path for finding in findings if finding.rule == "forbidden-directory"},
                {"ProJecTs", "DATA", "DataSets", "RAW", "Tmp", ".VENV-review"},
            )

    def test_ignored_data_extensions_are_forbidden_case_insensitively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            names = (
                "paper.PDF",
                "bundle.zip",
                "archive.tar",
                "archive.tar.gz",
                "table.csv",
                "array.npy",
                "arrays.npz",
                "weights.bin",
            )
            for name in names:
                (root / name).write_bytes(b"public-test")
            flagged = {
                finding.path for finding in audit_tree(root) if finding.rule == "forbidden-extension"
            }
            self.assertEqual(flagged, set(names))

    def test_demo_output_directory_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "demo" / "output"
            output.mkdir(parents=True)
            (output / "manifest.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(audit_tree(root), [])


if __name__ == "__main__":
    unittest.main()
