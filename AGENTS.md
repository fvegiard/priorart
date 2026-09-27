# Research agent workflow

PriorArt has two note types. Domain guides are deep references for a technology or skill area. Fix recipes are specific problems with a root cause, a recipe, verification, and a rollback. A research agent adds or refreshes a note only by the steps below. A debugging agent reads notes through the MCP server and does not edit them.

## File layout

```
knowledge/domains/<id>.md                 domain guide (type: domain-guide)
knowledge/fixes/<id>.md                   fix recipe (type: fix)
knowledge/sources/domains/<id>.json       source pack for that domain guide
knowledge/sources/fixes/<id>.json         source pack for that fix
knowledge/domains/_template.md            copy this; leading-underscore files are ignored
knowledge/fixes/_template.md
knowledge/sources/domains/_template.json
knowledge/sources/fixes/_template.json
```

`<id>` is lowercase kebab-case and matches the filename, the frontmatter `id`, and the pack `note_id`. Ids are unique across both folders. Example notes use an `example-` prefix and `example: true`. Real notes do not.

## Domain guides

`type` is `domain-guide`. Frontmatter fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable kebab-case id |
| `type` | yes | `domain-guide` |
| `title` | yes | One line |
| `summary` | yes | What the area covers |
| `tags` | yes | Kebab-case tags |
| `platforms` | yes | `{name, versions}` entries. `name` is a slug such as `windows` or `wsl` |
| `related_fixes` | yes | Fix ids that belong to this area. May be empty |
| `created` | yes | ISO date the guide was first written |
| `last_refreshed` | yes | ISO date of the last research pass |
| `refresh_due` | yes | 1 to 35 days after `last_refreshed` (about 30) |
| `sources_count` | yes | Must equal the number of references in the source pack |
| `example` | no | Default `false`. Must be `true` exactly when the id starts with `example-` |

## Fix recipes

`type` is `fix`. Frontmatter fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable kebab-case id |
| `type` | yes | `fix` |
| `title` | yes | One line |
| `problem_summary` | yes | What breaks, without a personal path |
| `root_cause` | yes | Why it breaks |
| `tags` | yes | Kebab-case tags |
| `platforms` | yes | `{name, versions}` entries |
| `domains` | yes | One or more domain-guide ids |
| `recipe` | yes | Ordered steps. At least one step includes `code` and `language` |
| `verification` | yes | Steps that fail before the fix and pass after it |
| `rollback` | yes | Steps that undo the recipe |
| `sources` | yes | Cited sources. Each URL must match a pack reference exactly |
| `created` | yes | ISO date the note was first written |
| `last_refreshed` | yes | ISO date of the last research pass |
| `refresh_due` | yes | 1 to 35 days after `last_refreshed` (about 30) |
| `example` | no | Default `false`. Must be `true` exactly when the id starts with `example-` |

## Links

CI rejects a fix whose `domains` entry is not a domain guide, and a domain guide whose `related_fixes` entry is not a fix. The link is bidirectional: a fix names the domain, and that domain lists the fix.

## Source packs

Every note has a JSON pack:

```json
{
  "note_id": "<id>",
  "collected_at": "YYYY-MM-DD",
  "references": []
}
```

Each reference has `url` (https), `title`, `type`, `published`, `retrieved`, and `relevance`.

Source `type` is one of `official-docs`, `community`, `github-issue`, `github-discussion`, `github-repo`, `other`.

JSON Schema is in `schema/domain-guide.schema.json`, `schema/fix.schema.json`, and `schema/source-pack.schema.json`.

## Source minimums and freshness

- A real note's pack has **at least 25** references. Example notes are exempt. A domain guide's `sources_count` must match the pack length.
- Community posts (`type: community`, including Microsoft and Windows developer community threads) must have `published` **no more than 92 days** before `retrieved`. That is the 3-month rule. Drop or replace anything older.
- Official docs, GitHub issues, and GitHub discussions may be older. Record `published` and `retrieved` for every pack reference.
- GitHub repos (`type: github-repo`) should be ones that already solve the problem (bots, agent skills, MCP servers, scripts) and that were active recently. Put that last-activity date in `published`.
- Every URL cited in a fix's `sources` list is copied into the pack with the same title, type, and dates.

## Privacy

The repository is public. Do not commit:

- A home-directory path whose folder is a real account. On Windows write `C:\Users\<USER>\`, `%USERPROFILE%`, or `$env:USERPROFILE`. On macOS and Linux write `$HOME` or `/home/<USER>`.
- Email addresses. `dev@example.com` is the only acceptable illustration.
- Tokens and keys (GitHub PATs, cloud keys, Slack tokens, GitLab PATs).
- Internal DNS names (suffixes `.internal`, `.corp`, `.lan`, `.local`, `.localdomain`) and UNC paths that name a real host. Use `\\<HOST>\share` in prose.

`uv run priorart privacy` and gitleaks (`.gitleaks.toml`, default rules plus those custom rules) both run in CI.

## Add or refresh a note

1. Search first: `uv run priorart search "<problem>" --source auto`. Use `--type domain-guide` or `--type fix` to limit the kind. On a refresh, edit the existing id. Do not create a second note for the same subject.
2. Read the matching `_template.md` and `_template.json` if you are adding a note.
3. Collect 25 or more sources: official docs, community posts no older than 3 months, GitHub issues and discussions, and recently active repositories that already cover the area or the fix.
4. Write the note and the pack. A fix recipe must be specific enough to apply in one attempt, including the code, verification, and rollback. A domain guide explains the area and lists the related fix ids.
5. Point every fix at one or more domain guides, and list that fix on each of those guides.
6. Set `created` once. On every refresh set `last_refreshed` to today and `refresh_due` about 30 days later (never more than 35). Set `sources_count` on a domain guide to the pack length.
7. Example notes include an `Example only` banner in the body. Real notes leave `example` false.
8. Run `uv run priorart validate` and `uv run priorart privacy`.
9. Commit with a Conventional Commit. Open a pull request and complete the template checklist.

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
