"""Private HTTPS host: no legacy Easel routes or public file directories."""
import os
from pathlib import Path
import re
import secrets
import hmac
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from easel.growth.api import get_service, router as accounts
from easel.growth.database import PROJECT_ROOT
from easel.growth.private_auth import AuthStore, OwnedAccounts, digest
from easel.growth.projection import ProfileProjector
from easel.growth.research_api import router as research
from easel.growth.service import GrowthService
from easel.growth.studio_api import router as studio
from easel.growth.topics_api import router as topics

COOKIE = '__Host-growth-session'
CSRF = '__Host-growth-login'
AI_PATH = re.compile(r'/api/growth/accounts/[^/]+/(diagnoses|research/[^/]+/analysis|topics/recommendations|studio/drafts)/?')
LOGIN = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Growth Copilot · 登录</title>
<style>body{font:18px system-ui;background:#eef5f1;color:#163c36;max-width:420px;margin:12vh auto;padding:24px}form{display:grid;gap:18px}input,button{font:inherit;padding:12px;border:1px solid #ccdcd5;border-radius:10px}label{display:grid;gap:8px}</style>
<h1>Growth Copilot</h1><p>小红书 AI 增长助手 · 私人试用</p><form method="post" action="/login"><input type="hidden" name="csrf" value="TOKEN"><label>用户名<input name="username" autocomplete="username" maxlength="40" required></label><label>密码<input name="password" type="password" autocomplete="current-password" maxlength="200" required></label><button>登录</button></form><p>账号由管理员提供，不开放注册。</p></html>'''


def create_app(data_dir=None, origin=None, dist=None):
    root = data_dir or os.environ.get('GROWTH_PRIVATE_DATA_DIR')
    origin = origin or os.environ.get('GROWTH_PUBLIC_ORIGIN', '')
    url = urlsplit(origin)
    if not root or not Path(root).is_absolute() or url.scheme != 'https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise RuntimeError('Absolute GROWTH_PRIVATE_DATA_DIR and HTTPS GROWTH_PUBLIC_ORIGIN (no trailing slash) required')
    store = AuthStore(root)
    store.ready()  # Startup never imports history or creates a fallback database.
    dist = Path(dist or PROJECT_ROOT / 'web/frontend/dist').resolve()
    if not (dist / 'index.html').is_file():
        raise RuntimeError('Build frontend before production startup')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.auth_store = store

    def service(request: Request):
        return GrowthService(OwnedAccounts(store, request.state.uid), projector=ProfileProjector(store.root / 'profiles'))

    def authorize(request: Request):
        uid = request.state.uid
        aid = request.path_params.get('account_id')
        if aid is None and request.url.path == '/api/growth/state':
            aid = request.query_params.get('account_id')
        if aid is not None:
            if not store.owns(uid, aid):
                raise HTTPException(404, '账号或记录不存在。')
        elif (request.method, request.url.path) not in {('GET', '/api/growth/state'), ('POST', '/api/growth/accounts')}:
            raise HTTPException(403, '此接口未开放。')
        if request.method == 'POST' and AI_PATH.fullmatch(request.url.path):
            if not store.take('ai-minute:'+uid, 4, 60) or not store.take('ai-day:'+uid, 60, 86400):
                raise HTTPException(429, '模型调用频率或每日限额已达到，请稍后重试。')

    app.dependency_overrides[get_service] = service
    for router in (accounts, research, topics, studio):
        app.include_router(router, dependencies=[Depends(authorize)])

    @app.middleware('http')
    async def guard(request, call_next):
        if request.headers.get('host') != url.netloc:
            return JSONResponse({'detail': 'Invalid host'}, 400)
        path = request.url.path
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('origin') != origin:
            return JSONResponse({'detail': '跨站请求已拒绝，请从本站重新登录。'}, 403)
        uid = store.user(request.cookies.get(COOKIE, ''))
        if path != '/login' and uid is None:
            return RedirectResponse('/login', 303) if path in ('/', '/logout') else JSONResponse({'detail': '请先登录。'}, 401)
        request.state.uid = uid
        if request.method not in ('GET', 'HEAD'):
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 250000:
                    return JSONResponse({'detail': '请求内容过大。'}, 413)
                chunks.append(chunk)
            request._body = b''.join(chunks)
        response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'same-origin', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"})
        return response

    @app.get('/login')
    def login_page():
        token = secrets.token_urlsafe(32)
        response = HTMLResponse(LOGIN.replace('TOKEN', token))
        response.set_cookie(CSRF, token, max_age=600, secure=True, httponly=True, samesite='strict')
        return response

    @app.post('/login')
    async def login(request: Request):
        # Global ceiling also works when Caddy is the only visible client IP.
        if not store.take('login-global', 30, 60):
            return HTMLResponse('登录尝试过多，请稍后重试。', 429)
        form = await request.form()
        token, cookie = str(form.get('csrf', '')), request.cookies.get(CSRF, '')
        if not token or not hmac.compare_digest(token.encode(), cookie.encode()):
            return HTMLResponse('登录页面已过期，请<a href="/login">重新登录</a>。', 403)
        username = str(form.get('username', ''))
        if not store.take('login-user:'+digest(username), 10, 900):
            return HTMLResponse('尝试过多，请15分钟后重试。', 429)
        session = store.login(username, str(form.get('password', '')))
        if not session:
            return HTMLResponse('用户名或密码错误。<a href="/login">重试</a>', 401)
        store.logout(request.cookies.get(COOKIE, ''))
        response = RedirectResponse('/session-start', 303)
        response.set_cookie(COOKIE, session, max_age=8*3600, secure=True, httponly=True, samesite='strict')
        response.delete_cookie(CSRF, secure=True, httponly=True, samesite='strict')
        return response

    @app.get('/session-start')
    def session_start():
        return HTMLResponse('<meta charset="utf-8"><script src="/session-start.js"></script>正在打开工作空间…')

    @app.get('/session-start.js')
    def session_script():
        return Response("try { localStorage.removeItem('growth_account_id'); } catch {} location.replace('/#/dashboard');", media_type='text/javascript')

    @app.get('/logout')
    def logout_page():
        return HTMLResponse('<meta charset="utf-8"><form action="/logout" method="post"><button>退出 Growth Copilot 登录</button></form>')

    @app.post('/logout')
    def logout(request: Request):
        store.logout(request.cookies.get(COOKIE, ''))
        response = RedirectResponse('/login', 303)
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite='strict')
        return response

    @app.get('/')
    def index():
        return FileResponse(dist / 'index.html')

    @app.get('/favicon.svg')
    def favicon():
        if not (dist / 'favicon.svg').is_file():
            raise HTTPException(404)
        return FileResponse(dist / 'favicon.svg')

    @app.get('/assets/{path:path}')
    def asset(path: str):
        file = (dist / 'assets' / path).resolve()
        if not file.is_relative_to(dist / 'assets') or file.suffix not in {'.js', '.css', '.woff2', '.png', '.svg', '.jpg', '.webp'} or not file.is_file():
            raise HTTPException(404)
        return FileResponse(file)

    return app
