# Growth Copilot — SQLite Growth Data Layer (Phase 2)

中文产品描述：小红书 AI 增长助手。

Growth Copilot is built upon the open-source Easel project. Easel's Apache-2.0
LICENSE, existing copyright notices and attribution are preserved. Internal
`easel` package names remain unchanged. User-visible branding will be changed
in the frontend implementation phase, not as part of this data-layer change.

## Scope

This module provides persistence only. It does **not** implement AI diagnosis,
research analysis, recommendations, content generation, HTTP endpoints, pages,
scraping or publishing. Stored JSON is a data contract, not validated AI output.
Later phases must validate their own structured AI outputs and Fact Lock rules
before calling this repository. `create_recommendation` stores a supplied bundle;
it does not generate recommendations.

Existing `easel/persona.py`, `profiles/`, `web/app.py`, Skills and frontend code
are unchanged. The Growth database is the source of truth for Growth objects.
Markdown projection/synchronization is not enabled in Phase 2. Future projection
must use stable account IDs and a dedicated directory, never overwrite existing
Persona files, and surface projection failures explicitly.

## Initialization and database location

From the repository root with the virtual environment Python:

```powershell
& .\.venv\Scripts\python.exe -m easel.growth
```

Default: `<repository>/data/growth.sqlite3`, independent of the shell's current
working directory. `data/` and its journal files are gitignored. Override with
`GROWTH_DB_PATH` (a relative value is resolved against the process working directory)
or `python -m easel.growth --db PATH`. Explicit paths take precedence over the
environment. `Database.initialize()` is also available for later application
startup; importing the module does not create a database or change Easel storage.

Migrations are ordered, packaged Python SQL constants in `migrations.py`:

- V1: nine core tables, three evidence relation tables, indexes and constraints.
- V2: additional immutable source/audit triggers and a lookup index.

`schema_migrations` tracks applied versions. Initialization serializes migration
work with `BEGIN IMMEDIATE`; DDL and version writes commit together. It is
idempotent, preserves existing data, and rejects unsupported/gapped/newer migration
histories. There is no automatic downgrade. Back up a database before upgrading
a deployed installation. Do not copy a live SQLite file during a write transaction.

Each operation uses a fresh connection with foreign keys enabled and a 10-second
busy timeout. Writes use `BEGIN IMMEDIATE`, commit or roll back atomically, and
close the connection. SQLite's default rollback journal is retained; no extra
service, ORM or new Python dependency is needed. This is a local, single-user MVP,
not a multi-user authorization or high-throughput database design.

## Models and relations

All nine core objects have UUID4 string IDs and UTC ISO-8601 `created_at` values.

| Object | Fields and constraints |
|---|---|
| Account | name, creator_type (`new`/`existing`), current_profile_version_id |
| ProfileVersion | account_id, monotonic version, raw_input JSON; append-only |
| Diagnosis | account_id, profile_version_id, result JSON, pending/confirmed |
| ResearchItem | account_id, source_url, title, body, nullable likes/collects/comments, comment_samples, analysis, confirmed_for_topic, updated_at |
| TopicRecommendation | account_id, profile_version_id, diagnosis_id, not_recommended |
| Topic | account_id, recommendation_id, rank 1–3, content JSON |
| Draft | account_id, topic_id, latest_version_id |
| DraftVersion | account_id, draft_id, topic_id, version, content, source_evidence; append-only |
| WorkflowRun | account_id, workflow_id, stage, status, model, started_at, completed_at, latency (seconds), error, retry_count, tokens, cost, usage |

Composite foreign keys ensure parent/child account scope, correct
Diagnosis/Profile pairing, and correct Account/Draft version pointers. Version
numbers are unique within their owner.

Research input metrics accept only nonnegative integers or `None`. `None` is
SQL NULL (unknown); `0` is a known zero. Negative values, floats, numeric strings
and booleans are rejected by the input contract. No truthiness fallback is used.

Three normalized relation tables preserve evidence:

| Relation | Guarantee |
|---|---|
| recommendation_evidence | research belongs to the same account and was confirmed when attached; a full immutable ResearchItem snapshot is stored |
| topic_evidence | topic references only research in its recommendation input snapshot |
| draft_version_evidence | version references only its Topic's evidence |

The authoritative evidence IDs come from these relations, not arbitrary IDs
inside a free-form content JSON payload. `topic_context()` resolves Account,
ProfileVersion, Diagnosis, recommendation and research snapshots. DraftVersion's
`source_evidence` is built by the repository from this context, not supplied by
the caller. Original text, comment samples, null metrics and confirmed status
are frozen in recommendation snapshots. Later Research edits do not rewrite
historical recommendations or drafts.

## Repository interface

```python
from easel.growth import Database, GrowthRepository
from easel.growth.models import AccountInput, ResearchInput

database = Database()
database.initialize()
repository = GrowthRepository(database)
account = repository.create_account(AccountInput(name="我的账号", creator_type="new"))
profile = repository.create_profile_version(
    account.id, {"occupation": "用户明确输入的职业"}, expected_current_id=None,
)
research = repository.create_research(
    account.id, ResearchInput(title="手动导入", body="原文", likes=None, collects=0),
)
```

Every object read/update/delete requires `account_id`; this is data integrity
scoping, not a replacement for authentication if multi-user support is added.
Methods return Pydantic records, not raw database connections.

