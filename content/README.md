# Content

| Path | Role |
| --- | --- |
| `notes/<id>.md` | Fix note. YAML frontmatter is the schema; the body is optional context. |
| `sources/<id>.json` | Raw source pack for that note. Real notes need at least 25 references. |
| `notes/_template.md` | Copy this when adding a note. Leading `_` files are ignored. |
| `sources/_template.json` | Matching pack template. |
| `notes/example-*.md` | Fictional samples. `example: true` keeps them out of search and refresh. |

The field names and the research workflow are defined in `AGENTS.md`.
