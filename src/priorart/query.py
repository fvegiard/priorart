"""Hybrid search: reciprocal rank fusion of cosine similarity and BM25."""

import math
from dataclasses import dataclass

from priorart.embed import Embedder
from priorart.models import IndexedNote, NoteKind, SearchHit, SearchIndex, SearchResponse
from priorart.textutil import tokenize

_K1 = 1.5
_B = 0.75
_RRF_K = 60


@dataclass
class _BM25:
    docs: list[list[str]]
    avgdl: float
    idf: dict[str, float]
    k1: float = _K1
    b: float = _B

    @classmethod
    def build(cls, docs: list[list[str]]) -> "_BM25":
        df: dict[str, int] = {}
        for tokens in docs:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1
        count = len(docs)
        idf = {
            token: math.log(1.0 + (count - freq + 0.5) / (freq + 0.5)) for token, freq in df.items()
        }
        total = sum(len(tokens) for tokens in docs)
        avgdl = (total / count) if count else 0.0
        return cls(docs=docs, avgdl=avgdl, idf=idf)

    def score(self, query: list[str], index: int) -> float:
        tokens = self.docs[index]
        if not tokens or self.avgdl == 0:
            return 0.0
        frequencies: dict[str, int] = {}
        for token in tokens:
            frequencies[token] = frequencies.get(token, 0) + 1
        length = len(tokens)
        total = 0.0
        for token in query:
            idf = self.idf.get(token)
            if idf is None:
                continue
            freq = frequencies.get(token, 0)
            denom = freq + self.k1 * (1 - self.b + self.b * length / self.avgdl)
            total += idf * (freq * (self.k1 + 1)) / denom
        return total


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding lengths differ")
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for x_value, y_value in zip(left, right, strict=True):
        dot += x_value * y_value
        left_norm += x_value * x_value
        right_norm += y_value * y_value
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / math.sqrt(left_norm * right_norm)


def _filter_notes(
    notes: list[IndexedNote],
    *,
    tag: str | None,
    platform: str | None,
    note_type: NoteKind | None,
) -> list[IndexedNote]:
    selected: list[IndexedNote] = []
    tag_key = tag.casefold() if tag else None
    platform_key = platform.casefold() if platform else None
    for note in notes:
        if note_type is not None and note.note_type is not note_type:
            continue
        if tag_key is not None and tag_key not in {item.casefold() for item in note.tags}:
            continue
        if platform_key is not None and platform_key not in {
            item.name.casefold() for item in note.platforms
        }:
            continue
        selected.append(note)
    return selected


def _order(pairs: list[tuple[str, float]]) -> list[str]:
    return [note_id for note_id, _score in sorted(pairs, key=lambda item: (-item[1], item[0]))]


def _fuse(rankings: list[list[str]]) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, note_id in enumerate(ranking, start=1):
            scores[note_id] = scores.get(note_id, 0.0) + 1.0 / (_RRF_K + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _hit(note: IndexedNote, score: float) -> SearchHit:
    return SearchHit(
        id=note.id,
        note_type=note.note_type,
        title=note.title,
        summary=note.summary,
        tags=list(note.tags),
        platforms=list(note.platforms),
        score=round(score, 6),
        last_refreshed=note.last_refreshed,
        refresh_due=note.refresh_due,
        related_fixes=list(note.related_fixes),
        sources_count=note.sources_count,
        problem_summary=note.problem_summary,
        root_cause=note.root_cause,
        recipe=list(note.recipe),
        verification=list(note.verification),
        rollback=list(note.rollback),
        domains=list(note.domains),
        sources=list(note.sources),
    )


def search_index(
    index: SearchIndex,
    query: str,
    *,
    embedder: Embedder | None,
    top_k: int,
    tag: str | None = None,
    platform: str | None = None,
    note_type: NoteKind | None = None,
    origin: str,
) -> SearchResponse:
    selected = _filter_notes(index.notes, tag=tag, platform=platform, note_type=note_type)
    kind = note_type.value if note_type is not None else None
    if not selected:
        return SearchResponse(
            query=query, origin=origin, retrieval="keyword", note_type=kind, results=[]
        )

    tokens = [tokenize(note.text) for note in selected]
    bm25 = _BM25.build(tokens)
    query_tokens = tokenize(query)
    keyword_scores = [
        (note.id, bm25.score(query_tokens, position)) for position, note in enumerate(selected)
    ]
    keyword_rank = _order(keyword_scores)

    warning: str | None = None
    retrieval = "keyword"
    fused: list[tuple[str, float]]
    if embedder is None:
        warning = "keyword search only; no embedder is available for this index"
        fused = keyword_scores
        fused.sort(key=lambda item: (-item[1], item[0]))
    elif embedder.model_name != index.model or embedder.dim != index.embedding_dim:
        warning = (
            f"keyword search only; embedder {embedder.model_name} "
            f"does not match index model {index.model}"
        )
        fused = keyword_scores
        fused.sort(key=lambda item: (-item[1], item[0]))
    else:
        query_vector = embedder.embed_query(query)
        semantic_scores = [(note.id, _cosine(query_vector, note.embedding)) for note in selected]
        fused = _fuse([_order(semantic_scores), keyword_rank])
        retrieval = "hybrid"

    by_id = {note.id: note for note in selected}
    hits = [_hit(by_id[note_id], score) for note_id, score in fused[:top_k]]
    return SearchResponse(
        query=query,
        origin=origin,
        retrieval=retrieval,
        note_type=kind,
        warning=warning,
        results=hits,
    )
