"""Command line for validation, indexing, search, and the MCP server."""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from priorart.constants import INDEX_FILENAME, MANIFEST_FILENAME
from priorart.embed import embedder_by_kind
from priorart.maintain import (
    apply_labels,
    apply_refresh,
    fetch_open_refresh_issues,
    load_labels,
    load_real_notes,
    plan_refresh,
)
from priorart.models import Note, SourcePack
from priorart.privacy import scan_path
from priorart.query import search_index
from priorart.server import serve
from priorart.sitegen import build_site
from priorart.store import build_local_knowledge, load_knowledge, notes_dir_from_env, write_index
from priorart.validate import repo_root_from, validate_repository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="priorart", description="PriorArt fix-note tools")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Check note schema, source packs, and freshness rules")
    sub.add_parser("privacy", help="Scan the tree for secrets and personal machine details")

    index = sub.add_parser("index", help="Build a search index and manifest")
    index.add_argument("--output", default=f"dist/{INDEX_FILENAME}")
    index.add_argument("--embedder", choices=("fastembed", "hash"), default="fastembed")
    index.add_argument("--include-examples", action="store_true")
    index.add_argument("--notes-dir")

    search = sub.add_parser("search", help="Search notes")
    search.add_argument("query")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--tag")
    search.add_argument("--platform")
    search.add_argument("--source", choices=("local", "remote", "auto"), default="local")
    search.add_argument("--embedder", choices=("fastembed", "hash"), default="fastembed")
    search.add_argument("--include-examples", action="store_true")
    search.add_argument("--notes-dir")
    search.add_argument("--json", action="store_true")
    search.add_argument("--expect-id", help="Exit 1 unless this note id is the top hit")

    serve_cmd = sub.add_parser("serve", help="Run the MCP server")
    serve_cmd.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8000)

    due = sub.add_parser("due", help="Print real notes whose refresh is due")
    due.add_argument("--as-of")
    due.add_argument("--notes-dir")

    refresh = sub.add_parser("refresh-issues", help="Plan or apply monthly refresh issues")
    refresh.add_argument("--as-of")
    refresh.add_argument("--notes-dir")
    refresh.add_argument("--apply", action="store_true")

    labels = sub.add_parser("sync-labels", help="Show or apply .github/labels.yml")
    labels.add_argument("--apply", action="store_true")

    site = sub.add_parser("site", help="Write the GitHub Pages HTML")
    site.add_argument("--output", default="_site")

    schema = sub.add_parser("export-schema", help="Write JSON Schema files")
    schema.add_argument("--output", default="schema")
    return parser


def _notes_dir(value: str | None) -> Path:
    if value:
        return Path(value)
    return notes_dir_from_env()


def _as_of(value: str | None) -> date:
    if value is None:
        return date.today()
    return date.fromisoformat(value)


def cmd_validate() -> int:
    root = repo_root_from()
    errors = validate_repository(root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Validated notes in {root / 'content' / 'notes'}")
    return 0


def cmd_privacy() -> int:
    root = repo_root_from()
    findings = scan_path(root)
    if findings:
        print("\n".join(item.format() for item in findings), file=sys.stderr)
        return 1
    print(f"No privacy findings in {root}")
    return 0


def cmd_index(output: str, embedder: str, include_examples: bool, notes_dir: str | None) -> int:
    directory = _notes_dir(notes_dir)
    knowledge = build_local_knowledge(
        directory,
        embedder_by_kind(embedder),
        include_examples=include_examples,
    )
    destination = Path(output)
    manifest = write_index(knowledge.index, destination)
    print(
        f"Wrote {destination} and {destination.parent / MANIFEST_FILENAME} "
        f"({manifest.note_count} notes, {manifest.model})"
    )
    return 0


def cmd_search(namespace: argparse.Namespace) -> int:
    directory = Path(namespace.notes_dir) if namespace.notes_dir else None
    knowledge = load_knowledge(
        source=namespace.source,
        notes_dir=directory,
        include_examples=namespace.include_examples,
        embedder_kind=namespace.embedder,
    )
    response = search_index(
        knowledge.index,
        namespace.query,
        embedder=knowledge.embedder(),
        top_k=namespace.top_k,
        tag=namespace.tag,
        platform=namespace.platform,
        origin=knowledge.origin,
    )
    if namespace.json:
        print(json.dumps(response.model_dump(mode="json"), indent=2))
    else:
        print(f"origin: {response.origin}")
        print(f"retrieval: {response.retrieval}")
        if response.warning:
            print(f"warning: {response.warning}")
        if not response.results:
            print("no matches")
        for rank, hit in enumerate(response.results, start=1):
            print(f"{rank}. {hit.id}  score={hit.score}")
            print(f"   {hit.title}")
    if namespace.expect_id:
        top = response.results[0].id if response.results else ""
        if top != namespace.expect_id:
            print(f"expected top hit {namespace.expect_id}, got {top or '(none)'}", file=sys.stderr)
            return 1
    return 0


def cmd_due(as_of: str | None, notes_dir: str | None) -> int:
    day = _as_of(as_of)
    notes = load_real_notes(_notes_dir(notes_dir))
    payload = [
        {
            "id": note.id,
            "title": note.title,
            "last_refreshed": note.last_refreshed.isoformat(),
            "refresh_due": note.refresh_due.isoformat(),
        }
        for note in notes
        if note.refresh_due <= day
    ]
    print(json.dumps(payload, indent=2))
    return 0


def cmd_refresh(as_of: str | None, notes_dir: str | None, apply: bool) -> int:
    day = _as_of(as_of)
    notes = load_real_notes(_notes_dir(notes_dir))
    issues = fetch_open_refresh_issues() if apply else []
    actions = plan_refresh(notes, issues, day)
    print(json.dumps([action.model_dump() for action in actions], indent=2))
    if apply:
        apply_refresh(actions)
    return 0


def cmd_labels(apply: bool) -> int:
    path = repo_root_from() / ".github" / "labels.yml"
    labels = load_labels(path)
    print(json.dumps([label.model_dump() for label in labels], indent=2))
    if apply:
        apply_labels(labels)
    return 0


def cmd_site(output: str) -> int:
    root = repo_root_from()
    count = build_site(root, Path(output))
    print(f"Wrote {count} notes to {output}")
    return 0


def cmd_export_schema(output: str) -> int:
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    documents = {
        "note.schema.json": Note.model_json_schema(),
        "source-pack.schema.json": SourcePack.model_json_schema(),
    }
    for name, document in documents.items():
        (destination / name).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {', '.join(documents)} to {destination}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    parser = _parser()
    namespace = parser.parse_args(argv)
    command = namespace.command
    if command == "validate":
        return cmd_validate()
    if command == "privacy":
        return cmd_privacy()
    if command == "index":
        return cmd_index(
            namespace.output,
            namespace.embedder,
            namespace.include_examples,
            namespace.notes_dir,
        )
    if command == "search":
        return cmd_search(namespace)
    if command == "serve":
        serve(namespace.transport, namespace.host, namespace.port)
        return 0
    if command == "due":
        return cmd_due(namespace.as_of, namespace.notes_dir)
    if command == "refresh-issues":
        return cmd_refresh(namespace.as_of, namespace.notes_dir, namespace.apply)
    if command == "sync-labels":
        return cmd_labels(namespace.apply)
    if command == "site":
        return cmd_site(namespace.output)
    if command == "export-schema":
        return cmd_export_schema(namespace.output)
    parser.error(f"unknown command {command}")
    return 2


def cli() -> None:
    sys.exit(main())
