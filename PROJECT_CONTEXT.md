# Growth Copilot｜小红书 AI 增长助手
Updated: 2026-11-09. Based on Easel; preserve Apache-2.0 LICENSE and attribution.

## Temporary judge demo — 2026-11-10
- Scope supersedes the pending multi-user VPS plan: one shared judge login, Cloudflare Quick Tunnel, no server purchase or migration.
- Independent `web.judge_demo` entrypoint only exposes authenticated Growth routes and built frontend; personal SQLite and legacy Easel routes are excluded.
- New demo SQLite/projections/credentials live under ignored `data/judge-demo`; model API key stays server-side. Four real model calls passed over public HTTPS using fictional inputs, with draft V1/V2 preserved.
- Final core deterministic regression: 122 passed / 3 skipped, including the four demo security tests. TypeScript passed. See docs/judge-demo.md and docs/judge-demo-validation.md for limits and unverified browser/launcher checks.
- Browser tool timed out; do not claim independent browser E2E passed. No V0.2 or multi-user migration performed.

## Post-release checkpoint — 2026-11-09
- Pearl-jade UI and reference-inspired Dashboard layout; account selector in sidebar, Chinese navigation, live account-scoped research/topics. No mock content inserted.
- Topics now accepts 1–3 confirmed/analyzed references; exactly three output topics and evidence validation remain unchanged.
- Account switching clears stale frontend state; delayed responses cannot replace another account. New-account mode and rename guidance clarified; no schema migration.
- Research shows newest saved references first. Existing historical data retained.
- TypeScript and production build passed; lint has two existing warnings. Frontend account-isolation regression passed. Previous full V0.1 results below are historical, not a new full-suite run.
- Production build on this Windows environment uses `vite build --configLoader native` to avoid default-loader spawn EPERM.
- Local service available on port 7860. No cloud deployment or server purchase performed. Next: choose hosting, confirm eligibility/filing, then deploy with persistent SQLite and private credentials.
- Remaining limitations: no multi-user permissions; homepage source covers are decorative; reference image is a layout direction, not exact photo reproduction.

## Current mode and status
**V0.1 DEMO READY — final human browser acceptance passed 2026-10-13.**
All V0.1 modules frozen. Final account: V0.1 Final Validation 20261013.
526 passed / 0 failed / 74 skipped; TypeScript/lint/build exit 0 (2 legacy warnings).
Real HTTP/model Core E2E passed: Account/Profile -> Diagnosis -> 3 Research analyses
-> confirmation -> TOP 3/evidence -> selected Topic -> Draft V1 -> edit V2 -> refresh.
6 successful real-model workflows; one Research truncation failure retained as failed,
then same-item recovery passed after bounded-output fix. No model mock substitution.
Backend process restart retained exact V1/V2; SQLite integrity ok, 0 FK errors.
User confirmed final account UI, cards/evidence, version switching and refresh.
Final report: docs/v01-final-validation.md. Demo instructions: README.md.
No V0.2 development authorized. Stop after final checkpoint.

