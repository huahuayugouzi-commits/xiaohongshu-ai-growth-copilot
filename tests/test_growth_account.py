import asyncio
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import shutil
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from easel.growth import Database, Conflict
from easel.growth.accounts import AccountRepository
from easel.growth.api import get_service
from easel.growth.diagnosis_schema import AccountProfileInput, DiagnosisRequest, ProfileFields
from easel.growth.llm import CompatibleModel, ModelConfig, ModelError, ModelReply, provider_usage
from easel.growth.projection import ProfileProjector
from easel.growth.service import DiagnosisFailure, GrowthService
from tests.evaluation.diagnosis_cases import PROFILE, valid_result


class FixtureModel:
    model_name = "deterministic-test-fixture"
    def __init__(self):
        self.output = json.dumps(valid_result(), ensure_ascii=False)
        self.calls = 0
    async def diagnose(self, account, profile):
        self.calls += 1
        return ModelReply(self.output)


@pytest.fixture
def service(monkeypatch):
    root = Path(__file__).resolve().parents[1] / ".scratch" / "growth-phase3-tests"
    directory = root / str(uuid4())
    directory.mkdir(parents=True)
    # Unit/API tests must never discover the developer's credential-bearing .env.
    import easel.growth.llm as adapter
    monkeypatch.setattr(adapter, "PROJECT_ROOT", directory)
    db = Database(directory / "growth.sqlite3")
    db.initialize()
    service = GrowthService(AccountRepository(db), FixtureModel(), ProfileProjector(directory / "profiles" / "_growth"))
    yield service
    assert directory.resolve().parent == root.resolve()
    cleanup = service.projector.root.parent.parent
    assert cleanup.samefile(directory)
    shutil.rmtree(cleanup)


@pytest.fixture
def client(service):
    from web.app import app
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app, base_url="http://127.0.0.1:7860", client=("127.0.0.1", 12345)) as client:
        yield client
    app.dependency_overrides.pop(get_service, None)


def payload(**changes):
    return {"name": "测试账号", "creator_type": "new", "profile": PROFILE.copy(), "expected_current_id": None, **changes}


