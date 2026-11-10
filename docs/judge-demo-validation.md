# Temporary Judge Demo Validation — 2026-11-10

## Implemented
Isolated app entrypoint, one server-authenticated judge login, bounded AI attempts, dedicated demo SQLite/projections, Windows start/stop scripts and usage instructions. No frozen business workflow or frontend code changed. No personal database migration. No cloud server purchased.

## Actual public HTTP validation
Public login page 200; unauthenticated Growth state 401. Authenticated session successfully created a fictional Account/Profile, ran real Diagnosis, confirmed it, created a fictional ResearchItem (likes null, collects 0), ran real Research Analysis, confirmed the reference, generated exactly three real Topics, read evidence, generated real Draft V1, saved edited V2, and retrieved both versions. Four actual model calls; no mock substitution. Local acceptance metadata resides in ignored data/judge-demo/acceptance.json. Public URL is transient, stored locally rather than hard-coded into scripts.

## Automated security/core tests
Final Growth + demo suite: 122 passed / 3 skipped in 16.93 seconds. Three skipped tests require explicit separate live opt-in; they are not counted as passed. Actual live checks above were separate.
Final focused demo suite including private-database sentinel: 4 passed in 3.66 seconds. Test assertions cover unauthenticated denial, wrong password, session/logout, Host and Origin rejection, unavailable legacy/file/config/debug routes, demo-only projections, restart persistence, call cap persistence, public Secure cookie and rejection of actual foreign account IDs even when GROWTH_DB_PATH points to a private fixture database.
Pytest's default Windows temp-directory ACL failed; tests were executed with a plugin providing fresh project-local temp directories. Assertions and business code unchanged; no failed test was skipped to obtain the result.
TypeScript: exit 0. Frontend code unchanged; existing built bundle reused. No claim of a fresh production build.

## Not verified / remaining checks
- Independent browser click-through and screenshot: browser tool timed out. HTTP E2E is not a substitute for browser rendering acceptance.
- Double-click launcher end-to-end: not verified in the ordinary Windows user session. This tool environment cannot restrict the folder ACL, so the launcher correctly fails closed there. App and tunnel were started individually for HTTP validation; local files currently inherit workspace permissions and are not exposed via HTTP. Run the launcher from the owner Windows session to apply its credential-folder restriction before handing credentials to judges.
- Final browser smoke test should verify login, navigation, visible synthetic evidence and V1/V2 refresh. Check a second device/network, particularly mainland reachability.
- Tunnel availability is temporary, dependent on this computer/network; no uptime guarantee. The current link must be rechecked immediately before sharing.

## Limits
Shared demo workspace and shared login; not independent-user isolation. 4 AI attempts/minute and 30 total; this is not a monetary spend guarantee. No private real data may be entered. Credentials only in a local ignored file, never this report. Closing tunnel ends public access; data persists. No public-ready multi-user or production certification is implied.

Final public recheck after restart and chunked-body compatibility fix: login page 200, anonymous state 401, login 303, protected home 200, exactly one synthetic demo account. Restart retained both Draft versions. Public sensitive/configuration/database routes returned 404 after login.

Login correction: changed Referrer-Policy from no-referrer to same-origin. Native HTML form posts can otherwise send Origin:null and fail the strict CSRF guard; prior manual HTTP Origin tests missed this browser behavior. Cross-site/null Origins remain rejected. Focused tests: 4 passed. Live public recheck: GET login 200 with same-origin policy; POST login 303; authenticated state 200. Human browser retry still pending.
