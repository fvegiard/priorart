from datetime import date
from pathlib import Path

from priorart.cli import main
from priorart.maintain import OpenIssue, TrackedNote, issue_body, load_labels, plan_refresh
from priorart.models import NoteKind

ROOT = Path(__file__).resolve().parents[1]


def _note(note_id: str, refreshed: str, due: str) -> TrackedNote:
    return TrackedNote(
        id=note_id,
        title="A real note that needs a refresh plan",
        last_refreshed=date.fromisoformat(refreshed),
        refresh_due=date.fromisoformat(due),
        example=False,
        kind=NoteKind.FIX,
    )


def test_plan_creates_then_skips_an_unchanged_issue() -> None:
    note = _note("debugger-map", "2026-09-01", "2026-09-20")
    created = plan_refresh([note], [], date(2026, 10, 1))
    assert [item.action for item in created] == ["create"]
    assert f"priorart-note-id: {note.id}" in created[0].body
    assert "knowledge/fixes/debugger-map.md" in created[0].body
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
