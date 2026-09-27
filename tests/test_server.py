import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from mcp import Client
from mcp.types import TextContent

from helpers import write_note
from priorart.embed import HashEmbedder
from priorart.server import create_server
from priorart.store import build_local_knowledge


def _knowledge(tmp_path: Path):
    write_note(
        tmp_path,
        note_id="debugger-map",
        example=False,
        source_count=25,
        title="Map debugger sources with sourceFileMap",
        problem="The debugger looks for sources at a foreign absolute path and cannot open them.",
        code="sourceFileMap maps the foreign root onto the workspace.",
        tag="debugger",
        platform="windows",
    )
    return build_local_knowledge(tmp_path / "knowledge", HashEmbedder(), include_examples=False)


@pytest.mark.anyio
async def test_tools_round_trip(tmp_path: Path) -> None:
    server = create_server(_knowledge(tmp_path))
    async with Client(server) as client:
        found = await client.call_tool(
            "search_knowledge",
            {"query": "sourceFileMap debugger", "top_k": 3, "platform": "windows"},
        )
        assert found.is_error is False
        payload = found.structured_content
        assert payload is not None
        assert payload["results"][0]["id"] == "debugger-map"
        assert payload["results"][0]["note_type"] == "problem"
        assert payload["results"][0]["documented_solutions"]
        assert payload["results"][0]["caveats"]
        assert payload["results"][0]["sources"]

        guides = await client.call_tool(
            "search_knowledge",
            {"query": "fixture domain", "note_type": "domain-guide"},
        )
        assert guides.structured_content is not None
        assert guides.structured_content["results"][0]["id"] == "fixture-domain"

        bundle = await client.call_tool("get_domain_guide", {"domain_id": "fixture-domain"})
        assert bundle.structured_content is not None
        assert bundle.structured_content["problems"][0]["id"] == "debugger-map"
        assert bundle.structured_content["problems"][0]["causes"]

        record = await client.call_tool("get_problem", {"note_id": "debugger-map"})
        assert record.structured_content is not None
        assert len(record.structured_content["source_pack"]) == 25

        missing = await client.call_tool("get_problem", {"note_id": "missing-note"})
        assert missing.is_error is True
        detail = missing.content[0]
        assert isinstance(detail, TextContent)
        assert "unknown note" in detail.text

        topics = await client.call_tool("list_topics", {})
        assert topics.structured_content is not None
        assert topics.structured_content["tags"][0]["name"] == "debugger"

        due = await client.call_tool("list_refresh_due", {"as_of": "2026-10-01"})
        assert due.structured_content is not None
        assert due.structured_content["notes"][0]["id"] == "debugger-map"

        not_due = await client.call_tool("list_refresh_due", {"as_of": "2026-09-01"})
        assert not_due.structured_content is not None
        assert not_due.structured_content["notes"] == []


@pytest.mark.anyio
async def test_streamable_http_lists_tools(tmp_path: Path) -> None:
    server = create_server(_knowledge(tmp_path))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    app = server.streamable_http_app(stateless_http=True, json_response=True)
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    http_server = uvicorn.Server(config)

    def install_signal_handlers() -> None:
        return None

    http_server.install_signal_handlers = install_signal_handlers  # type: ignore[method-assign]
    thread = threading.Thread(target=http_server.run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while time.time() < deadline and not http_server.started:
        time.sleep(0.05)
    assert http_server.started
    try:
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            listed = await client.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == {
                "search_knowledge",
                "get_problem",
                "get_domain_guide",
                "list_topics",
                "list_refresh_due",
            }
    finally:
        http_server.should_exit = True
        thread.join(timeout=5)
