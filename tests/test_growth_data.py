"""Real on-disk SQLite tests; no LLM, browser, network or Persona writes."""

import json
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from easel.growth import Conflict, Database, GrowthRepository, NotFound
from easel.growth.models import AccountInput, DraftContent, ProviderUsage, ResearchInput, TopicInput


@pytest.fixture
def storage_dir():
    # Project-local real files; does not depend on OS-private pytest temp ACLs.
    root = Path(__file__).resolve().parents[1] / ".scratch" / "growth-tests"
    path = root / str(uuid4())
    path.mkdir(parents=True)
    yield path
    assert path.resolve().parent == root.resolve()
    shutil.rmtree(path)


@pytest.fixture
def repo(storage_dir):
    database = Database(storage_dir / "growth.sqlite3")
    database.initialize()
    return GrowthRepository(database)


@pytest.fixture
def context(repo):
    account = repo.create_account(AccountInput(name="中文账号", creator_type="new"))
    profile = repo.create_profile_version(account.id, {"occupation": "设计师"}, expected_current_id=None)
    diagnosis = repo.create_diagnosis(account.id, profile.id, {"positioning_hypothesis": "待验证的定位"})
    diagnosis = repo.confirm_diagnosis(account.id, diagnosis.id)
    research = [repo.create_research(account.id, ResearchInput(title=f"参考{i}", body="原文", confirmed_for_topic=True)) for i in range(3)]
    return account, profile, diagnosis, research


def recommend(repo, context, *, research_ids=None, topics=None):
    account, profile, diagnosis, research = context
    ids = research_ids if research_ids is not None else [r.id for r in research]
    entries = topics if topics is not None else [TopicInput(rank=i+1, content={"topic": f"方向{i}"}, research_ids=[ids[i]]) for i in range(3)]
    return repo.create_recommendation(account.id, profile.id, diagnosis.id, ids, entries, not_recommended=["无依据的增长保证"])


@pytest.fixture
def chain(repo, context):
    rec = recommend(repo, context)
    account = context[0]
    topic = repo.list("topics", account_id=account.id)[0]
    draft = repo.create_draft(account.id, topic.id, DraftContent(title="初稿", body="正文"))
    return (*context, rec, topic, draft)


def test_initialize_idempotent_and_integrity(repo):
    repo.database.initialize()
    with closing(repo.database.connect()) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert [r[0] for r in conn.execute("SELECT version FROM schema_migrations")] == [1, 2, 3]


def test_migration_failure_rolls_back(storage_dir, monkeypatch):
    import easel.growth.database as module
    db = Database(storage_dir / "failure.sqlite3")
    monkeypatch.setattr(module, "MIGRATIONS", ((1, "CREATE TABLE partial(id TEXT);\nNOT VALID SQL;\n"),))
    with pytest.raises(sqlite3.OperationalError):
        db.initialize()
    with closing(db.connect()) as conn:
        assert not conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()


def test_future_migration_rejected(repo):
    with repo.database.transaction() as conn:
        conn.execute("INSERT INTO schema_migrations VALUES (99)")
    with pytest.raises(RuntimeError, match="Unsupported"):
        repo.database.initialize()


def test_path_override(storage_dir, monkeypatch):
    monkeypatch.setenv("GROWTH_DB_PATH", str(storage_dir / "configured.sqlite3"))
    assert Database().path == storage_dir / "configured.sqlite3"
    assert Database(storage_dir / "explicit.sqlite3").path == storage_dir / "explicit.sqlite3"


def test_account_crud(repo):
    a = repo.create_account(AccountInput(name="A", creator_type="new"))
    assert str(UUID(a.id)) == a.id
    assert a.created_at.endswith("+00:00")
    assert a.current_profile_version_id is None
    assert repo.get("accounts", a.id, account_id=a.id) == a
    assert repo.list_accounts() == [a]
    updated = repo.update_account(a.id, AccountInput(name="B", creator_type="existing"))
    assert updated.name == "B" and updated.id == a.id
    repo.delete("accounts", a.id, account_id=a.id)
    with pytest.raises(NotFound):
        repo.get("accounts", a.id, account_id=a.id)


