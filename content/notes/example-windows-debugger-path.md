---
id: example-windows-debugger-path
title: Map a debugger source path without a personal profile directory
problem_summary: >
  A native debugger opens sources using absolute paths recorded on the machine
  that built the binary. Those paths miss on another checkout, and hardcoding a
  Windows profile directory would publish a personal username. Map the foreign
  root onto this workspace and pass paths through environment variables.
tags:
  - debugger
  - vscode
  - windows
platforms:
  - name: windows
    versions: ["10", "11"]
  - name: wsl
    versions: ["2"]
recipe:
  - name: Map the foreign source root in launch.json
    detail: >
      Point cppdbg at the sources in this workspace. The placeholder on the
      right is the workspace folder, not a user profile path.
    language: json
    code: |
      {
        "version": "0.2.0",
        "configurations": [
          {
            "name": "Debug",
            "type": "cppdbg",
            "request": "launch",
            "program": "${workspaceFolder}/build/app.exe",
            "sourceFileMap": {
              "/original/source/root": "${workspaceFolder}"
            }
          }
        ]
      }
  - name: Set the native source path from the profile environment variable
    detail: >
      When a native debugger needs a directory, derive it from USERPROFILE
      instead of writing a username into the note.
    language: powershell
    code: |
      $env:_NT_SOURCE_PATH = Join-Path $env:USERPROFILE "src"
verification:
  - name: Confirm the workspace mapping is present
    detail: The launch configuration contains sourceFileMap and does not name a user profile directory.
    language: powershell
    code: |
      Select-String -Path .\.vscode\launch.json -Pattern "sourceFileMap"
  - name: Confirm the source path uses the profile variable
    detail: The process environment exposes _NT_SOURCE_PATH under the current profile.
    language: powershell
    code: |
      Test-Path $env:_NT_SOURCE_PATH
sources:
  - url: https://example.com/priorart/example/official/source-file-map
    title: Example official note on debugger source maps
    type: official-docs
    published: 2026-02-11
    retrieved: 2026-09-27
  - url: https://example.com/priorart/example/official/environment-paths
    title: Example official note on environment-based source paths
    type: official-docs
    published: 2026-04-02
    retrieved: 2026-09-27
  - url: https://example.com/priorart/example/community/source-map-windows
    title: Example community thread on Windows source maps
    type: community
    published: 2026-08-01
    retrieved: 2026-09-27
  - url: https://example.com/priorart/example/community/wsl-debugger-paths
    title: Example community thread on WSL debugger paths
    type: community
    published: 2026-09-02
    retrieved: 2026-09-27
  - url: https://example.com/priorart/example/issues/cppdbg-source-map
    title: Example GitHub issue about cppdbg source maps
    type: github-issue
    published: 2026-05-02
    retrieved: 2026-09-27
  - url: https://example.com/priorart/example/repos/source-map-helper
    title: Example repository that rewrites debugger source maps
    type: github-repo
    published: 2026-09-12
    retrieved: 2026-09-27
created: 2026-09-27
last_refreshed: 2026-09-27
refresh_due: 2026-10-27
example: true
---

> **Example only.** This note is fictional scaffolding so the repository has a
> valid sample. It is excluded from the search index and from the monthly
> refresh queue. Do not apply it as a verified fix. Every URL points at
> example.com and is not a real citation.
