"""MCP server for the Priorart knowledge base. Tools return knowledge and apply nothing."""

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
    IndexedNote,
    NoteKind,
    ProblemRecord,
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
        raise ToolError("note_type must be domain-guide, problem, or all") from exc


def _problem_record(note: IndexedNote) -> ProblemRecord:
    return ProblemRecord(
        id=note.id,
        title=note.title,
        symptoms=note.symptoms,
        causes=note.causes,
        tags=list(note.tags),
        platforms=list(note.platforms),
        domains=list(note.domains),
        documented_solutions=list(note.documented_solutions),
        verification=list(note.verification),
        caveats=list(note.caveats),
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
    def search_knowledge(
        query: Annotated[
            str, Field(min_length=1, description="What you want to know, in plain language.")
        ],
        top_k: Annotated[int, Field(ge=1, le=20, description="How many notes to return.")] = 5,
        tag: Annotated[str | None, Field(description="Exact tag filter, such as debugger.")] = None,
        platform: Annotated[
            str | None, Field(description="Platform slug filter, such as windows.")
        ] = None,
        note_type: Annotated[
            str | None,
            Field(description="domain-guide, problem, or all. Omit to search both."),
        ] = None,
    ) -> SearchResponse:
        """Search domain guides and problem knowledge. Does not apply any change.

        Filter with note_type. Problem hits include symptoms, causes, documented
        solutions, verification methods, caveats, and cited sources. Domain hits
        include the summary and related problem ids. Example notes are omitted
        unless PRIORART_INCLUDE_EXAMPLES=1.
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
    def get_problem(
        note_id: Annotated[
            str,
            Field(
                min_length=1,
                description="Problem id, such as example-windows-debugger-path.",
            ),
        ],
    ) -> ProblemRecord:
        """Return what is known about one problem, including sources. Does not apply it."""
        library = get_knowledge()
        for note in library.index.notes:
            if note.id == note_id:
                if note.note_type is not NoteKind.PROBLEM:
                    raise ToolError(f"{note_id} is a domain guide; call get_domain_guide")
                return _problem_record(note)
        raise ToolError(f"unknown note: {note_id}")

    @mcp.tool(annotations=_READ_ONLY)
    def get_domain_guide(
        domain_id: Annotated[
            str,
            Field(min_length=1, description="Domain guide id, such as example-windows-debugger."),
        ],
    ) -> DomainGuideRecord:
        """Return one domain guide together with the problem notes it lists."""
        library = get_knowledge()
        guide = next((note for note in library.index.notes if note.id == domain_id), None)
        if guide is None:
            raise ToolError(f"unknown domain guide: {domain_id}")
        if guide.note_type is not NoteKind.DOMAIN_GUIDE:
            raise ToolError(f"{domain_id} is a problem note; call get_problem")
        by_id = {note.id: note for note in library.index.notes}
        problems: list[ProblemRecord] = []
        missing: list[str] = []
        for problem_id in guide.related_problems:
            linked = by_id.get(problem_id)
            if linked is None or linked.note_type is not NoteKind.PROBLEM:
                missing.append(problem_id)
                continue
            problems.append(_problem_record(linked))
        return DomainGuideRecord(
            id=guide.id,
            title=guide.title,
            summary=guide.summary,
            tags=list(guide.tags),
            platforms=list(guide.platforms),
            related_problems=list(guide.related_problems),
            problems=problems,
            missing_problem_ids=missing,
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
