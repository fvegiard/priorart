"""Tokenization and the text that gets embedded for a note."""

import re
from typing import assert_never

from priorart.models import DomainGuide, FixNote, KnowledgeNote, SourcePack

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


def document_text(note: KnowledgeNote, pack: SourcePack) -> str:
    parts = [note.title, note.type.value, " ".join(note.tags)]
    for platform in note.platforms:
        parts.append(platform.name)
        parts.extend(platform.versions)
    match note:
        case DomainGuide() as guide:
            parts.append(guide.summary)
            parts.extend(guide.related_fixes)
        case FixNote() as fix:
            parts.append(fix.problem_summary)
            parts.append(fix.root_cause)
            parts.extend(fix.domains)
            for step in [*fix.recipe, *fix.verification, *fix.rollback]:
                parts.append(step.name)
                parts.append(step.detail)
                if step.code:
                    parts.append(step.code)
            for source in fix.sources:
                parts.append(source.title)
        case _ as other:
            assert_never(other)
    for reference in pack.references:
        parts.append(reference.title)
        parts.append(reference.relevance)
    return "\n".join(parts)
