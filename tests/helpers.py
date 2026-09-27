"""Builders for temporary notes. Forbidden strings are concatenated so the suite stays clean."""

import json
from pathlib import Path


def reference(
    index: int,
    *,
    kind: str = "official-docs",
    published: str | None = "2026-01-15",
) -> dict[str, str]:
    item = {
        "url": f"https://example.com/fixture/{index}",
        "title": f"Fixture source {index} for the temporary note",
        "type": kind,
        "retrieved": "2026-09-27",
        "why_relevant": f"Fixture reference {index} records why this source was collected.",
    }
    if published is not None:
        item["published"] = published
    return item


def write_note(
    root: Path,
    *,
    note_id: str,
    example: bool,
    source_count: int,
    title: str = "Temporary fixture note for validation",
    problem: str = "A fixture problem summary that is long enough to satisfy the schema minimum.",
    code: str = "Write-Output 'fixture'",
    tag: str = "fixture",
    platform: str = "windows",
    kind: str = "official-docs",
    published: str | None = "2026-01-15",
) -> None:
    refs = [reference(index, kind=kind, published=published) for index in range(source_count)]
    cited = refs[0]
    published_line = f"    published: {cited['published']}\n" if cited.get("published") else ""
    body = "Example only. Fixture.\n" if example else "Fixture body.\n"
    note = f"""---
id: {note_id}
title: {title}
problem_summary: {problem}
tags:
  - {tag}
platforms:
  - name: {platform}
    versions: ["11"]
recipe:
  - name: Apply the fixture
    detail: Run the fixture command in a clean shell.
    language: powershell
    code: |
      {code}
verification:
  - name: Check the fixture
    detail: The fixture command exits without an error.
    language: powershell
    code: |
      Write-Output ok
sources:
  - url: {cited["url"]}
    title: {cited["title"]}
    type: {cited["type"]}
{published_line}    retrieved: {cited["retrieved"]}
created: 2026-09-01
last_refreshed: 2026-09-01
refresh_due: 2026-10-01
example: {"true" if example else "false"}
---

{body}
"""
    notes = root / "content" / "notes"
    sources = root / "content" / "sources"
    notes.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    (notes / f"{note_id}.md").write_text(note, encoding="utf-8")
    pack = {
        "note_id": note_id,
        "collected_at": "2026-09-27",
        "references": refs,
    }
    (sources / f"{note_id}.json").write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
