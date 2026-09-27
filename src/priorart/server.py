"""MCP server for the fix-note knowledge base."""

import logging
import os
import sys
from datetime import date
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from priorart.models import (
    DomainGuideRecord,
    DueList,
    DueNote,
    FixRecord,
    IndexedNote,
    NoteKind,
    SearchResponse,
    TopicCount,
    TopicList,
)
from priorart.query import search_index
from priorart.store import Knowledge, load_knowledge

logger = logging.getLogger("priorart")
_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_day(value: str | None) -> date:
    if value is None or not value.strip():
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError("as_of must be an ISO date, YYYY-MM-DD") from exc


def _parse_note_type(value: str | None) -> NoteKind | None:
    cleaned = _optional(value)
    if cleaned is None or cleaned == "all":
        return None
    try:
        return NoteKind(cleaned)
    except ValueError as exc:
        raise ToolError("note_type must be domain-guide, fix, or all") from exc


def _fix_record(note: IndexedNote) -> FixRecord:
    return FixRecord(
        id=note.id,
        title=note.title,
        problem_summary=note.problem_summary,
        root_cause=note.root_cause,
        tags=list(note.tags),
        platforms=list(note.platforms),
        domains=list(note.domains),
        recipe=list(note.recipe),
        verification=list(note.verification),
        rollback=list(note.rollback),
        sources=list(note.sources),
        source_pack=list(note.source_pack),
        created=note.created,
        last_refreshed=note.last_refreshed,
        refresh_due=note.refresh_due,
        example=note.example,
    )


