# Contributing

Content changes follow [AGENTS.md](AGENTS.md). That file is the contract for adding or refreshing a fix note: layout, schema, the 25-source minimum, the 92-day community freshness rule, privacy, and commit messages.

Code changes use the same commit style. Before a pull request:

```bash
uv sync --all-groups
uv run ruff check
uv run ruff format --check
uv run pyright
uv run pytest
uv run priorart validate
uv run priorart privacy
```

If you change `DomainGuide`, `FixNote`, or `SourcePack`, regenerate the schemas and commit them:

```bash
uv run priorart export-schema
```

Pull requests use `.github/PULL_REQUEST_TEMPLATE.md`. CI must be green. The search index is rebuilt on `main` and published as a GitHub Release; do not commit `dist/`.