def test_profile_append_and_conflict(repo, context):
    a, p, d, _ = context
    p2 = repo.create_profile_version(a.id, {"occupation": "教师"}, expected_current_id=p.id)
    assert p2.version == 2
    assert repo.get("profile_versions", p.id, account_id=a.id).raw_input == {"occupation": "设计师"}
    assert repo.get("accounts", a.id, account_id=a.id).current_profile_version_id == p2.id
    assert repo.get("diagnoses", d.id, account_id=a.id).profile_version_id == p.id
    with pytest.raises(Conflict):
        repo.create_profile_version(a.id, {}, expected_current_id=p.id)
    with pytest.raises(Conflict):
        repo.create_diagnosis(a.id, p.id, {})
    with pytest.raises(Conflict):
        repo.confirm_diagnosis(a.id, d.id)
    with pytest.raises(Conflict):
        recommend(repo, context)


@pytest.mark.parametrize("field", ["likes", "collects", "comments"])
def test_null_is_not_zero(repo, context, field):
    a = context[0]
    unknown = repo.create_research(a.id, ResearchInput(title="未知", body="", **{field: None}))
    zero = repo.create_research(a.id, ResearchInput(title="零", body="", **{field: 0}))
    assert getattr(repo.get("research_items", unknown.id, account_id=a.id), field) is None
    assert getattr(repo.get("research_items", zero.id, account_id=a.id), field) == 0
    with closing(repo.database.connect()) as conn:
        assert conn.execute(f"SELECT {field} IS NULL FROM research_items WHERE id=?", (unknown.id,)).fetchone()[0] == 1
        assert conn.execute(f"SELECT {field} IS NULL FROM research_items WHERE id=?", (zero.id,)).fetchone()[0] == 0


@pytest.mark.parametrize("value", [-1, 1.5, "0", True])
@pytest.mark.parametrize("field", ["likes", "collects", "comments"])
def test_invalid_metric_rejected(field, value):
    with pytest.raises(ValidationError):
        ResearchInput(title="参考", body="", **{field: value})


def test_research_crud(repo, context):
    a = context[0]
    r = repo.create_research(a.id, ResearchInput(source_url="https://example.org/note", title="引用", body="内容", comment_samples=["评论"], likes=0))
    assert repo.confirm_research(a.id, r.id).confirmed_for_topic
    updated = repo.update_research(a.id, r.id, ResearchInput(title="改正", body="原文修订", likes=None, confirmed_for_topic=True))
    assert updated.id == r.id and updated.likes is None
    assert not updated.confirmed_for_topic
    repo.delete("research_items", r.id, account_id=a.id)
    with pytest.raises(NotFound):
        repo.get("research_items", r.id, account_id=a.id)


def test_pending_diagnosis_cannot_recommend(repo, context):
    a, p, _, rs = context
    pending = repo.create_diagnosis(a.id, p.id, {})
    with pytest.raises(Conflict, match="confirmed diagnosis"):
        recommend(repo, (a, p, pending, rs))
    assert repo.list("topic_recommendations", account_id=a.id) == []


