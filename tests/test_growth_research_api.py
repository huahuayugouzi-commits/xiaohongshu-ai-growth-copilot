from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import shutil

import pytest
from fastapi.testclient import TestClient
from easel.growth.database import Database
from easel.growth.repository import GrowthRepository
from easel.growth.models import AccountInput
from easel.growth.api import get_service


@pytest.fixture
def research():
    from web.app import app
    root = Path(__file__).resolve().parents[1] / '.scratch' / 'research-tests' / str(uuid4())
    root.mkdir(parents=True)
    db = Database(root / 'research.sqlite3'); db.initialize()
    repo = GrowthRepository(db)
    account = repo.create_account(AccountInput(name='Research test', creator_type='new'))
    app.dependency_overrides[get_service] = lambda: SimpleNamespace(repository=repo)
    try:
        with TestClient(app, base_url='http://127.0.0.1:7860', client=('127.0.0.1', 1000)) as client:
            yield client, repo, account.id, app
    finally:
        app.dependency_overrides.pop(get_service, None)
        shutil.rmtree(root)


def payload(**kwargs):
    return dict(title='参考标题', body='手动粘贴正文', source_url='https://www.xiaohongshu.com/explore/example',
                comment_samples=['真实输入样本'], **kwargs)


def test_null_zero_roundtrip_and_restart(research):
    client, repo, aid, app = research
    path = f'/api/growth/accounts/{aid}/research'
    result = client.post(path, json=payload(likes=None, collects=0, comments=3))
    assert result.status_code == 201
    saved = result.json()
    assert saved['account_id'] == aid and saved['likes'] is None and saved['collects'] == 0
    # Reopen database with a fresh repository, as after process restart.
    app.dependency_overrides[get_service] = lambda: SimpleNamespace(repository=GrowthRepository(Database(repo.database.path)))
    assert client.get(path).json() == [saved]
    assert saved['analysis'] is None and saved['confirmed_for_topic'] is False


def test_confirm_and_unconfirm_persist(research):
    client, repo, aid, _ = research
    path = f'/api/growth/accounts/{aid}/research'
    rid = client.post(path, json=payload()).json()['id']
    for flag in (True, False):
        response = client.patch(f'{path}/{rid}/confirmation', json={'confirmed_for_topic': flag})
        assert response.status_code == 200
        assert client.get(path).json()[0]['confirmed_for_topic'] is flag
        assert repo.get('research_items', rid, account_id=aid).confirmed_for_topic is flag


def test_account_scope(research):
    client, repo, aid, _ = research
    other = repo.create_account(AccountInput(name='Other', creator_type='existing')).id
    path = f'/api/growth/accounts/{aid}/research'
    rid = client.post(path, json=payload()).json()['id']
    assert client.get(f'/api/growth/accounts/{other}/research').json() == []
    assert client.patch(f'/api/growth/accounts/{other}/research/{rid}/confirmation', json={'confirmed_for_topic': True}).status_code == 404
    assert client.post('/api/growth/accounts/missing/research', json=payload()).status_code == 404


def test_validation_and_no_injected_analysis(research):
    client, _, aid, _ = research
    path = f'/api/growth/accounts/{aid}/research'
    for change in ({'likes': -1}, {'likes': False}, {'comments': 1.5}, {'collects': '0'},
                   {'title': '  '}, {'body': ''}, {'analysis': {}}, {'confirmed_for_topic': True},
                   {'source_url': 'javascript:alert(1)'}, {'comment_samples': ['']}):
        assert client.post(path, json={**payload(), **change}).status_code == 422
    assert client.get(path).json() == []


def test_origin_guard(research):
    client, _, aid, _ = research
    assert client.post(f'/api/growth/accounts/{aid}/research', json=payload(),
                       headers={'Origin': 'https://evil.example'}).status_code == 403
