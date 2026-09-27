# Knowledge

| Path | Role |
| --- | --- |
| `domains/<id>.md` | Domain guide. A deep reference for one technology or skill area. |
| `fixes/<id>.md` | Fix recipe. One problem, with root cause, recipe, verification, and rollback. |
| `sources/domains/<id>.json` | Source pack for that domain guide. Real guides need at least 25 references. |
| `sources/fixes/<id>.json` | Source pack for that fix. Real fixes need at least 25 references. |
| `domains/_template.md` | Copy this when adding a domain guide. Leading `_` files are ignored. |
| `fixes/_template.md` | Copy this when adding a fix. |
| `*/example-*.md` | Fictional samples. `example: true` keeps them out of search and refresh. |

Each fix lists one or more domain ids in `domains`. Each domain lists fix ids in `related_fixes`. CI checks that both sides resolve and name each other.

The field names and the research workflow are defined in `AGENTS.md`.
