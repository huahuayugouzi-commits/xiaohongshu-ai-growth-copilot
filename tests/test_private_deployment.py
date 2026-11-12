"""Real HTTP boundary and SQLite; deterministic AI only, no network/model fees."""
from contextlib import closing
import json
import os
from pathlib import Path
from runpy import run_path
import shutil
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from easel.growth.private_auth import AuthStore, backup
from easel.growth.database import Database
from easel.growth.models import AccountInput
from easel.growth.repository import GrowthRepository
from easel.growth.llm import ModelReply, CompatibleModel
from easel.growth.research_api import get_research_model
from easel.growth.topics_api import get_model as topic_model
from easel.growth.studio_api import get_model as draft_model
from web.production import create_app, COOKIE, CSRF

support = run_path(str(Path(__file__).with_name('test_growth_studio.py')))
research_support = run_path(str(Path(__file__).with_name('test_growth_research_analysis.py')))
case_support = run_path(str(Path(__file__).parent / 'evaluation/diagnosis_cases.py'))
ORIGIN = 'https://growth.example.test'
PASSWORD = 'test-only-password-12345'


@pytest.fixture
def private(monkeypatch):
    root = Path(__file__).resolve().parents[1] / '.scratch/private-tests' / str(uuid4())
    root.mkdir(parents=True)
    monkeypatch.setattr('easel.growth.llm.PROJECT_ROOT', root)
    for key in ('GROWTH_LLM_API_KEY', 'GROWTH_LLM_BASE_URL', 'GROWTH_LLM_MODEL'):
        monkeypatch.delenv(key, raising=False)
    (root / 'dist/assets').mkdir(parents=True)
    (root / 'dist/index.html').write_text('frontend fixture')
    store = AuthStore(root / 'data'); store.initialize()
    store.create_user('alice', PASSWORD); store.create_user('bob', PASSWORD)
    async def diagnosis(self, account, profile):
        return ModelReply(json.dumps(case_support['valid_result']()))
    monkeypatch.setattr(CompatibleModel, 'diagnose', diagnosis)
    def app_factory():
        app = create_app(store.root, ORIGIN, root / 'dist')
        app.dependency_overrides[get_research_model] = research_support['Fake']
        app.dependency_overrides[topic_model] = support['_support']['Fake']
        app.dependency_overrides[draft_model] = support['Fake']
        return app
    yield store, app_factory
    assert root.resolve().parent.name == 'private-tests'
    shutil.rmtree('\\\\?\\' + str(root.resolve()) if os.name == 'nt' else root)


def login(app, username):
    client = TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN})
    assert client.get('/login').status_code == 200
    response = client.post('/login', data={'username': username, 'password': PASSWORD, 'csrf': client.cookies.get(CSRF)}, follow_redirects=False)
    assert response.status_code == 303
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    return client


def create_account(client, name):
    profile = {**case_support['PROFILE'], 'skills': '整理会议记录'}
    response = client.post('/api/growth/accounts', json=dict(name=name, creator_type='new', profile=profile))
    assert response.status_code == 201, response.text
    state = response.json(); aid = state['account']['id']; pid = state['current_profile']['id']
    response = client.post(f'/api/growth/accounts/{aid}/diagnoses', json={'profile_version_id': pid})
    assert response.status_code == 200, response.text
    did = response.json()['current_diagnosis']['id']
    assert client.post(f'/api/growth/accounts/{aid}/diagnoses/{did}/confirm').status_code == 200
    return aid, pid, did


