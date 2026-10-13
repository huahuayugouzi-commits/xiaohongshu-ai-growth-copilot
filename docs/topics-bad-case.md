# Topics Bad Case — Truncation (2026-10-13)

User reported two failed browser workflows. Historical raw responses were not
retained; both failed before parse_topics under a combined adapter guard message.
Reproduction used the current confirmed Profile/Diagnosis and all four eligible
confirmed ResearchItems. Original and fixed context SHA256 both:
31c19115886b6279b5a65b1e41cdc44752f43236a422542ec2c96cc01c61d184.

## Root cause evidence
- Original reproduction: HTTP 200, text response, sensitive_match=false,
  finish_reason=length, completion_tokens=4000 (exact max_tokens=4000).
- Input 49011 characters / 27114 prompt tokens including schema/prompt.
- JSON was incomplete (JSONDecodeError), so downstream schema/required fields/
  exactly-three/profile/source validation could not complete. No invalid save.
- Classification A: Truncation; not a proven sensitive false positive or transport
  failure. Historical two requests cannot individually be reconstructed.
- Research shares the ambiguous-error-message defect, but its historical root
  cause remains unknown; cannot assert both failures were truncation.

## Minimal fix
Only Topics: shorter field-specific output guidance; one relevant short Profile
quote and source quote per topic, one assumption/risk, no repeated background.
All fields and validators remain, token cap unchanged. Separate safe guard error
codes and preserve actual provider usage on adapter rejection, never invent cost.
Frozen Account/Diagnosis/Research and Studio not modified.

## Regression
- Same-input real workflow: stop, completion_tokens=3357, exactly 3 topics;
  JSON/schema/ranks/reasons/Profile quotes/source IDs/source quotes PASS.
- reason field is existing why_now, plus priority_reason (no schema rename).
- Saved recommendation 4c217dcb-5c2e-43ff-b54f-d45b8ac7ff22; fresh repository
  returns 3 topics and 3 evidence records. Original failed workflows retained.
- Semantic review: proposed angles, assumptions and risks remain separated;
  no invented completed experiments/counts found in this output. Not a universal
  semantic guarantee. Human review of suggestions still required.
- Topics tests: 6 passed, 1 skipped (opt-in live synthetic test); same-input live
  run above performed separately. Added deterministic truncated-response regression
  asserting no topics saved, accurate failure reason and actual usage retention.
- Local diagnostic artifacts: workspace outputs/topics-bad-case (not committed).

Next: restart backend to load fix, refresh Topics and inspect the already-saved
recommendation/evidence. Browser refresh acceptance remains user verification.
No repeated generation required, no Studio work.
