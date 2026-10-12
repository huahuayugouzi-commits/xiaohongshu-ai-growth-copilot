"""Manual reference input only; no collection or model execution."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from urllib.parse import urlsplit

from .api import call, get_service
from .models import Count, ResearchInput
from .service import GrowthService

router = APIRouter(prefix="/api/growth/accounts/{account_id}/research", tags=["Growth Research"])


class ManualResearch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_url: str | None = Field(default=None, max_length=2048)
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=50000)
    likes: Count | None = None
    collects: Count | None = None
    comments: Count | None = None
    comment_samples: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value):
        if not value:
            return None
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
            raise ValueError("Use an http(s) source URL without credentials")
        return value

    @field_validator("comment_samples")
    @classmethod
    def samples(cls, values):
        if any(not v.strip() or len(v) > 3000 for v in values):
            raise ValueError("Comment samples must be nonempty and at most 3000 characters")
        return [v.strip() for v in values]


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed_for_topic: StrictBool


@router.get("")
def list_items(account_id: str, limit: int = Query(1000, ge=1, le=1000),
               offset: int = Query(0, ge=0), service: GrowthService = Depends(get_service)):
    def operation():
        service.repository.get("accounts", account_id, account_id=account_id)
        return service.repository.list("research_items", account_id=account_id, limit=limit, offset=offset)
    return call(operation)


@router.post("", status_code=201)
def create_item(account_id: str, data: ManualResearch, service: GrowthService = Depends(get_service)):
    return call(service.repository.create_research, account_id, ResearchInput(**data.model_dump()))


@router.patch("/{research_id}/confirmation")
def confirm_item(account_id: str, research_id: str, data: Confirmation, service: GrowthService = Depends(get_service)):
    return call(service.repository.confirm_research, account_id, research_id, data.confirmed_for_topic)
