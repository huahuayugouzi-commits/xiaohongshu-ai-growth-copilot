# Growth Copilot｜小红书 AI 增长助手
Updated: 2026-10-10. Based on Easel; preserve Apache-2.0 LICENSE and attribution.

## Current mode and status
V0.1 Fast Track.
Phase 1: 完成。Phase 2: 完成并验收、冻结。
Phase 3: 代码完成，正在最终验收，尚未冻结。Phase 4: 未开始。
This checkpoint is for cross-device handoff, not Phase 3 acceptance.
Core flow: Account → Diagnosis → Research → TOP 3 Topics → Studio Draft.

## Phase 3 evidence
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
