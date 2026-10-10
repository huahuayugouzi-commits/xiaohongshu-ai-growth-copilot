"""Ordered SQLite migrations, shipped as Python so installed wheels include them."""

SCHEMA_V1 = """
CREATE TABLE accounts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL CHECK(length(name)>0),
    creator_type TEXT NOT NULL CHECK(creator_type IN ('new','existing')),
    current_profile_version_id TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(current_profile_version_id,id) REFERENCES profile_versions(id,account_id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE profile_versions (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK(typeof(version)='integer' AND version>0),
    raw_input TEXT NOT NULL CHECK(json_valid(raw_input)), created_at TEXT NOT NULL,
    UNIQUE(account_id,version), UNIQUE(id,account_id)
);
CREATE TABLE diagnoses (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
    profile_version_id TEXT NOT NULL, result TEXT NOT NULL CHECK(json_valid(result)),
    status TEXT NOT NULL CHECK(status IN ('pending','confirmed')), created_at TEXT NOT NULL,
    UNIQUE(id,profile_version_id,account_id),
    FOREIGN KEY(profile_version_id,account_id) REFERENCES profile_versions(id,account_id) ON DELETE CASCADE
);
CREATE TABLE research_items (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    source_url TEXT, title TEXT NOT NULL CHECK(length(title)>0), body TEXT NOT NULL,
    likes INTEGER CHECK(likes IS NULL OR (typeof(likes)='integer' AND likes>=0)),
    collects INTEGER CHECK(collects IS NULL OR (typeof(collects)='integer' AND collects>=0)),
    comments INTEGER CHECK(comments IS NULL OR (typeof(comments)='integer' AND comments>=0)),
    comment_samples TEXT NOT NULL CHECK(json_valid(comment_samples)),
    analysis TEXT CHECK(analysis IS NULL OR json_valid(analysis)),
    confirmed_for_topic INTEGER NOT NULL DEFAULT 0 CHECK(confirmed_for_topic IN (0,1)),
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(id,account_id)
);
CREATE TABLE topic_recommendations (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, profile_version_id TEXT NOT NULL,
    diagnosis_id TEXT NOT NULL, not_recommended TEXT NOT NULL CHECK(json_valid(not_recommended)),
    created_at TEXT NOT NULL, UNIQUE(id,account_id),
    FOREIGN KEY(diagnosis_id,profile_version_id,account_id)
        REFERENCES diagnoses(id,profile_version_id,account_id) ON DELETE CASCADE
);
CREATE TABLE recommendation_evidence (
    recommendation_id TEXT NOT NULL, research_id TEXT NOT NULL, account_id TEXT NOT NULL,
    snapshot TEXT NOT NULL CHECK(json_valid(snapshot)),
    PRIMARY KEY(recommendation_id,research_id),
    FOREIGN KEY(recommendation_id,account_id) REFERENCES topic_recommendations(id,account_id) ON DELETE CASCADE,
    FOREIGN KEY(research_id,account_id) REFERENCES research_items(id,account_id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE topics (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, recommendation_id TEXT NOT NULL,
    rank INTEGER NOT NULL CHECK(typeof(rank)='integer' AND rank BETWEEN 1 AND 3),
    content TEXT NOT NULL CHECK(json_valid(content)), created_at TEXT NOT NULL,
    UNIQUE(recommendation_id,rank), UNIQUE(id,account_id), UNIQUE(id,recommendation_id),
    FOREIGN KEY(recommendation_id,account_id) REFERENCES topic_recommendations(id,account_id) ON DELETE CASCADE
);
CREATE TABLE topic_evidence (
    topic_id TEXT NOT NULL, recommendation_id TEXT NOT NULL, research_id TEXT NOT NULL,
    PRIMARY KEY(topic_id,research_id),
    FOREIGN KEY(topic_id,recommendation_id) REFERENCES topics(id,recommendation_id) ON DELETE CASCADE,
    FOREIGN KEY(recommendation_id,research_id)
        REFERENCES recommendation_evidence(recommendation_id,research_id) ON DELETE CASCADE
);
CREATE TABLE drafts (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, topic_id TEXT NOT NULL,
    latest_version_id TEXT, created_at TEXT NOT NULL, UNIQUE(id,topic_id,account_id),
    FOREIGN KEY(topic_id,account_id) REFERENCES topics(id,account_id) ON DELETE CASCADE,
    FOREIGN KEY(latest_version_id,id) REFERENCES draft_versions(id,draft_id)
        DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE draft_versions (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, draft_id TEXT NOT NULL, topic_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK(typeof(version)='integer' AND version>0),
    content TEXT NOT NULL CHECK(json_valid(content)),
    source_evidence TEXT NOT NULL CHECK(json_valid(source_evidence)), created_at TEXT NOT NULL,
    UNIQUE(draft_id,version), UNIQUE(id,draft_id), UNIQUE(id,topic_id),
    FOREIGN KEY(draft_id,topic_id,account_id) REFERENCES drafts(id,topic_id,account_id) ON DELETE CASCADE
);
CREATE TABLE draft_version_evidence (
    draft_version_id TEXT NOT NULL, topic_id TEXT NOT NULL, research_id TEXT NOT NULL,
    PRIMARY KEY(draft_version_id,research_id),
    FOREIGN KEY(draft_version_id,topic_id) REFERENCES draft_versions(id,topic_id) ON DELETE CASCADE,
    FOREIGN KEY(topic_id,research_id) REFERENCES topic_evidence(topic_id,research_id) ON DELETE CASCADE
);
CREATE TABLE workflow_runs (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('diagnosis','research_analysis','topic_recommendation','content_creation')),
    status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
    model TEXT, started_at TEXT NOT NULL, completed_at TEXT,
    latency REAL CHECK(latency IS NULL OR latency>=0), error TEXT,
    retry_count INTEGER NOT NULL CHECK(typeof(retry_count)='integer' AND retry_count>=0),
    tokens INTEGER CHECK(tokens IS NULL OR (typeof(tokens)='integer' AND tokens>=0)),
    cost REAL CHECK(cost IS NULL OR cost>=0), usage TEXT CHECK(usage IS NULL OR json_valid(usage)),
    created_at TEXT NOT NULL,
    UNIQUE(account_id,workflow_id,retry_count),
    CHECK((status='running' AND completed_at IS NULL AND latency IS NULL AND error IS NULL)
       OR (status='succeeded' AND completed_at IS NOT NULL AND latency IS NOT NULL AND error IS NULL)
       OR (status='failed' AND completed_at IS NOT NULL AND latency IS NOT NULL AND length(error)>0)),
    CHECK(usage IS NOT NULL OR (tokens IS NULL AND cost IS NULL))
);
CREATE TRIGGER immutable_profile BEFORE UPDATE ON profile_versions
BEGIN SELECT RAISE(ABORT,'profile versions are immutable'); END;
CREATE TRIGGER immutable_draft_version BEFORE UPDATE ON draft_versions
BEGIN SELECT RAISE(ABORT,'draft versions are immutable'); END;
CREATE TRIGGER immutable_evidence BEFORE UPDATE ON recommendation_evidence
BEGIN SELECT RAISE(ABORT,'evidence snapshots are immutable'); END;
CREATE TRIGGER recommendation_context BEFORE INSERT ON topic_recommendations
WHEN NOT EXISTS (
    SELECT 1 FROM accounts a JOIN diagnoses d ON d.id=NEW.diagnosis_id
    WHERE a.id=NEW.account_id AND a.current_profile_version_id=NEW.profile_version_id
      AND d.account_id=a.id AND d.profile_version_id=NEW.profile_version_id AND d.status='confirmed'
)
BEGIN SELECT RAISE(ABORT,'recommendation requires current profile and confirmed diagnosis'); END;
CREATE TRIGGER confirmed_evidence BEFORE INSERT ON recommendation_evidence
WHEN NOT EXISTS (SELECT 1 FROM research_items WHERE id=NEW.research_id
    AND account_id=NEW.account_id AND confirmed_for_topic=1)
BEGIN SELECT RAISE(ABORT,'research must be confirmed and belong to this account'); END;
CREATE INDEX profile_account ON profile_versions(account_id);
CREATE INDEX diagnosis_profile ON diagnoses(profile_version_id,account_id);
CREATE INDEX research_account ON research_items(account_id);
CREATE INDEX recommendation_account ON topic_recommendations(account_id);
CREATE INDEX recommendation_diagnosis ON topic_recommendations(diagnosis_id,profile_version_id,account_id);
CREATE INDEX evidence_research ON recommendation_evidence(research_id,account_id);
CREATE INDEX topic_account ON topics(account_id);
CREATE INDEX topic_evidence_recommendation ON topic_evidence(recommendation_id,research_id);
CREATE INDEX draft_topic ON drafts(topic_id,account_id);
CREATE INDEX draft_account ON drafts(account_id);
CREATE INDEX draft_evidence_topic ON draft_version_evidence(topic_id,research_id);
CREATE INDEX workflow_account ON workflow_runs(account_id,started_at);
"""

