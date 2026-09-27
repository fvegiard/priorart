from pathlib import Path

from helpers import write_note
from priorart.embed import HashEmbedder
from priorart.models import SearchIndex
from priorart.query import search_index
from priorart.store import build_local_knowledge, write_index

ROOT = Path(__file__).resolve().parents[1]


def _library(tmp_path: Path):
    write_note(
        tmp_path,
        note_id="debugger-map",
        example=False,
        source_count=25,
        title="Map debugger sources with sourceFileMap",
        problem="The debugger looks for sources at a foreign absolute path and cannot open them.",
        code="sourceFileMap maps /original/source/root onto the workspace.",
        tag="debugger",
        platform="windows",
    )
    write_note(
        tmp_path,
        note_id="printer-spooler",
        example=False,
        source_count=25,
        title="Restart the print spooler service",
        problem="The print spooler service stops after a driver update and jobs stay queued.",
        code="Restart-Service -Name Spooler",
        tag="printing",
        platform="linux",
    )
    return build_local_knowledge(
        tmp_path / "content" / "notes", HashEmbedder(), include_examples=False
    )


def test_hybrid_search_ranks_the_matching_note(tmp_path: Path) -> None:
    knowledge = _library(tmp_path)
    response = search_index(
        knowledge.index,
        "sourceFileMap debugger path",
        embedder=knowledge.embedder(),
        top_k=2,
        origin=knowledge.origin,
    )
    assert response.retrieval == "hybrid"
    assert response.results[0].id == "debugger-map"
    assert response.results[0].recipe[0].code
    assert response.results[0].sources


def test_tag_and_platform_filters(tmp_path: Path) -> None:
    knowledge = _library(tmp_path)
    tagged = search_index(
        knowledge.index,
        "service",
        embedder=knowledge.embedder(),
        top_k=5,
        tag="printing",
        origin="local",
    )
    assert [hit.id for hit in tagged.results] == ["printer-spooler"]
    platform = search_index(
        knowledge.index,
        "sourceFileMap",
        embedder=knowledge.embedder(),
        top_k=5,
        platform="linux",
        origin="local",
    )
    assert [hit.id for hit in platform.results] == ["printer-spooler"]


def test_sample_is_searchable_only_when_requested() -> None:
    notes = ROOT / "content" / "notes"
    hidden = build_local_knowledge(notes, HashEmbedder(), include_examples=False)
    assert hidden.index.notes == []
    shown = build_local_knowledge(notes, HashEmbedder(), include_examples=True)
    response = search_index(
        shown.index,
        "sourceFileMap debugger",
        embedder=shown.embedder(),
        top_k=3,
        origin="local",
    )
    assert response.results[0].id == "example-windows-debugger-path"
    assert "sourceFileMap" in (response.results[0].recipe[0].code or "")
    assert response.results[0].sources


def test_index_round_trip(tmp_path: Path) -> None:
    knowledge = _library(tmp_path)
    manifest = write_index(knowledge.index, tmp_path / "dist" / "priorart-index.json")
    payload = (tmp_path / "dist" / "priorart-index.json").read_text(encoding="utf-8")
    restored = SearchIndex.model_validate_json(payload)
    assert restored.model == "hash-bow"
    assert manifest.note_count == 2
    assert manifest.note_ids == ["debugger-map", "printer-spooler"]
