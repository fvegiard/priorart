"""Cross-file checks that the note schema cannot express on its own."""

from pathlib import Path

from pydantic import ValidationError

from priorart.constants import MIN_REAL_SOURCES
from priorart.load import LoadedNote, format_validation_error, load_note, note_paths
from priorart.models import Source


def repo_root_from(start: Path | None = None) -> Path:
    seeds: list[Path] = []
    if start is not None:
        seeds.append(start.resolve())
    else:
        seeds.append(Path.cwd().resolve())
        seeds.append(Path(__file__).resolve())
    seen: set[Path] = set()
    for seed in seeds:
        for candidate in [seed, *seed.parents]:
            if candidate in seen:
                continue
            seen.add(candidate)
            if (candidate / "content" / "notes").is_dir() and (
                candidate / "pyproject.toml"
            ).is_file():
                return candidate
    raise FileNotFoundError("could not find the priorart repository root")


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def cross_file_errors(loaded: LoadedNote) -> list[str]:
    note = loaded.note
    where = loaded.path.as_posix()
    errors: list[str] = []
    if loaded.path.stem != note.id:
        errors.append(f"{where}: file name must match id {note.id}")
    if loaded.pack.note_id != note.id:
        errors.append(f"{loaded.pack_path.as_posix()}: note_id must be {note.id}")
    if not note.example and len(loaded.pack.references) < MIN_REAL_SOURCES:
        errors.append(
            f"{loaded.pack_path.as_posix()}: source pack has {len(loaded.pack.references)} "
            f"references; real notes need at least {MIN_REAL_SOURCES}"
        )
    if note.example and "example only" not in loaded.body.casefold():
        errors.append(f"{where}: example notes must include an 'Example only' banner in the body")
    by_url = {item.url: item for item in loaded.pack.references}
    for source in note.sources:
        packed = by_url.get(source.url)
        if packed is None:
            errors.append(f"{where}: cited source is missing from the source pack: {source.url}")
            continue
        packed_source = Source(
            url=packed.url,
            title=packed.title,
            type=packed.type,
            published=packed.published,
            retrieved=packed.retrieved,
        )
        if packed_source != source:
            errors.append(f"{where}: cited source does not match the pack entry for {source.url}")
    return errors


def validate_repository(root: Path) -> list[str]:
    notes_dir = root / "content" / "notes"
    sources_dir = root / "content" / "sources"
    if not notes_dir.is_dir():
        return ["content/notes is missing"]
    errors: list[str] = []
    seen_ids: set[str] = set()
    for path in note_paths(notes_dir):
        label = relative(path, root)
        try:
            loaded = load_note(path, sources_dir)
        except FileNotFoundError:
            errors.append(f"{label}: missing source pack content/sources/{path.stem}.json")
            continue
        except ValidationError as exc:
            errors.extend(f"{label}: {line}" for line in format_validation_error(exc))
            continue
        except (ValueError, OSError, UnicodeError) as exc:
            errors.append(f"{label}: {exc}")
            continue
        if loaded.note.id in seen_ids:
            errors.append(f"{label}: duplicate id {loaded.note.id}")
        seen_ids.add(loaded.note.id)
        errors.extend(_relative_errors(loaded, root))
    if sources_dir.is_dir():
        for pack_path in sorted(sources_dir.glob("*.json")):
            if pack_path.name.startswith("_"):
                continue
            if pack_path.stem not in {path.stem for path in note_paths(notes_dir)}:
                errors.append(f"{relative(pack_path, root)}: no matching note")
    return errors


def _relative_errors(loaded: LoadedNote, root: Path) -> list[str]:
    rewritten: list[str] = []
    for message in cross_file_errors(loaded):
        for raw in (loaded.path, loaded.pack_path):
            message = message.replace(raw.as_posix(), relative(raw, root))
        rewritten.append(message)
    return rewritten
