from pathlib import Path

from priorart.privacy import scan_path, scan_text

ROOT = Path(__file__).resolve().parents[1]


def test_repository_has_no_privacy_findings() -> None:
    assert scan_path(ROOT) == []


def test_windows_profile_path_is_blocked() -> None:
    text = "log " + "C:\\Users\\" + "alice" + "\\src"
    findings = scan_text("note.md", text)
    assert [item.rule for item in findings] == ["windows-user-path"]


def test_profile_placeholder_is_allowed() -> None:
    assert scan_text("note.md", r"C:\Users\<USER>\src") == []
    assert scan_text("note.md", "/home/user/src") == []
    assert scan_text("note.md", "dev@example.com") == []


def test_email_token_host_and_unc_are_blocked() -> None:
    email = "ada" + "@" + "secret.test"
    token = "ghp_" + ("a" * 36)
    host = "build-box" + ".internal"
    unc = "\\\\" + "fileserver" + "\\share"
    text = "\n".join([email, token, host, unc])
    rules = {item.rule for item in scan_text("note.md", text)}
    assert rules == {"email-address", "secret-token", "internal-hostname", "unc-path"}


def test_scan_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "leak.md"
    path.write_text("mail " + "ada" + "@" + "secret.test" + "\n", encoding="utf-8")
    findings = scan_path(path)
    assert len(findings) == 1
    assert findings[0].rule == "email-address"
    assert findings[0].detail == "***@secret.test"
