"""Cross-file checks that a single note schema cannot express."""

from pathlib import Path
from typing import assert_never

from priorart.constants import MIN_REAL_SOURCES
from priorart.load import LoadedNote, knowledge_dirs, load_tree, note_paths
from priorart.models import DomainGuide, FixNote, Source


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
            if (candidate / "knowledge" / "domains").is_dir() and (
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
    match note:
        case DomainGuide():
            if note.sources_count != len(loaded.pack.references):
                errors.append(
                    f"{where}: sources_count is {note.sources_count} "
                    f"but the pack has {len(loaded.pack.references)} references"
                )
        case FixNote():
            errors.extend(_cited_source_errors(loaded))
        case _ as other:
            assert_never(other)
    return errors


def _cited_source_errors(loaded: LoadedNote) -> list[str]:
    note = loaded.note
    if not isinstance(note, FixNote):
        return []
    where = loaded.path.as_posix()
    errors: list[str] = []
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


def link_errors(notes: list[LoadedNote], root: Path) -> list[str]:
    """Domain ids on fixes, and fix ids on domain guides, must exist and agree."""
    domains = {item.note.id: item for item in notes if isinstance(item.note, DomainGuide)}
    fixes = {item.note.id: item for item in notes if isinstance(item.note, FixNote)}
    errors: list[str] = []
    for item in notes:
        where = relative(item.path, root)
        match item.note:
            case FixNote() as fix:
                for domain_id in fix.domains:
                    guide = domains.get(domain_id)
                    if guide is None:
                        errors.append(f"{where}: domains link does not resolve: {domain_id}")
                        continue
                    linked = guide.note
                    if isinstance(linked, DomainGuide) and fix.id not in linked.related_fixes:
                        errors.append(
                            f"{where}: domain {domain_id} does not list this fix in related_fixes"
                        )
            case DomainGuide() as guide:
                for fix_id in guide.related_fixes:
                    linked = fixes.get(fix_id)
                    if linked is None:
                        errors.append(f"{where}: related_fixes link does not resolve: {fix_id}")
                        continue
                    fix = linked.note
                    if isinstance(fix, FixNote) and guide.id not in fix.domains:
                        errors.append(f"{where}: fix {fix_id} does not list this domain in domains")
            case _ as other:
                assert_never(other)
    return errors


def validate_repository(root: Path) -> list[str]:
    loaded, errors = load_tree(root)
    seen: set[str] = set()
    for item in loaded:
        label = relative(item.path, root)
        if item.note.id in seen:
            errors.append(f"{label}: duplicate id {item.note.id}")
        seen.add(item.note.id)
        errors.extend(_relative_errors(item, root))
    errors.extend(link_errors(loaded, root))
    errors.extend(_orphan_packs(root, loaded))
    return errors


def _orphan_packs(root: Path, loaded: list[LoadedNote]) -> list[str]:
    stems = {item.path.stem for item in loaded}
    errors: list[str] = []
    for _kind, (_notes_dir, sources_dir) in knowledge_dirs(root).items():
        if not sources_dir.is_dir():
            continue
        for pack_path in sorted(sources_dir.glob("*.json")):
            if pack_path.name.startswith("_"):
                continue
            if pack_path.stem not in stems and pack_path.stem not in {
                path.stem for path in note_paths(_notes_dir)
            }:
                errors.append(f"{relative(pack_path, root)}: no matching note")
    return errors


def _relative_errors(loaded: LoadedNote, root: Path) -> list[str]:
    rewritten: list[str] = []
    for message in cross_file_errors(loaded):
        for raw in (loaded.path, loaded.pack_path):
            message = message.replace(raw.as_posix(), relative(raw, root))
        rewritten.append(message)
    return rewritten
