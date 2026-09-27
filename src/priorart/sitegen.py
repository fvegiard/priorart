"""Static HTML browser for domain guides and fix recipes."""

import html
from pathlib import Path
from typing import assert_never

from priorart.constants import DEFAULT_INDEX_URL, PAGES_URL, REPO
from priorart.load import LoadedNote, load_tree
from priorart.models import DomainGuide, FixNote, Source, SourcePackEntry, Step

_CSS = """
:root { color-scheme: light; }
body {
  font-family: system-ui, sans-serif;
  line-height: 1.5;
  max-width: 46rem;
  margin: 2rem auto;
  padding: 0 1rem;
  color: #18181b;
}
a { color: #1d4ed8; }
pre { overflow: auto; background: #f4f4f5; padding: 0.75rem 1rem; }
code { font-family: ui-monospace, SFMono-Regular, monospace; }
.banner { background: #fef3c7; border: 1px solid #f59e0b; padding: 0.75rem 1rem; }
.meta { color: #3f3f46; }
"""


def _steps(title: str, steps: list[Step]) -> str:
    blocks = [f"<h2>{html.escape(title)}</h2>", "<ol>"]
    for step in steps:
        language = f" ({html.escape(step.language)})" if step.language else ""
        code = ""
        if step.code:
            code = f"<pre><code>{html.escape(step.code)}</code></pre>"
        blocks.append(
            "<li>"
            f"<strong>{html.escape(step.name)}</strong>{language}"
            f"<p>{html.escape(step.detail)}</p>{code}</li>"
        )
    blocks.append("</ol>")
    return "\n".join(blocks)


def _source_list(sources: list[Source] | list[SourcePackEntry]) -> str:
    rows = ["<ul>"]
    for source in sources:
        published = source.published.isoformat() if source.published else "undated"
        rows.append(
            "<li>"
            f'<a href="{html.escape(source.url)}">{html.escape(source.title)}</a>'
            f" ({html.escape(source.type.value)}; published {html.escape(published)}; "
            f"retrieved {html.escape(source.retrieved.isoformat())})"
            "</li>"
        )
    rows.append("</ul>")
    return "".join(rows)


def _page(title: str, body: str, *, depth: int) -> str:
    prefix = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{prefix}style.css">
</head>
<body>
{body}
</body>
</html>
"""


def _banner(example: bool) -> str:
    if not example:
        return ""
    return (
        '<p class="banner"><strong>Example only.</strong> '
        "This note is fictional scaffolding and is excluded from search.</p>"
    )


def _meta(loaded: LoadedNote) -> str:
    note = loaded.note
    platforms = ", ".join(
        html.escape(platform.name)
        + (f" ({html.escape(', '.join(platform.versions))})" if platform.versions else "")
        for platform in note.platforms
    )
    tags = ", ".join(html.escape(tag) for tag in note.tags)
    return (
        f'<p><a href="../index.html">All notes</a></p>\n  {_banner(note.example)}\n'
        f"  <h1>{html.escape(note.title)}</h1>\n"
        f'  <p class="meta">{html.escape(note.type.value)} · {html.escape(note.id)}'
        f" · {tags} · {platforms}</p>\n"
        f'  <p class="meta">Created {note.created.isoformat()}'
        f" · refreshed {note.last_refreshed.isoformat()}"
        f" · due {note.refresh_due.isoformat()}</p>"
    )


def render_note(loaded: LoadedNote) -> str:
    note = loaded.note
    paragraphs = [
        f"<p>{html.escape(chunk.strip())}</p>"
        for chunk in loaded.body.split("\n\n")
        if chunk.strip()
    ]
    match note:
        case DomainGuide() as guide:
            blob = f"https://github.com/{REPO}/blob/main/knowledge/sources/domains/{guide.id}.json"
            fixes = ", ".join(html.escape(fix_id) for fix_id in guide.related_fixes) or "none yet"
            body = f"""  {_meta(loaded)}
  <h2>Summary</h2>
  <p>{html.escape(guide.summary)}</p>
  <h2>Related fixes</h2>
  <p>{fixes}</p>
  <h2>Sources</h2>
  {_source_list(loaded.pack.references)}
  <p><a href="{html.escape(blob)}">Raw source pack</a>
  ({guide.sources_count} references)</p>
  {"".join(paragraphs)}
"""
        case FixNote() as fix:
            blob = f"https://github.com/{REPO}/blob/main/knowledge/sources/fixes/{fix.id}.json"
            domains = ", ".join(html.escape(domain_id) for domain_id in fix.domains)
            body = f"""  {_meta(loaded)}
  <h2>Problem</h2>
  <p>{html.escape(fix.problem_summary)}</p>
  <h2>Root cause</h2>
  <p>{html.escape(fix.root_cause)}</p>
  <p class="meta">Domains: {domains}</p>
  {_steps("Recipe", list(fix.recipe))}
  {_steps("Verification", list(fix.verification))}
  {_steps("Rollback", list(fix.rollback))}
  <h2>Sources</h2>
  {_source_list(list(fix.sources))}
  <p><a href="{html.escape(blob)}">Raw source pack</a>
  ({len(loaded.pack.references)} references)</p>
  {"".join(paragraphs)}
"""
        case _ as other:
            assert_never(other)
    return _page(note.title, body, depth=1)


def _group_items(group: list[LoadedNote], folder: str) -> str:
    if not group:
        return "<p>None yet.</p>"
    rows = ["<ul>"]
    for item in group:
        href = f"{folder}/{html.escape(item.note.id)}.html"
        title = html.escape(item.note.title)
        note_id = html.escape(item.note.id)
        rows.append(f'<li><a href="{href}">{title}</a> <span class="meta">{note_id}</span></li>')
    rows.append("</ul>")
    return "\n".join(rows)


def render_index(notes: list[LoadedNote]) -> str:
    domains = [item for item in notes if isinstance(item.note, DomainGuide)]
    fixes = [item for item in notes if isinstance(item.note, FixNote)]
    body = f"""  <h1>PriorArt</h1>
  <p>Domain guides and verified fix recipes. Search them through the MCP server.</p>
  <p class="meta">Published search index:
  <a href="{html.escape(DEFAULT_INDEX_URL)}">{html.escape(DEFAULT_INDEX_URL)}</a></p>
  <h2>Domain guides</h2>
  {_group_items(domains, "domains")}
  <h2>Fix recipes</h2>
  {_group_items(fixes, "fixes")}
  <p class="meta">Example notes are marked on their pages. Ignored by search.</p>
  <p class="meta"><a href="{html.escape(PAGES_URL)}">Pages</a>
  · <a href="https://github.com/{REPO}">Repository</a></p>
"""
    return _page("PriorArt notes", body, depth=0)


def build_site(root: Path, output: Path) -> int:
    loaded, errors = load_tree(root)
    if errors:
        raise ValueError("\n".join(errors))
    output.mkdir(parents=True, exist_ok=True)
    (output / "style.css").write_text(_CSS, encoding="utf-8")
    (output / "index.html").write_text(render_index(loaded), encoding="utf-8")
    for folder, model in (("domains", DomainGuide), ("fixes", FixNote)):
        destination = output / folder
        destination.mkdir(exist_ok=True)
        for item in loaded:
            if isinstance(item.note, model):
                page = destination / f"{item.note.id}.html"
                page.write_text(render_note(item), encoding="utf-8")
    return len(loaded)
