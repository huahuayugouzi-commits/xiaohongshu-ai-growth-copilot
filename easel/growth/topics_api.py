import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .api import get_service, call
from .repository import Conflict, NotFound
from .topics import TopicRepository, TopicFailure, recommend
from .topic_model import TopicModel

router = APIRouter(prefix='/api/growth/accounts/{account_id}/topics', tags=['Growth Topics'])


def repository(service=Depends(get_service)): return TopicRepository(service.repository.database)
def get_model(): return TopicModel()


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    research_ids: list[str] = Field(min_length=1, max_length=3)
    retry_of: str | None = None


@router.get('')
def state(account_id: str, repo=Depends(repository)):
    return call(repo.state, account_id)


@router.post('/recommendations', status_code=201)
async def generate(account_id: str, data: GenerateRequest, repo=Depends(repository), model=Depends(get_model)):
    try:
        await recommend(repo, model, account_id, data.research_ids, data.retry_of)
        return repo.state(account_id)
    except NotFound: raise HTTPException(404, '账号或参考内容不存在。') from None
    except Conflict: raise HTTPException(409, '请确认当前定位并选择 1–3 篇已分析且已确认的参考内容；有运行任务时请等待或中断。内容过长时请缩短后重试。') from None
    except TopicFailure as exc: raise HTTPException(422, str(exc)) from None
    except sqlite3.Error: raise HTTPException(503, '数据库暂时不可用，未确认任务成功。') from None


@router.get('/{topic_id}/evidence')
def evidence(account_id: str, topic_id: str, repo=Depends(repository)):
    return call(repo.evidence, account_id, topic_id)


@router.post('/runs/{run_id}/interrupt')
def interrupt(account_id: str, run_id: str, repo=Depends(repository)):
    call(repo.interrupt, account_id, run_id)
    return call(repo.state, account_id)
