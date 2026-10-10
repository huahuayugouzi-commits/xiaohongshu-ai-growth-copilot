# Growth Copilot — Phase 3: Account + AI Diagnosis

## Scope and entry points

The active React entry imports `src/growth/GrowthApp.tsx`. Navigation is Dashboard,
Account, Research, Topics, Studio. The last three are Coming Soon. The old Easel
components and backend remain present but are not the Growth navigation.
No Research AI, Topic generator, Studio, metrics, scraping or publishing is added.

Serve a built frontend at `http://127.0.0.1:7860/`; hash routes are `#/dashboard`
and `#/account`. Vite development runs on 5173 with `/api` proxied to 7860.
The main page title and visible product brand are Growth Copilot / 小红书 AI 增长助手.
The legacy `/onepage` and old static assets remain technical legacy endpoints,
not the supported Growth entry. Build the React frontend before launching Growth.

## Data flow

1. POST Account or PUT Profile validates explicit form fields.
2. Account metadata and ProfileVersion are persisted in one SQLite transaction.
3. A substantive edit appends a Profile version; an identical save does not.
   `expected_current_id` prevents overwriting another window's newer edit.
4. `raw_input.fields` contains user fields; `raw_input.account` snapshots name/type.
   Empty strings mean the user did not provide information, not absence of ability.
5. A managed six-file Persona projection is attempted. Database remains authoritative.
6. A diagnosis request pins the saved current Profile ID and creates a WorkflowRun.
7. Model response → strict JSON → Pydantic Schema → deterministic Fact Lock guards.
8. A valid pending Diagnosis and the succeeded run are committed in one transaction.
9. Explicit human confirmation is restricted to the latest diagnosis of the current
   Profile. Older versions remain readable, never silently overwritten/rebased.

The browser stores only the selected account ID in localStorage. All business data,
version history, diagnosis results and statuses are loaded from SQLite on refresh.

## Endpoints

All routes are under `/api/growth` and inherit existing host/Origin write protection.
This is local single-user software, not authenticated multi-user hosting.

| Route | Purpose |
|---|---|
| GET `/state?account_id=...` | Accounts, current Profile/Diagnosis, histories, runs, projection status, real counts, next step |
| POST `/accounts` | Create Account + Profile V1 |
| PUT `/accounts/{id}/profile` | Append changed Profile with optimistic pointer check |
| POST `/accounts/{id}/diagnoses` | Pin profile_version_id, optional retry_of; run real workflow |
| POST `/accounts/{id}/diagnoses/{diagnosis_id}/confirm` | Explicit human confirmation |
| POST `/accounts/{id}/projection/retry` | Retry managed Markdown export |
| POST `/accounts/{id}/runs/{run_id}/interrupt` | Explicitly mark a running diagnosis interrupted |

404 = absent/out-of-scope; 409 = stale Profile, active run or invalid transition;
422 = input/output validation or controlled model failure; 503 = database unavailable.
No arbitrary table write/delete endpoint or frontend API-key field is exposed.

## Model and Skill

Set these values in the repository-local `.env` before starting the backend:
`GROWTH_LLM_BASE_URL`, `GROWTH_LLM_MODEL`, `GROWTH_LLM_API_KEY`.
The adapter appends `/chat/completions`, requests `response_format: json_object`,
uses a 90-second timeout, and does not attach tools or follow redirects. Remote
URLs must use HTTPS; local loopback HTTP is allowed. It does not read legacy key
files. `.env` is Git-ignored, parsed without interpolation and never exported to
child-process environments. Explicit process variables take precedence for tests
and deployment. Keep personal API keys only in `.env`; restart after editing it.

The Skill lives in `skills/growth/diagnosis/`: SKILL.md, prompt.md, rules.md,
examples.json. This reuses Easel's Skill organization without granting a full
OpenClaw agent collection/publishing tools. `ProfileFields` and `DiagnosisResult`
in `diagnosis_schema.py` are the single sources for input/output JSON Schema.
Output schema is included in the server-side prompt, never in frontend prompt text.

Response fields: positioning_hypothesis (positioning, target_audience, core_value,
differentiation), content_pillars (name/reason), strengths, risks,
missing_information, assumptions and confidence (low/medium/high). All fields are
required; extras, Markdown fences, malformed JSON and duplicate keys are rejected.
The model never silently falls back to a deterministic sample.

