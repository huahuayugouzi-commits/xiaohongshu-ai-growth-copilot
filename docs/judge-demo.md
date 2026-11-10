# Growth Copilot — temporary hackathon judge demo

This is a single shared judge login, NOT independent multi-user hosting. Keep the computer awake, online and the demo process running. Quick Tunnel URLs change on each launch and have no availability guarantee. No domain/server purchase is required.

## Start and stop (Windows)
1. Use the existing project `.venv` and built `web/frontend/dist`. Do not run the legacy `web.app:app` through the tunnel.
2. The official cloudflared 2026.10.7 binary is downloaded locally to `outputs/judge-tools/cloudflared.exe` (ignored by Git). To reinstall, download the Windows amd64 executable from https://github.com/cloudflare/cloudflared/releases and put it at that path. Never disable TLS verification.
3. Double-click `Start-Judge-Demo.cmd`. The launcher checks port 7861, restricts the demo folder ACL, initializes only missing credentials, starts an isolated host, verifies unauthenticated API denial, then starts the tunnel. The console prints the new HTTPS URL, never the password.
4. Privately open `data/judge-demo/judge-credentials.txt` on your computer. Share its judge credentials separately with intended judges; never upload this file or paste it into a public README.
5. Share the URL printed by the launcher. If port 7861 is occupied by the previous demo, stop the previous instance first.
6. Ctrl+C in the launcher stops its own child processes. Alternatively double-click `Stop-Judge-Demo.cmd`; it targets only this repository's demo command lines. Its process-scoped execution policy does not change Windows policy. Closing sharing does not delete saved data.

The launcher must run from the ordinary Windows user session. Restricted tool environments may not allow setting folder ACLs. A failure stops the launcher before opening a tunnel.

## Judge instructions
Log in with the supplied judge account. This is a shared synthetic demonstration workspace. Never enter personal or confidential data.

- Dashboard / Account: view the prepared synthetic creator profile and confirmed diagnosis, or create a separate synthetic creator account.
- Research: view the explicitly labeled fictional reference and AI Research Card, inspect its evidence; manual inputs are supported.
- Topics: select 1–3 analyzed, confirmed references; generate exactly TOP 3; inspect source evidence.
- Studio: select a topic, generate a draft, edit and save a new version, then switch V1/V2 and refresh.
- To sign out, close the private browser session. Sessions expire after 8 hours and restart revokes them; a same-origin POST `/logout` also revokes a session.

## Security boundary
- `web/judge_demo.py` mounts only Growth routers and built index/assets. It does not import legacy `web.app` or expose platform credentials, file browsing, environment configuration, uploads, shell actions, docs/OpenAPI, debug routes or source maps.
- Passwords use salted scrypt; random opaque cookies are HttpOnly/SameSite Strict and Secure on the public hostname. Every data/asset route is authenticated server-side. Writes require the exact Origin; public Host must match the current tunnel hostname.
- SQLite is fixed at `data/judge-demo/demo.sqlite3`, independent of `GROWTH_DB_PATH`. Persona projections stay under `data/judge-demo/profiles`. No personal database was copied or migrated.
- Model settings are read server-side from the existing local configuration. The API key is not returned to the browser or written to the demo account file.
- AI attempts are limited to 4/minute and 30 total for this demo. Failed attempts count. The limit survives restart in `guard.sqlite3`; it is a call-count cap, not a precise currency budget. The initial live acceptance used 4 calls. Do not remove this guard database to bypass the cap.
- Login attempts are globally limited to 10/minute. A shared judge password can be forwarded; this is temporary access only.
- Data, credentials, logs and downloaded binary are in already Git-ignored directories. Do not commit them. Preserve original Easel Apache-2.0 attribution.

## Transport and persistence
Growth uses non-streaming JSON requests; the existing core does not require SSE. Quick Tunnel does not support SSE; legacy Easel streaming is intentionally not exposed. See https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ .

Restart preserves the demo database and credentials. An app restart revokes sessions. A tunnel restart changes the URL. For backup, stop only the demo and copy its data folder to a private local backup, never Git. The original personal app/database are unchanged.

## Validation (2026-11-10)
- Real public HTTP login, unauthenticated 401, diagnosis, research analysis, confirmation, TOP 3/evidence, draft creation, V2 save and fresh read all passed. Exactly four real model stages, no mock substitution.
- Deterministic Growth + demo suite initially 121 passed / 3 live opt-in tests skipped; those skips are not passes. Added private-database denial test is recorded in the final report.
- Browser automation did not complete: the browser tool timed out. Independent private-browser click-through and visual rendering are NOT verified. Owner must perform the final browser smoke test before sending to judges.
- This is temporary demo hosting, not production readiness or a multi-user security implementation.
