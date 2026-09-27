import hashlib
import json
from pathlib import Path

import httpx

from helpers import write_note
from priorart.embed import HashEmbedder
from priorart.store import (
    IndexFetchError,
    build_local_knowledge,
    fetch_index,
    load_knowledge,
    write_index,
)


def test_remote_index_is_preferred_and_local_is_the_fallback(tmp_path: Path) -> None:
    write_note(
        tmp_path,
        note_id="debugger-map",
        example=False,
        source_count=25,
        title="Map debugger sources with sourceFileMap",
        problem="The debugger looks for sources at a foreign absolute path and cannot open them.",
        code="sourceFileMap maps the foreign root.",
    )
    local = build_local_knowledge(
        tmp_path / "knowledge",
        HashEmbedder(),
        include_examples=False,
    )
    body = local.index.model_dump(mode="json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/missing.json"):
            return httpx.Response(404)
        return httpx.Response(200, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    remote = load_knowledge(
        source="auto",
        index_url="https://example.com/priorart-index.json",
        knowledge_dir=tmp_path / "knowledge",
        include_examples=False,
        embedder_kind="hash",
        client=client,
    )
    assert remote.origin == "remote"
    assert remote.index.notes[0].id == "debugger-map"

    fallback = load_knowledge(
        source="auto",
        index_url="https://example.com/missing.json",
        knowledge_dir=tmp_path / "knowledge",
        include_examples=False,
        embedder_kind="hash",
        client=client,
    )
    assert fallback.origin == "local"
    assert fallback.index.model == "hash-bow"


def test_fetch_index_rejects_invalid_json() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        fetch_index("https://example.com/priorart-index.json", client=client)
    except IndexFetchError as exc:
        assert "not a valid" in str(exc)
    else:
        raise AssertionError("expected IndexFetchError")


def test_manifest_hash_matches_bytes(tmp_path: Path) -> None:
    write_note(tmp_path, note_id="example-one", example=True, source_count=1)
    knowledge = build_local_knowledge(
        tmp_path / "knowledge",
        HashEmbedder(),
        include_examples=True,
    )
    output = tmp_path / "priorart-index.json"
    manifest = write_index(knowledge.index, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest.index_sha256 == digest
    saved = json.loads((tmp_path / "priorart-index-manifest.json").read_text(encoding="utf-8"))
    assert saved["note_ids"] == ["example-fixture-domain", "example-one"]
