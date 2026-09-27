## Summary

<!-- What changed and why. Link the note id when this PR adds or refreshes one. -->

## Checklist

- [ ] Note id, filename, and the source pack `note_id` match (`knowledge/sources/domains/` or `knowledge/sources/fixes/`)
- [ ] Fix `domains` and domain `related_fixes` resolve to each other
- [ ] Real notes cite at least 25 source-pack references; a domain guide's `sources_count` matches the pack; `example: true` is only for `example-` ids
- [ ] Community sources were published no more than 92 days before `retrieved`
- [ ] `refresh_due` is within 35 days of `last_refreshed`
- [ ] No personal paths, emails, tokens, or internal hostnames (`uv run priorart privacy`)
- [ ] `uv run priorart validate` passes
- [ ] Commit messages follow Conventional Commits

## Notes for the reviewer

<!-- Which recipe step changed, and how you verified it. -->
