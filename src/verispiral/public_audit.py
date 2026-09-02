"""Conservative, value-redacting checks for a public research-agent repository."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAX_BYTES = 20 * 1024 * 1024
SKIPPED_DIRECTORIES = {".git"}
FORBIDDEN_DIRECTORIES = {
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "data",
    "datasets",
    "inputs",
    "memory",
    "node_modules",
    "private",
    "projects",
    "raw",
    "raw_data",
    "secrets",
    "tmp",
    "venv",
}
FORBIDDEN_FILENAMES = {".env", ".rhistory", "credentials.json"}
FORBIDDEN_EXTENSIONS = {
    ".7z",
    ".bin",
    ".ckpt",
    ".csv",
    ".db",
    ".dmg",
    ".gz",
    ".key",
    ".npy",
    ".npz",
    ".p12",
    ".parquet",
    ".pdf",
    ".pem",
    ".pfx",
    ".pickle",
    ".pkl",
    ".sqlite",
    ".tar",
    ".zip",
}

TEXT_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "local-absolute-path",
        re.compile(r"(?:/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._-]+\\\\)"),
        "contains an obvious machine-local absolute path",
    ),
    (
        "aws-access-key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "contains a value shaped like an AWS access key",
    ),
    (
        "openai-style-key",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "contains a value shaped like an API key",
    ),
    (
        "github-token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
        "contains a value shaped like a GitHub token",
    ),
    (
        "private-key",
        re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
        "contains a private-key header",
    ),
    (
        "assigned-secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
        ),
        "contains a credential-like assignment",
    ),
)


@dataclass(frozen=True, order=True)
class AuditFinding:
    path: str
    rule: str
    message: str
    line: int | None = None

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location} [{self.rule}] {self.message}"


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_forbidden_directory(name: str) -> bool:
    normalized = name.casefold()
    return normalized in FORBIDDEN_DIRECTORIES or normalized.startswith(".venv-")


def _is_forbidden_filename(name: str) -> bool:
    normalized = name.casefold()
    return normalized in FORBIDDEN_FILENAMES or normalized.startswith(".env.")


def _inspect_symlink(base: Path, path: Path) -> AuditFinding | None:
    try:
        target = path.resolve(strict=True)
        target.relative_to(base)
    except (OSError, ValueError):
        return AuditFinding(
            _relative(base, path),
            "external-symlink",
            "symbolic link is broken or resolves outside the repository",
        )
    return None


def _collect_public_files(root: Path) -> tuple[list[Path], list[AuditFinding]]:
    files: list[Path] = []
    findings: list[AuditFinding] = []
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            findings.append(
                AuditFinding(_relative(root, current), "unreadable", "could not list directory")
            )
            continue
        for entry in entries:
            normalized = entry.name.casefold()
            if normalized in SKIPPED_DIRECTORIES:
                continue
            if entry.is_symlink():
                finding = _inspect_symlink(root, entry)
                if finding:
                    findings.append(finding)
                elif entry.is_file():
                    files.append(entry)
                continue
            if entry.is_dir():
                if _is_forbidden_directory(entry.name):
                    findings.append(
                        AuditFinding(
                            _relative(root, entry),
                            "forbidden-directory",
                            "directory is excluded from the public-release profile",
                        )
                    )
                else:
                    pending.append(entry)
            elif entry.is_file():
                files.append(entry)
    return files, findings


def _looks_binary(data: bytes) -> bool:
    return b"\x00" in data


def audit_tree(
    root: str | Path, max_file_bytes: int = DEFAULT_MAX_BYTES
) -> list[AuditFinding]:
    base = Path(root).resolve()
    files, findings = _collect_public_files(base)

    for path in files:
        relative = _relative(base, path)
        if _is_forbidden_filename(path.name):
            findings.append(
                AuditFinding(
                    relative,
                    "forbidden-filename",
                    "file is excluded from the public-release profile",
                )
            )
        if path.suffix.casefold() in FORBIDDEN_EXTENSIONS:
            findings.append(
                AuditFinding(
                    relative,
                    "forbidden-extension",
                    "file type is excluded from the public-release profile",
                )
            )
        try:
            size = path.stat().st_size
        except OSError:
            findings.append(AuditFinding(relative, "unreadable", "could not inspect file"))
            continue
        if size > max_file_bytes:
            findings.append(
                AuditFinding(
                    relative,
                    "large-file",
                    f"file is {size} bytes; public limit is {max_file_bytes} bytes",
                )
            )
            # A file above the release limit already fails closed.  Avoid
            # loading an arbitrarily large file merely to add redundant text
            # findings.
            continue
        try:
            data = path.read_bytes()
        except OSError:
            findings.append(AuditFinding(relative, "unreadable", "could not read file"))
            continue
        if _looks_binary(data):
            continue
        text = data.decode("utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for rule, pattern, message in TEXT_RULES:
                if pattern.search(line):
                    findings.append(AuditFinding(relative, rule, message, line_number))

    return sorted(set(findings))