### Historical progress log (superseded by final status above)
V0.1 Fast Track.
2026-10-13 Studio: PASS / FROZEN by user browser acceptance after 44e3716.
Current scope: V0.1 Final Validation only (full regression, real-model Core E2E,
blocking/high-priority fixes, final demo acceptance). No feature/UI/prompt polish.
Studio save-feedback fix: user DB already contained V1–V11; save events/API/SQLite
worked. Feedback and version picker were above the long editor. Added inline
success/error/current version beside Save and explicit latest-version selection.
Studio regression 4 passed/1 live skipped; browser reacceptance pending. No Core E2E.
2026-10-13 Topics: PASS / FROZEN by user browser acceptance. Freeze supersedes
earlier pending-browser notes. Do not optimize Topics prompt/UI or add features.
Current minimum task: Topic -> Studio Draft, generation + manual edit/version
persistence, using existing immutable Topic evidence and Draft data layer.
Topics freeze checkpoint: 6ef0ca9.
Studio minimum implementation ready for acceptance (not frozen): independent
studio.py/studio_model.py/studio_api.py + StudioPage. Existing Draft/Version
tables reused, no migration. 20 affected tests passed, 3 live skipped; separate
Studio run 4 deterministic + 1 real passed (12.90s). tsc/lint/build passed.
AI drafts are neutral proposals, not first-person autobiographies; a reproduced
invented-experience case is rejected automatically. Manual edits remain unverified.
Full regression blocked by sandbox temp permissions; host run requested.
Next: browser select Topic -> generate V1 -> edit/save V2 -> inspect V1/evidence
-> refresh; then freeze Studio and proceed to final core E2E/evaluation, not extras.
2026-10-13 Topics blocking truncation reproduced and locally fixed (shorter
output guidance; all guards retained). Same 4-source context generated 3 valid
persisted topics, stop/3357 completion tokens; 6 Topics tests passed, 1 skipped.
See docs/topics-bad-case.md. Browser refresh/evidence reacceptance pending.
2026-10-13 Research blocking report: same-item recovery saved; 11 Research tests
including normal live case passed. Original combined adapter rejection remains
unclassified because historical raw response was not retained. Only safe error
branch diagnostics changed; see docs/research-bad-case.md. No Topics/Studio edits.
Host Research+Topics regression supplied by user: 521 passed, 73 skipped (24.77s),
before this diagnostic-only Research change; supersedes earlier host-pending note.
Phase 1: 完成。Phase 2: 完成并验收、冻结。
Phase 3: PASS / FROZEN（2026-10-12），checkpoint 1711071。
Research Task 1: PASS / FROZEN; user browser acceptance passed. 5 module cases,
TypeScript/lint/build passed. Current-profile confirmation guide included.
Research AI Analysis → Structured Research Card: PASS / FROZEN; user browser acceptance passed.
10 deterministic/mock Research module tests passed; 1 real synthetic-reference case
passed schema/evidence validation and semantic review. tsc/lint/build passed.
Research AI frozen at 1081798. TOP 3 Topics + Evidence Recommendation implemented;
pending host full regression and human browser acceptance. No Studio implementation.
15 affected deterministic/mock tests passed, 2 live skipped. Latest Topics suite:
5 deterministic/mock + 1 real model passed (21.90s). tsc/lint/build passed.
Full-suite collection collision fixed in test imports only; sandbox regression
stopped on pytest temp WinError 5 (14 passed, 5 skipped, 1 setup error).
Next: host regression and browser Topics/evidence persistence acceptance;
then Topic -> Studio Draft. See docs/topics-checkpoint.md.
Freeze evidence: docs/phase3-freeze.md. The following historical test log is retained;
its earlier pending/blocker entries are superseded by the freeze evidence.
Do not change Account / Diagnosis / Growth Data Layer except blocking regression.
Core flow: Account → Diagnosis → Research → TOP 3 Topics → Studio Draft.

## Phase 3 evidence
- Latest minimum task: real output retention + semantic review completed 2026-10-12.
  Repeated live runs exposed invalid/truncated JSON (D03 finish_reason=length).
  Local prompt brevity/array-format fix; subsequent full Diagnosis regression:
  41 passed (36 deterministic/mock + 5 real), 0 skipped, 37.45s.
  Evidence/review: workspace outputs/Phase3-Live-Diagnosis-Review.md.
  Browser diagnosis confirmation and V1/V2 chain remain pending; phase not frozen.
  Show whole-project status after each minimum task: Account done; Diagnosis
  acceptance in progress; Research / Topics / Studio / Core E2E not started.
- Live D01–D05 schema/guard tests: **5 passed in 54.23s** after granting network
  access on 2026-10-12. Initial restricted-network attempt failed at transport.
  Current test does not retain outputs, so semantic review and result artifacts
  remain pending; do not equate these passes with full AI quality acceptance.