def test_unconfirmed_evidence_atomic_rollback(repo, context):
    a, _, _, rs = context
    repo.confirm_research(a.id, rs[-1].id, False)
    with pytest.raises(Conflict, match="confirmed"):
        recommend(repo, context)
    assert repo.list("topics", account_id=a.id) == []
    assert repo.list("topic_recommendations", account_id=a.id) == []
    with closing(repo.database.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM recommendation_evidence").fetchone()[0] == 0


def test_cross_account_scope(repo, context):
    a, p, d, rs = context
    other = repo.create_account(AccountInput(name="other", creator_type="existing"))
    for table, record in [("profile_versions", p), ("diagnoses", d), ("research_items", rs[0])]:
        with pytest.raises(NotFound):
            repo.get(table, record.id, account_id=other.id)
        assert not repo.list(table, account_id=other.id)
    with pytest.raises(NotFound):
        repo.create_diagnosis(other.id, p.id, {})
    foreign = repo.create_research(other.id, ResearchInput(title="外部", body="", confirmed_for_topic=True))
    with pytest.raises(NotFound):
        recommend(repo, context, research_ids=[rs[0].id, rs[1].id, foreign.id])
    with pytest.raises(NotFound):
        repo.delete("research_items", rs[0].id, account_id=other.id)
    assert len(repo.list("research_items", account_id=a.id)) == 3


def test_missing_evidence_rejected(repo, context):
    ids = [r.id for r in context[3]][:2] + [str(uuid4())]
    with pytest.raises(NotFound):
        recommend(repo, context, research_ids=ids)


@pytest.mark.parametrize("ranks", [[1, 2], [1, 1, 3], [1, 2, 3, 3]])
def test_top_three_bundle_contract(repo, context, ranks):
    rid = context[3][0].id
    with pytest.raises(ValueError):
        recommend(repo, context, topics=[TopicInput(rank=i, content={}, research_ids=[rid]) for i in ranks])


def test_out_of_snapshot_evidence_rejected(repo, context):
    other = repo.create_research(context[0].id, ResearchInput(title="not in input", body="", confirmed_for_topic=True))
    entries = [TopicInput(rank=i, content={}, research_ids=[other.id]) for i in range(1, 4)]
    with pytest.raises(ValueError, match="subset"):
        recommend(repo, context, topics=entries)


def test_duplicate_or_insufficient_input_rejected(repo, context):
    ids = [r.id for r in context[3]]
    topics = [TopicInput(rank=i, content={}, research_ids=[ids[0]]) for i in range(1, 4)]
    for invalid in [ids[:2], [ids[0]] * 3]:
        with pytest.raises(ValueError, match="distinct"):
            recommend(repo, context, research_ids=invalid, topics=topics)


def test_provenance_and_snapshot_survive_edit(repo, chain):
    a, p, d, rs, rec, topic, draft = chain
    evidence = repo.topic_context(a.id, topic.id)
    assert evidence["profile_version_id"] == p.id
    assert evidence["diagnosis_id"] == d.id
    assert evidence["account_id"] == a.id
    before = repo.recommendation_evidence(a.id, rec.id)
    for r in rs:
        repo.update_research(a.id, r.id, ResearchInput(title="later edit", body="new text", likes=0))
    assert repo.recommendation_evidence(a.id, rec.id) == before
    assert repo.topic_context(a.id, topic.id) == evidence
    v1 = repo.get("draft_versions", draft.latest_version_id, account_id=a.id)
    assert v1.source_evidence == evidence
    assert all(s["likes"] is None for s in evidence["research_snapshots"])
    with closing(repo.database.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM draft_version_evidence WHERE draft_version_id=?", (v1.id,)).fetchone()[0] == len(evidence["research_ids"])


def test_draft_versions_and_optimistic_conflict(repo, chain):
    a, _, _, _, _, topic, draft = chain
    v1 = repo.get("draft_versions", draft.latest_version_id, account_id=a.id)
    v2 = repo.save_draft_version(a.id, draft.id, DraftContent(title="人工编辑", facts_to_verify=["数据待核实"]), expected_latest_id=v1.id)
    assert v2.version == 2 and v2.topic_id == topic.id and v2.draft_id == draft.id
    assert v2.content.facts_to_verify == ["数据待核实"]
    assert repo.get("draft_versions", v1.id, account_id=a.id) == v1
    assert repo.get("drafts", draft.id, account_id=a.id).latest_version_id == v2.id
    with pytest.raises(Conflict):
        repo.save_draft_version(a.id, draft.id, DraftContent(), expected_latest_id=v1.id)
    assert len(repo.list("draft_versions", account_id=a.id)) == 2


def test_concurrent_version_save(repo, chain):
    a, *_, draft = chain
    def save(index):
        try:
            return repo.save_draft_version(a.id, draft.id, DraftContent(title=str(index)), expected_latest_id=draft.latest_version_id)
        except Conflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, [1, 2]))
    assert sum(result is not None for result in results) == 1
    assert len(repo.list("draft_versions", account_id=a.id)) == 2


