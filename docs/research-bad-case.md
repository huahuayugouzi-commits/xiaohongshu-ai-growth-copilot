# Research adapter rejection — 2026-10-13

Status: recovery verified; historical root cause UNRESOLVED (not classified as
Truncation, Schema Error, Sensitive Config False Positive or Evidence Validation
without evidence). Do not claim the intermittent failure has been eliminated.

Original workflow was failed before parse_card, with a combined adapter error.
Raw historical response and finish_reason were not retained. It is impossible
to distinguish non-text content, exact API-key echo, and finish_reason=length
from that stored message. JSON/schema/required fields/evidence were not reached.

Reproduced the same ResearchItem snapshot three times without modifying Prompt:
all finish_reason=stop, sensitive_match=false, all required fields/JSON/schema/
quotes valid. Body 953 chars; 24 comments, total 957 chars; system/schema 2617
chars; serialized input 2337 chars; original max_tokens=3000. Two captured usage
values: completion_tokens 1416 and 1602 (third original call did not record usage).

Minimal change: split the three existing rejection conditions into explicit safe
error codes. Exact key detection remains unchanged; never display matching text.
No Prompt, token cap, schema, quote validation, Topics or Studio changes.
Diagnostic script takes explicit account/item IDs, saves only secret-checked
response content locally under workspace outputs/research-bad-case, not in Git.

Same-item full workflow after change: succeeded, finish_reason=stop,
completion_tokens=1859; JSON/all required fields/schema/quotes PASS. Original
failed workflow retained; new success saved with retry_count incremented.
Research regression including a normal real-model case: 11 passed, 0 skipped,
11.74s. This demonstrates recovery, not causality of a generation fix.

Next: restart backend to activate differentiated errors, refresh Research to see
saved result. No repeat analysis needed for the recovered item. If recurring,
the persisted error code identifies the branch without exposing any secret.
