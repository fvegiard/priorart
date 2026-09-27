"""Read note markdown and the matching source pack."""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from priorart.models import Note, SourcePack


@dataclass(frozen=True)
class LoadedNote:
    path: Path
    body: str
    note: Note
    pack: SourcePack
    pack_path: Path


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        raise ValueError("note must start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("frontmatter is not closed with ---")
    loaded = yaml.safe_load(text[4:end])
    if not isinstance(loaded, dict):
        raise ValueError("frontmatter must be a mapping")
    body = text[end + 5 :].lstrip("\n")
    return loaded, body


def note_paths(notes_dir: Path) -> list[Path]:
    return sorted(path for path in notes_dir.glob("*.md") if not path.name.startswith("_"))


def load_note(path: Path, sources_dir: Path) -> LoadedNote:
    raw, body = split_frontmatter(path.read_text(encoding="utf-8"))
    note = Note.model_validate(raw)
    pack_path = sources_dir / f"{path.stem}.json"
    if not pack_path.is_file():
        raise FileNotFoundError(pack_path)
    pack_raw = json.loads(pack_path.read_text(encoding="utf-8"))
    pack = SourcePack.model_validate(pack_raw)
    return LoadedNote(path=path, body=body, note=note, pack=pack, pack_path=pack_path)


def format_validation_error(exc: ValidationError) -> list[str]:
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"{location}: {error['msg']}")
    return lines