@pytest.mark.parametrize("table,index", [("profile_versions", 1), ("topics", 5)])
def test_individual_history_delete_forbidden(repo, chain, table, index):
    with pytest.raises(Conflict):
        repo.delete(table, chain[index].id, account_id=chain[0].id)


def test_database_immutable_versions(repo, chain):
    a, p, *_, draft = chain
    for table, field, value, entity_id in [("profile_versions", "raw_input", "{}", p.id),
                                            ("draft_versions", "content", "{}", draft.latest_version_id)]:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with repo.database.transaction() as conn:
                conn.execute(f"UPDATE {table} SET {field}=? WHERE id=?", (value, entity_id))


def test_database_foreign_keys_and_pointer_scope(repo, chain):
    a, p, _, _, _, topic, draft = chain
    b = repo.create_account(AccountInput(name="B", creator_type="new"))
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("UPDATE accounts SET current_profile_version_id=? WHERE id=?", (p.id, b.id))
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("UPDATE drafts SET account_id=? WHERE id=?", (b.id, draft.id))
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("INSERT INTO draft_version_evidence VALUES (?,?,?)", (draft.latest_version_id, topic.id, str(uuid4())))


def test_database_metric_check(repo, context):
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("UPDATE research_items SET likes=-1 WHERE id=?", (context[3][0].id,))


def test_referenced_research_delete_restricted(repo, chain):
    a, _, _, rs, *_ = chain
    with pytest.raises(Conflict):
        repo.delete("research_items", rs[0].id, account_id=a.id)
    assert repo.get("research_items", rs[0].id, account_id=a.id)


@pytest.mark.parametrize("aggregate", ["accounts", "diagnoses", "topic_recommendations", "drafts"])
def test_cascade_delete(repo, chain, aggregate):
    a, _, d, rs, rec, _, draft = chain
    run = repo.start_workflow(a.id, "diagnosis")
    roots = {"accounts": a, "diagnoses": d, "topic_recommendations": rec, "drafts": draft}
    repo.delete(aggregate, roots[aggregate].id, account_id=a.id)
    assert repo.list("drafts", account_id=a.id) == []
    assert repo.list("draft_versions", account_id=a.id) == []
    if aggregate != "drafts":
        assert repo.list("topics", account_id=a.id) == []
        assert repo.list("topic_recommendations", account_id=a.id) == []
    if aggregate == "accounts":
        for table in ["accounts", "profile_versions", "diagnoses", "research_items", "workflow_runs"]:
            assert repo.list(table, account_id=a.id) == []
    else:
        assert repo.get("workflow_runs", run.id, account_id=a.id)
        assert len(repo.list("research_items", account_id=a.id)) == len(rs)
    with closing(repo.database.connect()) as conn:
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert conn.execute("SELECT COUNT(*) FROM draft_version_evidence").fetchone()[0] == 0


def test_workflow_lifecycle_retry_and_missing_usage(repo, context):
    a = context[0]
    run = repo.start_workflow(a.id, "diagnosis", model="test-provider-model")
    assert run.status == "running" and run.tokens is None and run.cost is None
    failed = repo.finish_workflow(a.id, run.id, status="failed", error="invalid structured output")
    assert failed.error and failed.completed_at and failed.latency >= 0
    retried = repo.start_workflow(a.id, "diagnosis", retry_of=failed.id)
    assert retried.retry_count == 1 and retried.workflow_id == run.workflow_id
    with pytest.raises(Conflict):
        repo.start_workflow(a.id, "diagnosis", retry_of=failed.id)
    done = repo.finish_workflow(a.id, retried.id, status="succeeded")
    assert done.usage is None and done.tokens is None and done.cost is None
    with pytest.raises(Conflict):
        repo.finish_workflow(a.id, retried.id, status="succeeded")
    with pytest.raises(Conflict):
        repo.start_workflow(a.id, "diagnosis", retry_of=done.id)
    repo.delete("workflow_runs", run.id, account_id=a.id)
    with pytest.raises(NotFound):
        repo.get("workflow_runs", run.id, account_id=a.id)


