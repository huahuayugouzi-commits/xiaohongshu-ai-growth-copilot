# Research AI Analysis — minimum task

Scope: analyze one manually entered reference with the configured real compatible
model. No scraping, batch import, topic generation, or strategy updates.

- Strict structured card: title, hook, structure, keywords, comments, pain points,
  popularity hypotheses, reusable patterns, missing information.
- Each interpretation is labeled a hypothesis; each quote must match the declared
  source field verbatim. No comment text means no comment analysis. Citation match
  is not proof that every interpretation is true; users still review the card.
- Exact input snapshot preserves null vs 0 and source URL. It is user-provided,
  not externally verified. One sample cannot establish causal popularity claims.
- Existing analysis JSON stores status/run_id/research_id/snapshot/result/error.
  No migrations or changes to frozen core models. Latest analysis replaces prior
  card; workflow rows remain. Historical analysis card versioning is not included.
- Atomic start and completion; concurrent analysis rejected. Failure has no result.
  Usage only from provider; no cost estimate. Failed attempts increment retry_count.
  Explicit interrupt allows recovery after process failure, rejects late results.
- Re-analysis clears topic confirmation; user reviews and confirms again.

Verification: Research input+analysis deterministic/mock cases 10 passed; real
deepseek-flash synthetic example 1 passed. The real output cited exact text,
distinguished unknown likes from zero collects, and refused causal claims.
Output artifact: workspace outputs/research-analysis-eval/research-live-result.json.
TypeScript/lint/build passed. Browser rendering/interaction pending user acceptance.

Restart backend, refresh #/research, select one saved reference, click 分析参考内容.
Check result/quotes/missing information, refresh persistence, then re-confirm for topics.
Stop after this task; do not automatically build Topics.
