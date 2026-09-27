"""Monthly refresh issues and the repository label set."""

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Literal, assert_never

import yaml
from pydantic import BaseModel, ConfigDict

from priorart.load import load_note, note_paths
from priorart.models import Note

NOTE_MARKER = "priorart-note-id"


class OpenIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int
    title: str
    body: str


class LabelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    color: str
    description: str


class RefreshAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["create", "update"]
    number: int | None = None
    title: str
    body: str
    note_id: str


def issue_body(note: Note, as_of: date) -> str:
    return (
        f"<!-- {NOTE_MARKER}: {note.id} -->\n\n"
        f"This fix note is due for its monthly re-check as of {as_of.isoformat()}.\n\n"
        f"- id: `{note.id}`\n"
        f"- title: {note.title}\n"
        f"- last refreshed: {note.last_refreshed.isoformat()}\n"
        f"- refresh due: {note.refresh_due.isoformat()}\n"
        f"- note: `content/notes/{note.id}.md`\n"
        f"- sources: `content/sources/{note.id}.json`\n\n"
        "Research bot: follow `AGENTS.md`. Re-verify the recipe, refresh sources "
        "(community posts no older than 3 months), and open a pull request. "
        "Do not copy personal paths, emails, tokens, or internal hostnames.\n"
    )


def due_notes(notes: list[Note], as_of: date) -> list[Note]:
    due = [note for note in notes if not note.example and note.refresh_due <= as_of]
    return sorted(due, key=lambda note: (note.refresh_due, note.id))


def load_real_notes(notes_dir: Path) -> list[Note]:
    sources_dir = notes_dir.parent / "sources"
    notes: list[Note] = []
    for path in note_paths(notes_dir):
        loaded = load_note(path, sources_dir)
        if not loaded.note.example:
            notes.append(loaded.note)
    return notes


def plan_refresh(notes: list[Note], issues: list[OpenIssue], as_of: date) -> list[RefreshAction]:
    open_by_id: dict[str, OpenIssue] = {}
    marker = f"<!-- {NOTE_MARKER}: "
    for issue in issues:
        for line in issue.body.splitlines():
            stripped = line.strip()
            if stripped.startswith(marker) and stripped.endswith("-->"):
                note_id = stripped[len(marker) : -3].strip()
                open_by_id[note_id] = issue
                break
    actions: list[RefreshAction] = []
    for note in due_notes(notes, as_of):
        body = issue_body(note, as_of)
        title = f"Refresh note: {note.id}"
        existing = open_by_id.get(note.id)
        if existing is None:
            actions.append(RefreshAction(action="create", title=title, body=body, note_id=note.id))
            continue
        if existing.body.strip() == body.strip() and existing.title == title:
            continue
        actions.append(
            RefreshAction(
                action="update",
                number=existing.number,
                title=title,
                body=body,
                note_id=note.id,
            )
        )
    return actions


def load_labels(path: Path) -> list[LabelSpec]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("labels file must be a list")
    return [LabelSpec.model_validate(item) for item in raw]


def _run_gh(args: list[str]) -> None:
    subprocess.run(["gh", *args], check=True)


def apply_refresh(actions: list[RefreshAction]) -> None:
    for action in actions:
        match action.action:
            case "create":
                _run_gh(
                    [
                        "issue",
                        "create",
                        "--title",
                        action.title,
                        "--body",
                        action.body,
                        "--label",
                        "research-bot",
                        "--label",
                        "refresh",
                    ]
                )
            case "update":
                if action.number is None:
                    raise ValueError(f"update for {action.note_id} is missing an issue number")
                _run_gh(
                    [
                        "issue",
                        "edit",
                        str(action.number),
                        "--title",
                        action.title,
                        "--body",
                        action.body,
                    ]
                )
            case _ as other:
                assert_never(other)


def fetch_open_refresh_issues() -> list[OpenIssue]:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--label",
            "refresh",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,body",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout or "[]")
    if not isinstance(payload, list):
        raise ValueError("gh issue list did not return a list")
    return [OpenIssue.model_validate(item) for item in payload]


def apply_labels(labels: list[LabelSpec]) -> None:
    for label in labels:
        _run_gh(
            [
                "label",
                "create",
                label.name,
                "--color",
                label.color.removeprefix("#"),
                "--description",
                label.description,
                "--force",
            ]
        )
