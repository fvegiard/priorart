"""Builders for temporary notes. Forbidden strings are concatenated so the suite stays clean."""

import json
import re
from pathlib import Path


def reference(
    index: int,
    *,
    kind: str = "official-docs",
    published: str = "2026-01-15",
) -> dict[str, str]:
    return {
        "url": f"https://example.com/fixture/{index}",
        "title": f"Fixture source {index} for the temporary note",
        "type": kind,
        "published": published,
        "retrieved": "2026-09-27",
        "relevance": f"Fixture reference {index} records why this source was collected.",
    }


def _related_fixes(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    match = re.search(r"related_fixes:\n(?P<body>(?:  - .+\n)*)", text)
    if match is None:
        return []
    return re.findall(r"^  - (\S+)$", match.group("body"), flags=re.MULTILINE)


def write_domain(
    root: Path, *, domain_id: str, example: bool, fix_ids: list[str], count: int
) -> None:
    refs = [reference(index) for index in range(count)]
    # Domain packs use a distinct URL space so they do not collide with a fix pack in reviews.
    for index, item in enumerate(refs):
        item["url"] = f"https://example.com/fixture/domain/{index}"
        item["title"] = f"Fixture domain source {index} for the temporary guide"
    body = "Example only. Fixture domain.\n" if example else "Fixture domain.\n"
    related = "\n".join(f"  - {fix_id}" for fix_id in fix_ids)
    related_block = f"related_fixes:\n{related}\n" if related else "related_fixes: []\n"
    note = f"""---
id: {domain_id}
type: domain-guide
title: Fixture domain for temporary notes
summary: A fixture domain guide that is long enough to satisfy the schema minimum.
tags:
  - fixture
platforms:
  - name: windows
    versions: ["11"]
{related_block}sources_count: {count}
created: 2026-09-01
last_refreshed: 2026-09-01
refresh_due: 2026-10-01
example: {"true" if example else "false"}
---

{body}
"""
    domains = root / "knowledge" / "domains"
    sources = root / "knowledge" / "sources" / "domains"
    domains.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    (domains / f"{domain_id}.md").write_text(note, encoding="utf-8")
    pack = {"note_id": domain_id, "collected_at": "2026-09-27", "references": refs}
    (sources / f"{domain_id}.json").write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")


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
    if published is None:
        published = "2026-01-15"
    refs = [reference(index, kind=kind, published=published) for index in range(source_count)]
    cited = refs[0]
    body = "Example only. Fixture.\n" if example else "Fixture body.\n"
    domain_id = "example-fixture-domain" if example else "fixture-domain"
    note = f"""---
id: {note_id}
type: fix
title: {title}
problem_summary: {problem}
root_cause: The fixture fails because the temporary setup does not match the expected state.
tags:
  - {tag}
platforms:
  - name: {platform}
    versions: ["11"]
domains:
  - {domain_id}
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
rollback:
  - name: Undo the fixture
    detail: Remove the fixture change so the shell returns to its previous state.
    language: powershell
    code: |
      Write-Output rolled-back
sources:
  - url: {cited["url"]}
    title: {cited["title"]}
    type: {cited["type"]}
    published: {cited["published"]}
    retrieved: {cited["retrieved"]}
created: 2026-09-01
last_refreshed: 2026-09-01
refresh_due: 2026-10-01
example: {"true" if example else "false"}
---

{body}
"""
    fixes = root / "knowledge" / "fixes"
    sources = root / "knowledge" / "sources" / "fixes"
    fixes.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    (fixes / f"{note_id}.md").write_text(note, encoding="utf-8")
    pack = {"note_id": note_id, "collected_at": "2026-09-27", "references": refs}
    (sources / f"{note_id}.json").write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    domain_path = root / "knowledge" / "domains" / f"{domain_id}.md"
    related = _related_fixes(domain_path)
    if note_id not in related:
        related.append(note_id)
    domain_count = source_count if example else max(source_count, 25)
    write_domain(
        root,
        domain_id=domain_id,
        example=example,
        fix_ids=related,
        count=domain_count,
    )
