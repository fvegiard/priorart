---
id: replace-with-kebab-case
type: problem
title: Short name of the error or failure
symptoms: >
  What is observed. Who hits it, and which messages or missing files show up.
  Do not include personal account names, email addresses, tokens, or internal hosts.
causes: >
  What published sources say causes it. Name the component and the condition.
tags:
  - replace-me
platforms:
  - name: windows
    versions: ["11"]
domains:
  - replace-with-domain-id
documented_solutions:
  - name: Documented change
    detail: >
      What a vendor or community source says to change. Quote the command.
      Priorart does not run it.
    language: powershell
    code: |
      Write-Output $env:USERPROFILE
verification:
  - name: Documented check
    detail: A check the sources say fails before the change and passes after it.
    language: powershell
    code: |
      Write-Output "ok"
caveats:
  - A limit, side effect, or case where the documented solution does not hold.
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

Copy this file to `knowledge/problems/<id>.md` and the pack template to
`knowledge/sources/problems/<id>.json`. Files whose names start with `_` are
templates and are not validated or indexed.

Real notes need at least 25 source-pack references. Set `example: false` and do
not use an `example-` id. Every id in `domains` must be an existing domain guide
that lists this problem in `related_problems`.

Use `$env:USERPROFILE`, `%USERPROFILE%`, or `C:\Users\<USER>\` when a documented
solution must mention a profile directory.
