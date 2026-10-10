"""Bounded diagnosis workflow. No silent fallback, no tools or automatic retries."""

import asyncio

from .accounts import AccountRepository
from .diagnosis_schema import FactLockError, ProfileFields, parse_diagnosis
from .llm import CompatibleModel, ModelError
from .projection import ProfileProjector
from .repository import Conflict


class DiagnosisFailure(Exception):
    def __init__(self, message, run_id):
        super().__init__(message)
        self.run_id = run_id


class GrowthService:
    def __init__(self, repository: AccountRepository, model=None, projector=None):
        self.repository = repository
        self.model = model if model is not None else CompatibleModel()
        self.projector = projector if projector is not None else ProfileProjector()

    def project(self, account, profile, diagnosis=None):
        repo = self.repository
        did = diagnosis.id if diagnosis else None
        repo.projection_status(account.id, profile.id, did, status="pending")
        try:
            path = self.projector.export(account, profile, diagnosis)
        except (OSError, ValueError):
            repo.projection_status(account.id, profile.id, did, status="failed", error="画像同步失败；数据库数据已保存，可重试同步。")
        else:
            repo.projection_status(account.id, profile.id, did, status="synced", relative_path=path)

    def save(self, data, account_id=None):
        account, profile = self.repository.save_account_profile(data, account_id)
        self.project(account, profile)
        return self.repository.state(account.id)

    def confirm(self, account_id, diagnosis_id):
        diagnosis = self.repository.confirm_current_diagnosis(account_id, diagnosis_id)
        account = self.repository.get("accounts", account_id, account_id=account_id)
        profile = self.repository.get("profile_versions", diagnosis.profile_version_id, account_id=account_id)
        self.project(account, profile, diagnosis)
        return self.repository.state(account_id)

    def retry_projection(self, account_id):
        state = self.repository.state(account_id)
        if not state["current_profile"]:
            raise Conflict("Save a profile first")
        diagnosis = state["current_diagnosis"]
        self.project(state["account"], state["current_profile"], diagnosis if diagnosis and diagnosis.status == "confirmed" else None)
        return self.repository.state(account_id)

    async def diagnose(self, account_id, request):
        repo = self.repository
        account, profile, run = repo.begin_diagnosis(account_id, request.profile_version_id, self.model.model_name, request.retry_of)
        usage = None
        try:
            fields = ProfileFields.model_validate(profile.raw_input.get("fields", profile.raw_input))
            reply = await self.model.diagnose({"name": account.name, "creator_type": account.creator_type}, fields)
            usage = reply.usage
            result = parse_diagnosis(reply.content, fields)
            repo.complete_diagnosis(account_id, run.id, result, usage)
            return repo.state(account_id)
        except asyncio.CancelledError:
            repo.finish_workflow(account_id, run.id, status="failed", error="诊断请求已中断。", usage=usage)
            raise
        except Exception as exc:
            if isinstance(exc, ModelError):
                message = str(exc)  # Only adapter-owned fixed messages; never HTTP/provider details.
            elif isinstance(exc, FactLockError):
                message = "诊断未通过 Fact Lock 校验，未保存结果；请补充信息或重试。"
            elif isinstance(exc, Conflict):
                message = "Profile 已更新或任务已停止，本次过期诊断未保存。"
            else:
                message = "诊断输出或处理未通过校验，未保存结果；请重试。"
            # An explicit cancellation may already have finished this run.
            existing = repo.get("workflow_runs", run.id, account_id=account_id)
            if existing.status == "running":
                repo.finish_workflow(account_id, run.id, status="failed", error=message, usage=usage)
            raise DiagnosisFailure(message, run.id) from None