def test_local_dotenv_is_private_and_not_interpolated(service, monkeypatch):
    import os
    import easel.growth.llm as adapter
    # Use the fixture's private workspace, without pytest's sandbox-sensitive tmp_path.
    root = service.projector.root.parent.parent
    monkeypatch.setattr(adapter, "PROJECT_ROOT", root)
    for key in ("GROWTH_LLM_BASE_URL", "GROWTH_LLM_MODEL", "GROWTH_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    (root / ".env").write_text('GROWTH_LLM_BASE_URL=https://example.invalid/v1\nGROWTH_LLM_MODEL=test-model\nGROWTH_LLM_API_KEY="fixture-${DO_NOT_EXPAND}"\n', encoding="utf-8")
    config = ModelConfig.from_environment()
    assert config.ready
    assert config.api_key == "fixture-${DO_NOT_EXPAND}"
    assert "GROWTH_LLM_API_KEY" not in os.environ
    assert config.api_key not in repr(config)
    monkeypatch.setenv("GROWTH_LLM_MODEL", "explicit-override")
    assert ModelConfig.from_environment().model == "explicit-override"


def saved(service):
    return service.save(AccountProfileInput.model_validate(payload()))


def diagnose(service, state, retry_of=None):
    return asyncio.run(service.diagnose(state["account"].id, DiagnosisRequest(profile_version_id=state["current_profile"].id, retry_of=retry_of)))


def test_account_api_real_persistence(client, service):
    assert client.get("/api/growth/state").json()["next_step"] == "完成账号建档"
    response = client.post("/api/growth/accounts", json=payload())
    assert response.status_code == 201
    result = response.json(); aid = result["account"]["id"]
    assert result["current_profile"]["version"] == 1
    assert result["next_step"] == "生成账号诊断"
    fresh = AccountRepository(Database(service.repository.database.path)).state(aid)
    assert fresh["current_profile"].raw_input["fields"]["occupation"] == PROFILE["occupation"]
    assert client.get("/api/growth/state", params={"account_id": aid}).json()["current_profile"]["id"] == result["current_profile"]["id"]


def test_existing_creator_all_fields_and_version(client):
    initial = client.post("/api/growth/accounts", json=payload()).json()
    aid = initial["account"]["id"]; pid = initial["current_profile"]["id"]
    data = payload(creator_type="existing", expected_current_id=pid,
                   profile={**PROFILE, "bio": "简介", "current_positioning": "探索", "operation_duration": "刚开始", "current_problem": "选题困难"})
    updated = client.put(f"/api/growth/accounts/{aid}/profile", json=data).json()
    assert updated["current_profile"]["version"] == 2
    assert updated["current_profile"]["raw_input"]["fields"]["bio"] == "简介"
    assert updated["profiles"][1]["id"] == pid
    assert client.put(f"/api/growth/accounts/{aid}/profile", json=data).status_code == 409


def test_noop_save_does_not_create_version(service):
    state = saved(service)
    again = service.save(AccountProfileInput.model_validate(payload(expected_current_id=state["current_profile"].id)), state["account"].id)
    assert len(again["profiles"]) == 1


def test_diagnosis_confirm_and_dashboard(client):
    state = client.post("/api/growth/accounts", json=payload()).json()
    aid = state["account"]["id"]; pid = state["current_profile"]["id"]
    response = client.post(f"/api/growth/accounts/{aid}/diagnoses", json={"profile_version_id": pid})
    assert response.status_code == 200
    state = response.json(); diagnosis = state["current_diagnosis"]
    assert diagnosis["status"] == "pending" and diagnosis["profile_version_id"] == pid
    assert state["runs"][0]["status"] == "succeeded" and state["runs"][0]["tokens"] is None
    assert state["next_step"] == "确认或调整定位"
    state = client.post(f"/api/growth/accounts/{aid}/diagnoses/{diagnosis['id']}/confirm").json()
    assert state["current_diagnosis"]["status"] == "confirmed"
    assert state["next_step"] == "下一步进入 Research（Coming Soon）"
    assert state["counts"] == {"research": 0, "topics": 0, "drafts": 0}


@pytest.mark.parametrize("bad", ["not JSON", "```json\n{}\n```", "{}", '{"confidence":"low","confidence":"high"}', '[]'])
def test_invalid_schema_failure_never_saved(service, bad):
    state = saved(service); service.model.output = bad
    with pytest.raises(DiagnosisFailure):
        diagnose(service, state)
    after = service.repository.state(state["account"].id)
    assert after["diagnoses"] == [] and after["runs"][0].status == "failed"
    assert after["runs"][0].completed_at is not None


def test_hallucination_fails_workflow(service):
    state = saved(service)
    result = valid_result(); result["strengths"] = ["拥有10万粉丝"]
    service.model.output = json.dumps(result)
    with pytest.raises(DiagnosisFailure, match="Fact Lock"):
        diagnose(service, state)
    assert not service.repository.state(state["account"].id)["diagnoses"]


def test_retry_retains_failed_run(service):
    state = saved(service); service.model.output = "{}"
    with pytest.raises(DiagnosisFailure):
        diagnose(service, state)
    failed = service.repository.state(state["account"].id)["runs"][0]
    service.model.output = json.dumps(valid_result())
    state = diagnose(service, state, failed.id)
    assert state["runs"][0].retry_count == 1
    assert state["runs"][0].workflow_id == failed.workflow_id
    assert state["runs"][1].status == "failed"


def test_profile_v1_v2_diagnosis_history(service):
    state = diagnose(service, saved(service)); old = state["current_diagnosis"]
    service.confirm(state["account"].id, old.id)
    updated = service.save(AccountProfileInput.model_validate(payload(expected_current_id=state["current_profile"].id, profile={**PROFILE, "skills": "课程设计和教具制作"})), state["account"].id)
    assert updated["current_diagnosis"] is None
    with pytest.raises(Conflict):
        service.confirm(state["account"].id, old.id)
    latest = diagnose(service, updated)
    assert latest["current_diagnosis"].profile_version_id == latest["current_profile"].id
    assert latest["diagnoses"][1].id == old.id and latest["diagnoses"][1].status == "confirmed"


def test_stale_generation_rejected(service):
    state = saved(service)
    async def changed(account, profile):
        service.save(AccountProfileInput.model_validate(payload(expected_current_id=state["current_profile"].id, profile={**PROFILE, "interests": "新方向"})), state["account"].id)
        return ModelReply(json.dumps(valid_result()))
    service.model.diagnose = changed
    with pytest.raises(DiagnosisFailure, match="过期"):
        diagnose(service, state)
    assert not service.repository.state(state["account"].id)["diagnoses"]


def test_atomic_diagnosis_and_run(service, monkeypatch):
    state = saved(service)
    original = service.repository._insert
    def failed_insert(conn, table, **data):
        item = original(conn, table, **data)
        if table == "diagnoses":
            raise RuntimeError("simulated after insert")
        return item
    monkeypatch.setattr(service.repository, "_insert", failed_insert)
    with pytest.raises(DiagnosisFailure):
        diagnose(service, state)
    state = service.repository.state(state["account"].id)
    assert state["diagnoses"] == [] and state["runs"][0].status == "failed"


def test_projection_uses_six_files_and_persona_reader(service, monkeypatch):
    from easel import persona
    state = saved(service)
    monkeypatch.setattr(persona, "PROFILES_DIR", service.projector.root.parent)
    relative = state["projections"][0]["relative_path"]
    text = persona.load_profile_text("_growth/" + relative)
    assert "小学教师" in text and "尚无用户确认" in text
    assert persona.list_personas() == []  # Managed namespace hidden from legacy Persona selector.
    diagnosed = diagnose(service, state)
    confirmed = service.confirm(state["account"].id, diagnosed["current_diagnosis"].id)
    relative = confirmed["projections"][0]["relative_path"]
    assert "已确认的 AI HYPOTHESIS" in persona.load_profile_text("_growth/" + relative)


def test_projection_failure_is_visible_and_retryable(service, monkeypatch):
    original = service.projector.export
    monkeypatch.setattr(service.projector, "export", lambda *a: (_ for _ in ()).throw(OSError("sensitive path")))
    state = saved(service)
    assert state["current_profile"] and state["projections"][0]["status"] == "failed"
    assert "sensitive path" not in state["projections"][0]["error"]
    monkeypatch.setattr(service.projector, "export", original)
    assert service.retry_projection(state["account"].id)["projections"][0]["status"] == "synced"


def test_projection_does_not_overwrite_modified_files(service):
    state = saved(service)
    target = service.projector.root / state["projections"][0]["relative_path"] / "identity.md"
    target.write_text("user edit", encoding="utf-8")
    result = service.retry_projection(state["account"].id)
    assert result["projections"][0]["status"] == "failed"
    assert target.read_text(encoding="utf-8") == "user edit"


def test_missing_model_failure_no_demo(client, service, monkeypatch):
    for key in ("GROWTH_LLM_BASE_URL", "GROWTH_LLM_MODEL", "GROWTH_LLM_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    service.model = CompatibleModel()
    state = client.post("/api/growth/accounts", json=payload()).json()
    response = client.post(f"/api/growth/accounts/{state['account']['id']}/diagnoses", json={"profile_version_id": state["current_profile"]["id"]})
    assert response.status_code == 422 and "模型未配置" in response.json()["detail"]
    after = client.get("/api/growth/state").json()
    assert after["diagnoses"] == [] and after["runs"][0]["status"] == "failed"


def test_cross_origin_guard_preserved(client):
    assert client.post("/api/growth/accounts", json=payload(), headers={"Origin": "https://evil.example"}).status_code == 403


def test_duplicate_run_interrupt_and_restart(client, service):
    state = saved(service); aid = state["account"].id; pid = state["current_profile"].id
    _, _, run = service.repository.begin_diagnosis(aid, pid, "fixture")
    assert client.post(f"/api/growth/accounts/{aid}/diagnoses", json={"profile_version_id": pid}).status_code == 409
    assert client.post(f"/api/growth/accounts/{aid}/runs/{run.id}/interrupt").status_code == 200
    with pytest.raises(Conflict):
        service.repository.complete_diagnosis(aid, run.id, None, None)
    assert diagnose(service, state, run.id)["current_diagnosis"]


def test_cross_account_confirmation_rejected(client, service):
    first = diagnose(service, saved(service))
    second = saved(service)
    response = client.post(f"/api/growth/accounts/{second['account'].id}/diagnoses/{first['current_diagnosis'].id}/confirm")
    assert response.status_code == 404


def test_invalid_account_whitespace_and_extra_fields(client):
    assert client.post("/api/growth/accounts", json=payload(name="  ")).status_code == 422
    assert client.post("/api/growth/accounts", json={**payload(), "api_key": "not-allowed"}).status_code == 422


def test_adapter_mock_request_shape_and_usage():
    config = ModelConfig("https://provider.invalid/v1", "test-model", "test-secret")
    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-secret"
        data = json.loads(request.content)
        assert "tools" not in data and data["response_format"] == {"type": "json_object"}
        assert "FACT LOCK" in data["messages"][0]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(valid_result())}}], "usage": {"total_tokens": 123, "unexpected": "secret"}})
    reply = asyncio.run(CompatibleModel(config, httpx.MockTransport(handler)).diagnose({"name": "test", "creator_type": "new"}, ProfileFields(**PROFILE)))
    assert reply.usage.tokens == 123 and reply.usage.cost is None
    assert "unexpected" not in reply.usage.raw