SCHEMA_V2 = """
CREATE TRIGGER immutable_diagnosis_result BEFORE UPDATE OF id,account_id,profile_version_id,result,created_at ON diagnoses
BEGIN SELECT RAISE(ABORT,'diagnosis source and result are immutable'); END;
CREATE TRIGGER immutable_recommendation BEFORE UPDATE ON topic_recommendations
BEGIN SELECT RAISE(ABORT,'recommendations are immutable'); END;
CREATE TRIGGER immutable_topic BEFORE UPDATE ON topics
BEGIN SELECT RAISE(ABORT,'topics are immutable'); END;
CREATE TRIGGER immutable_topic_evidence BEFORE UPDATE ON topic_evidence
BEGIN SELECT RAISE(ABORT,'topic evidence is immutable'); END;
CREATE TRIGGER immutable_draft_evidence BEFORE UPDATE ON draft_version_evidence
BEGIN SELECT RAISE(ABORT,'draft evidence is immutable'); END;
CREATE TRIGGER immutable_draft_source BEFORE UPDATE OF id,account_id,topic_id,created_at ON drafts
BEGIN SELECT RAISE(ABORT,'draft source is immutable'); END;
CREATE TRIGGER immutable_completed_workflow BEFORE UPDATE ON workflow_runs
WHEN OLD.status IN ('succeeded','failed')
BEGIN SELECT RAISE(ABORT,'completed workflows are immutable; create a retry'); END;
CREATE INDEX draft_version_account ON draft_versions(account_id);
"""

