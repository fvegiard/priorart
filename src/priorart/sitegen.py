"""Static HTML browser for the notes. GitHub Pages publishes the output."""

import html
from pathlib import Path

from priorart.constants import DEFAULT_INDEX_URL, PAGES_URL, REPO
from priorart.load import LoadedNote, load_note, note_paths
from priorart.models import Step

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


def render_note(loaded: LoadedNote) -> str:
    note = loaded.note
    banner = ""
    if note.example:
        banner = (
            '<p class="banner"><strong>Example only.</strong> '
            "This note is fictional scaffolding and is excluded from search.</p>"
        )
    platforms = ", ".join(
        html.escape(platform.name)
        + (f" ({html.escape(', '.join(platform.versions))})" if platform.versions else "")
        for platform in note.platforms
    )
    tags = ", ".join(html.escape(tag) for tag in note.tags)
    sources = ["<ul>"]
    for source in note.sources:
        published = source.published.isoformat() if source.published else "undated"
        sources.append(
            "<li>"
            f'<a href="{html.escape(source.url)}">{html.escape(source.title)}</a>'
            f" ({html.escape(source.type.value)}; published {html.escape(published)}; "
            f"retrieved {html.escape(source.retrieved.isoformat())})"
            "</li>"
        )
    sources.append("</ul>")
    paragraphs = [
        f"<p>{html.escape(chunk.strip())}</p>"
        for chunk in loaded.body.split("\n\n")
        if chunk.strip()
    ]
    blob = f"https://github.com/{REPO}/blob/main/content/sources/{note.id}.json"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(note.title)}</title>
  <link rel="stylesheet" href="../style.css">
</head>
<body>
  <p><a href="../index.html">All notes</a></p>
  {banner}
  <h1>{html.escape(note.title)}</h1>
  <p class="meta">{html.escape(note.id)} · {tags} · {platforms}</p>
  <p class="meta">Created {note.created.isoformat()}
  · refreshed {note.last_refreshed.isoformat()}
  · due {note.refresh_due.isoformat()}</p>
  <h2>Problem</h2>
  <p>{html.escape(note.problem_summary)}</p>
  {_steps("Recipe", list(note.recipe))}
  {_steps("Verification", list(note.verification))}
  <h2>Sources</h2>
  {"".join(sources)}
  <p><a href="{html.escape(blob)}">Raw source pack</a>
  ({len(loaded.pack.references)} references)</p>
  {"".join(paragraphs)}
</body>
</html>
"""


def render_index(notes: list[LoadedNote]) -> str:
    real = [item for item in notes if not item.note.example]
    examples = [item for item in notes if item.note.example]

    def items(group: list[LoadedNote]) -> str:
        if not group:
            return "<p>None yet.</p>"
        rows = ["<ul>"]
        for item in group:
            href = f"notes/{html.escape(item.note.id)}.html"
            title = html.escape(item.note.title)
            note_id = html.escape(item.note.id)
            rows.append(
                f'<li><a href="{href}">{title}</a> <span class="meta">{note_id}</span></li>'
            )
        rows.append("</ul>")
        return "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PriorArt notes</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>PriorArt</h1>
  <p>Verified fix notes. Search them through the MCP server; this site is for reading.</p>
  <p class="meta">Published search index:
  <a href="{html.escape(DEFAULT_INDEX_URL)}">{html.escape(DEFAULT_INDEX_URL)}</a></p>
  <h2>Notes</h2>
  {items(real)}
  <h2>Examples</h2>
  <p class="meta">Ignored by search.</p>
  {items(examples)}
  <p class="meta"><a href="{html.escape(PAGES_URL)}">Pages</a> · <a href="https://github.com/{REPO}">Repository</a></p>
</body>
</html>
"""


def build_site(root: Path, output: Path) -> int:
    notes_dir = root / "content" / "notes"
    sources_dir = root / "content" / "sources"
    loaded = [load_note(path, sources_dir) for path in note_paths(notes_dir)]
    output.mkdir(parents=True, exist_ok=True)
    notes_out = output / "notes"
    notes_out.mkdir(exist_ok=True)
    (output / "style.css").write_text(_CSS, encoding="utf-8")
    (output / "index.html").write_text(render_index(loaded), encoding="utf-8")
    for item in loaded:
        (notes_out / f"{item.note.id}.html").write_text(render_note(item), encoding="utf-8")
    return len(loaded)
