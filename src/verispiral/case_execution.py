"""Receipts for explicitly authorized local Python programs.

This is an execution boundary, not a security sandbox: programs retain the
user's filesystem/network access, and the program hash is not a dependency
closure. The caller authorizes paths, validates output semantics, persists
receipts and charges budgets. POSIX process groups are cleaned up best-effort;
detached descendants and non-POSIX process trees are not contained.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
from typing import Any


def _validate_json(value: Any) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return
    if type(value) is list:
        for item in value:
            _validate_json(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            _validate_json(item)
        return
    raise ValueError("value is not a built-in JSON value")


def _json_bytes(value: Any) -> bytes:
    _validate_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest_json(value: Any) -> str:
    """SHA-256 of sorted-key, compact UTF-8 JSON; reject non-JSON values."""
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _pairs_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise ValueError("non-finite JSON number: " + value)


def _decode_object(content: bytes) -> dict:
    value = json.loads(content.decode("utf-8"), object_pairs_hook=_pairs_object,
                       parse_constant=_nonfinite)
    if type(value) is not dict:
        raise ValueError("JSON output must be a single object")
    # A legal numeric token such as 1e999 can overflow the float parser.
    _validate_json(value)
    return value


def read_json_object(path: Path) -> dict:
    """Read one strict UTF-8 JSON object; raise on I/O or JSON violations."""
    return _decode_object(Path(path).read_bytes())


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reap(process: subprocess.Popen) -> str | None:
    """Kill the owned process/group, including after an early parent exit."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass
    except OSError as error:
        return "process cleanup failed: " + str(error)
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        return "process could not be reaped after termination"
    return None


def _exchange(process: subprocess.Popen, payload: bytes, deadline: float,
              max_output_bytes: int) -> tuple[bytes, bytes, int]:
    # Bounded queue plus fixed-size reads prevent communicate()-style unlimited
    # capture. The limit counts stdout AND stderr, even if stderr is discarded.
    events: queue.Queue = queue.Queue(maxsize=8)
    stop = threading.Event()

    def emit(name: str, data: bytes | None | OSError) -> None:
        while not stop.is_set():
            try:
                events.put((name, data), timeout=0.05)
                return
            except queue.Full:
                pass

    def read_stream(name: str, stream: Any) -> None:
        try:
            while not stop.is_set():
                chunk = stream.read(16384)
                if not chunk:
                    break
                emit(name, chunk)
        except OSError as error:
            emit(name, error)
        finally:
            stream.close()
            emit(name, None)

    def write_request() -> None:
        try:
            remaining = memoryview(payload)
            while remaining and not stop.is_set():
                written = process.stdin.write(remaining[:16384])
                if not written:
                    break
                remaining = remaining[written:]
        except BrokenPipeError:
            pass  # Programs may intentionally ignore their request.
        except OSError as error:
            emit("stdin", error)
        finally:
            process.stdin.close()

    threads = [
        threading.Thread(target=read_stream, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=read_stream, args=("stderr", process.stderr), daemon=True),
        threading.Thread(target=write_request, daemon=True),
    ]
    for thread in threads:
        thread.start()
    stdout = bytearray()
    stderr = bytearray()
    total = 0
    closed = set()
    try:
        while len(closed) < 2:
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                raise TimeoutError("program timed out")
            try:
                name, data = events.get(timeout=remaining_time)
            except queue.Empty:
                raise TimeoutError("program timed out") from None
            if isinstance(data, OSError):
                raise data
            if data is None:
                closed.add(name)
                continue
            total += len(data)
            if total > max_output_bytes:
                raise ValueError("combined stdout/stderr output limit exceeded")
            if name == "stdout":
                stdout.extend(data)
            else:
                stderr.extend(data[:max(0, 4096 - len(stderr))])
        try:
            returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise TimeoutError("program timed out") from None
        return bytes(stdout), bytes(stderr), returncode
    finally:
        stop.set()
        cleanup_error = _reap(process)
        for thread in threads:
            thread.join(timeout=0.25)
        if cleanup_error:
            raise OSError(cleanup_error)


def run_program(program: Path, request: dict, *, timeout_seconds: float = 10.0,
                max_output_bytes: int = 1_000_000) -> dict:
    """Run ``sys.executable -I -B program`` with strict JSON on stdin.

    The working directory is the resolved program's parent. Output is accepted
    only after zero exit, bounded capture, strict decoding and unchanged file
    hash. Hashes of JSON use digest_json(), not raw whitespace/ordering. Hashes
    unavailable during preflight errors are None. Failed receipts never expose
    an apparently accepted output. Timeout covers process startup/exchange;
    bounded cleanup and hashing may add to elapsed time. Pre/post hashing does
    not detect a transient edit restored before the final check.
    """
    started = time.monotonic()
    receipt = {"status": "error", "program_sha256": None,
               "request_sha256": None, "output": None, "output_sha256": None,
               "error": None, "elapsed_seconds": 0.0}
    resolved: Path | None = None
    process: subprocess.Popen | None = None
    output: dict | None = None
    try:
        if (type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be positive and finite")
        if type(max_output_bytes) is not int or max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be a positive integer")
        resolved = Path(program).resolve(strict=True)
        receipt["program_sha256"] = _digest_file(resolved)
        if type(request) is not dict:
            raise ValueError("request must be a JSON object")
        encoded = _json_bytes(request)
        receipt["request_sha256"] = hashlib.sha256(encoded).hexdigest()
        deadline = time.monotonic() + timeout_seconds
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", str(resolved)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=resolved.parent,
            bufsize=0, start_new_session=(os.name == "posix"),
        )
        stdout, stderr, returncode = _exchange(
            process, encoded + b"\n", deadline, max_output_bytes)
        if returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise ValueError("program exited with code " + str(returncode)
                             + (": " + detail if detail else ""))
        output = _decode_object(stdout)
        receipt["output_sha256"] = digest_json(output)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError,
            subprocess.SubprocessError) as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)[:4096]
    finally:
        if process is not None:
            cleanup_error = _reap(process)
            if cleanup_error:
                receipt["error"] = cleanup_error
            try:
                if _digest_file(resolved) != receipt["program_sha256"]:
                    receipt["error"] = "program changed during execution"
            except OSError as error:
                receipt["error"] = "program unavailable after execution: " + str(error)[:4096]
        if receipt["error"] is None:
            receipt["status"] = "ok"
            receipt["output"] = output
        else:
            receipt["output_sha256"] = None
        receipt["elapsed_seconds"] = time.monotonic() - started
    return receipt
