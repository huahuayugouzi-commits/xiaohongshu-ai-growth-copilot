# Cross-device Development Handoff
Growth Copilot｜小红书 AI 增长助手 — V0.1 Fast Track — 2026-10-10

## Status
Phase 1 complete, Phase 2 accepted, Phase 3 code complete but acceptance pending.
Phase 4 not started. Read PROJECT_CONTEXT.md first.
This is a saved checkpoint, not a successful Phase 3 acceptance report.
Only configured remote at preparation time is upstream ZJU-REAL/Easel.
No push to upstream is authorized. Cloning upstream alone WILL NOT recover changes.
First create/supply your own GitHub repository or fork and push this checkpoint there.

## A. Software (Windows instructions)
- Git, with access to your own GitHub repository.
- Python 3.12.x; current machine used 3.12.14.
- Node.js 24.x and npm on PATH; current machine used Node 24.19.0.
- Normal terminal/PowerShell, browser and a code editor.
- Use a short writable checkout path; internet needed for Git, PyPI and npm.
- No OpenClaw gateway, browser automation installation, FFmpeg or model API key is
  required for Phase 3 deterministic tests/build. Legacy integration tests may skip.
- Do not disable system security or PowerShell execution policy.
  Commands below use python.exe directly and npm.cmd to avoid activation/.ps1 issues.

## B. Git transfer and Clone
On OLD computer, after user provides their own URL:
```powershell
git remote add personal <YOUR_GITHUB_REPOSITORY_URL>
git remote -v
git push personal main
```
Replace the angle-bracket placeholder; verify the destination belongs to you.
If personal already exists, inspect it before changing anything. Never force push.
If rejected as non-fast-forward, stop and reconcile, do not overwrite remote history.
For a new repository, create it empty (do not initialize a separate README).
On NEW computer:
```powershell
git clone <YOUR_GITHUB_REPOSITORY_URL> GrowthCopilot
Set-Location GrowthCopilot
git log -1 --oneline
git status --short
Get-Content PROJECT_CONTEXT.md
```
Confirm the log contains the checkpoint subject or a later verified commit.
Do not use an upstream clone as if it contains the Growth implementation.

## C–E. Environment and dependencies
Run from repository root:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio
.\.venv\Scripts\python.exe -m easel.growth
npm.cmd --prefix web/frontend ci
```
pyproject.toml contains existing Easel media dependencies, so first install can be
large. Do not remove them solely for migration. package-lock.json is tracked.
Python dependencies use version ranges: the new environment is reproducible in
setup steps, not guaranteed bit-for-bit identical; record failures if versions drift.
Linux/macOS equivalents: python3.12 -m venv .venv and .venv/bin/python; use npm.

## F–G. Build and start
Production build from repository root:
```powershell
node web/frontend/node_modules/typescript/bin/tsc -b web/frontend
node web/frontend/node_modules/vite/bin/vite.js build web/frontend --configLoader native
.\.venv\Scripts\python.exe -X utf8 -m uvicorn web.app:app --host 127.0.0.1 --port 7860
```
Backend serves the built frontend. For frontend development open a SECOND terminal
at repository root:
```powershell
npm.cmd --prefix web/frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort --configLoader native
```
Keep backend running on 7860: Vite proxies /api to it. Use Ctrl+C to stop each.
If a port is occupied, stop your known old server; do not kill unidentified processes.
If Growth returns 404, verify backend was restarted from this checkout.
No machine-specific node/python paths or activation scripts are required.

## H–I. Verification
One-command deterministic acceptance (tests + TypeScript + lint + production build):
```powershell
.\scripts\Verify-Phase3.cmd
```
Result and per-command exit codes: outputs/phase3-host-verification.log (ignored).
The script disables live evaluation for this invocation; no paid API calls.
Individual commands from repo root:
```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests skills/openclaw/skill-wechat-publisher/tests -q --tb=short -p no:cacheprovider
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_growth_data.py tests/test_growth_account.py tests/evaluation -q --tb=short -p no:cacheprovider
```
Do not count skipped cases as passed. Current targeted result: 98 passed, 5 skipped.
Previous full sandbox run was blocked by temporary-directory permissions; full host
regression is still REQUIRED before freeze. No expected count substitutes execution.

After personally configuring the model, actual API evaluation (uses credits and
sends only synthetic test inputs to your configured provider):
```powershell
$env:GROWTH_LIVE_EVAL = "1"
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/evaluation/test_live_diagnosis.py -q --tb=short -p no:cacheprovider
Remove-Item Env:GROWTH_LIVE_EVAL
```
This checks schema/guards only. Still record actual Structured Output, unsupported
facts, fact/hypothesis separation, missing information, and semantic assessment
for D01–D05; do not claim these reviews passed just from pytest.

## J. Browser acceptance
- Production: http://127.0.0.1:7860/
- Development: http://127.0.0.1:5173/
- Create New Creator → fill/save → refresh → generate real Diagnosis → confirm.
- Verify Dashboard uses real state; edit profile → save V2 → diagnose again.
- Inspect persisted Profile V1/Diagnosis V1 and Profile V2/Diagnosis V2 without overwrite.
- Capture Dashboard, Account and actual Diagnosis Result. Missing-model errors and
  mock fixtures are not successful real E2E evidence.

## K. Local configuration and secrets
If .env does not exist, copy the blank template:
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
Edit locally in your editor; never send the contents to chat or logs:
- GROWTH_LLM_BASE_URL: compatible provider API root, not /chat/completions.
- GROWTH_LLM_MODEL: model ID available to your account, supporting JSON object output.
- GROWTH_LLM_API_KEY: private local credential; never commit.
Optional process variables: GROWTH_DB_PATH (database location),
GROWTH_LIVE_EVAL (explicit live-test opt-in).
Only the three model variables load from .env; no interpolation or child-process
export. Explicit process values override .env. Restart backend after edits.
No real credentials or provider configuration values are included in this document.

## Database and files not transferred
data/growth.sqlite3 and .scratch test DBs are runtime data, ignored and untracked.
python -m easel.growth applies migrations and creates a clean database automatically.
No seed is needed: the New Creator UI can create a demo account. Test fixtures are
synthetic and are not inserted into production. Prior demo accounts do not migrate.
.env, credentials/cookies, local profiles, .venv, node_modules, build artifacts and
debug logs are intentionally excluded. Recreate dependencies and refill credentials.
Do not copy a database containing private data into Git.

## First instruction to Codex on the new computer
Read PROJECT_CONTEXT.md and outputs/CROSS_DEVICE_SETUP.md. Continue Phase 3
acceptance only: verify environment/full regression, then real Diagnosis and
V1/V2 browser E2E. Never read/output keys. Freeze and commit only after core
acceptance passes, then proceed to Research Input + ResearchItem persistence.
No extra refactoring or Phase 4 work before that.