- Latest host rerun (2026-10-12): **506 passed / 0 failed / 71 skipped in
  17.53s**. PYTEST_EXIT, TSC_EXIT, LINT_EXIT, BUILD_EXIT all 0; lint has 2
  nonblocking legacy warnings. This supersedes the earlier failed host run.
  Full regression blocker resolved; real model + browser diagnosis acceptance remains.
- 2026-10-12 host regression: 505 passed / 1 failed / 71 skipped; tsc, lint,
  production build exit 0. Failure: missing-model unit test cleared environment
  but still discovered local .env, returning 200 instead of expected 422.
  Fixed test fixture to use its isolated workspace for dotenv discovery. No key
  inspected. Focused Account + deterministic Diagnosis regression: 36 passed.
  Full host rerun after this fix remains required; phase not yet frozen.
- Growth tests: 98 passed / 0 failed / 5 skipped (live model cases).
- TypeScript: pass. Lint: pass (2 existing legacy warnings).
- Production build: pass using vite build --configLoader native on Node 24.
- Account persistence and backend restart persistence: pass in actual browser.
- Real model E2E: pending. Full regression: pending.
- Full suite collected 577 tests. Sandbox full run hit temporary-directory
  PermissionError; fail-fast diagnostic: 14 passed / 5 skipped / 1 setup error.
  Neither skipped tests nor this partial run count as full regression success.
- Phase 2 previous host regression: 470 passed / 66 skipped, not Phase 3 evidence.
- Browser verified empty Dashboard, New Creator save, refresh/restart Profile V1,
  real failed Workflow for missing model, Research/Topics/Studio Coming Soon.
- Actual Diagnosis V1 → confirmation → Profile V2 → Diagnosis V2 still pending.
  Version-chain automated tests use mocks; do not claim real-model verification.
- Visual direction verified: light blue-gray/beige, white/glass cards and buttons,
  large radii, soft shadows. Result fact/hypothesis/missing visual check pending.

## Blockers and next task
Current: Phase 3 blockers resolved. Research Input + Persistence implemented.
Routes: GET/POST /api/growth/accounts/{account_id}/research and
PATCH /api/growth/accounts/{account_id}/research/{research_id}/confirmation.
Existing Phase 2 repository/schema unchanged. Blank counts are null, explicit 0
remains 0; account isolation enforced. UI uses current account and reloads from DB.
Restart backend to register new routes; frontend build is ready at #/research.
Research analysis extends existing research_items.analysis JSON (no schema migration).
POST research/{id}/analysis records a real workflow + source snapshot; result and
workflow success are saved atomically. Evidence quotes are validated against source.
POST research/{id}/analysis/interrupt supports explicit recovery of interrupted runs.
Re-analysis clears confirmed_for_topic; user re-confirms after reviewing the new card.
Source input and metrics remain unchanged; original Account/Diagnosis/data models frozen.
Restart backend and refresh for new analysis routes/build. No Topics/scraping/bulk/search.
Historical checklist below is completed:
1. User configures Growth LLM in local .env; never request or print the key.
2. Run scripts/Verify-Phase3.cmd in normal host terminal.
3. Real Diagnosis E2E: D01 complete beginner, D02 sparse information,
   D03 conflicting constraints, D04 unsupported fact, D05 no history.
   Record actual input/output/schema/unsupported facts/separation/missing/result.
   Schema checks alone are not semantic evaluation.
Then finish browser confirmation + V1/V2 chain, freeze Phase 3, update report and
commit; next minimum task: Research Input + ResearchItem persistence.
No Research implementation until core Phase 3 blockers close.

## Architecture and key directories
- FastAPI: web/app.py mounts easel/growth/api.py at /api/growth.
  Existing Easel Persona/Profile and legacy routes remain intact.
  Local single-user only: host/origin checks are not authentication.
- React/TypeScript/Vite: web/frontend/src/growth/; GrowthApp, Dashboard,
  AccountPage, DiagnosisCards. main.tsx selects GrowthApp.
  Dashboard and Account implemented; Research/Topics/Studio are Coming Soon.