def full_flow(client, aid, store):
    path = f'/api/growth/accounts/{aid}'
    response = client.post(path+'/research', json={'title':'参考标题', 'body':'先按议题整理会议记录，最后人工核对。', 'likes':None, 'collects':0})
    assert response.status_code == 201, response.text
    rid = response.json()['id']
    assert client.post(path+f'/research/{rid}/analysis').status_code == 200
    assert client.patch(path+f'/research/{rid}/confirmation', json={'confirmed_for_topic':True}).status_code == 200
    response = client.post(path+'/topics/recommendations', json={'research_ids':[rid]})
    assert response.status_code == 201, response.text
    assert len(response.json()['topics']) == 3
    topic = response.json()['topics'][0]['id']
    evidence = client.get(path+f'/topics/{topic}/evidence').json()
    assert evidence['research_snapshots'][0]['likes'] is None
    assert evidence['research_snapshots'][0]['collects'] == 0
    response = client.post(path+'/studio/drafts', json={'topic_id':topic})
    assert response.status_code == 201, response.text
    data = response.json(); did = data['created_draft_id']; v1 = data['versions'][0]
    edited = {**v1['content'], 'body':v1['content']['body']+'\n人工补充：仍需验证。'}
    assert client.post(path+f'/studio/drafts/{did}/versions', json={'content':edited, 'expected_latest_id':v1['id']}).status_code == 200
    state = client.get(path+'/studio').json()
    assert {v['version'] for v in state['versions']} == {1,2}
    assert next(v for v in state['versions'] if v['version']==2)['content'] == edited
    return rid, topic, did, v1


def test_two_users_full_flow_cross_user_denial_and_restart(private):
    store, factory = private
    app = factory(); a = login(app, 'alice'); b = login(app, 'bob')
    aid, pid, diagnosis = create_account(a, 'A private')
    ra, ta, da, va = full_flow(a, aid, store)
    assert b.get('/api/growth/state').json()['accounts'] == []
    bid, _, _ = create_account(b, 'B private')
    rb, tb, db, vb = full_flow(b, bid, store)
    for attacker, victim, profile, diag, rid, tid, did, version in [(b,aid,pid,diagnosis,ra,ta,da,va),(a,bid,pid,diagnosis,rb,tb,db,vb)]:
        base = f'/api/growth/accounts/{victim}'
        requests = [('GET', '/api/growth/state?account_id='+victim, None),
            ('GET',base+'/research',None), ('GET',base+'/topics',None), ('GET',base+'/studio',None),
            ('PUT',base+'/profile',{}), ('POST',base+'/diagnoses',{'profile_version_id':profile}),
            ('POST',base+f'/diagnoses/{diag}/confirm',None), ('POST',base+'/projection/retry',None),
            ('POST',base+'/runs/foreign/interrupt',None), ('POST',base+'/research',{}),
            ('PATCH',base+f'/research/{rid}/confirmation',{'confirmed_for_topic':False}),
            ('POST',base+f'/research/{rid}/analysis',None), ('POST',base+f'/research/{rid}/analysis/interrupt',None),
            ('POST',base+'/topics/recommendations',{'research_ids':[rid]}), ('GET',base+f'/topics/{tid}/evidence',None),
            ('POST',base+'/topics/runs/foreign/interrupt',None), ('POST',base+'/studio/drafts',{'topic_id':tid}),
            ('POST',base+f'/studio/drafts/{did}/versions',{'content':version['content'],'expected_latest_id':version['id']}),
            ('POST',base+'/studio/runs/foreign/interrupt',None)]
        with closing(store.database.connect()) as conn:
            before = conn.execute('SELECT COUNT(*) FROM workflow_runs').fetchone()[0]
        for method, path, payload in requests:
            assert attacker.request(method,path,json=payload).status_code == 404, (method,path)
        with closing(store.database.connect()) as conn:
            assert conn.execute('SELECT COUNT(*) FROM workflow_runs').fetchone()[0] == before
    # Forged descendant IDs under an OWNED account must still be rejected.
    with store.database.transaction() as conn:
        conn.execute("DELETE FROM private_limits WHERE bucket LIKE 'ai-%'")
    assert b.post(f'/api/growth/accounts/{bid}/topics/recommendations',json={'research_ids':[ra]}).status_code == 404
    assert b.post(f'/api/growth/accounts/{bid}/studio/drafts',json={'topic_id':ta}).status_code == 404
    assert b.get(f'/api/growth/accounts/{bid}/topics/{ta}/evidence').status_code == 404
    assert b.post(f'/api/growth/accounts/{bid}/studio/drafts/{da}/versions',json={'content':va['content'],'expected_latest_id':va['id']}).status_code == 404
    for client, own in [(a,aid),(b,bid)]:
        restarted = TestClient(factory(),base_url=ORIGIN,headers={'Origin':ORIGIN})
        restarted.cookies.update(client.cookies)
        assert [x['id'] for x in restarted.get('/api/growth/state').json()['accounts']] == [own]
        assert len(restarted.get(f'/api/growth/accounts/{own}/studio').json()['versions']) == 2


