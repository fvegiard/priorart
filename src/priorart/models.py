"""Content model for domain guides, problem knowledge, and the published search index."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, assert_never

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


def _unique(values: list[str], label: str) -> None:
    folded = [value.casefold() for value in values]
    if len(folded) != len(set(folded)):
        raise ValueError(f"{label} must be unique")


def _check_source_dates(kind: "SourceType", published: date | None, retrieved: date) -> None:
    if published is not None and published > retrieved:
        raise ValueError("published is after retrieved")
    match kind:
        case SourceType.COMMUNITY:
            if published is None:
                raise ValueError("community sources need a published date")
            age = (retrieved - published).days
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


def _check_refresh(note_id: str, created: date, refreshed: date, due: date, example: bool) -> None:
    if example != note_id.startswith("example-"):
        raise ValueError(
            "example notes must use an example- id, and that prefix must set example: true"
        )
    if created > refreshed:
        raise ValueError("created is after last_refreshed")
    window = (due - refreshed).days
    if window < 1 or window > REFRESH_MAX_DAYS:
        raise ValueError(f"refresh_due must be 1 to {REFRESH_MAX_DAYS} days after last_refreshed")


class NoteKind(StrEnum):
    DOMAIN_GUIDE = "domain-guide"
    PROBLEM = "problem"


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
    """A source cited in a problem note. The pack copy adds relevance."""

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
        _check_source_dates(self.type, self.published, self.retrieved)
        return self


class SourcePackEntry(StrictModel):
    url: Annotated[str, Field(pattern=r"^https://\S+$", max_length=500)]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    type: SourceType
    published: date
    retrieved: date
    relevance: Annotated[str, Field(min_length=10, max_length=1000)]

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
    def check_dates(self) -> "SourcePackEntry":
        _check_source_dates(self.type, self.published, self.retrieved)
        return self


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


Slug = Annotated[str, Field(pattern=NOTE_ID_PATTERN)]
TagList = Annotated[list[Slug], Field(min_length=1, max_length=12)]
PlatformList = Annotated[list[Platform], Field(min_length=1, max_length=8)]


class DomainGuide(StrictModel):
    id: Slug
    type: Literal[NoteKind.DOMAIN_GUIDE]
    title: Annotated[str, Field(min_length=10, max_length=160)]
    summary: Annotated[str, Field(min_length=40, max_length=4000)]
    tags: TagList
    platforms: PlatformList
    related_problems: Annotated[list[Slug], Field(max_length=40)]
    created: date
    last_refreshed: date
    refresh_due: date
    sources_count: Annotated[int, Field(ge=1, le=80)]
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
    def check_guide(self) -> "DomainGuide":
        _check_refresh(self.id, self.created, self.last_refreshed, self.refresh_due, self.example)
        _unique(self.tags, "tags")
        _unique([platform.name for platform in self.platforms], "platforms")
        _unique(self.related_problems, "related_problems")
        return self


class ProblemNote(StrictModel):
    """What is known about one error or failure. Priorart records it and does not apply it."""

    id: Slug
    type: Literal[NoteKind.PROBLEM]
    title: Annotated[str, Field(min_length=10, max_length=160)]
    symptoms: Annotated[str, Field(min_length=40, max_length=2000)]
    causes: Annotated[str, Field(min_length=40, max_length=4000)]
    tags: TagList
    platforms: PlatformList
    domains: Annotated[list[Slug], Field(min_length=1, max_length=8)]
    documented_solutions: Annotated[list[Step], Field(min_length=1, max_length=20)]
    verification: Annotated[list[Step], Field(min_length=1, max_length=10)]
    caveats: Annotated[
        list[Annotated[str, Field(min_length=10, max_length=2000)]],
        Field(min_length=1, max_length=12),
    ]
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
    def check_problem(self) -> "ProblemNote":
        _check_refresh(self.id, self.created, self.last_refreshed, self.refresh_due, self.example)
        _unique(self.tags, "tags")
        _unique([platform.name for platform in self.platforms], "platforms")
        _unique(self.domains, "domains")
        _unique(self.caveats, "caveats")
        urls = [source.url for source in self.sources]
        if len(urls) != len(set(urls)):
            raise ValueError("cited source URLs must be unique")
        if not any(step.code for step in self.documented_solutions):
            raise ValueError("at least one documented solution must include the published code")
        return self


KnowledgeNote = DomainGuide | ProblemNote


class IndexedNote(StrictModel):
    id: str
    note_type: NoteKind
    title: str
    summary: str
    tags: list[str]
    platforms: list[Platform]
    source_pack: list[SourcePackEntry]
    created: date
    last_refreshed: date
    refresh_due: date
    example: bool
    text: str
    embedding: list[float]
    related_problems: list[str] = Field(default_factory=list)
    sources_count: int = 0
    symptoms: str = ""
    causes: str = ""
    documented_solutions: list[Step] = Field(default_factory=list)
    verification: list[Step] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


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
    note_type: NoteKind
    title: str
    summary: str
    tags: list[str]
    platforms: list[Platform]
    score: float
    last_refreshed: date
    refresh_due: date
    related_problems: list[str] = Field(default_factory=list)
    sources_count: int = 0
    symptoms: str = ""
    causes: str = ""
    documented_solutions: list[Step] = Field(default_factory=list)
    verification: list[Step] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)


class SearchResponse(StrictModel):
    query: str
    origin: str
    retrieval: str
    note_type: str | None = None
    warning: str | None = None
    results: list[SearchHit]


class ProblemRecord(StrictModel):
    id: str
    title: str
    symptoms: str
    causes: str
    tags: list[str]
    platforms: list[Platform]
    domains: list[str]
    documented_solutions: list[Step]
    verification: list[Step]
    caveats: list[str]
    sources: list[Source]
    source_pack: list[SourcePackEntry]
    created: date
    last_refreshed: date
    refresh_due: date
    example: bool


class DomainGuideRecord(StrictModel):
    id: str
    title: str
    summary: str
    tags: list[str]
    platforms: list[Platform]
    related_problems: list[str]
    problems: list[ProblemRecord]
    missing_problem_ids: list[str]
    sources_count: int
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
    note_types: list[TopicCount]


class DueNote(StrictModel):
    id: str
    note_type: NoteKind
    title: str
    last_refreshed: date
    refresh_due: date


class DueList(StrictModel):
    as_of: date
    notes: list[DueNote]