## Fact Lock implementation and limitations

- System prompt treats profile strings as data, not instructions.
- Strengths must quote a substring of explicit occupation/experience/skills/
  interests/content_assets. Aspirational creator_goal is excluded as factual evidence.
- Fewer than two nonempty context fields requires abstention: unknown positioning/
  audience, no pillars, low confidence and explicit missing information.
- The supplied no-face/no-personal-experience vs strong-personal-IP pattern must
  be recognized as a constraint conflict.
- Checks reject selected unsupported credentials/income/follower claims and
  verified-performance/guaranteed-growth claims in assertion fields.
- UI separates user-supplied FACT (not externally verified), AI HYPOTHESIS and
  MISSING INFORMATION. Human confirmation is not proof of effectiveness.

These are deliberately conservative guards, **not a complete semantic truth
checker**. Paraphrased unsupported facts, less explicit contradictions and indirect
injection can escape finite rules. Substring quotation also cannot prove correct
semantic context in every case. No claim of universally zero hallucinations is made.
Live evaluation and human review remain necessary before accepting model quality.

## Persona bridge

Managed exports live at `profiles/_growth/<account UUID hex>/<profile UUID hex>/`
with separate `input/` and `<confirmed diagnosis UUID hex>/` directories. Each
contains identity/style/audience/platforms/preferences/memory Markdown, matching
the existing Persona helper's six-file format. The `_growth` namespace is hidden
from old Persona lists; `load_profile_text('_growth/...')` can read it explicitly.
Original profiles are untouched. Versions are immutable; different existing files
are never overwritten. Atomic directory rename publishes the six files together.
Windows uses extended-length filesystem paths without altering system security policy.

Migration V3 adds `diagnosis_runs` (run → Profile → Diagnosis) and
`profile_projections` (pending/synced/failed, safe error, relative path). Migration
V1/V2 data is preserved. Projection failure does not erase a successfully saved
Profile/confirmation: UI shows the explicit failure and offers retry.

## Workflow lifecycle and costs

Only one active diagnosis per account is allowed. Retry creates a new attempt
under the same workflow ID and Profile; prior failed rows remain. No automatic
retries or model calls occur on page load. Invalid output marks failed and saves
no Diagnosis. A Profile changed during inference also rejects the stale result.
Confirmation cannot turn an old diagnostic result into the current strategy.

Tokens/cost remain null unless explicitly returned. Only numerical whitelisted
usage fields are stored; prompt/completion totals are not added to invent an
unreported total, and pricing is never estimated. Credentials are not serialized,
provider error bodies are not exposed/logged, and credential echoes are rejected.
The model is selected via environment, not through user-form input.

An interrupted process may leave a running run. User can explicitly mark it
interrupted; any later response is rejected. That action cannot cancel an already
dispatched provider charge. SQLite/connection failure itself can also prevent
writing a terminal status; such a run remains visible instead of becoming success.

## Dashboard logic

No Account/current Profile → 完成账号建档. Current Profile without current Diagnosis
→ 生成账号诊断. Pending Diagnosis → 确认或调整定位. Confirmed Diagnosis → 下一步进入
Research（Coming Soon）. The frontend reads this state, profile version, counts and
run history from the API. Research/Topics/Draft indicators derive from stored counts,
but their pages still disclose that implementation is pending.

## Verification

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_growth_data.py tests/test_growth_account.py tests/evaluation -q -p no:cacheprovider
.\.venv\Scripts\python.exe -X utf8 -m pytest tests skills/openclaw/skill-wechat-publisher/tests -q --tb=short -p no:cacheprovider
```

D01–D05 are deterministic positive/negative fixtures covering aspirations vs facts,
insufficient information, conflicting constraints, fabricated sensitive facts and
unsupported historical performance claims. They prove guard behavior on those
fixtures, not actual model pass rates. HTTP adapter tests use httpx.MockTransport.

Live tests in `tests/evaluation/test_live_diagnosis.py` are skipped unless explicitly
enabled via `GROWTH_LIVE_EVAL=1` with configured credentials. Running them transmits
only test fixtures and incurs real provider usage. Successful guard checks still
require human semantic review; do not equate them to a universal Unsupported Fact=0.

Current completion evidence and UI screenshots are documented separately in the
Phase 3 Completion Report. Do not advance to Phase 4 automatically.
