"""Build a search index from notes, or download the published one."""

import hashlib
import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import assert_never

import httpx
from pydantic import ValidationError

from priorart.constants import (
    DEFAULT_INDEX_URL,
    INDEX_FILENAME,
    INDEX_SCHEMA_VERSION,
    MANIFEST_FILENAME,
)
from priorart.embed import Embedder, embedder_by_kind, embedder_for
from priorart.load import LoadedNote, load_tree
from priorart.models import DomainGuide, FixNote, IndexedNote, IndexManifest, SearchIndex
from priorart.textutil import document_text
from priorart.validate import repo_root_from, validate_repository

logger = logging.getLogger("priorart")

USER_AGENT = "priorart/0.1.0"


class IndexFetchError(Exception):
    """The published index could not be downloaded or parsed."""


def git_sha(root: Path | None = None) -> str:
    env = os.environ.get("GITHUB_SHA")
    if env:
        return env
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"
    return output.strip()


def knowledge_dir_from_env(start: Path | None = None) -> Path:
    override = os.environ.get("PRIORART_KNOWLEDGE_DIR")
    if override:
        return Path(override)
    return repo_root_from(start) / "knowledge"


def load_corpus(knowledge_dir: Path, *, include_examples: bool) -> list[LoadedNote]:
    root = knowledge_dir.parent
    errors = validate_repository(root)
    if errors:
        raise ValueError("\n".join(errors))
    loaded, load_errors = load_tree(root)
    if load_errors:
        raise ValueError("\n".join(load_errors))
    if not include_examples:
        return [item for item in loaded if not item.note.example]
    return loaded


def _index_note(item: LoadedNote, text: str, vector: list[float]) -> IndexedNote:
    note = item.note
    shared = {
        "id": note.id,
        "note_type": note.type,
        "title": note.title,
        "tags": list(note.tags),
        "platforms": list(note.platforms),
        "source_pack": list(item.pack.references),
        "created": note.created,
        "last_refreshed": note.last_refreshed,
        "refresh_due": note.refresh_due,
        "example": note.example,
        "text": text,
        "embedding": vector,
    }
    match note:
        case DomainGuide() as guide:
            return IndexedNote(
                summary=guide.summary,
                related_fixes=list(guide.related_fixes),
                sources_count=guide.sources_count,
                **shared,
            )
        case FixNote() as fix:
            return IndexedNote(
                summary=fix.problem_summary,
                problem_summary=fix.problem_summary,
                root_cause=fix.root_cause,
                recipe=list(fix.recipe),
                verification=list(fix.verification),
                rollback=list(fix.rollback),
                domains=list(fix.domains),
                sources=list(fix.sources),
                **shared,
            )
        case _ as other:
            assert_never(other)


def build_index(
    notes: list[LoadedNote],
    embedder: Embedder,
    *,
    git_sha_value: str,
    built_at: datetime | None = None,
) -> SearchIndex:
    texts = [document_text(item.note, item.pack) for item in notes]
    vectors = embedder.embed_passages(texts) if texts else []
    indexed = [
        _index_note(item, text, vector)
        for item, text, vector in zip(notes, texts, vectors, strict=True)
    ]
    indexed.sort(key=lambda note: note.id)
    stamp = built_at or datetime.now(UTC).replace(microsecond=0)
    return SearchIndex(
        schema_version=INDEX_SCHEMA_VERSION,
        model=embedder.model_name,
        embedding_dim=embedder.dim,
        built_at=stamp,
        git_sha=git_sha_value,
        notes=indexed,
    )


def write_index(index: SearchIndex, output: Path) -> IndexManifest:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(index.model_dump(mode="json"), indent=2) + "\n"
    output.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    manifest = IndexManifest(
        schema_version=index.schema_version,
        model=index.model,
        embedding_dim=index.embedding_dim,
        built_at=index.built_at,
        git_sha=index.git_sha,
        note_count=len(index.notes),
        note_ids=[note.id for note in index.notes],
        index_sha256=digest,
        index_filename=INDEX_FILENAME,
        index_url=DEFAULT_INDEX_URL,
    )
    manifest_path = output.parent / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def fetch_index(url: str, *, client: httpx.Client | None = None) -> SearchIndex:
    owns_client = client is None
    http = client or httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        try:
            response = http.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise IndexFetchError(str(exc)) from exc
        try:
            return SearchIndex.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            raise IndexFetchError(f"published index is not a valid priorart index: {exc}") from exc
    finally:
        if owns_client:
            http.close()


class Knowledge:
    def __init__(self, index: SearchIndex, origin: str, embedder: Embedder | None) -> None:
        self.index = index
        self.origin = origin
        self._embedder = embedder

    def embedder(self) -> Embedder | None:
        if self._embedder is not None:
            return self._embedder
        try:
            self._embedder = embedder_for(self.index.model)
        except ValueError as exc:
            logger.warning("%s", exc)
            return None
        return self._embedder


def build_local_knowledge(
    knowledge_dir: Path,
    embedder: Embedder,
    *,
    include_examples: bool,
    origin: str = "local",
) -> Knowledge:
    notes = load_corpus(knowledge_dir, include_examples=include_examples)
    index = build_index(notes, embedder, git_sha_value=git_sha(knowledge_dir.parent))
    return Knowledge(index=index, origin=origin, embedder=embedder)


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip() in {"1", "true", "yes"}


def load_knowledge(
    *,
    source: str | None = None,
    index_url: str | None = None,
    knowledge_dir: Path | None = None,
    include_examples: bool | None = None,
    embedder_kind: str | None = None,
    client: httpx.Client | None = None,
) -> Knowledge:
    mode = source or os.environ.get("PRIORART_SOURCE", "auto")
    url = index_url or os.environ.get("PRIORART_INDEX_URL", DEFAULT_INDEX_URL)
    examples = _flag("PRIORART_INCLUDE_EXAMPLES") if include_examples is None else include_examples
    kind = embedder_kind or os.environ.get("PRIORART_EMBEDDER", "fastembed")
    if mode not in {"auto", "remote", "local"}:
        raise ValueError("PRIORART_SOURCE must be auto, remote, or local")

    def local() -> Knowledge:
        directory = knowledge_dir or knowledge_dir_from_env()
        logger.info("building a local index from %s", directory)
        return build_local_knowledge(
            directory,
            embedder_by_kind(kind),
            include_examples=examples,
        )

    if mode == "local":
        return local()
    try:
        logger.info("fetching published index %s", url)
        index = fetch_index(url, client=client)
    except IndexFetchError as exc:
        if mode == "remote":
            raise
        logger.warning("published index unavailable (%s); using local notes", exc)
        return local()
    logger.info("loaded published index %s (%s notes)", index.git_sha, len(index.notes))
    return Knowledge(index=index, origin="remote", embedder=None)
