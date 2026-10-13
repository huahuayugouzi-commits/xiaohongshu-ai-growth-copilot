# Studio save feedback blocking issue

Classification F: successful saves without visible feedback at the button.
Read-only inspection found V1 through V11 for the user's draft, with latest pointer
at V11. V2–V4 differ from V1, proving requests and version creation worked.
Do not delete these versions. Historical click/network traces were not retained;
no claim that every click has a captured browser trace.

Payload is correct: draft_id is in the URL, content and expected_latest_id in JSON.
Topic and source evidence are derived server-side from the scoped Draft; clients
must not supply or replace provenance. No backend/API change needed.

Minimal frontend fix: explicit response latest_version_id selection, exact saved
version message, inline success/error and current version beside the save button,
busy feedback. On error the editor content remains intact.

Regression: Studio 4 passed, 1 opt-in live skipped. Strengthened test verifies
edited content equality, immutable V1, V2 evidence, latest pointer and fresh GET
returning both versions. User browser switching and visible feedback reacceptance
remain pending. No Prompt or frozen module changes; no Core E2E.