SCHEMA_V3 = """
CREATE UNIQUE INDEX workflow_scope ON workflow_runs(id,account_id);
CREATE TABLE diagnosis_runs (
    run_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, profile_version_id TEXT NOT NULL,
    diagnosis_id TEXT,
    FOREIGN KEY(run_id,account_id) REFERENCES workflow_runs(id,account_id) ON DELETE CASCADE,
    FOREIGN KEY(profile_version_id,account_id) REFERENCES profile_versions(id,account_id) ON DELETE CASCADE,
    FOREIGN KEY(diagnosis_id,profile_version_id,account_id) REFERENCES diagnoses(id,profile_version_id,account_id) ON DELETE CASCADE
);
CREATE INDEX diagnosis_runs_profile ON diagnosis_runs(profile_version_id);
CREATE TABLE profile_projections (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, profile_version_id TEXT NOT NULL, diagnosis_id TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending','synced','failed')), error TEXT,
    relative_path TEXT, updated_at TEXT NOT NULL,
    FOREIGN KEY(profile_version_id,account_id) REFERENCES profile_versions(id,account_id) ON DELETE CASCADE,
    FOREIGN KEY(diagnosis_id,profile_version_id,account_id) REFERENCES diagnoses(id,profile_version_id,account_id) ON DELETE CASCADE
);
"""

MIGRATIONS = ((1, SCHEMA_V1), (2, SCHEMA_V2), (3, SCHEMA_V3))
