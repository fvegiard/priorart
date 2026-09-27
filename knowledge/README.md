# Knowledge

Priorart stores knowledge for any AI agent or bot. It does not apply changes.

| Path | Role |
| --- | --- |
| `domains/<id>.md` | Domain guide. A deep reference for one technology or skill area. |
| `problems/<id>.md` | Problem knowledge. Symptoms, causes, documented solutions, verification methods, and caveats for one error or failure. |
| `sources/domains/<id>.json` | Source pack for that domain guide. Real guides need at least 25 references. |
| `sources/problems/<id>.json` | Source pack for that problem note. Real notes need at least 25 references. |
| `domains/_template.md` | Copy this when adding a domain guide. Leading `_` files are ignored. |
| `problems/_template.md` | Copy this when adding a problem note. |
| `*/example-*.md` | Fictional samples. `example: true` keeps them out of search and refresh. |

Each problem note lists one or more domain ids in `domains`. Each domain lists problem ids in `related_problems`. CI checks that both sides resolve and name each other.

The field names and the research workflow are defined in `AGENTS.md`.
