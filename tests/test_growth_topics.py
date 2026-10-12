import asyncio
import json
import os
from pathlib import Path
from copy import deepcopy
import pytest
import httpx

from runpy import run_path
_support = run_path(str(Path(__file__).with_name('test_growth_research_analysis.py')))
research, card = _support['research'], _support['card']
from easel.growth.models import ResearchInput
from easel.growth.llm import ModelReply, ModelConfig, ModelError
from easel.growth.topics import TopicRepository, parse_topics, recommend, TopicFailure
from easel.growth.topic_model import TopicModel
from easel.growth.topics_api import get_model
from easel.growth.repository import Conflict


def setup(research):
    client, repo, aid, app = research
    profile = repo.create_profile_version(aid, {'fields': {'occupation': 'AI 工具学习者', 'skills': '整理会议记录',
        'creator_goal': '分享实测过程', 'target_audience': '初入职场的同事'}}, expected_current_id=None)
    diagnosis = repo.create_diagnosis(aid, profile.id, {'positioning_hypothesis': '用真实操作解释 AI 工具的边界，待验证'})
    repo.confirm_diagnosis(aid, diagnosis.id)
    items = []
    for i, body in enumerate(['先将笔记按议题分组，再提取行动项，最后人工核对。',
                              'AI 会把待讨论当成已决定，需要逐条检查来源。',
                              '评论希望获取匿名模板，先去掉个人身份信息再分享。']):
        item = repo.create_research(aid, ResearchInput(title=f'参考标题 {i+1}', body=body,
            likes=None, collects=0, comment_samples=['能否分享检查清单？'],
            analysis={'status': 'succeeded', 'result': card(), 'fixture': True}))
        repo.confirm_research(aid, item.id)
        items.append(item.id)
    return client, TopicRepository(repo.database), aid, app, profile, items


def output(context):
    return {'topics': [dict(rank=i+1, title=f'会议记录实验角度 {i+1}', target_audience='初入职场的同事',
        angle=f'从参考 {i+1} 的过程开展实验', hook='怎样减少整理遗漏？', why_now='已有整理技能，可用原文场景设计小实验',
        priority_reason='按制作成本排序，效果待验证', profile_basis=[{'field': 'skills', 'quote': '整理会议记录'}],
        evidence=[{'research_id': r['id'], 'field': 'body', 'quote': r['body']}],
        assumptions=['受众有此需求，待验证'], risks=['没有历史表现，不能承诺增长']) for i, r in enumerate(context['research'])],
        'not_recommended': ['暂不做缺少经验的复杂自动化教程']}


class Fake:
    model_name = 'deterministic-topic-fixture'
    async def recommend(self, context): return ModelReply(json.dumps(output(context), ensure_ascii=False))


def test_top3_atomic_persistence_provenance_and_snapshot(research):
    client, repo, aid, app, profile, ids = setup(research)
    app.dependency_overrides[get_model] = Fake
    try:
        response = client.post(f'/api/growth/accounts/{aid}/topics/recommendations', json={'research_ids': ids})
        assert response.status_code == 201
        data = response.json(); assert len(data['topics']) == 3
        assert {t['rank'] for t in data['topics']} == {1, 2, 3}
        assert data['runs'][0]['status'] == 'succeeded' and data['runs'][0]['tokens'] is None
        topic = data['topics'][0]
        evidence = client.get(f'/api/growth/accounts/{aid}/topics/{topic["id"]}/evidence').json()
        assert evidence['profile_version_id'] == profile.id and evidence['account_id'] == aid
        assert evidence['research_snapshots'][0]['likes'] is None and evidence['research_snapshots'][0]['collects'] == 0
        target_id = evidence['research_ids'][0]
        repo.update_research(aid, target_id, ResearchInput(title='已修改', body='新内容'))
        assert repo.evidence(aid, topic['id'])['research_snapshots'] == evidence['research_snapshots']
        assert len(TopicRepository(repo.database).state(aid)['topics']) == 3
        assert client.get(f'/api/growth/accounts/other/topics/{topic["id"]}/evidence').status_code == 404
    finally: app.dependency_overrides.pop(get_model, None)


