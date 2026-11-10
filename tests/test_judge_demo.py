import json
import re
import sqlite3
from fastapi.testclient import TestClient
from web.judge_demo import create_app, initialize


def setup(tmp_path):
    root = tmp_path / 'demo'
    initialize(root)
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'index.html').write_text('<h1>Demo</h1>')
    app = create_app(root, dist)
    client = TestClient(app)
    password = (root / 'judge-credentials.txt').read_text().split('Password: ')[1].splitlines()[0]
    return root, dist, app, client, password


def login(client, password):
    token = re.search(r'name="csrf" value="([^"]+)"', client.get('/login').text).group(1)
    return client.post('/login', data={'username': 'judge', 'password': password, 'csrf': token}, headers={'Origin': 'http://testserver'}, follow_redirects=False)


def test_auth_and_closed_legacy_routes(tmp_path):
    root, dist, app, client, password = setup(tmp_path)
    # Native HTML POST forms must retain same-origin Origin; no-referrer sends null.
    assert client.get('/login').headers['referrer-policy'] == 'same-origin'
    assert client.post('/login', data={'username': 'judge', 'password': password}, headers={'Origin': 'null'}).status_code == 403
    assert client.post('/login', data={'username': 'judge', 'password': password}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    paths = ['/api/growth/state', '/assets/main.js', '/api/env', '/api/personas', '/api/outputs', '/.env', '/docs', '/openapi.json', '/data/demo.sqlite3', '/api/accounts/x/credentials']
    for path in paths:
        assert client.get(path).status_code == 401
    assert login(client, 'incorrect').status_code == 401
    assert login(client, password).status_code == 303
    assert 'HttpOnly' in login(client, password).headers['set-cookie']
    assert client.get('/api/growth/state').json()['accounts'] == []
    for path in paths[2:]:
        assert client.get(path).status_code == 404
    assert client.post('/api/growth/accounts', json={}).status_code == 403
    assert client.post('/api/growth/accounts', json={}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    assert client.get('/', headers={'Host': 'evil.example'}).status_code == 400
    client.post('/logout', headers={'Origin': 'http://testserver'})
    assert client.get('/api/growth/state').status_code == 401


def test_persistence_separate_projection_and_missing_foreign_account(tmp_path):
    root, dist, app, client, password = setup(tmp_path)
    login(client, password)
    payload = {'name': 'Judge synthetic', 'creator_type': 'new', 'profile': {'skills': '整理工具使用笔记'}, 'expected_current_id': None}
    response = client.post('/api/growth/accounts', json=payload, headers={'Origin': 'http://testserver'})
    assert response.status_code == 201, response.text
    account = response.json()['account']['id']
    assert list((root / 'profiles').rglob('identity.md'))
    assert client.get('/api/growth/state?account_id=personal-account-id').status_code == 404
    assert client.get('/api/growth/accounts/personal-account-id/research').status_code == 404
    fresh = TestClient(create_app(root, dist))
    assert fresh.get('/api/growth/state').status_code == 401
    login(fresh, password)
    assert fresh.get('/api/growth/state').json()['account']['id'] == account
    before = (root / 'auth.json').read_bytes()
    initialize(root)
    assert (root / 'auth.json').read_bytes() == before


def test_ai_limit_persists_and_public_secure_cookie(tmp_path):
    root, dist, app, client, password = setup(tmp_path)
    login(client, password)
    with sqlite3.connect(root / 'guard.sqlite3') as c:
        c.executemany('INSERT INTO attempts VALUES (?,?)', [('ai', 0)]*30)
    response = client.post('/api/growth/accounts/anything/diagnoses', json={}, headers={'Origin': 'http://testserver'})
    assert response.status_code == 429
    (root / 'public-origin.txt').write_text('https://judge-test.trycloudflare.com')
    public = TestClient(create_app(root, dist), base_url='https://judge-test.trycloudflare.com')
    token = re.search(r'name="csrf" value="([^"]+)"', public.get('/login').text).group(1)
    response = public.post('/login', data={'username': 'judge', 'password': password, 'csrf': token}, headers={'Origin': 'https://judge-test.trycloudflare.com'}, follow_redirects=False)
    assert response.status_code == 303
    assert 'Secure' in response.headers['set-cookie']
    assert public.get('/api/growth/state').status_code == 200
    assert public.post('/api/growth/accounts/anything/studio/drafts', json={}, headers={'Origin': 'https://judge-test.trycloudflare.com'}).status_code == 429


def test_personal_database_override_cannot_enter_demo(tmp_path, monkeypatch):
    from easel.growth.database import Database
    from easel.growth.repository import GrowthRepository
    from easel.growth.models import AccountInput
    private = Database(tmp_path / 'private.sqlite3')
    private.initialize()
    owner = GrowthRepository(private).create_account(AccountInput(name='PRIVATE_SENTINEL', creator_type='new'))
    monkeypatch.setenv('GROWTH_DB_PATH', str(private.path))
    root, dist, app, client, password = setup(tmp_path)
    login(client, password)
    assert client.get('/api/growth/state').json()['accounts'] == []
    assert client.get('/api/growth/state?account_id=' + owner.id).status_code == 404
    for area in ('research', 'topics', 'studio'):
        assert client.get(f'/api/growth/accounts/{owner.id}/{area}').status_code == 404
    for path in ('/api/output/private.sqlite3', '/assets/%2e%2e/%2e%2e/.env', '/static/anything', '/profiles/identity.md'):
        assert client.get(path).status_code == 404
    assert GrowthRepository(private).get('accounts', owner.id, account_id=owner.id).name == 'PRIVATE_SENTINEL'


def test_browser_suppressed_origin_requires_signed_cookie_bound_form(tmp_path):
    root, dist, app, client, password = setup(tmp_path)
    for origin in (None, 'null', 'http://testserver'):
        token = re.search(r'name="csrf" value="([^"]+)"', client.get('/login').text).group(1)
        headers = {} if origin is None else {'Origin': origin}
        response = client.post('/login', data={'username': 'judge', 'password': password, 'csrf': token}, headers=headers, follow_redirects=False)
        assert response.status_code == 303
    token = re.search(r'name="csrf" value="([^"]+)"', client.get('/login').text).group(1)
    assert client.post('/login', data={'username': 'judge', 'password': password, 'csrf': token}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    stranger = TestClient(app)
    assert stranger.post('/login', data={'username': 'judge', 'password': password, 'csrf': token}).status_code == 403
    assert client.post('/login', data={'username': 'judge', 'password': password, 'csrf': 'forged'}, headers={'Origin': 'null'}).status_code == 403
    assert client.post('/api/growth/accounts', json={}, headers={'Origin': 'null'}).status_code == 403
