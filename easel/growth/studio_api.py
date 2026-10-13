import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from .api import get_service, call
from .repository import NotFound, Conflict
from .studio import StudioRepository, EditableDraft, DraftFailure, generate_draft
from .studio_model import DraftModel

router=APIRouter(prefix='/api/growth/accounts/{account_id}/studio',tags=['Growth Studio'])
def repository(service=Depends(get_service)): return StudioRepository(service.repository.database)
def get_model(): return DraftModel()
class Generate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    topic_id: str
    retry_of: str | None = None
class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    content: EditableDraft
    expected_latest_id: str

@router.get('')
def state(account_id: str, repo=Depends(repository)): return call(repo.state,account_id)
@router.post('/drafts',status_code=201)
async def generate(account_id: str, data: Generate, repo=Depends(repository), model=Depends(get_model)):
    try:
        draft=await generate_draft(repo,model,account_id,data.topic_id,data.retry_of)
        return {**repo.state(account_id),'created_draft_id':draft.id}
    except NotFound: raise HTTPException(404,'账号或选题不存在。') from None
    except Conflict: raise HTTPException(409,'请使用当前已确认定位的选题；已有运行任务时请等待或中断。') from None
    except DraftFailure as exc: raise HTTPException(422,str(exc)) from None
    except sqlite3.Error: raise HTTPException(503,'数据库暂时不可用，未确认保存成功。') from None
@router.post('/drafts/{draft_id}/versions')
def edit(account_id: str, draft_id: str, data: Edit, repo=Depends(repository)):
    call(repo.edit,account_id,draft_id,data.content,data.expected_latest_id)
    return call(repo.state,account_id)
@router.post('/runs/{run_id}/interrupt')
def interrupt(account_id: str, run_id: str, repo=Depends(repository)):
    call(repo.interrupt,account_id,run_id)
    return call(repo.state,account_id)
