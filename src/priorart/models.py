"""Content model for fix notes and the published search index."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, assert_never

from pydantic import BaseModel, ConfigDict, Field, model_validator

from priorart.constants import (
    COMMUNITY_MAX_AGE_DAYS,
    EMBEDDING_MODEL,
    INDEX_SCHEMA_VERSION,
    NOTE_ID_PATTERN,
    REFRESH_MAX_DAYS,
)


def _coerce_date(value: object) -> object:
    if isinstance(value, datetime):
        return value.date()
    return value


DateValue = Annotated[date, Field(description="ISO date, YYYY-MM-DD.")]


class SourceType(StrEnum):
    OFFICIAL_DOCS = "official-docs"
    COMMUNITY = "community"
    GITHUB_ISSUE = "github-issue"
    GITHUB_DISCUSSION = "github-discussion"
    GITHUB_REPO = "github-repo"
    OTHER = "other"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Platform(StrictModel):
    name: Annotated[str, Field(pattern=NOTE_ID_PATTERN, description="Platform slug.")]
    versions: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(default_factory=list)


class Step(StrictModel):
    name: Annotated[str, Field(min_length=3, max_length=120)]
    detail: Annotated[str, Field(min_length=10, max_length=2000)]
    language: Annotated[str, Field(pattern=r"^[A-Za-z0-9#+.-]{1,32}$")] | None = None
    code: Annotated[str, Field(min_length=1, max_length=8000)] | None = None

    @model_validator(mode="after")
    def code_names_its_language(self) -> "Step":
        if self.code is not None and self.language is None:
            raise ValueError("steps with code must set language")
        return self


class Source(StrictModel):
    url: Annotated[str, Field(pattern=r"^https://\S+$", max_length=500)]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    type: SourceType
    published: date | None = Field(default=None, description="Publication or last-activity date.")
    retrieved: date

    @model_validator(mode="before")
    @classmethod
    def coerce_dates(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        updated = dict(data)
        for key in ("published", "retrieved"):
            if key in updated:
                updated[key] = _coerce_date(updated[key])
        return updated

    @model_validator(mode="after")
    def check_dates(self) -> "Source":
        if self.published is not None and self.published > self.retrieved:
            raise ValueError("published is after retrieved")
        match self.type:
            case SourceType.COMMUNITY:
                if self.published is None:
                    raise ValueError("community sources need a published date")
                age = (self.retrieved - self.published).days
                if age > COMMUNITY_MAX_AGE_DAYS:
                    raise ValueError(
                        f"community source is {age} days old; maximum is {COMMUNITY_MAX_AGE_DAYS}"
                    )
            case (
                SourceType.OFFICIAL_DOCS
                | SourceType.GITHUB_ISSUE
                | SourceType.GITHUB_DISCUSSION
                | SourceType.GITHUB_REPO
                | SourceType.OTHER
            ):
                pass
            case _ as other:
                assert_never(other)
        return self


class SourcePackEntry(Source):
    excerpt: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    why_relevant: Annotated[str, Field(min_length=10, max_length=1000)]


class SourcePack(StrictModel):
    note_id: Annotated[str, Field(pattern=NOTE_ID_PATTERN)]
    collected_at: date
    references: Annotated[list[SourcePackEntry], Field(min_length=1, max_length=80)]

    @model_validator(mode="before")
    @classmethod
    def coerce_collected_at(cls, data: object) -> object:
        if isinstance(data, dict) and "collected_at" in data:
            updated = dict(data)
            updated["collected_at"] = _coerce_date(updated["collected_at"])
            return updated
        return data

    @model_validator(mode="after")
    def unique_urls(self) -> "SourcePack":
        urls = [item.url for item in self.references]
        if len(urls) != len(set(urls)):
            raise ValueError("source pack URLs must be unique")
        return self


class Note(StrictModel):
    id: Annotated[str, Field(pattern=NOTE_ID_PATTERN)]
    title: Annotated[str, Field(min_length=10, max_length=160)]
    problem_summary: Annotated[str, Field(min_length=40, max_length=2000)]
    tags: Annotated[
        list[Annotated[str, Field(pattern=NOTE_ID_PATTERN)]], Field(min_length=1, max_length=12)
    ]
    platforms: Annotated[list[Platform], Field(min_length=1, max_length=8)]
    recipe: Annotated[list[Step], Field(min_length=1, max_length=20)]
    verification: Annotated[list[Step], Field(min_length=1, max_length=10)]
    sources: Annotated[list[Source], Field(min_length=1, max_length=30)]
    created: date
    last_refreshed: date
    refresh_due: date
    example: bool = False

    @model_validator(mode="before")
    @classmethod
    def coerce_note_dates(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        updated = dict(data)
        for key in ("created", "last_refreshed", "refresh_due"):
            if key in updated:
                updated[key] = _coerce_date(updated[key])
        return updated

    @model_validator(mode="after")
    def check_note(self) -> "Note":
        if self.example != self.id.startswith("example-"):
            raise ValueError(
                "example notes must use an example- id, and that prefix must set example: true"
            )
        if self.created > self.last_refreshed:
            raise ValueError("created is after last_refreshed")
        window = (self.refresh_due - self.last_refreshed).days
        if window < 1 or window > REFRESH_MAX_DAYS:
            raise ValueError(
                f"refresh_due must be 1 to {REFRESH_MAX_DAYS} days after last_refreshed"
            )
        tags = [tag.casefold() for tag in self.tags]
        if len(tags) != len(set(tags)):
            raise ValueError("tags must be unique")
        names = [platform.name.casefold() for platform in self.platforms]
        if len(names) != len(set(names)):
            raise ValueError("platforms must be unique")
        urls = [source.url for source in self.sources]
        if len(urls) != len(set(urls)):
            raise ValueError("cited source URLs must be unique")
        if not any(step.code for step in self.recipe):
            raise ValueError("at least one recipe step must include code")
        return self


class IndexedNote(StrictModel):
    id: str
    title: str
    problem_summary: str
    tags: list[str]
    platforms: list[Platform]
    recipe: list[Step]
    verification: list[Step]
    sources: list[Source]
    source_pack: list[SourcePackEntry]
    created: date
    last_refreshed: date
    refresh_due: date
    example: bool
    text: str
    embedding: list[float]


class SearchIndex(StrictModel):
    schema_version: int = INDEX_SCHEMA_VERSION
    model: str = EMBEDDING_MODEL
    embedding_dim: Annotated[int, Field(ge=1)]
    built_at: datetime
    git_sha: Annotated[str, Field(min_length=1, max_length=80)]
    notes: list[IndexedNote]

    @model_validator(mode="after")
    def embeddings_match_dim(self) -> "SearchIndex":
        if self.schema_version != INDEX_SCHEMA_VERSION:
            raise ValueError(f"unsupported index schema {self.schema_version}")
        for note in self.notes:
            if len(note.embedding) != self.embedding_dim:
                raise ValueError(f"{note.id} embedding length does not match embedding_dim")
        return self


class IndexManifest(StrictModel):
    schema_version: int
    model: str
    embedding_dim: int
    built_at: datetime
    git_sha: str
    note_count: int
    note_ids: list[str]
    index_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    index_filename: str
    index_url: str


class SearchHit(StrictModel):
    id: str
    title: str
    problem_summary: str
    tags: list[str]
    platforms: list[Platform]
    score: float
    recipe: list[Step]
    verification: list[Step]
    sources: list[Source]
    last_refreshed: date
    refresh_due: date


class SearchResponse(StrictModel):
    query: str
    origin: str
    retrieval: str
    warning: str | None = None
    results: list[SearchHit]


class FixRecord(StrictModel):
    id: str
    title: str
    problem_summary: str
    tags: list[str]
    platforms: list[Platform]
    recipe: list[Step]
    verification: list[Step]
    sources: list[Source]
    source_pack: list[SourcePackEntry]
    created: date
    last_refreshed: date
    refresh_due: date
    example: bool


class TopicCount(StrictModel):
    name: str
    count: int


class TopicList(StrictModel):
    tags: list[TopicCount]
    platforms: list[TopicCount]


class DueNote(StrictModel):
    id: str
    title: str
    last_refreshed: date
    refresh_due: date


class DueList(StrictModel):
    as_of: date
    notes: list[DueNote]