def test_prerequisites_no_partial_runs(research):
    _, repo, aid, _, profile, ids = setup(research)
    for bad in (ids[:2], [ids[0]] * 3):
        with pytest.raises(Conflict): repo.begin(aid, bad, 'fixture')
    repo.confirm_research(aid, ids[0], False)
    with pytest.raises(Conflict): repo.begin(aid, ids, 'fixture')
    repo.confirm_research(aid, ids[0], True)
    repo.create_profile_version(aid, {'fields': {'skills': '新技能'}}, expected_current_id=profile.id)
    with pytest.raises(Conflict): repo.begin(aid, ids, 'fixture')
    assert repo.list('workflow_runs', account_id=aid) == []


def test_reject_schema_rank_and_fabricated_evidence(research):
    _, repo, aid, _, _, ids = setup(research)
    run, context = repo.begin(aid, ids, 'fixture')
    for variant in ('rank', 'quote', 'profile', 'id'):
        data = output(context)
        if variant == 'rank': data['topics'][1]['rank'] = 1
        if variant == 'quote': data['topics'][0]['evidence'][0]['quote'] = '不存在的原文'
        if variant == 'profile': data['topics'][0]['profile_basis'][0]['quote'] = '年入百万'
        if variant == 'id': data['topics'][0]['evidence'][0]['research_id'] = 'other-account'
        with pytest.raises(ValueError): parse_topics(json.dumps(data), context)
    repo.interrupt(aid, run.id)
    class Broken(Fake):
        async def recommend(self, context): return ModelReply('{')
    with pytest.raises(TopicFailure): asyncio.run(recommend(repo, Broken(), aid, ids, run.id))
    assert repo.list('topics', account_id=aid) == [] and repo.list('topic_recommendations', account_id=aid) == []
    retry = repo.state(aid)['runs'][0]
    assert retry.status == 'failed' and retry.retry_count == 1


def test_inflight_lock_and_stale_context(research):
    _, repo, aid, _, profile, ids = setup(research)
    run, context = repo.begin(aid, ids, 'fixture')
    with pytest.raises(Conflict): repo.begin(aid, ids, 'fixture')
    repo.confirm_research(aid, ids[0], False)
    with pytest.raises(Conflict): repo.complete(aid, run.id, context, parse_topics(json.dumps(output(context)), context), None)
    assert not repo.list('topics', account_id=aid)
    repo.interrupt(aid, run.id)
    with pytest.raises(Conflict): repo.complete(aid, run.id, context, parse_topics(json.dumps(output(context)), context), None)


def test_provider_json_mode_usage_and_redaction():
    def response(request):
        body = json.loads(request.content)
        assert body['response_format']['type'] == 'json_object' and 'tools' not in body
        return httpx.Response(200, json={'choices': [{'message': {'content': '{}'}, 'finish_reason': 'stop'}], 'usage': {'total_tokens': 7}})
    model = TopicModel(ModelConfig('https://example.invalid/v1', 'fixture', 'test-secret'), httpx.MockTransport(response))
    assert asyncio.run(model.recommend({})).usage.tokens == 7
    model.transport = httpx.MockTransport(lambda r: httpx.Response(200, json={'choices': [{'message': {'content': 'test-secret'}}]}))
    with pytest.raises(ModelError) as exc: asyncio.run(model.recommend({}))
    assert 'test-secret' not in str(exc.value)


@pytest.mark.skipif(os.environ.get('GROWTH_LIVE_TOPICS') != '1', reason='Explicit real model opt-in required')
def test_live_top3(research):
    _, repo, aid, _, _, ids = setup(research)
    rec = asyncio.run(recommend(repo, TopicModel(), aid, ids))
    state = repo.state(aid)
    assert len(state['topics']) == 3 and state['runs'][0].status == 'succeeded'
    if directory := os.environ.get('GROWTH_TOPICS_EVAL_DIR'):
        folder = Path(directory); folder.mkdir(parents=True, exist_ok=True)
        result = {'note': 'Real topic model; synthetic profiles/references and fixture research analyses',
                  'recommendation': rec.model_dump(), 'topics': [t.model_dump() for t in state['topics']],
                  'evidence': repo.recommendation_evidence(aid, rec.id)}
        (folder / 'topics-live-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
