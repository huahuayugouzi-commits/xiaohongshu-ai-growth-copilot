"""Local Growth HTTP API, mounted under Easel's existing host/origin protection."""

import sqlite3
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .accounts import AccountRepository
from .database import Database
from .diagnosis_schema import AccountProfileInput, DiagnosisRequest
from .llm import ModelConfig
from .repository import Conflict, NotFound
from .service import DiagnosisFailure, GrowthService

router = APIRouter(prefix="/api/growth", tags=["Growth Copilot"])


@lru_cache(maxsize=1)
def get_service():
    database = Database()
    database.initialize()
    return GrowthService(AccountRepository(database))


def call(operation, *args):
    try:
        return operation(*args)
    except NotFound:
        raise HTTPException(404, "账号或记录不存在。") from None
    except Conflict:
        raise HTTPException(409, "数据已更新、任务正在运行或版本不匹配，请刷新后重试。") from None
    except sqlite3.Error:
        raise HTTPException(503, "数据库暂时不可用，请稍后重试。") from None


@router.get("/state")
def state(account_id: str | None = None, service=Depends(get_service)):
    result = call(service.repository.state, account_id)
    result["model_configured"] = ModelConfig.from_environment().ready
    return result


@router.post("/accounts", status_code=201)
def create_account(data: AccountProfileInput, service=Depends(get_service)):
    return call(service.save, data)


@router.put("/accounts/{account_id}/profile")
def save_profile(account_id: str, data: AccountProfileInput, service=Depends(get_service)):
    return call(service.save, data, account_id)


@router.post("/accounts/{account_id}/diagnoses")
async def diagnose(account_id: str, data: DiagnosisRequest, service=Depends(get_service)):
    try:
        return await service.diagnose(account_id, data)
    except DiagnosisFailure as exc:
        return JSONResponse({"detail": str(exc), "run_id": exc.run_id}, status_code=422)
    except NotFound:
        raise HTTPException(404, "账号或 Profile 不存在。") from None
    except Conflict:
        raise HTTPException(409, "Profile 已更新或有任务正在运行，请刷新后重试。") from None
    except sqlite3.Error:
        raise HTTPException(503, "数据库暂时不可用。") from None


@router.post("/accounts/{account_id}/diagnoses/{diagnosis_id}/confirm")
def confirm(account_id: str, diagnosis_id: str, service=Depends(get_service)):
    return call(service.confirm, account_id, diagnosis_id)


@router.post("/accounts/{account_id}/projection/retry")
def retry_projection(account_id: str, service=Depends(get_service)):
    return call(service.retry_projection, account_id)


@router.post("/accounts/{account_id}/runs/{run_id}/interrupt")
def interrupt_run(account_id: str, run_id: str, service=Depends(get_service)):
    # Explicit user recovery, not automatic failure/success after a guessed timeout.
    def interrupt():
        run = service.repository.get("workflow_runs", run_id, account_id=account_id)
        if run.stage != "diagnosis":
            raise Conflict("Not a diagnosis run")
        service.repository.finish_workflow(account_id, run_id, status="failed", error="用户手动标记任务为已中断；后续返回的结果将被拒绝。")
        return service.repository.state(account_id)
    return call(interrupt)
