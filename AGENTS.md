# Research agent workflow

PriorArt notes are verified fix recipes. A research agent adds or refreshes a note only by the steps below. A debugging agent reads notes through the MCP server and does not edit them.

## File layout

```
content/notes/<id>.md          fix note (YAML frontmatter + optional body)
content/sources/<id>.json      raw source pack for that id
content/notes/_template.md     copy this; leading-underscore files are ignored
content/sources/_template.json
```

`<id>` is lowercase kebab-case and matches the filename, the frontmatter `id`, and the pack `note_id`. Example notes use an `example-` prefix and `example: true`. Real notes do not.

## Schema

Frontmatter fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable kebab-case id |
| `title` | yes | One line |
| `problem_summary` | yes | What breaks, without a personal path |
| `tags` | yes | Kebab-case tags |
| `platforms` | yes | `{name, versions}` entries. `name` is a slug such as `windows` or `wsl` |
| `recipe` | yes | Ordered steps. At least one step includes `code` and `language` |
| `verification` | yes | Steps that fail before the fix and pass after it |
| `sources` | yes | Cited sources. Each URL must match a pack reference exactly |
| `created` | yes | ISO date the note was first written |
| `last_refreshed` | yes | ISO date of the last research pass |
| `refresh_due` | yes | 1 to 35 days after `last_refreshed` (about 30) |
| `example` | no | Default `false`. Must be `true` exactly when the id starts with `example-` |

Each source, in the note and in the pack, has `url` (https), `title`, `type`, `retrieved`, and `published` when a publication or last-activity date exists.

`type` is one of `official-docs`, `community`, `github-issue`, `github-discussion`, `github-repo`, `other`.

The pack is JSON:

```json
{
  "note_id": "<id>",
  "collected_at": "YYYY-MM-DD",
  "references": []
}
```

Each reference adds `why_relevant` and may add a short `excerpt`. JSON Schema for both documents is in `schema/`.

## Source minimums and freshness

- A real note's pack has **at least 25** references. Example notes are exempt.
- Community posts (`type: community`, including Microsoft and Windows developer community threads) must have `published` **no more than 92 days** before `retrieved`. That is the 3-month rule. Drop or replace anything older.
- Official docs, GitHub issues, and GitHub discussions may be older. Record `retrieved` for every source.
- GitHub repos (`type: github-repo`) should be ones that already solve the problem (bots, agent skills, MCP servers, scripts) and that were active recently. Put that last-activity date in `published`.
- Every URL cited in the note's `sources` list is copied into the pack with the same title, type, and dates.

## Privacy

The repository is public. Do not commit:

- A home-directory path whose folder is a real account. On Windows write `C:\Users\<USER>\`, `%USERPROFILE%`, or `$env:USERPROFILE`. On macOS and Linux write `$HOME` or `/home/<USER>`.
- Email addresses. `dev@example.com` is the only acceptable illustration.
- Tokens and keys (GitHub PATs, cloud keys, Slack tokens, GitLab PATs).
- Internal DNS names (suffixes `.internal`, `.corp`, `.lan`, `.local`, `.localdomain`) and UNC paths that name a real host. Use `\\<HOST>\share` in prose.

`uv run priorart privacy` and gitleaks (`.gitleaks.toml`, default rules plus those custom rules) both run in CI.

## Add or refresh a note

1. Search first: `uv run priorart search "<problem>" --source auto`. On a refresh, edit the existing id. Do not create a second note for the same fix.
2. Read `_template.md` and `_template.json` if you are adding a note.
3. Collect 25 or more sources: official docs, community posts no older than 3 months, GitHub issues and discussions, and recently active repositories that already solve it.
4. Write the note and the pack. Keep the recipe specific enough to apply in one attempt, including the code. Add verification that shows the fix held.
5. Set `created` once. On every refresh set `last_refreshed` to today and `refresh_due` about 30 days later (never more than 35).
6. Example notes start the body with `Example only.` Real notes leave `example` false.
7. Run `uv run priorart validate` and `uv run priorart privacy`.
8. Commit with a Conventional Commit. Open a pull request and complete the template checklist.

Monthly, `.github/workflows/refresh.yml` opens or updates one issue per due note, labelled `research-bot` and `refresh`. Work those issues with this same workflow. The issue body contains `<!-- priorart-note-id: <id> -->`; keep that marker.

## Conventional Commits

```
docs(notes): add windows debugger source map
docs(notes): refresh windows debugger source map
feat(mcp): add platform filter
fix(privacy): detect unc paths
ci: run gitleaks on pull requests
test: cover a short source pack
```

Types: `feat`, `fix`, `docs`, `test`, `ci`, `chore`, `refactor`. Use the `notes` scope for content. Subject is imperative, lowercase, and has no trailing period.
