# Account Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent account switching/creation from displaying another account's data without deleting historical records.

**Architecture:** Reuse existing account-scoped SQLite relationships and queries. First reproduce frontend account selection and stale-response behavior; fix only the proven failing boundary. Existing backend Research, Topics and Studio list queries already filter by account_id.

**Tech Stack:** React/TypeScript, FastAPI, SQLite, pytest.

**Spec:** User request in this chat, 2026-11-05: A/B isolation, preserved history, refresh/restart persistence, no migration without approval.

## Global Constraints

- No deletion, database clearing, schema migration, authentication or multi-user redesign.
- No AI prompt or recommendation/generation logic changes.
- Preserve existing uncommitted bilingual UI and 1–3 reference changes.
- Run only directly related tests and necessary frontend checks.

## Review Focus

- Late account A refresh must not replace selected account B.
- Unsaved new-account mode must not present A's research as a new account's data.
- Failed B loading must not silently fall back to A.
- Cross-account evidence IDs must be rejected before generation/persistence.
- Returning to A after B and restarting must retain A's original records.

### Task 1: Reproduce and locally fix active-account state

**Files:** inspect/conditionally modify `web/frontend/src/growth/GrowthApp.tsx`; inspect child page effects. Add focused frontend regression coverage using available local test facilities, without installing dependencies.

**Interfaces:** Selected account ID and `/api/growth/state?account_id=...` response; child page accountId props.

- [ ] Reproduce A → B with delayed A responses and new-account mode; assert rendered data belongs to the selected ID and loading errors do not restore A.
- [ ] Guard late state updates against the active selection and reset old visible state at the proven boundary; do not refactor routes.
- [ ] Verify normal creation and switching, cancellation of new-account mode, and no stale success notice.

### Task 2: Prove persistence and generation isolation

**Files:** add `tests/test_growth_account_isolation.py`, reuse fixtures in existing Growth Research/Topics/Studio tests. Only change repositories/APIs if a failing isolation test proves a missing filter.

**Interfaces:** Existing account-scoped Research, Topics and Studio endpoints and repositories.

- [ ] Create A with Research, mock-generated Topics and Draft V1/V2. Create B and assert all B lists are empty.
- [ ] Submit A research/topic/draft/profile IDs under B and assert rejection and no new B records.
- [ ] Reopen the database and request A again; assert original IDs, evidence and versions remain, while B remains empty.
- [ ] Run focused isolation plus affected module tests; label mock tests separately from real-model tests.
- [ ] Run TypeScript, affected-file lint and frontend build; verify served frontend/backend version matches the fix.
- [ ] Review diff and create a scoped checkpoint without including unrelated uncommitted changes.

No migration is indicated by the inspected model/query code. Final root cause remains subject to reproduction; frontend stale-response/new-account state is a candidate, not yet a demonstrated cause.
