---
id: replace-with-kebab-case
type: fix
title: Short description of the verified fix
problem_summary: >
  One paragraph. What breaks, who hits it, and what a successful fix changes.
  Do not include personal account names, email addresses, tokens, or internal hosts.
root_cause: >
  Why the failure happens. Name the component and the condition, not a personal path.
tags:
  - replace-me
platforms:
  - name: windows
    versions: ["11"]
domains:
  - replace-with-domain-id
recipe:
  - name: First change
    detail: What to change and why this step is safe to repeat.
    language: powershell
    code: |
      Write-Output $env:USERPROFILE
verification:
  - name: Show the fix held
    detail: A command or check that fails before the fix and passes after it.
    language: powershell
    code: |
      Write-Output "ok"
rollback:
  - name: Undo the change
    detail: How to put the machine back if the recipe should not stay applied.
    language: powershell
    code: |
      Write-Output "rolled back"
sources:
  - url: https://example.com/replace-me
    title: Replace with the cited source title
    type: official-docs
    published: 2026-01-15
    retrieved: 2026-09-27
created: 2026-09-27
last_refreshed: 2026-09-27
refresh_due: 2026-10-27
example: false
---

Copy this file to `knowledge/fixes/<id>.md` and the pack template to
`knowledge/sources/fixes/<id>.json`. Files whose names start with `_` are
templates and are not validated or indexed.

Real notes need at least 25 source-pack references. Set `example: false` and do
not use an `example-` id. Every id in `domains` must be an existing domain guide
that lists this fix in `related_fixes`.

Use `$env:USERPROFILE`, `%USERPROFILE%`, or `C:\Users\<USER>\` when a recipe must
mention a profile directory.
