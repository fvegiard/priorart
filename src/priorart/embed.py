"""Embedding backends. FastEmbed runs locally; the hash backend is for tests."""

import hashlib
import math
import os
from typing import Protocol

from fastembed import TextEmbedding

from priorart.constants import EMBEDDING_MODEL, HASH_EMBEDDING_DIM, HASH_EMBEDDING_MODEL
from priorart.textutil import tokenize


class Embedder(Protocol):
    model_name: str
    dim: int

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _unit(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [round(value / norm, 6) for value in values]


class HashEmbedder:
    """Bag-of-tokens vectors. Deterministic and offline, not semantic."""

    model_name = HASH_EMBEDDING_MODEL
    dim = HASH_EMBEDDING_DIM

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "little") % self.dim
            vector[slot] += 1.0
        return _unit(vector)


class FastEmbedder:
    """BAAI/bge-small-en-v1.5 through FastEmbed. No API key."""

    model_name = EMBEDDING_MODEL
    dim = 384

    def __init__(self) -> None:
        self._model = TextEmbedding(model_name=self.model_name, cache_dir=_cache_dir())

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"passage: {text}" for text in texts]
        return [_unit([float(value) for value in vector]) for vector in self._model.embed(prefixed)]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._model.embed([f"query: {text}"])))
        return _unit([float(value) for value in vector])


def _cache_dir() -> str | None:
    return os.environ.get("FASTEMBED_CACHE_PATH")


def embedder_for(model_name: str) -> Embedder:
    if model_name == HashEmbedder.model_name:
        return HashEmbedder()
    if model_name == FastEmbedder.model_name:
        return FastEmbedder()
    raise ValueError(f"no local embedder for model {model_name}")


def embedder_by_kind(kind: str) -> Embedder:
    if kind == "hash":
        return HashEmbedder()
    if kind == "fastembed":
        return FastEmbedder()
    raise ValueError(f"unknown embedder {kind!r}; use hash or fastembed")
