# Private User Deployment Implementation Plan

**Goal:** Deploy existing Growth Copilot for 5–10 independent users on Tencent Hong Kong Ubuntu 24.04 without exposing another user's data.
**Architecture:** Keep existing account-scoped domain relationships. Add authenticated users, server-side sessions and an account ownership mapping. Production serves only the Growth API and built frontend; legacy Easel configuration, files, platform credentials and execution APIs are not exposed.
**Tech Stack:** FastAPI, SQLite, React, Ubuntu 24.04 Python 3.12, systemd, Caddy.
**Spec:** User request in this conversation, 2026-11-10. User requests native execution; no additional skills, paid APIs, unrelated changes or real-server operations.

## Verified audit
- `easel/growth/api.py:get_service` is a global cached service, without an authenticated principal.
- `accounts` has no owner column; Growth schema contains no user/session tables.
- All descendant domain objects have existing account relationships. These can remain unchanged.
- Read-only inspection: local default SQLite has 3 historical accounts; quick_check = ok. No personal contents or credentials printed.
- `web/app.py:local_write_guard` is a localhost/origin guard, not user authentication. Legacy settings, persona, output and credential routes must not become public.
- `projection.py` writes account persona exports outside SQLite; deployment must persist them and prevent direct public access.
- Existing deterministic account-isolation test: 1 passed. This tests accounts, NOT independent authenticated users.

## Decision requiring confirmation
**Resolved 2026-11-12: user selected A, fresh production database.** Implementation uses independent `private_auth.py` / `web.production` and leaves frozen domain migrations/APIs unchanged. Production-only auth tables are initialized explicitly; populated legacy databases are refused. No history assignment/import performed.

Historical account ownership cannot be inferred. Proposed additive migration introduces users, hashed sessions and `account_owners(account_id PRIMARY KEY REFERENCES accounts(id), user_id REFERENCES users(id))`.
Existing accounts stay unassigned and inaccessible to ordinary users. Explicit administrator CLI assignment, after backup, can attach all existing accounts to the owner's login. Never assign existing data to the first registrant automatically.
Recommended alternative for the first public trial: fresh server database; existing local database remains untouched. Historical import can be authorized later.
No migration or real database mutation has been performed. Implementation awaits the user's required migration-risk decision.

## Constraints and review focus
- No paid model calls; model-dependent regression uses deterministic fixtures.
- No public self-registration: operator provisions 5–10 users with hidden password input and salted password hashes.
- Secure HttpOnly SameSite cookie, expiring/revocable opaque sessions stored as hashes; login throttling; logout invalidation and same-origin write validation.
- Every list/read/write/generation/evidence/retry/interrupt route checks authenticated ownership. Client account IDs are never authority.
- Sessions, user lists and password hashes never appear in normal business responses.
- Unassigned history defaults to deny. Cross-user denial must happen before model execution or mutation.
- Backup uses SQLite backup API, not copying a live WAL database; restore tested on a separate path.
- Production startup fails closed on missing authentication/domain configuration. No fallback to unauthenticated legacy host.

## Task 1 — Authentication and ownership
Files: new `easel/growth/auth.py`, `auth_api.py`, operator CLI; modify `migrations.py`, `api.py`, `accounts.py` and relevant Research/Topics/Studio dependencies. Add focused login UI in existing frontend; preserve domain workflows/prompts.
- [ ] Reproduce unauthenticated and cross-user access in new temporary-database tests.
- [ ] Implement additive ownership migration and explicit provisioning/assignment commands after approval.
- [ ] Filter state/account lists and authorize all account-bound routes, including evidence and workflow controls.
- [ ] Test A/B full mocked flows, forged IDs, missing/expired/revoked sessions, CSRF, unassigned history, persistence after restart, null versus zero and version retention.

## Task 2 — Production boundary and deployment
Files: `web/production.py`, `deploy/ubuntu24/` scripts and templates, `docs/deployment-ubuntu24.md`.
- [ ] Minimal production entrypoint mounts only authenticated Growth routes and frontend assets. Deny legacy APIs, database/config/output paths and traversal.
- [ ] Reproducible deploy script: validate Ubuntu and inputs, use a dedicated unprivileged service user, per-release venv and locally built frontend; preserve existing dependencies rather than optimize them.
- [ ] Persist SQLite and projections under `/var/lib/growth-copilot`, backups separately, private environment under `/etc/growth-copilot`; never overwrite populated data or existing secrets.
- [ ] systemd runs one worker on loopback only, restarts failures, logs no secrets. Caddy terminates HTTPS for confirmed domain. Firewall exposes 80/443; SSH restricted where possible.
- [ ] Daily SQLite backup timer, documented retention, off-server copy and restore drill. Deployment reruns preserve users/data and support rollback; rollback must respect schema compatibility.
- [ ] Document model variables by name only; no API calls during preparation. No server actions until explicitly authorized.

## Task 3 — Local acceptance and handoff
- [ ] Cross-user security tests pass (cannot be skipped or substituted by account tests).
- [ ] Existing core deterministic regression, TypeScript/lint/build, backup/restore and migration-on-copy tests pass.
- [ ] Record unavailable Linux/systemd/Caddy/HTTPS checks as pending, never inferred from Windows tests.
- [ ] Update PROJECT_CONTEXT, save deployment acceptance report, checkpoint commit excluding credentials/databases/user data.
- [ ] Obtain server SSH access and domain configuration privately, then request approval for real deployment; verify real HTTPS link and two-user isolation before declaring public-ready.
