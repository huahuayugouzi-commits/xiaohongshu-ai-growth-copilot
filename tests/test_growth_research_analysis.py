import json
import asyncio
import os
from pathlib import Path
from copy import deepcopy

import pytest
import httpx
from runpy import run_path
# Both Easel and the publisher skill have a package named tests.
# Load this local fixture by path so full-suite collection cannot select the other package.
_support = run_path(str(Path(__file__).with_name('test_growth_research_api.py')))
research, payload = _support['research'], _support['payload']
from easel.growth.models import ResearchInput
from easel.growth.llm import ModelReply, ModelError, ModelConfig
from easel.growth.research_api import get_research_model
from easel.growth.research_analysis import (parse_card, snapshot, ResearchAnalysisRepository,
                                           ResearchModel, analyze_item, ResearchAnalysisFailure)


def card():
    insight = {'hypothesis': '可能通过具体问题吸引兴趣，仍需验证', 'evidence': [{'field': 'title', 'quote': '参考标题'}]}
    return dict(title_analysis=[insight], hook=[], content_structure=[insight], keywords=[],
                comment_feedback=[], audience_pain_points=[], popularity_hypotheses=[],
                reusable_patterns=[insight], missing_information=['缺少曝光及对照数据，不能确认因果'])


class Fake:
    model_name = 'deterministic-research-fixture'
    output = json.dumps(card(), ensure_ascii=False)
    async def analyze(self, source):
        return ModelReply(self.output)


def setup(research):
    client, base, aid, app = research
    profile = base.create_profile_version(aid, {'occupation': '测试'}, expected_current_id=None)
    diagnosis = base.create_diagnosis(aid, profile.id, {})
    base.confirm_diagnosis(aid, diagnosis.id)
    item = base.create_research(aid, ResearchInput(**payload(likes=None, collects=0)))
    return client, ResearchAnalysisRepository(base.database), aid, app, item


def test_success_persistence_evidence_and_reconfirmation(research):
    client, repo, aid, app, item = setup(research)
    repo.confirm_research(aid, item.id)
    app.dependency_overrides[get_research_model] = Fake
    try:
        response = client.post(f'/api/growth/accounts/{aid}/research/{item.id}/analysis')
        assert response.status_code == 200
        saved = response.json()
        assert saved['confirmed_for_topic'] is False
        assert saved['analysis']['source_snapshot']['likes'] is None
        assert saved['analysis']['source_snapshot']['collects'] == 0
        assert saved['analysis']['research_id'] == item.id
        assert saved['analysis']['status'] == 'succeeded'
        fresh = ResearchAnalysisRepository(repo.database).get('research_items', item.id, account_id=aid)
        assert fresh.analysis == saved['analysis']
        run = repo.get('workflow_runs', saved['analysis']['run_id'], account_id=aid)
        assert run.status == 'succeeded' and run.tokens is None and run.cost is None
    finally:
        app.dependency_overrides.pop(get_research_model, None)


def test_reject_bad_schema_and_unsupported_evidence(research):
    _, repo, aid, _, item = setup(research)
    for output in ('{', json.dumps({}), json.dumps({**card(), 'extra': 1})):
        model = Fake(); model.output = output
        with pytest.raises(ResearchAnalysisFailure):
            asyncio.run(analyze_item(repo, model, aid, item.id))
    bad = deepcopy(card()); bad['title_analysis'][0]['evidence'][0]['quote'] = '不存在的学历或粉丝事实'
    with pytest.raises(ValueError):
        parse_card(json.dumps(bad), snapshot(item))
    bad = card(); bad['comment_feedback'] = bad['title_analysis']
    with pytest.raises(ValueError):
        parse_card(json.dumps(bad), {**snapshot(item), 'comment_samples': []})
    failed = repo.get('research_items', item.id, account_id=aid)
    assert failed.analysis['result'] is None and failed.analysis['status'] == 'failed'
    result = asyncio.run(analyze_item(repo, Fake(), aid, item.id))
    assert repo.get('workflow_runs', result.analysis['run_id'], account_id=aid).retry_count == 3


def test_scope_and_confirmed_profile_required(research):
    client, repo, aid, app = research
    item = repo.create_research(aid, ResearchInput(**payload()))
    app.dependency_overrides[get_research_model] = Fake
    try:
        assert client.post(f'/api/growth/accounts/{aid}/research/{item.id}/analysis').status_code == 409
        assert client.post(f'/api/growth/accounts/other/research/{item.id}/analysis').status_code == 404
        assert not repo.list('workflow_runs', account_id=aid)
    finally:
        app.dependency_overrides.pop(get_research_model, None)


def test_running_lock_interrupt_and_late_output(research):
    _, repo, aid, _, item = setup(research)
    from easel.growth.repository import Conflict
    run, _ = repo.begin(aid, item.id, 'fixture')
    with pytest.raises(Conflict): repo.begin(aid, item.id, 'fixture')
    repo.interrupt(aid, item.id)
    with pytest.raises(Conflict): repo.finish(aid, item.id, run.id, result=parse_card(json.dumps(card()), snapshot(item)))
    assert repo.get('workflow_runs', run.id, account_id=aid).status == 'failed'


def test_model_transport_contract_and_redaction():
    def ok(request):
        body = json.loads(request.content)
        assert body['response_format'] == {'type': 'json_object'}
        assert 'tools' not in body and body['model'] == 'fixture'
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(card())}, 'finish_reason': 'stop'}], 'usage': {'total_tokens': 12}})
    model = ResearchModel(ModelConfig('https://example.invalid/v1', 'fixture', 'local-test-secret'), httpx.MockTransport(ok))
    assert asyncio.run(model.analyze({})).usage.tokens == 12
    for content, finish in [('local-test-secret', 'stop'), ('{}', 'length')]:
        model.transport = httpx.MockTransport(lambda r: httpx.Response(200, json={'choices': [{'message': {'content': content}, 'finish_reason': finish}]}))
        with pytest.raises(ModelError) as exc: asyncio.run(model.analyze({}))
        assert 'local-test-secret' not in str(exc.value)


@pytest.mark.skipif(os.environ.get('GROWTH_LIVE_RESEARCH') != '1', reason='Explicit real model opt-in required')
def test_live_research_card(research):
    _, repo, aid, _, _ = setup(research)
    source = ResearchInput(title='用 AI 整理会议记录：我的三步实验',
        body='每次开会后整理记录很费时间。我先把匿名笔记按议题分组，再让 AI 提取行动项，最后人工核对负责人和截止时间。AI 曾把待讨论事项写成已决定事项，我逐条修正后才分享。这个方法只是我的一次实验。',
        likes=None, collects=0, comments=2, comment_samples=['具体怎么检查遗漏？', '可以分享匿名模板吗？'])
    item = repo.create_research(aid, source)
    result = asyncio.run(analyze_item(repo, ResearchModel(), aid, item.id))
    assert result.analysis['status'] == 'succeeded'
    directory = os.environ.get('GROWTH_RESEARCH_EVAL_DIR')
    if directory:
        folder = Path(directory); folder.mkdir(parents=True, exist_ok=True)
        (folder / 'research-live-result.json').write_text(json.dumps(result.analysis, ensure_ascii=False, indent=2), encoding='utf-8')
