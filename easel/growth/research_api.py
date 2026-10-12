"""Manual reference input only; no collection or model execution."""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from urllib.parse import urlsplit

from .api import call, get_service
from .models import Count, ResearchInput
from .service import GrowthService
from .research_analysis import ResearchModel, ResearchAnalysisRepository, ResearchAnalysisFailure, analyze_item

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
    item = call(lambda: service.repository.get('research_items', research_id, account_id=account_id))
    if data.confirmed_for_topic and item.analysis and item.analysis.get('status') in {'running', 'failed'}:
        raise HTTPException(409, '请先完成分析，再确认用于选题。')
    return call(service.repository.confirm_research, account_id, research_id, data.confirmed_for_topic)


def get_research_model():
    return ResearchModel()


@router.post('/{research_id}/analysis')
async def analyze(account_id: str, research_id: str, service: GrowthService = Depends(get_service), model=Depends(get_research_model)):
    from .repository import Conflict, NotFound
    try:
        return await analyze_item(ResearchAnalysisRepository(service.repository.database), model, account_id, research_id)
    except ResearchAnalysisFailure as exc:
        raise HTTPException(422, str(exc)) from None
    except NotFound:
        raise HTTPException(404, '参考内容不存在。') from None
    except Conflict:
        raise HTTPException(409, '请确认当前定位，或等待/中断正在运行的分析。') from None


@router.post('/{research_id}/analysis/interrupt')
def interrupt_analysis(account_id: str, research_id: str, service: GrowthService = Depends(get_service)):
    return call(ResearchAnalysisRepository(service.repository.database).interrupt, account_id, research_id)
