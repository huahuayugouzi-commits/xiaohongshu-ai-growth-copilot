# Topic -> Studio Draft minimum checkpoint — 2026-10-13

Topics PASS / FROZEN at 6ef0ca9. Studio implemented, NOT FROZEN; acceptance pending.

## Delivered
- Studio selects an existing Topic (no frozen Topics UI/Prompt changes).
- Generate title, Hook, body, CTA, tags, cover text, visual suggestions and
  facts-to-verify. No images, publishing, extra agent or Quality Check workflow.
- Independent compatible model adapter, JSON schema and exact source ID/quote
  validation; no mock fallback. Source context excludes duplicate nested analysis.
- Draft V1 and successful WorkflowRun commit atomically. Existing Phase 2 tables
  and repository version writing reused, no migration. Account isolation, current
  positioning check, stale-context rejection, interrupt/retry, real usage only.
- Manual edit creates V2 with optimistic concurrency; immutable V1 remains.
  Source snapshots retain Topic/Profile/Diagnosis/Research lineage and null != 0.
- History is read-only; manual edits are explicitly not fact-checked. Switching
  drafts or refreshing requires saving first; autosave is out of scope.

## Tests / limitations
- Affected Research/Topics/Studio suite: 20 passed, 3 optional live skipped.
- Studio real-model run: 4 deterministic/mock + 1 real passed (12.90s).
  Synthetic upstream data, actual Studio model; not whole real-model E2E.
- Real output review found invented autobiographical opening. Tightened only
  Studio instructions and added first-person rejection guard + regression.
  V0.1 automatic drafts are neutral proposals; verified first-person narration
  can be added manually. This deliberately conservative guard is not a universal
  semantic truth checker. Human review remains necessary before publication.
- Final reviewed output uses conditional/planned experiments, no fabricated past
  user result observed. Local artifacts: workspace outputs/studio-eval.
- tsc, scoped Growth lint, Vite production build exit 0.
- Full suite attempted: 14 passed, 5 skipped, 1 setup error (pytest temp WinError 5,
  fail-fast). Host full regression requested, not passed yet.
- No agent browser acceptance claimed. User browser checks below remain required.

## API
GET /api/growth/accounts/{account_id}/studio
POST /api/growth/accounts/{account_id}/studio/drafts (topic_id, optional retry_of)
POST /api/growth/accounts/{account_id}/studio/drafts/{draft_id}/versions
  (content, expected_latest_id)
POST /api/growth/accounts/{account_id}/studio/runs/{run_id}/interrupt

## Acceptance / next
Restart backend to load new router; open /#/studio, select a current Topic,
generate V1, inspect content/evidence, edit and save V2, inspect V1, refresh and
verify both versions. Complete host regression. Then freeze Studio and run final
Account -> Diagnosis -> Research -> Topics -> Draft E2E and core AI evaluation.