| Method | Meaning |
|---|---|
| create_account / update_account / list_accounts | Account metadata CRUD |
| create_profile_version(..., expected_current_id=...) | Append Profile; atomically change current pointer; stale caller gets Conflict |
| create_diagnosis / confirm_diagnosis | Persist supplied result then confirm; both require current Profile; result immutable |
| create_research / update_research / confirm_research | Manual Research CRUD; replacement edit clears confirmation even if request sets it true |
| create_recommendation | Atomically persist three supplied topics and ≥3 distinct confirmed research snapshots; requires current Profile and confirmed Diagnosis |
| topic_context / recommendation_evidence | Resolve provenance and frozen Research snapshots |
| create_draft | Atomically create Draft and V1 |
| save_draft_version(..., expected_latest_id=...) | Append version and update latest pointer; conflict on stale edit |
| start_workflow / finish_workflow | Record lifecycle only; no AI calls |
| get / list | Whitelisted table names, account scoping; list has limit/offset |
| delete | Explicit aggregate deletion with documented cascades |

`DraftContent` supports title, hook, body, cta, tags, cover_text,
visual_suggestions and facts_to_verify. Historical versions cannot be edited or
individually deleted through the repository. Topic/Recommendation updates are
also immutable: persist a new recommendation bundle instead.

`NotFound` reports absent/out-of-scope IDs; `Conflict` reports invariant,
foreign-key or stale-version conflicts. Pydantic validation errors/ValueError
report malformed input. SQLite I/O/busy failures propagate rather than being
silently converted into success. Future routes should map these deliberately
to HTTP 404/409/422/503, without exposing sensitive internal errors.

## Deletion and update policy

- Delete Account: cascade all owned data, including Research and WorkflowRun.
- Delete Diagnosis: cascade its Recommendations → Topics → Drafts → versions.
- Delete Recommendation: cascade its Topics, evidence joins, Drafts and versions.
- Delete Draft: cascade versions and their evidence joins.
- Delete unreferenced Research: allowed. Referenced Research: rejected until its
  recommendation aggregate is explicitly removed. Deferred foreign keys allow
  a complete Account deletion while rejecting isolated evidence deletion.
- Individual ProfileVersion, DraftVersion or TOP3 member deletion is rejected.
- Profile updates append V2/V3; old diagnosis/topic/draft records remain readable,
  but cannot be used as current recommendation context. Historical draft editing
  stays tied to its original Topic/Profile evidence, never silently rebased.
- Draft and Profile concurrent saves serialize and compare caller pointers; one
  stale writer fails rather than overwriting another writer's version.

Hard aggregate deletion is not undoable in-app; a future UI must ask before
deleting an aggregate and explain downstream impact. This phase adds no delete UI.

## WorkflowRun contract

Stages: `diagnosis`, `research_analysis`, `topic_recommendation`, `content_creation`.
Statuses: `running` → `succeeded` or `failed`. Finished runs cannot be overwritten.
A retry creates a new row with the same workflow_id and an incremented retry_count;
only the same stage of a failed run can be retried. Duplicate retries are rejected.

Absent model name, token counts and cost remain NULL. `finish_workflow` records
elapsed wall-clock seconds; it does not estimate model cost. Optional `ProviderUsage`
requires a source label and raw provider response usage metadata. Future adapters
must pass only usage actually returned by their model interface; the persistence
layer cannot independently authenticate a caller's provider response. Unit tests
use explicitly labeled fixtures, not real API usage. Tokens do not imply a known
cost; either can independently be NULL. No API keys should be included in result,
error or usage payloads; future AI adapters must redact them before persistence.

Interrupted processes leave `running` runs visible; there is no scheduler,
automatic retry or crash-recovery workflow in Phase 2. Phase 3 must show this state
honestly rather than treating it as success. Likewise, persisting a business result
and completing its WorkflowRun are currently separate calls; future orchestration
must handle the interruption window explicitly before claiming workflow success.

## Validation

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_growth_data.py -q -p no:cacheprovider
& .\.venv\Scripts\python.exe -X utf8 -m pytest tests skills/openclaw/skill-wechat-publisher/tests -q --tb=short -p no:cacheprovider
```

The complete regression command includes the original 43 tests outside the main
`tests/` directory. Collection totals 536: the original 474 plus 62 new tests.

Growth tests use isolated on-disk UUID directories under `.scratch/growth-tests/`
and remove only those directories. They do not change OS ACLs or execution policy.
They cover CRUD, null vs zero, all nine records, scoped FKs, cascade/restrict,
immutable versions and snapshots, duplicate versions, concurrency, rollback,
idempotent initialization, incremental migration, reopened persistence and Persona
compatibility. Runtime model behavior, UI refresh and AI quality are later-phase
tests, not claimed by these data-layer tests.

## Phase 3 boundary

Ready interfaces: AccountInput, ProfileVersion.raw_input, create_diagnosis,
confirm_diagnosis, current-profile guards, WorkflowRun lifecycle, scoped readers
and explicit initialization. Still to implement in Phase 3: API registration,
Account/Diagnosis field-specific contracts, model adapters, Fact Lock, validation,
error UX, workflow/result consistency and any controlled Markdown projection.
Do not expose generic repository table operations directly as unrestricted HTTP
endpoints. No frontend product-name migration has been performed yet.
