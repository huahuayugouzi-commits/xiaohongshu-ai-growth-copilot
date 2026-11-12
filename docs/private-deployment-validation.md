# Private Deployment Preparation Validation

2026-11-12 — User approved option A: fresh server database, retain all local history.

## Implemented
- Dedicated production entrypoint; only authenticated Growth routes and built frontend exposed.
- Provisioned users, scrypt passwords, opaque hashed/revocable sessions, CSRF/origin checks, secure cookies, login/AI throttling.
- Atomic account ownership mapping; cross-user requests denied before model invocation/mutation. Existing domain workflows unchanged.
- Fresh database initialization rejects populated legacy data; no migration of personal SQLite.
- Ubuntu24 Python/systemd/Caddy templates, release packaging, daily SQLite backups and separate-directory restore instructions.

## Verification
- User-run full repository regression: **541 passed, 74 skipped in 37.71s**. Skips are not passes.
- User-run production frontend build: **built in 663ms**.
- Agent rerun dedicated security suite: **5 passed in 7.08s**. Two users each complete deterministic diagnosis/research/topics/draft V1/V2; cross-user endpoints/forged IDs denied, reopen persistence, backup restore, orphan/history refusal, session revocation/expiry, CSRF/host/file boundary, rate limits, failed model status.
- TypeScript passed; lint completed with two pre-existing warnings in legacy AccountsPage/linkifyOutputs.
- Earlier restricted-terminal full-suite attempt hit Windows temporary-directory permissions; default Vite builder hit spawn EPERM. Those attempts are not counted as passing. Host-run results above are the successful runs.
- All new model tests are deterministic, no paid API calls. Real hosted model E2E is **not verified**.
- Runtime archive: `outputs/releases/growth-private-20261112.tar.gz`, 59 runtime files. Manifest hashes, disallowed file exclusions, common credential signature scan, Apache License/upstream attribution and built login redirect verified. This is a scoped release-package check, not a claim of exhaustive repository-history audit.
- Archive SHA256: `eea346d00b018c3b3e98adb25ed29774fd9769f10b2fab8b3f2eb3db7ee53b9f`.
- Git Bash syntax-check process could not start (Windows signal-pipe access denied); bash syntax/systemd/Caddy checks must run on the target Ubuntu host before activation. Scripts are packaged with Unix newlines.

## Pending deployment gate
- Target server IP, SSH access and domain/DNS have not yet been supplied.
- Ubuntu dependency installation, systemd/Caddy execution, valid public HTTPS, actual server restart/backup drill and two-browser remote isolation remain **unverified**.
- No server purchased/changed; no personal database or secrets uploaded. No live HTTPS URL exists from this preparation task.

Status: **LOCAL PREPARATION COMPLETE; SERVER ACCEPTANCE PENDING**. Do not label public production ready before the deployment checklist passes.
