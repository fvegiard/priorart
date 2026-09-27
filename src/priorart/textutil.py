"""Tokenization and the text that gets embedded for a note."""

import re

from priorart.models import Note, SourcePack

_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "with",
    }
)
_CAMEL = re.compile(r"([a-z])([A-Z])")
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    spaced = _CAMEL.sub(r"\1 \2", text).lower()
    return [token for token in _TOKEN.findall(spaced) if len(token) >= 2 and token not in _STOP]


def document_text(note: Note, pack: SourcePack) -> str:
    parts = [note.title, note.problem_summary, " ".join(note.tags)]
    for platform in note.platforms:
        parts.append(platform.name)
        parts.extend(platform.versions)
    for step in [*note.recipe, *note.verification]:
        parts.append(step.name)
        parts.append(step.detail)
        if step.code:
            parts.append(step.code)
    for source in note.sources:
        parts.append(source.title)
    for reference in pack.references:
        parts.append(reference.title)
    return "\n".join(parts)
