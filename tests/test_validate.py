import json
from pathlib import Path

from helpers import write_note
from priorart.models import DomainGuide, FixNote, SourcePack
from priorart.validate import validate_repository

ROOT = Path(__file__).resolve().parents[1]


def test_repository_notes_validate() -> None:
    assert validate_repository(ROOT) == []


def test_committed_schemas_match_models() -> None:
    domain_schema = json.loads(
        (ROOT / "schema" / "domain-guide.schema.json").read_text(encoding="utf-8")
    )
    fix_schema = json.loads((ROOT / "schema" / "fix.schema.json").read_text(encoding="utf-8"))
    pack_schema = json.loads(
        (ROOT / "schema" / "source-pack.schema.json").read_text(encoding="utf-8")
    )
    assert domain_schema == DomainGuide.model_json_schema()
    assert fix_schema == FixNote.model_json_schema()
    assert pack_schema == SourcePack.model_json_schema()


def test_real_note_needs_25_sources(tmp_path: Path) -> None:
    write_note(tmp_path, note_id="short-pack", example=False, source_count=24)
    errors = validate_repository(tmp_path)
    assert any("at least 25" in error for error in errors)

    write_note(tmp_path, note_id="full-pack", example=False, source_count=25)
    errors = validate_repository(tmp_path)
    assert not any("full-pack" in error for error in errors)


def test_example_note_can_have_a_short_pack(tmp_path: Path) -> None:
    write_note(tmp_path, note_id="example-short", example=True, source_count=1)
    assert validate_repository(tmp_path) == []


def test_stale_community_source_is_rejected(tmp_path: Path) -> None:
    write_note(
        tmp_path,
        note_id="stale-community",
        example=False,
        source_count=25,
        kind="community",
        published="2026-01-01",
    )
    errors = validate_repository(tmp_path)
    assert any("community source" in error for error in errors)


def test_cited_source_must_be_in_the_pack(tmp_path: Path) -> None:
    write_note(tmp_path, note_id="full-pack", example=False, source_count=25)
    note_path = tmp_path / "knowledge" / "fixes" / "full-pack.md"
    text = note_path.read_text(encoding="utf-8").replace(
        "https://example.com/fixture/0",
        "https://example.com/fixture/missing",
    )
    note_path.write_text(text, encoding="utf-8")
    errors = validate_repository(tmp_path)
    assert any("missing from the source pack" in error for error in errors)


def test_domain_links_must_resolve(tmp_path: Path) -> None:
    write_note(tmp_path, note_id="full-pack", example=False, source_count=25)
    note_path = tmp_path / "knowledge" / "fixes" / "full-pack.md"
    text = note_path.read_text(encoding="utf-8").replace(
        "  - fixture-domain\n",
        "  - missing-domain\n",
    )
    note_path.write_text(text, encoding="utf-8")
    errors = validate_repository(tmp_path)
    assert any("does not resolve: missing-domain" in error for error in errors)