- SQLite: easel/growth/database.py, migrations.py, models.py, repository.py.
  Account orchestration: accounts.py, service.py, projection.py.
- Default DB data/growth.sqlite3 is ignored. python -m easel.growth initializes
  V1–V3 migrations and checks integrity/FKs. GROWTH_DB_PATH is a process override.
- Nine objects: Account, ProfileVersion, Diagnosis, ResearchItem,
  TopicRecommendation, Topic, Draft, DraftVersion, WorkflowRun.
  Stable UUIDs; account-scoped foreign keys; immutable version/evidence snapshots.
- Relationships: Account → ProfileVersion → Diagnosis; Account → ResearchItem;
  ProfileVersion + Diagnosis + confirmed research → TopicRecommendation → Topic
  → Draft → DraftVersion. WorkflowRun records state, timing, failure and real usage.
- easel/growth/llm.py: compatible /chat/completions + JSON object output.
  diagnosis_schema.py defines schema and guards. Skill:
  skills/growth/diagnosis/{SKILL.md,prompt.md,rules.md,examples.json}.
- Saved profile projects into ignored profiles/_growth/ without replacing legacy
  personas. SQLite is authoritative. New computer starts with an empty workspace.
- Tests: tests/test_growth_data.py, tests/test_growth_account.py,
  tests/evaluation/ plus Easel tests and skills/openclaw/skill-wechat-publisher/tests.
- Setup: outputs/CROSS_DEVICE_SETUP.md; verification: scripts/Verify-Phase3.cmd.
  Details: docs/growth-data-layer.md and docs/growth-phase3.md.

## AI Workflow and non-negotiable rules
Save Profile version → running WorkflowRun → actual model → parse/schema/Fact Lock
→ pending Diagnosis → explicit human confirmation. No production mock fallback.
Errors must remain failed, not successful fabricated diagnoses.
Fact Lock: goals are not achievements, strengths grounded in stated input, sparse
profiles require missing information and low confidence, respect user constraints.
Finite guards do not guarantee zero hallucinations; review actual model outputs.
Evidence First: facts/hypotheses/missing information separated; confirmed hypotheses
are not proven growth. null metrics mean unknown; 0 means known zero.
Topics and DraftVersions retain source/profile/diagnosis provenance.
Record tokens/cost only when actually supplied, otherwise unknown.

## Fast Track
30–90 minute minimum tasks: one goal, small diff, independently testable.
No rescanning/redesign of accepted architecture; no cosmetic refactors or renames.
Level 1: affected tests, necessary tsc/lint/schema, 3–5 business cases.
Level 2 full regression: Phase 3 freeze, Research+Topics, first Studio core E2E,
final V0.1 release. Commit completed phases and update formal milestone reports.
Small-task updates: Completed / Files / Tests / Issues / Next.
P0: core flow, credible AI, stable demo. P1: evaluation and demo refinement.
P2/V0.2 backlog: visual polish, coverage targets, performance, non-core pages.

## V0.1 out of scope
Automatic scraping/publishing, multi-platform/video/music expansion, analytics
growth loop (V0.2/V0.3), commercial multi-user architecture and unrelated upgrades.

## Cross-device checkpoint
Branch: main. Upstream baseline: 5e0ccc1bed3f67c4b3b2b2aa36870e73d4f19825.
Only remote at handoff: origin=https://github.com/ZJU-REAL/Easel.git (UPSTREAM).
DO NOT PUSH there. User must supply their own repository/fork before remote sync.
Checkpoint subject: checkpoint: phase 3 fast-track handoff.
Read git log -1 for actual checkpoint hash; do not infer acceptance from commit.
Local .env, keys, cookies, DBs, profiles, dependencies and logs are not transferred.
The model adapter reads only repo .env (no interpolation, no export to children);
explicit process configuration overrides it. Restart backend after configuring.
Development ports: backend 7860, Vite 5173 proxying to 7860.
Previous isolated acceptance ran backend 7870 with .scratch/phase3-ui DB; these
machine-local test records are intentionally not part of the clone.