@pytest.mark.parametrize("code", [401, 429, 500, 302])
def test_adapter_error_redaction(code):
    config = ModelConfig("https://provider.invalid/v1", "test-model", "test-secret")
    transport = httpx.MockTransport(lambda _: httpx.Response(code, text="test-secret and private provider details"))
    with pytest.raises(ModelError) as exc:
        asyncio.run(CompatibleModel(config, transport).diagnose({}, ProfileFields()))
    assert "test-secret" not in str(exc.value) and "private" not in str(exc.value)


def test_adapter_timeout_and_key_echo_rejected():
    config = ModelConfig("https://provider.invalid/v1", "test-model", "test-secret")
    def timeout(request):
        raise httpx.ReadTimeout("test-secret", request=request)
    with pytest.raises(ModelError, match="超时"):
        asyncio.run(CompatibleModel(config, httpx.MockTransport(timeout)).diagnose({}, ProfileFields()))
    echo = httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "test-secret"}}]}))
    with pytest.raises(ModelError, match="敏感"):
        asyncio.run(CompatibleModel(config, echo).diagnose({}, ProfileFields()))


def test_no_usage_estimation_and_no_secret_repr():
    assert provider_usage({}) is None
    usage = provider_usage({"usage": {"prompt_tokens": 5, "completion_tokens": 6}})
    assert usage.tokens is None and usage.cost is None
    assert "credential-value" not in repr(ModelConfig("https://provider.invalid/v1", "test", "credential-value"))


def test_insecure_remote_model_url_rejected():
    assert not ModelConfig("http://remote.invalid/v1", "m", "key").ready
    assert not ModelConfig("https://user:pass@remote.invalid/v1", "m", "key").ready
    assert ModelConfig("http://127.0.0.1:8000/v1", "m", "key").ready
