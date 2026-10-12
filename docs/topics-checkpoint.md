# TOP 3 Topics checkpoint (2026-10-12)

Implemented, NOT FROZEN: host full regression and browser acceptance pending.
Research AI accepted by user and frozen at 1081798.

Scope: current confirmed Profile/Diagnosis + 3–5 analyzed/confirmed references
produce exactly three ranked topics, rationale, Hook, quoted Profile/source
evidence, hypotheses and risks. Existing SQLite tables reused without migration.
Atomic persistence, immutable snapshots, stale-context rejection, account scoping,
truthful workflow errors/retry, batch history and evidence panel. No Studio.

Tests: 15 affected deterministic/mock passed, 2 live skipped; latest Topics suite
5 deterministic/mock + 1 real model passed (21.90s). TypeScript, scoped lint and
production build passed. Full collection collision (two tests packages) fixed
only in test imports. Sandbox full run stopped at pytest temp WinError 5:
14 passed, 5 skipped, 1 setup error. Host regression remains pending.

Real-model artifacts: workspace outputs/topics-eval. Synthetic Profile/references
and fixture Research analyses; NOT full real Research-to-Topics E2E.
Initial schema-valid output invented completed experiments/counts in Hook.
Retry inferred unpublished history and mismatched step counts. Root cause:
proposal/history distinction insufficient in Topics prompt. Tightened that prompt
only: future/conditional experiments, unknown history, no numbered promises.
Final output passed schema/exact quotes and semantic review for observed issues.
Finite validation cannot guarantee no semantic hallucinations; human review remains.

Manual acceptance: restart backend, open /#/topics; select 3–5 eligible references,
generate TOP 1/2/3, inspect why-now and evidence (Profile/Diagnosis/source/counts),
refresh and verify persistence. New batch must preserve prior batch. Missing
prerequisites must guide user to Account/Research, never produce fake success.

Next after acceptance: Topic -> Studio Draft. No Studio changes in this checkpoint.
