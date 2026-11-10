"""Isolated, temporary judge host. Never import the legacy web.app application."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from easel.growth.api import router, get_service
from easel.growth.research_api import router as research_router
from easel.growth.topics_api import router as topics_router
from easel.growth.studio_api import router as studio_router
from easel.growth.accounts import AccountRepository
from easel.growth.database import Database, PROJECT_ROOT
from easel.growth.projection import ProfileProjector
from easel.growth.service import GrowthService

ROOT = PROJECT_ROOT / 'data' / 'judge-demo'
COOKIE = 'judge_session'
CSRF_COOKIE = 'judge_login_csrf'
AI_PATH = re.compile(r'^/api/growth/accounts/[^/]+/(diagnoses|research/[^/]+/analysis|topics/recommendations|studio/drafts)$')
LOGIN = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Growth Copilot · 评委体验</title>
<body style="background:#edf3ef;color:#203d37;font:16px system-ui;max-width:460px;margin:12vh auto;padding:24px"><h1>Growth Copilot</h1><h2>黑客松评委体验</h2><p>独立演示空间，请勿输入真实隐私信息。评委共用演示数据。</p><form method="post" action="/login"><label>测试账号<input name="username" autocomplete="username" required style="display:block;margin:12px 0;padding:12px"></label><label>密码<input name="password" type="password" autocomplete="current-password" required style="display:block;margin:12px 0;padding:12px"></label><button style="padding:12px 30px">登录体验</button></form></body></html>'''

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def initialize(root=ROOT):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / 'auth.json'
    if config_path.exists():
        return
    password = secrets.token_urlsafe(24)
    salt = secrets.token_hex(16)
    config = dict(username='judge', salt=salt, password_hash=password_hash(password, salt))
    # x mode ensures repeat startup never overwrites credentials.
    with config_path.open('x', encoding='utf-8') as f:
        json.dump(config, f)
    with (root / 'judge-credentials.txt').open('x', encoding='utf-8') as f:
        f.write('Username: judge\nPassword: ' + password + '\nShared temporary demo only. Do not commit or publish this file.\n')

def create_app(root=ROOT, dist=None):
    root = Path(root).resolve()
    config = json.loads((root / 'auth.json').read_text(encoding='utf-8'))
    dist = Path(dist or PROJECT_ROOT / 'web/frontend/dist').resolve()
    if not (dist / 'index.html').is_file():
        raise RuntimeError('Build frontend before starting the judge demo')
    db = Database(root / 'demo.sqlite3')
    db.initialize()
    service = GrowthService(AccountRepository(db), projector=ProfileProjector(root / 'profiles'))
    guard = root / 'guard.sqlite3'
    with sqlite3.connect(guard) as c:
        c.execute('CREATE TABLE IF NOT EXISTS attempts(kind TEXT NOT NULL, ts REAL NOT NULL)')
    sessions = {}  # Restart intentionally revokes all sessions; demo data persists.
    csrf_secret = secrets.token_bytes(32)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.dependency_overrides[get_service] = lambda: service
    for r in (router, research_router, topics_router, studio_router):
        app.include_router(r)

    def take(kind, per_minute, total=None):
        with sqlite3.connect(guard, timeout=10) as c:
            c.execute('BEGIN IMMEDIATE')
            count = c.execute('SELECT count(*) FROM attempts WHERE kind=? AND ts>?', (kind, time.time()-60)).fetchone()[0]
            all_count = c.execute('SELECT count(*) FROM attempts WHERE kind=?', (kind,)).fetchone()[0]
            if count >= per_minute or (total is not None and all_count >= total):
                return False
            c.execute('INSERT INTO attempts VALUES (?,?)', (kind, time.time()))
        return True

    @app.middleware('http')
    async def protect(request: Request, call_next):
        path = request.url.path
        allowed_hosts = {'127.0.0.1:7861', 'localhost:7861', 'testserver'}
        origin_file = root / 'public-origin.txt'
        public = origin_file.read_text().strip() if origin_file.exists() else ''
        if re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com', public):
            allowed_hosts.add(public.removeprefix('https://'))
        host = request.headers.get('host', '')
        if host not in allowed_hosts:
            return JSONResponse({'detail': 'Invalid host'}, 400)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            expected = public if host.endswith('.trycloudflare.com') else 'http://' + host
            # Some browser privacy modes suppress Origin on native form posts.
            # Only login may use a signed, browser-bound form token instead.
            if origin != expected and not (path == '/login' and origin in (None, 'null')):
                return JSONResponse({'detail': '跨站请求已拒绝'}, 403)
        token = request.cookies.get(COOKIE, '')
        authenticated = sessions.get(hashlib.sha256(token.encode()).hexdigest(), 0) > time.time()
        if path != '/login' and not authenticated:
            if path == '/':
                return RedirectResponse('/login', status_code=303)
            return JSONResponse({'detail': '请先登录评委体验账号'}, 401)
        if request.method == 'POST' and AI_PATH.fullmatch(path) and not take('ai', 4, 30):
            return JSONResponse({'detail': '演示调用限额：每分钟4次，总计30次，请联系演示负责人。'}, 429, headers={'Retry-After': '60'})
        try:
            length = int(request.headers.get('content-length', '0') or '0')
        except ValueError:
            return JSONResponse({'detail': 'Invalid content length'}, 400)
        if length > 250000:
            return JSONResponse({'detail': '请求内容过大'}, 413)
        if length or request.headers.get('transfer-encoding'):
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 250000:
                    return JSONResponse({'detail': '请求内容过大'}, 413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        if path == '/login' and request.method == 'POST':
            # Classifications only: never log form values, cookies or credentials.
            origin = request.headers.get('origin')
            (root / 'login-diagnostic.json').write_text(json.dumps({
                'origin_kind': 'missing' if origin is None else 'null' if origin == 'null' else 'present',
                'status': response.status_code,
            }), encoding='utf-8')
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'same-origin', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"})
        return response

    @app.get('/login')
    def login_page(request: Request):
        payload = str(int(time.time()) + 600) + '.' + secrets.token_hex(24)
        token = payload + '.' + hmac.new(csrf_secret, payload.encode(), hashlib.sha256).hexdigest()
        html = LOGIN.replace('<label>测试账号', '<input type="hidden" name="csrf" value="' + token + '"><label>测试账号')
        response = HTMLResponse(html)
        response.set_cookie(CSRF_COOKIE, token, max_age=600, httponly=True, samesite='lax', secure=request.headers.get('host', '').endswith('.trycloudflare.com'))
        return response

    @app.post('/login')
    async def login(request: Request):
        if not take('login', 10):
            return HTMLResponse('尝试过多，请一分钟后重试。', 429)
        form = await request.form()
        csrf = str(form.get('csrf', ''))
        cookie = request.cookies.get(CSRF_COOKIE, '')
        valid = False
        if len(csrf) < 200 and hmac.compare_digest(csrf.encode(), cookie.encode()):
            try:
                payload, signature = csrf.rsplit('.', 1)
                valid = int(payload.split('.')[0]) > time.time() and hmac.compare_digest(signature, hmac.new(csrf_secret, payload.encode(), hashlib.sha256).hexdigest())
            except (ValueError, TypeError):
                pass
        if not valid:
            return HTMLResponse('登录页面已过期或浏览器未保存验证 Cookie。请重新打开登录页；不要重复提交旧页面。<a href="/login">重新打开登录页</a>', 403)
        username, password = str(form.get('username', '')), str(form.get('password', ''))
        if len(password) > 200 or not (hmac.compare_digest(username.encode(), config['username'].encode()) and hmac.compare_digest(password_hash(password, config['salt']), config['password_hash'])):
            return HTMLResponse('账号或密码错误。<a href="/login">重新登录</a>', 401)
        token = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(token.encode()).hexdigest()] = time.time() + 8*3600
        response = RedirectResponse('/#/dashboard', 303)
        response.set_cookie(COOKIE, token, max_age=8*3600, httponly=True, samesite='strict', secure=request.headers.get('host', '').endswith('.trycloudflare.com'))
        return response

    @app.post('/logout')
    def logout(request: Request):
        sessions.pop(hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest(), None)
        response = RedirectResponse('/login', 303)
        response.delete_cookie(COOKIE)
        return response

    @app.get('/')
    def index():
        return FileResponse(dist / 'index.html')

    @app.get('/assets/{path:path}')
    def asset(path: str):
        file = (dist / 'assets' / path).resolve()
        if not file.is_relative_to(dist / 'assets') or file.suffix not in {'.js', '.css', '.woff2', '.png', '.svg', '.jpg', '.webp'} or not file.is_file():
            return JSONResponse({'detail': 'Not found'}, 404)
        return FileResponse(file)

    return app

if __name__ == '__main__':
    initialize()
