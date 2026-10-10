"""Data contracts only; AI output semantics belong to later phases."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

Count = Annotated[int, Field(strict=True, ge=0)]
Positive = Annotated[int, Field(strict=True, ge=1)]
Text = Annotated[str, Field(min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AccountInput(Contract):
    name: Text
    creator_type: Literal["new", "existing"]


class ResearchInput(Contract):
    source_url: str | None = None
    title: Text
    body: str
    likes: Count | None = None
    collects: Count | None = None
    comments: Count | None = None
    comment_samples: list[str] = Field(default_factory=list)
    analysis: dict[str, JsonValue] | None = None
    confirmed_for_topic: bool = False


class TopicInput(Contract):
    rank: Annotated[int, Field(strict=True, ge=1, le=3)]
    content: dict[str, JsonValue]
    research_ids: Annotated[list[str], Field(min_length=1)]


class DraftContent(Contract):
    title: str = ""
    hook: str = ""
    body: str = ""
    cta: str = ""
    tags: list[str] = Field(default_factory=list)
    cover_text: str = ""
    visual_suggestions: list[str] = Field(default_factory=list)
    facts_to_verify: list[str] = Field(default_factory=list)


class ProviderUsage(Contract):
    """Only instantiate with usage actually returned by the provider; no estimates."""

    source: Text
    tokens: Count | None = None
    cost: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    currency: str | None = None
    raw: dict[str, JsonValue]


class Record(Contract):
    id: str
    created_at: str


class Account(Record, AccountInput):
    current_profile_version_id: str | None


class ProfileVersion(Record):
    account_id: str
    version: Positive
    raw_input: dict[str, JsonValue]


class Diagnosis(Record):
    account_id: str
    profile_version_id: str
    result: dict[str, JsonValue]
    status: Literal["pending", "confirmed"]


class ResearchItem(Record, ResearchInput):
    account_id: str
    updated_at: str


class TopicRecommendation(Record):
    account_id: str
    profile_version_id: str
    diagnosis_id: str
    not_recommended: list[JsonValue]


class Topic(Record):
    account_id: str
    recommendation_id: str
    rank: Positive
    content: dict[str, JsonValue]


class Draft(Record):
    account_id: str
    topic_id: str
    latest_version_id: str | None


class DraftVersion(Record):
    account_id: str
    draft_id: str
    topic_id: str
    version: Positive
    content: DraftContent
    source_evidence: dict[str, JsonValue]


class WorkflowRun(Record):
    account_id: str
    workflow_id: str
    stage: Literal["diagnosis", "research_analysis", "topic_recommendation", "content_creation"]
    status: Literal["running", "succeeded", "failed"]
    model: str | None
    started_at: str
    completed_at: str | None
    latency: float | None
    error: str | None
    retry_count: Count
    tokens: Count | None
    cost: float | None
    usage: ProviderUsage | None


MODELS = {
    "accounts": Account,
    "profile_versions": ProfileVersion,
    "diagnoses": Diagnosis,
    "research_items": ResearchItem,
    "topic_recommendations": TopicRecommendation,
    "topics": Topic,
    "drafts": Draft,
    "draft_versions": DraftVersion,
    "workflow_runs": WorkflowRun,
}

JSON_FIELDS = {
    "raw_input", "result", "comment_samples", "analysis", "not_recommended",
    "content", "source_evidence", "usage",
}
