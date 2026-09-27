---
id: example-windows-debugger
type: domain-guide
title: Windows debugger source paths and cppdbg maps
summary: >
  How native debuggers and cppdbg resolve source files on Windows and WSL.
  Covers source file maps, _NT_SOURCE_PATH, workspace-relative roots, and the
  difference between a build-machine path and the checkout that is open now.
tags:
  - debugger
  - vscode
  - windows
platforms:
  - name: windows
    versions: ["10", "11"]
  - name: wsl
    versions: ["2"]
related_fixes:
  - example-windows-debugger-path
sources_count: 25
created: 2026-09-27
last_refreshed: 2026-09-27
refresh_due: 2026-10-27
example: true
---

> **Example only.** This domain guide is fictional scaffolding. It is excluded
> from the search index and from the monthly refresh queue. Every URL points
> at example.com and is not a real citation.

## What this area covers

A debugger opens a source file by a path stored in the binary or in the symbol
file. On Windows that path is often absolute and belongs to the machine that
compiled the code. cppdbg can rewrite one root with `sourceFileMap`. Native
debuggers also consult `_NT_SOURCE_PATH`.

## How the pieces fit

The build records a source root. The debugger asks for a file under that root.
A map or a source path tells it to look in the open workspace instead. Profile
directories stay behind environment variables so a public note never names an
account.

## Related fixes

`example-windows-debugger-path` is the sample recipe for applying that map
without writing a personal profile path into the repository.
