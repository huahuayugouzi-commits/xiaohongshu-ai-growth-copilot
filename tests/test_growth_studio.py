import asyncio
import json
import os
from copy import deepcopy
from contextlib import closing
from pathlib import Path
from runpy import run_path
import httpx
import pytest
from easel.growth.studio import StudioRepository, EditableDraft, parse_draft, generate_draft, DraftFailure
from easel.growth.studio_model import DraftModel
from easel.growth.studio_api import get_model
from easel.growth.llm import ModelReply, ModelConfig, ModelError
from easel.growth.repository import Conflict
from easel.growth.topics import recommend

_support = run_path(str(Path(__file__).with_name('test_growth_topics.py')))
research = _support['research']


def setup(research):
    client, base, aid, app, profile, ids = _support['setup'](research)
    asyncio.run(recommend(base, _support['Fake'](), aid, ids))
    topic = base.state(aid)['topics'][0]
    return client, StudioRepository(base.database), aid, app, topic


def output(context):
    source = context['evidence']['research_snapshots'][0]
    return {'draft': dict(title='计划核对一次会议记录', hook='如何检查遗漏？', body='计划准备脱敏素材，再逐条核对。尚未实测，效果待验证。',
                         cta='你会先核对哪一项？', tags=['会议记录'], cover_text='待开展的小实验', visual_suggestions=['用虚构样例演示流程'],
                         facts_to_verify=['先确认素材可以公开，核实适用条件']),
            'evidence': [{'research_id':source['id'], 'field':'body', 'quote':source['body']}]}


class Fake:
    model_name = 'deterministic-draft-fixture'
    async def generate(self, context): return ModelReply(json.dumps(output(context), ensure_ascii=False))


def test_generate_edit_history_scope_and_reopen(research):
    client, repo, aid, app, topic = setup(research)
    app.dependency_overrides[get_model] = Fake
    try:
        path = f'/api/growth/accounts/{aid}/studio'
        result = client.post(path+'/drafts', json={'topic_id':topic.id})
        assert result.status_code == 201
        data=result.json(); did=data['created_draft_id']; v1=data['versions'][0]
        assert v1['source_evidence']['topic_id'] == topic.id and v1['source_evidence']['research_ids']
        source=v1['source_evidence']['research_snapshots'][0]
        assert source['likes'] is None and source['collects'] == 0
        edited=deepcopy(v1['content']); edited['body'] += '\n这是人工补充的待核实计划。'
        result=client.post(path+f'/drafts/{did}/versions',json={'content':edited,'expected_latest_id':v1['id']})
        assert result.status_code == 200
        versions=StudioRepository(repo.database).state(aid)['versions']
        assert {v.version for v in versions} == {1,2}
        assert next(v for v in versions if v.version==1).content.body == v1['content']['body']
        assert client.post(path+f'/drafts/{did}/versions',json={'content':edited,'expected_latest_id':v1['id']}).status_code == 409
        assert client.get('/api/growth/accounts/other/studio').status_code == 404
        assert repo.state(aid)['runs'][0].status == 'succeeded'
    finally: app.dependency_overrides.pop(get_model,None)


def test_invalid_outputs_never_save_and_retry(research):
    _,repo,aid,_,topic=setup(research)
    class Bad(Fake):
        async def generate(self, context): return ModelReply('{')
    with pytest.raises(DraftFailure): asyncio.run(generate_draft(repo,Bad(),aid,topic.id))
    state=repo.state(aid); assert not state['drafts'] and state['runs'][0].status=='failed'
    failed=state['runs'][0]
    draft=asyncio.run(generate_draft(repo,Fake(),aid,topic.id,failed.id))
    assert draft.latest_version_id and repo.state(aid)['runs'][0].retry_count==1
    with closing(repo.database.connect()) as conn: context=repo._context(conn,aid,topic.id)
    for mutate in ('source','quote','schema','unsupported_experience'):
        value=output(context)
        if mutate=='source': value['evidence'][0]['research_id']='fake'
        if mutate=='quote': value['evidence'][0]['quote']='无依据成果'
        if mutate=='schema': del value['draft']['body']
        if mutate=='unsupported_experience': value['draft']['body']='刚入职时我容易在会议记录里漏掉待办和责任人。'
        with pytest.raises(ValueError): parse_draft(json.dumps(value),context)


def test_lock_interrupt_and_changed_profile(research):
    _,repo,aid,_,topic=setup(research)
    run,context=repo.begin(aid,topic.id,'fixture')
    with pytest.raises(Conflict): repo.begin(aid,topic.id,'fixture')
    repo.interrupt(aid,run.id)
    with pytest.raises(Conflict): repo.complete(aid,run.id,context,parse_draft(json.dumps(output(context)),context),None)
    run,context=repo.begin(aid,topic.id,'fixture')
    repo.create_profile_version(aid,{'fields':{'skills':'新技能'}},expected_current_id=context['profile']['id'])
    with pytest.raises(Conflict): repo.complete(aid,run.id,context,parse_draft(json.dumps(output(context)),context),None)
    assert not repo.state(aid)['drafts']
    repo.interrupt(aid,run.id)
    with pytest.raises(Conflict): repo.begin(aid,topic.id,'fixture')


def test_transport_guards_usage_and_snapshot_compaction(research):
    _,repo,aid,_,topic=setup(research)
    with closing(repo.database.connect()) as conn: context=repo._context(conn,aid,topic.id)
    def good(request):
        data=json.loads(request.content)
        assert data['response_format']['type']=='json_object' and 'tools' not in data
        source=json.loads(data['messages'][1]['content'])['sources'][0]
        assert 'analysis' not in source and source['likes'] is None and source['collects']==0
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(output(context))},'finish_reason':'stop'}], 'usage':{'total_tokens':7}})
    model=DraftModel(ModelConfig('https://example.invalid/v1','fixture','secret-test-key'),httpx.MockTransport(good))
    assert asyncio.run(model.generate(context)).usage.tokens==7
    for content,finish in [('secret-test-key','stop'),('{}','length'),(None,'stop')]:
        model.transport=httpx.MockTransport(lambda r: httpx.Response(200,json={'choices':[{'message':{'content':content},'finish_reason':finish}]}))
        with pytest.raises(ModelError) as exc: asyncio.run(model.generate(context))
        assert 'secret-test-key' not in str(exc.value)


@pytest.mark.skipif(os.environ.get('GROWTH_LIVE_STUDIO')!='1',reason='Explicit real model opt-in required')
def test_live_studio(research):
    _,repo,aid,_,topic=setup(research)
    draft=asyncio.run(generate_draft(repo,DraftModel(),aid,topic.id))
    version=repo.get('draft_versions',draft.latest_version_id,account_id=aid)
    assert version.content.body and version.source_evidence['topic_id']==topic.id
    if folder:=os.environ.get('GROWTH_STUDIO_EVAL_DIR'):
        path=Path(folder); path.mkdir(parents=True,exist_ok=True)
        (path/'studio-live.json').write_text(version.model_dump_json(indent=2),encoding='utf-8')