def create_server(knowledge: Knowledge | None = None) -> MCPServer:
    mcp = MCPServer("priorart")
    holder: dict[str, Knowledge | None] = {"knowledge": knowledge}

    def get_knowledge() -> Knowledge:
        current = holder["knowledge"]
        if current is None:
            try:
                current = load_knowledge()
            except (OSError, ValueError, FileNotFoundError) as exc:
                raise ToolError(f"could not load the knowledge base: {exc}") from exc
            holder["knowledge"] = current
            logger.info("knowledge origin=%s notes=%s", current.origin, len(current.index.notes))
        return current

    @mcp.tool(annotations=_READ_ONLY)
    def search_fixes(
        query: Annotated[
            str, Field(min_length=1, description="What is broken, in plain language.")
        ],
        top_k: Annotated[int, Field(ge=1, le=20, description="How many notes to return.")] = 5,
        tag: Annotated[str | None, Field(description="Exact tag filter, such as debugger.")] = None,
        platform: Annotated[
            str | None, Field(description="Platform slug filter, such as windows.")
        ] = None,
        note_type: Annotated[
            str | None,
            Field(description="domain-guide, fix, or all. Omit to search both."),
        ] = None,
    ) -> SearchResponse:
        """Search domain guides and fix recipes.

        Filter with note_type. Fix hits include the recipe, verification, rollback,
        and cited sources. Domain hits include the summary and related fix ids.
        Example notes are omitted unless PRIORART_INCLUDE_EXAMPLES=1.
        """
        library = get_knowledge()
        return search_index(
            library.index,
            query,
            embedder=library.embedder(),
            top_k=top_k,
            tag=_optional(tag),
            platform=_optional(platform),
            note_type=_parse_note_type(note_type),
            origin=library.origin,
        )

    @mcp.tool(annotations=_READ_ONLY)
    def get_fix(
        note_id: Annotated[
            str, Field(min_length=1, description="Note id, such as example-windows-debugger-path.")
        ],
    ) -> FixRecord:
        """Fetch one fix recipe, including rollback and the full source pack."""
        library = get_knowledge()
        for note in library.index.notes:
            if note.id == note_id:
                if note.note_type is not NoteKind.FIX:
                    raise ToolError(f"{note_id} is a domain guide; call get_domain_guide")
                return _fix_record(note)
        raise ToolError(f"unknown note: {note_id}")

    @mcp.tool(annotations=_READ_ONLY)
    def get_domain_guide(
        domain_id: Annotated[
            str,
            Field(min_length=1, description="Domain guide id, such as example-windows-debugger."),
        ],
    ) -> DomainGuideRecord:
        """Return one domain guide together with the fix recipes it lists."""
        library = get_knowledge()
        guide = next((note for note in library.index.notes if note.id == domain_id), None)
        if guide is None:
            raise ToolError(f"unknown domain guide: {domain_id}")
        if guide.note_type is not NoteKind.DOMAIN_GUIDE:
            raise ToolError(f"{domain_id} is a fix; call get_fix")
        by_id = {note.id: note for note in library.index.notes}
        fixes: list[FixRecord] = []
        missing: list[str] = []
        for fix_id in guide.related_fixes:
            linked = by_id.get(fix_id)
            if linked is None or linked.note_type is not NoteKind.FIX:
                missing.append(fix_id)
                continue
            fixes.append(_fix_record(linked))
        return DomainGuideRecord(
            id=guide.id,
            title=guide.title,
            summary=guide.summary,
            tags=list(guide.tags),
            platforms=list(guide.platforms),
            related_fixes=list(guide.related_fixes),
            fixes=fixes,
            missing_fix_ids=missing,
            sources_count=guide.sources_count,
            source_pack=list(guide.source_pack),
            created=guide.created,
            last_refreshed=guide.last_refreshed,
            refresh_due=guide.refresh_due,
            example=guide.example,
        )

    @mcp.tool(annotations=_READ_ONLY)
    def list_topics() -> TopicList:
        """List tags and platforms in the loaded index, with note counts."""
        library = get_knowledge()
        tags: dict[str, int] = {}
        platforms: dict[str, int] = {}
        kinds: dict[str, int] = {}
        for note in library.index.notes:
            for tag in note.tags:
                tags[tag] = tags.get(tag, 0) + 1
            for platform in note.platforms:
                platforms[platform.name] = platforms.get(platform.name, 0) + 1
            kinds[note.note_type.value] = kinds.get(note.note_type.value, 0) + 1
        return TopicList(
            tags=[TopicCount(name=name, count=count) for name, count in sorted(tags.items())],
            platforms=[
                TopicCount(name=name, count=count) for name, count in sorted(platforms.items())
            ],
            note_types=[
                TopicCount(name=name, count=count) for name, count in sorted(kinds.items())
            ],
        )

    @mcp.tool(annotations=_READ_ONLY)
    def list_refresh_due(
        as_of: Annotated[
            str | None,
            Field(description="ISO date. Defaults to today. Example notes are never due."),
        ] = None,
    ) -> DueList:
        """List real notes whose refresh_due date is on or before as_of."""
        day = _parse_day(as_of)
        library = get_knowledge()
        due = [
            DueNote(
                id=note.id,
                note_type=note.note_type,
                title=note.title,
                last_refreshed=note.last_refreshed,
                refresh_due=note.refresh_due,
            )
            for note in library.index.notes
            if not note.example and note.refresh_due <= day
        ]
        due.sort(key=lambda item: (item.refresh_due, item.id))
        return DueList(as_of=day, notes=due)

    return mcp


mcp = create_server()


def serve(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the process-wide server. stdio is the local default; http is streamable HTTP."""
    _configure_logging()
    if transport == "stdio":
        mcp.run(transport="stdio")
        return
    if transport == "http":
        mcp.run(
            transport="streamable-http",
            host=host,
            port=port,
            stateless_http=True,
            json_response=True,
        )
        return
    raise ValueError(f"unknown transport {transport!r}; use stdio or http")


def main() -> None:
    transport = os.environ.get("PRIORART_TRANSPORT", "stdio")
    host = os.environ.get("PRIORART_HOST", "127.0.0.1")
    port = int(os.environ.get("PRIORART_PORT", "8000"))
    if transport == "streamable-http":
        transport = "http"
    try:
        serve(transport, host, port)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