def test_auth_csrf_logout_revocation_and_public_file_boundary(private):
    store, factory = private; app = factory()
    visitor = TestClient(app,base_url=ORIGIN)
    for path in ['/api/growth/state','/api/settings','/docs','/openapi.json','/.env','/data/growth.sqlite3','/profiles/identity.md','/assets/../private_auth.py']:
        assert visitor.get(path).status_code in (401,404)
    a = login(app,'alice')
    for path in ['/api/settings','/docs','/openapi.json','/.env','/data/growth.sqlite3','/profiles/identity.md','/api/personas','/assets/%2e%2e/private_auth.py']:
        assert a.get(path).status_code == 404
    assert a.post('/api/growth/accounts',headers={'Origin':'https://evil.test'},json={}).status_code == 403
    assert a.get('/api/growth/state',headers={'Host':'evil.test'}).status_code == 400
    assert visitor.post('/login',headers={'Origin':ORIGIN},data={'username':'alice','password':PASSWORD}).status_code == 403
    old = a.cookies.get(COOKIE)
    assert a.post('/logout',follow_redirects=False).status_code == 303
    assert store.user(old) is None
    a = login(app,'alice'); store.disable('alice')
    assert a.get('/api/growth/state').status_code == 401
    b = login(app,'bob')
    with store.database.transaction() as conn:
        conn.execute('UPDATE private_sessions SET expires_at=0')
    assert b.get('/api/growth/state').status_code == 401


def test_limits_backup_restore_and_no_historical_import(private):
    store, factory = private
    a = login(factory(),'alice'); aid,_,_ = create_account(a,'Persistent')
    assert [store.take('test-limit',2,60) for _ in range(3)] == [True,True,False]
    restored = store.root.parent / 'restored'; restored.mkdir()
    backup(store.database.path,restored/'growth.sqlite3')
    restored_store = AuthStore(restored); restored_store.ready()
    assert restored_store.owns(restored_store.user(a.cookies.get(COOKIE)),aid)
    with pytest.raises(FileExistsError): backup(store.database.path,restored/'growth.sqlite3')
    legacy = AuthStore(store.root.parent/'legacy'); legacy.database.initialize()
    GrowthRepository(legacy.database).create_account(AccountInput(name='do not import',creator_type='new'))
    before = legacy.database.path.read_bytes()
    with pytest.raises(RuntimeError,match='historical'): legacy.initialize()
    assert legacy.database.path.read_bytes() == before
    # Unassigned data is denied even if an operator accidentally adds it later.
    orphan = GrowthRepository(store.database).create_account(AccountInput(name='unassigned',creator_type='new'))
    assert a.get('/api/growth/state?account_id='+orphan.id).status_code == 404
    assert len(a.get('/api/growth/state').json()['accounts']) == 1


def test_failed_model_not_success_and_ai_limit_enforced(private, monkeypatch):
    store, factory = private
    a = login(factory(),'alice'); aid,pid,_ = create_account(a,'Failure case')
    async def broken(self, account, profile):
        return ModelReply('{')
    monkeypatch.setattr(CompatibleModel,'diagnose',broken)
    path = f'/api/growth/accounts/{aid}/diagnoses'
    assert a.post(path,json={'profile_version_id':pid}).status_code == 422
    state = a.get('/api/growth/state').json()
    assert state['runs'][0]['status'] == 'failed' and len(state['diagnoses']) == 1
    uid = store.user(a.cookies.get(COOKIE))
    while store.take('ai-minute:'+uid,4,60):
        pass
    assert a.post(path,json={'profile_version_id':pid}).status_code == 429
    assert len(a.get('/api/growth/state').json()['runs']) == 2


def test_startup_fails_closed(private):
    store, factory = private
    with pytest.raises(RuntimeError): create_app(store.root,'http://growth.example.test')
    with pytest.raises(RuntimeError): create_app(store.root.parent/'missing',ORIGIN)
    store.disable('alice'); store.disable('bob')
    with pytest.raises(RuntimeError): factory()