def test_provider_usage_preserved_without_estimation(repo, context):
    # Explicit fixture, not a real model call or claimed production cost.
    usage = ProviderUsage(source="test fixture", tokens=0, cost=0.0, currency="USD", raw={"total_tokens": 0, "cost": 0})
    run = repo.start_workflow(context[0].id, "research_analysis")
    done = repo.finish_workflow(context[0].id, run.id, status="succeeded", usage=usage)
    assert done.tokens == 0 and done.cost == 0 and done.usage == usage


@pytest.mark.parametrize("status,error", [("running", None), ("succeeded", "error"), ("failed", None)])
def test_workflow_invalid_completion(repo, context, status, error):
    run = repo.start_workflow(context[0].id, "diagnosis")
    with pytest.raises(ValueError):
        repo.finish_workflow(context[0].id, run.id, status=status, error=error)
    assert repo.get("workflow_runs", run.id, account_id=context[0].id).status == "running"


def test_reopen_persistence_all_objects(repo, chain):
    a, p, d, rs, rec, topic, draft = chain
    run = repo.start_workflow(a.id, "content_creation")
    finished = repo.finish_workflow(a.id, run.id, status="succeeded")
    expected = {table: repo.list(table, account_id=a.id) for table in
                ["accounts", "profile_versions", "diagnoses", "research_items", "topic_recommendations", "topics", "drafts", "draft_versions", "workflow_runs"]}
    reopened = Database(repo.database.path)
    reopened.initialize()
    fresh = GrowthRepository(reopened)
    for table, records in expected.items():
        assert fresh.list(table, account_id=a.id) == records
    assert fresh.get("workflow_runs", finished.id, account_id=a.id).status == "succeeded"
    assert fresh.topic_context(a.id, topic.id)["profile_version_id"] == p.id


def test_invalid_table_and_json(repo, context):
    with pytest.raises(ValueError):
        repo.list("accounts; DROP TABLE accounts", account_id=context[0].id)
    with pytest.raises(ValueError):
        repo.create_profile_version(context[0].id, {"value": float("nan")}, expected_current_id=context[1].id)
    assert len(repo.list("profile_versions", account_id=context[0].id)) == 1


def test_existing_persona_untouched(repo, context, monkeypatch, storage_dir):
    from easel import persona
    legacy = storage_dir / "profiles" / "legacy"
    legacy.mkdir(parents=True)
    (legacy / "identity.md").write_text("原有 Easel 画像", encoding="utf-8")
    monkeypatch.setattr(persona, "PROFILES_DIR", legacy.parent)
    assert persona.list_personas() == ["legacy"]
    assert persona.load_profile_text("legacy") == "原有 Easel 画像"
    repo.create_profile_version(context[0].id, {"occupation": "新资料"}, expected_current_id=context[1].id)
    assert persona.load_profile_text("legacy") == "原有 Easel 画像"


def test_upgrade_v1_keeps_data(storage_dir, monkeypatch):
    import easel.growth.database as module
    migrations = module.MIGRATIONS
    db = Database(storage_dir / "upgrade.sqlite3")
    monkeypatch.setattr(module, "MIGRATIONS", migrations[:1])
    db.initialize()
    r = GrowthRepository(db)
    account = r.create_account(AccountInput(name="Before upgrade", creator_type="new"))
    monkeypatch.setattr(module, "MIGRATIONS", migrations)
    db.initialize()
    assert r.get("accounts", account.id, account_id=account.id) == account
    with closing(db.connect()) as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 3


def test_concurrent_profile_save(repo, context):
    account, profile, *_ = context
    def save(index):
        try:
            return repo.create_profile_version(account.id, {"index": index}, expected_current_id=profile.id)
        except Conflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, [1, 2]))
    assert sum(result is not None for result in results) == 1
    assert len(repo.list("profile_versions", account_id=account.id)) == 2


