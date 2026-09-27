"""Read domain guides, fix recipes, and their source packs."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

import yaml
from pydantic import ValidationError

from priorart.models import DomainGuide, FixNote, KnowledgeNote, NoteKind, SourcePack


@dataclass(frozen=True)
class LoadedNote:
    path: Path
    body: str
    note: KnowledgeNote
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


def note_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.md") if not path.name.startswith("_"))


def knowledge_dirs(root: Path) -> dict[NoteKind, tuple[Path, Path]]:
    knowledge = root / "knowledge"
    return {
        NoteKind.DOMAIN_GUIDE: (knowledge / "domains", knowledge / "sources" / "domains"),
        NoteKind.FIX: (knowledge / "fixes", knowledge / "sources" / "fixes"),
    }


def parse_note(raw: dict[str, object]) -> KnowledgeNote:
    kind = raw.get("type")
    if kind == NoteKind.DOMAIN_GUIDE:
        return DomainGuide.model_validate(raw)
    if kind == NoteKind.FIX:
        return FixNote.model_validate(raw)
    raise ValueError("type must be domain-guide or fix")


def load_note(path: Path, sources_dir: Path) -> LoadedNote:
    raw, body = split_frontmatter(path.read_text(encoding="utf-8"))
    note = parse_note(raw)
    pack_path = sources_dir / f"{path.stem}.json"
    if not pack_path.is_file():
        raise FileNotFoundError(pack_path)
    pack_raw = json.loads(pack_path.read_text(encoding="utf-8"))
    pack = SourcePack.model_validate(pack_raw)
    return LoadedNote(path=path, body=body, note=note, pack=pack, pack_path=pack_path)


def load_tree(root: Path) -> tuple[list[LoadedNote], list[str]]:
    """Load every note. Schema failures are returned as messages and skipped."""
    loaded: list[LoadedNote] = []
    errors: list[str] = []
    for kind, (notes_dir, sources_dir) in knowledge_dirs(root).items():
        if not notes_dir.is_dir():
            errors.append(f"{notes_dir.relative_to(root).as_posix()} is missing")
            continue
        for path in note_paths(notes_dir):
            label = _relative(path, root)
            try:
                item = load_note(path, sources_dir)
            except FileNotFoundError:
                errors.append(f"{label}: missing source pack {_pack_hint(kind, path.stem)}")
                continue
            except ValidationError as exc:
                errors.extend(f"{label}: {line}" for line in format_validation_error(exc))
                continue
            except (ValueError, OSError, UnicodeError) as exc:
                errors.append(f"{label}: {exc}")
                continue
            if item.note.type is not kind:
                errors.append(
                    f"{label}: type {item.note.type.value} does not belong in "
                    f"the {kind.value} folder"
                )
                continue
            loaded.append(item)
    return loaded, errors


def format_validation_error(exc: ValidationError) -> list[str]:
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"{location}: {error['msg']}")
    return lines


def _pack_hint(kind: NoteKind, stem: str) -> str:
    match kind:
        case NoteKind.DOMAIN_GUIDE:
            return f"knowledge/sources/domains/{stem}.json"
        case NoteKind.FIX:
            return f"knowledge/sources/fixes/{stem}.json"
        case _ as other:
            assert_never(other)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
