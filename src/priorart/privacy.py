"""Block secrets and personal machine details before they reach a public commit."""

import re
from dataclasses import dataclass
from pathlib import Path

_SKIP_DIRS = {
    ".git",
    ".venv",
    "dist",
    "_site",
    ".fastembed_cache",
    "fastembed_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
}
_SKIP_FILES = {"uv.lock"}
_MAX_BYTES = 1_000_000
_PLACEHOLDER_USERS = {
    "public",
    "default",
    "default user",
    "all users",
    "shared",
    "user",
    "username",
    "<user>",
    "<username>",
    "{user}",
    "{username}",
}
_EMAIL_HOSTS = {"example.com", "example.org", "example.net", "localhost"}
_TOKEN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secret-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("secret-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("secret-token", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("secret-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("secret-token", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("secret-token", re.compile(r"\bglpat-[A-Za-z0-9\-_]{20,}\b")),
)
_WIN_USER = re.compile(r"(?i)[a-z]:[\\/]+users[\\/]+([^\\/\s\"'`<>]+)")
_UNIX_HOME = re.compile(r"(?i)(?<![A-Za-z0-9])/(?:home|Users)/([^/\s\"'`<>]+)")
_EMAIL = re.compile(r"\b([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b")
_INTERNAL_HOST = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\.)+(?:internal|corp|lan|local|localdomain|home\.arpa)\b",
    re.IGNORECASE,
)
_UNC = re.compile(r"\\\\(?!<)([A-Za-z0-9][A-Za-z0-9._$-]{0,62})\\[A-Za-z0-9$._-]+")
_UNC_ALLOWED = {"localhost", "server", "host"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.detail}"


def _user_allowed(name: str) -> bool:
    return name.casefold().strip(".,;:") in _PLACEHOLDER_USERS


def _redact_token(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-2:]}"


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        findings.extend(_scan_line(path, line_number, line))
    return findings


def _scan_line(path: str, line_number: int, line: str) -> list[Finding]:
    findings: list[Finding] = []
    for match in _WIN_USER.finditer(line):
        user = match.group(1)
        if not _user_allowed(user):
            findings.append(Finding(path, line_number, "windows-user-path", match.group(0)))
    for match in _UNIX_HOME.finditer(line):
        user = match.group(1)
        if not _user_allowed(user):
            findings.append(Finding(path, line_number, "home-directory-path", match.group(0)))
    for match in _EMAIL.finditer(line):
        host = match.group(2).casefold()
        if host not in _EMAIL_HOSTS:
            findings.append(Finding(path, line_number, "email-address", f"***@{host}"))
    for rule, pattern in _TOKEN_RULES:
        for match in pattern.finditer(line):
            findings.append(Finding(path, line_number, rule, _redact_token(match.group(0))))
    for match in _INTERNAL_HOST.finditer(line):
        findings.append(Finding(path, line_number, "internal-hostname", match.group(0)))
    for match in _UNC.finditer(line):
        host = match.group(1)
        if host.casefold() not in _UNC_ALLOWED:
            findings.append(Finding(path, line_number, "unc-path", match.group(0)))
    return findings


def scan_path(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if root.is_file():
        return _scan_file(root, root.parent)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.name in _SKIP_FILES:
            continue
        findings.extend(_scan_file(path, root))
    return findings


def _scan_file(path: Path, root: Path) -> list[Finding]:
    if path.stat().st_size > _MAX_BYTES:
        return []
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return []
    display = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
    return scan_text(display, text)
