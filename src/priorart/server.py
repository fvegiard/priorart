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

from priorart.models import DueList, DueNote, FixRecord, SearchResponse, TopicCount, TopicList
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
    ) -> SearchResponse:
        """Search verified fix notes and return the recipe plus cited sources.

        Call this before changing code or a dev environment. Example notes are
        omitted unless the server was started with PRIORART_INCLUDE_EXAMPLES=1.
        """
        library = get_knowledge()
        return search_index(
            library.index,
            query,
            embedder=library.embedder(),
            top_k=top_k,
            tag=_optional(tag),
            platform=_optional(platform),
            origin=library.origin,
        )

    @mcp.tool(annotations=_READ_ONLY)
    def get_fix(
        note_id: Annotated[
            str, Field(min_length=1, description="Note id, such as example-windows-debugger-path.")
        ],
    ) -> FixRecord:
        """Fetch one fix note, including its recipe, verification, and full source pack."""
        library = get_knowledge()
        for note in library.index.notes:
            if note.id == note_id:
                return FixRecord(
                    id=note.id,
                    title=note.title,
                    problem_summary=note.problem_summary,
                    tags=list(note.tags),
                    platforms=list(note.platforms),
                    recipe=list(note.recipe),
                    verification=list(note.verification),
                    sources=list(note.sources),
                    source_pack=list(note.source_pack),
                    created=note.created,
                    last_refreshed=note.last_refreshed,
                    refresh_due=note.refresh_due,
                    example=note.example,
                )
        raise ToolError(f"unknown note: {note_id}")

    @mcp.tool(annotations=_READ_ONLY)
    def list_topics() -> TopicList:
        """List tags and platforms in the loaded index, with note counts."""
        library = get_knowledge()
        tags: dict[str, int] = {}
        platforms: dict[str, int] = {}
        for note in library.index.notes:
            for tag in note.tags:
                tags[tag] = tags.get(tag, 0) + 1
            for platform in note.platforms:
                platforms[platform.name] = platforms.get(platform.name, 0) + 1
        return TopicList(
            tags=[TopicCount(name=name, count=count) for name, count in sorted(tags.items())],
            platforms=[
                TopicCount(name=name, count=count) for name, count in sorted(platforms.items())
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
