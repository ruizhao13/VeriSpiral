from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import tempfile
import time
import unittest

from verispiral.case_execution import digest_json, read_json_object, run_program


class CaseExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()

    def program(self, source: str) -> Path:
        path = self.directory / "program.py"
        path.write_text(source, encoding="utf-8")
        return path

    def assert_error(self, receipt: dict, text: str) -> None:
        self.assertEqual(receipt["status"], "error")
        self.assertIsNone(receipt["output"])
        self.assertIsNone(receipt["output_sha256"])
        self.assertIn(text, receipt["error"])
        self.assertIsInstance(receipt["elapsed_seconds"], float)
        self.assertGreaterEqual(receipt["elapsed_seconds"], 0)

    def test_valid_child_binds_request_program_and_canonical_output(self) -> None:
        path = self.program(
            "import json, os, sys\n"
            "request = json.load(sys.stdin)\n"
            "print(json.dumps({'request': request, 'cwd': os.getcwd(), "
            "'isolated': sys.flags.isolated, 'no_bytecode': sys.dont_write_bytecode}))\n")
        request = {"候选": [2, 1], "settings": {"b": 2, "a": True}}
        receipt = run_program(path, request)
        self.assertEqual(set(receipt), {"status", "program_sha256", "request_sha256",
                                       "output", "output_sha256", "error", "elapsed_seconds"})
        self.assertEqual(receipt["status"], "ok")
        self.assertIsNone(receipt["error"])
        self.assertEqual(receipt["program_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(receipt["request_sha256"], digest_json(request))
        self.assertEqual(receipt["output_sha256"], digest_json(receipt["output"]))
        self.assertEqual(receipt["output"]["request"], request)
        self.assertEqual(receipt["output"]["cwd"], str(self.directory))
        self.assertEqual(receipt["output"]["isolated"], 1)
        self.assertTrue(receipt["output"]["no_bytecode"])
        self.assertFalse((self.directory / "__pycache__").exists())

    def test_transport_success_does_not_claim_domain_acceptance(self) -> None:
        receipt = run_program(self.program('print(\'{"status":"rejected"}\')\n'), {})
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["output"], {"status": "rejected"})

    def test_stdout_must_be_exactly_one_object(self) -> None:
        for output in ('[]', 'null', '', '{} {}', 'log\n{}', '{}\ntrailing'):
            with self.subTest(output=output):
                receipt = run_program(self.program("print(" + repr(output) + ")\n"), {})
                self.assertEqual(receipt["status"], "error")
                self.assertIsNone(receipt["output"])

    def test_rejects_nested_duplicate_keys_and_nonfinite_numbers(self) -> None:
        for output in ('{"x":1,"x":2}', '{"nested":{"x":1,"x":2}}',
                       '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1e999}'):
            with self.subTest(output=output):
                receipt = run_program(self.program("print(" + repr(output) + ")\n"), {})
                expected = "duplicate" if '"x":1,"x":2' in output else "non-finite"
                self.assert_error(receipt, expected)

    def test_invalid_utf8_is_not_replaced_into_a_success(self) -> None:
        receipt = run_program(self.program("import os\nos.write(1, b'{\"x\":\"\\xff\"}')\n"), {})
        self.assert_error(receipt, "UnicodeDecodeError")

    def test_nonzero_exit_cannot_forge_a_success_receipt(self) -> None:
        receipt = run_program(self.program(
            "import sys\nprint('{\"status\":\"ok\"}')\n"
            "print('synthetic failure', file=sys.stderr)\nsys.exit(7)\n"), {})
        self.assert_error(receipt, "exited with code 7")
        self.assertIn("synthetic failure", receipt["error"])

    def test_stderr_is_allowed_but_does_not_corrupt_json(self) -> None:
        receipt = run_program(self.program(
            "import sys\nprint('diagnostic', file=sys.stderr)\nprint('{}')\n"), {})
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["output"], {})

    def test_timeout_reaps_child(self) -> None:
        path = self.program(
            "import os, time\nfrom pathlib import Path\n"
            "Path('child.pid').write_text(str(os.getpid()))\ntime.sleep(30)\n")
        receipt = run_program(path, {}, timeout_seconds=0.3)
        self.assert_error(receipt, "timed out")
        self.assertLess(receipt["elapsed_seconds"], 3.0)
        pid_file = self.directory / "child.pid"
        self.assertTrue(pid_file.exists(), "child must actually start for this test")
        if os.name == "posix":
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 0)

    def test_blocked_large_stdin_does_not_deadlock_timeout(self) -> None:
        receipt = run_program(self.program("import time\ntime.sleep(30)\n"),
                              {"input": "x" * 300_000}, timeout_seconds=0.2)
        self.assert_error(receipt, "timed out")
        self.assertLess(receipt["elapsed_seconds"], 3.0)

    def test_unbounded_stdout_and_stderr_hit_the_combined_limit(self) -> None:
        for descriptor in (1, 2):
            with self.subTest(descriptor=descriptor):
                receipt = run_program(self.program(
                    "import os\nwhile True:\n    os.write(" + str(descriptor)
                    + ", b'x' * 16384)\n"), {}, max_output_bytes=5000, timeout_seconds=2)
                self.assert_error(receipt, "output limit exceeded")
                self.assertLess(receipt["elapsed_seconds"], 3.0)

    def test_output_limit_exact_boundary_and_combined_streams(self) -> None:
        path = self.program("import os\nos.write(1, b'{}')\n")
        self.assertEqual(run_program(path, {}, max_output_bytes=2)["status"], "ok")
        self.assert_error(run_program(path, {}, max_output_bytes=1), "output limit")
        path = self.program("import os\nos.write(1, b'{}')\nos.write(2, b'x')\n")
        self.assert_error(run_program(path, {}, max_output_bytes=2), "output limit")

    def test_program_self_modification_invalidates_otherwise_valid_output(self) -> None:
        path = self.program(
            "from pathlib import Path\n"
            "with Path(__file__).open('a') as stream:\n    stream.write('# changed\\n')\n"
            "print('{}')\n")
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        receipt = run_program(path, {})
        self.assert_error(receipt, "program changed during execution")
        self.assertEqual(receipt["program_sha256"], before)
        self.assertNotEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_program_deletion_invalidates_otherwise_valid_output(self) -> None:
        receipt = run_program(self.program(
            "from pathlib import Path\nPath(__file__).unlink()\nprint('{}')\n"), {})
        self.assert_error(receipt, "program unavailable after execution")

    def test_preflight_failures_do_not_execute_program(self) -> None:
        path = self.program("from pathlib import Path\nPath('executed').touch()\nprint('{}')\n")
        for request in ({"x": math.nan}, {"x": math.inf}, {1: "key"}, {"x": (1, 2)}, None):
            with self.subTest(request=request):
                receipt = run_program(path, request)
                self.assertEqual(receipt["status"], "error")
                self.assertIsNone(receipt["request_sha256"])
                self.assertIsNone(receipt["output_sha256"])
                self.assertFalse((self.directory / "executed").exists())
        missing = run_program(self.directory / "missing.py", {})
        self.assert_error(missing, "FileNotFoundError")
        self.assertIsNone(missing["program_sha256"])

    def test_invalid_runtime_limits_are_error_receipts(self) -> None:
        path = self.program("print('{}')\n")
        for limit in (0, -1, True, math.nan, math.inf):
            with self.subTest(timeout=limit):
                self.assert_error(run_program(path, {}, timeout_seconds=limit), "timeout_seconds")
        for limit in (0, -1, True, 3.5):
            with self.subTest(output_limit=limit):
                self.assert_error(run_program(path, {}, max_output_bytes=limit), "max_output_bytes")

    def test_digest_json_is_canonical_and_rejects_non_json_values(self) -> None:
        self.assertEqual(digest_json({"a": 1, "b": 2}), digest_json({"b": 2, "a": 1}))
        expected = hashlib.sha256('{"文字":"值"}'.encode("utf-8")).hexdigest()
        self.assertEqual(digest_json({"文字": "值"}), expected)
        for value in (float("nan"), float("inf"), {"x": -float("inf")}, {2: "key"}, (1, 2)):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    digest_json(value)

    def test_read_json_object_enforces_same_strict_contract(self) -> None:
        path = self.directory / "object.json"
        path.write_text(' {"nested":[1,true,null,"文"]}\n', encoding="utf-8")
        self.assertEqual(read_json_object(path), {"nested": [1, True, None, "文"]})
        for text in ('{} {}', '[]', '{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_json_object(path)

    @unittest.skipUnless(os.name == "posix", "POSIX process-group cleanup")
    def test_descendant_holding_output_pipe_is_stopped_at_timeout(self) -> None:
        path = self.program(
            "import subprocess, sys\n"
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "print('{}')\n")
        started = time.monotonic()
        receipt = run_program(path, {}, timeout_seconds=0.3)
        self.assert_error(receipt, "timed out")
        self.assertLess(time.monotonic() - started, 3.0)


if __name__ == "__main__":
    unittest.main()