def test_draft_creation_failure_rolls_back(repo, context, monkeypatch):
    recommend(repo, context)
    topic = repo.list("topics", account_id=context[0].id)[0]
    original = repo._append_draft
    def fail_after_writes(*args):
        original(*args)
        raise RuntimeError("simulated transaction failure")
    monkeypatch.setattr(repo, "_append_draft", fail_after_writes)
    with pytest.raises(RuntimeError):
        repo.create_draft(context[0].id, topic.id, DraftContent(title="never committed"))
    assert repo.list("drafts", account_id=context[0].id) == []
    assert repo.list("draft_versions", account_id=context[0].id) == []


def test_diagnosis_profile_mismatch(repo, context):
    a, p, d, rs = context
    p2 = repo.create_profile_version(a.id, {}, expected_current_id=p.id)
    with pytest.raises(Conflict, match="mismatch"):
        recommend(repo, (a, p2, d, rs))


def test_foreign_draft_and_diagnosis_sql_rejected(repo, chain):
    a, p, d, rs, rec, topic, draft = chain
    other = repo.create_account(AccountInput(name="B", creator_type="new"))
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("INSERT INTO diagnoses VALUES (?,?,?,?,?,?)", (str(uuid4()), other.id, p.id, "{}", "pending", p.created_at))
    second_draft = repo.create_draft(a.id, topic.id, DraftContent())
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("UPDATE drafts SET latest_version_id=? WHERE id=?", (draft.latest_version_id, second_draft.id))


def test_direct_source_mutation_rejected(repo, chain):
    a, _, d, _, rec, topic, draft = chain
    for table, field, value, entity_id in [("diagnoses", "result", "{}", d.id),
                                            ("topic_recommendations", "not_recommended", "[]", rec.id),
                                            ("topics", "content", "{}", topic.id)]:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with repo.database.transaction() as conn:
                conn.execute(f"UPDATE {table} SET {field}=? WHERE id=?", (value, entity_id))


def test_research_snapshot_keeps_zero(repo, context):
    a, _, _, rs = context
    repo.update_research(a.id, rs[0].id, ResearchInput(title="Known zero", body="", likes=0, collects=None, comments=0))
    repo.confirm_research(a.id, rs[0].id)
    rec = recommend(repo, context)
    snapshot = next(x for x in repo.recommendation_evidence(a.id, rec.id) if x["id"] == rs[0].id)
    assert snapshot["likes"] == 0 and snapshot["comments"] == 0 and snapshot["collects"] is None


def test_draft_version_unique_and_delete_protected(repo, chain):
    a, *_, draft = chain
    with pytest.raises(Conflict):
        repo.delete("draft_versions", draft.latest_version_id, account_id=a.id)
    with pytest.raises(sqlite3.IntegrityError):
        with repo.database.transaction() as conn:
            conn.execute("""INSERT INTO draft_versions
                SELECT ?,account_id,draft_id,topic_id,version,content,source_evidence,created_at
                FROM draft_versions WHERE id=?""", (str(uuid4()), draft.latest_version_id))


def test_list_pagination_and_validation(repo, context):
    account = context[0]
    rows = repo.list("research_items", account_id=account.id)
    assert repo.list("research_items", account_id=account.id, limit=1, offset=1) == rows[1:2]
    with pytest.raises(ValueError):
        repo.list("research_items", account_id=account.id, limit=-1)


def test_workflow_invalid_stage_and_usage(repo, context):
    with pytest.raises(ValidationError):
        repo.start_workflow(context[0].id, "publishing")
    with pytest.raises(ValidationError):
        ProviderUsage(source="fixture", raw={}, tokens=-1)
    with pytest.raises(ValidationError):
        ProviderUsage(source="fixture", raw={}, cost=float("nan"))
    assert repo.list("workflow_runs", account_id=context[0].id) == []
