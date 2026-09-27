from datetime import date
from pathlib import Path

from priorart.cli import main
from priorart.maintain import OpenIssue, issue_body, load_labels, plan_refresh
from priorart.models import Note

ROOT = Path(__file__).resolve().parents[1]


def _note(note_id: str, refreshed: str, due: str) -> Note:
    return Note.model_validate(
        {
            "id": note_id,
            "title": "A real note that needs a refresh plan",
            "problem_summary": (
                "The fixture describes a repeatable failure and the change that clears it."
            ),
            "tags": ["fixture"],
            "platforms": [{"name": "windows", "versions": ["11"]}],
            "recipe": [
                {
                    "name": "Apply it",
                    "detail": "Run the fixture command in a clean shell.",
                    "language": "powershell",
                    "code": "Write-Output ok",
                }
            ],
            "verification": [
                {
                    "name": "Check it",
                    "detail": "The fixture command exits without an error.",
                    "language": "powershell",
                    "code": "Write-Output ok",
                }
            ],
            "sources": [
                {
                    "url": "https://example.com/fixture/0",
                    "title": "Fixture source 0 for the temporary note",
                    "type": "official-docs",
                    "published": "2026-01-15",
                    "retrieved": "2026-09-27",
                }
            ],
            "created": refreshed,
            "last_refreshed": refreshed,
            "refresh_due": due,
            "example": False,
        }
    )


def test_plan_creates_then_skips_an_unchanged_issue() -> None:
    note = _note("debugger-map", "2026-09-01", "2026-09-20")
    created = plan_refresh([note], [], date(2026, 10, 1))
    assert [item.action for item in created] == ["create"]
    assert f"priorart-note-id: {note.id}" in created[0].body
    existing = OpenIssue(number=7, title=created[0].title, body=created[0].body)
    assert plan_refresh([note], [existing], date(2026, 10, 1)) == []
    edited = OpenIssue(number=7, title="old", body=created[0].body)
    updated = plan_refresh([note], [edited], date(2026, 10, 1))
    assert updated[0].action == "update"
    assert updated[0].number == 7


def test_examples_and_future_notes_are_not_due() -> None:
    future = _note("later-note", "2026-09-20", "2026-10-15")
    assert plan_refresh([future], [], date(2026, 10, 1)) == []
    body = issue_body(future, date(2026, 10, 1))
    assert "later-note" in body


def test_label_file_has_the_research_bot_label() -> None:
    labels = {item.name: item for item in load_labels(ROOT / ".github" / "labels.yml")}
    assert "research-bot" in labels
    assert "refresh" in labels
    assert "outcome" in labels


def test_refresh_cli_on_the_sample_repo_is_idle() -> None:
    assert main(["refresh-issues", "--as-of", "2026-09-27"]) == 0
    assert main(["due", "--as-of", "2026-09-27"]) == 0
    assert main(["sync-labels"]) == 0
