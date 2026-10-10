"""Transactional CRUD and provenance invariants. No model calls or web routes."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .database import Database
from .models import (
    JSON_FIELDS, MODELS, AccountInput, DraftContent, ProviderUsage,
    ResearchInput, TopicInput, WorkflowRun,
)


class NotFound(LookupError):
    pass


class Conflict(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class GrowthRepository:
    def __init__(self, database: Database):
        self.database = database

    @contextmanager
    def _write(self):
        try:
            with self.database.transaction() as conn:
                yield conn
        except sqlite3.IntegrityError as exc:
            raise Conflict(str(exc)) from exc

    @staticmethod
    def _table(table: str) -> str:
        if table not in MODELS:
            raise ValueError(f"Unknown entity: {table}")
        return table

    @staticmethod
    def _record(table, row):
        data = dict(row)
        for key in JSON_FIELDS & data.keys():
            if data[key] is not None:
                data[key] = json.loads(data[key])
        return MODELS[table].model_validate(data)

    def _get(self, conn, table, entity_id, account_id):
        self._table(table)
        scope = "id" if table == "accounts" else "account_id"
        row = conn.execute(f"SELECT * FROM {table} WHERE id=? AND {scope}=?", (entity_id, account_id)).fetchone()
        if row is None:
            raise NotFound(f"{table}: {entity_id}")
        return self._record(table, row)

    def get(self, table: str, entity_id: str, *, account_id: str):
        with closing(self.database.connect()) as conn:
            return self._get(conn, table, entity_id, account_id)

    def list(self, table: str, *, account_id: str, limit: int = 100, offset: int = 0):
        self._table(table)
        if type(limit) is not int or type(offset) is not int or not 1 <= limit <= 1000 or offset < 0:
            raise ValueError("limit must be 1..1000 and offset nonnegative")
        scope = "id" if table == "accounts" else "account_id"
        with closing(self.database.connect()) as conn:
            return [self._record(table, row) for row in conn.execute(
                f"SELECT * FROM {table} WHERE {scope}=? ORDER BY created_at,id LIMIT ? OFFSET ?",
                (account_id, limit, offset),
            )]

    def list_accounts(self):
        with closing(self.database.connect()) as conn:
            return [self._record("accounts", row) for row in conn.execute("SELECT * FROM accounts ORDER BY created_at,id")]

    def _insert(self, conn, table, **data):
        self._table(table)
        data = {"id": str(uuid4()), "created_at": now(), **data}
        record = MODELS[table].model_validate(data)
        data = record.model_dump(mode="json")
        for key in JSON_FIELDS & data.keys():
            if data[key] is not None:
                data[key] = encode(data[key])
        columns = ",".join(data)
        conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in data)})", tuple(data.values()))
        return record

    def create_account(self, data: AccountInput):
        data = AccountInput.model_validate(data)
        with self._write() as conn:
            return self._insert(conn, "accounts", **data.model_dump(), current_profile_version_id=None)

    def update_account(self, account_id: str, data: AccountInput):
        data = AccountInput.model_validate(data)
        with self._write() as conn:
            self._get(conn, "accounts", account_id, account_id)
            conn.execute("UPDATE accounts SET name=?,creator_type=? WHERE id=?", (data.name, data.creator_type, account_id))
            return self._get(conn, "accounts", account_id, account_id)

    def create_profile_version(self, account_id: str, raw_input: dict, *, expected_current_id: str | None):
        """Append only. The caller supplies the last observed pointer (None for V1)."""
        with self._write() as conn:
            account = self._get(conn, "accounts", account_id, account_id)
            if account.current_profile_version_id != expected_current_id:
                raise Conflict("Profile changed; reload before saving")
            version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM profile_versions WHERE account_id=?", (account_id,)).fetchone()[0]
            profile = self._insert(conn, "profile_versions", account_id=account_id, version=version, raw_input=raw_input)
            conn.execute("UPDATE accounts SET current_profile_version_id=? WHERE id=?", (profile.id, account_id))
            return profile

    def create_diagnosis(self, account_id: str, profile_version_id: str, result: dict):
        with self._write() as conn:
            profile = self._get(conn, "profile_versions", profile_version_id, account_id)
            account = self._get(conn, "accounts", account_id, account_id)
            if account.current_profile_version_id != profile.id:
                raise Conflict("Cannot save a diagnosis against a stale profile")
            return self._insert(conn, "diagnoses", account_id=account_id, profile_version_id=profile.id, result=result, status="pending")

    def confirm_diagnosis(self, account_id: str, diagnosis_id: str):
        with self._write() as conn:
            diagnosis = self._get(conn, "diagnoses", diagnosis_id, account_id)
            account = self._get(conn, "accounts", account_id, account_id)
            if diagnosis.profile_version_id != account.current_profile_version_id:
                raise Conflict("Diagnosis belongs to an older profile")
            conn.execute("UPDATE diagnoses SET status='confirmed' WHERE id=?", (diagnosis.id,))
            return self._get(conn, "diagnoses", diagnosis.id, account_id)

    def create_research(self, account_id: str, data: ResearchInput):
        data = ResearchInput.model_validate(data)
        with self._write() as conn:
            self._get(conn, "accounts", account_id, account_id)
            return self._insert(conn, "research_items", account_id=account_id, **data.model_dump(), updated_at=now())

    def update_research(self, account_id: str, research_id: str, data: ResearchInput):
        """Replacement edit always clears confirmation; user must reconfirm edited evidence."""
        data = ResearchInput.model_validate(data)
        with self._write() as conn:
            self._get(conn, "research_items", research_id, account_id)
            values = data.model_dump()
            values.update(confirmed_for_topic=False, updated_at=now())
            for key in JSON_FIELDS & values.keys():
                if values[key] is not None:
                    values[key] = encode(values[key])
            conn.execute(f"UPDATE research_items SET {','.join(k+'=?' for k in values)} WHERE id=?", (*values.values(), research_id))
            return self._get(conn, "research_items", research_id, account_id)

    def confirm_research(self, account_id: str, research_id: str, confirmed: bool = True):
        if type(confirmed) is not bool:
            raise ValueError("confirmed must be a boolean")
        with self._write() as conn:
            self._get(conn, "research_items", research_id, account_id)
            conn.execute("UPDATE research_items SET confirmed_for_topic=?,updated_at=? WHERE id=?", (confirmed, now(), research_id))
            return self._get(conn, "research_items", research_id, account_id)

    def create_recommendation(self, account_id: str, profile_version_id: str, diagnosis_id: str,
                              research_ids: list[str], topics: list[TopicInput], *, not_recommended: list | None = None):
        """Persist an already validated bundle, not an AI recommendation workflow."""
        topics = [TopicInput.model_validate(t) for t in topics]
        if len(topics) != 3 or {t.rank for t in topics} != {1, 2, 3}:
            raise ValueError("A recommendation requires ranks 1, 2 and 3")
        if len(research_ids) < 3 or len(set(research_ids)) != len(research_ids):
            raise ValueError("At least three distinct confirmed research items are required")
        for topic in topics:
            if len(set(topic.research_ids)) != len(topic.research_ids) or not set(topic.research_ids) <= set(research_ids):
                raise ValueError("Topic evidence must be a distinct subset of the input snapshot")
        with self._write() as conn:
            self._get(conn, "profile_versions", profile_version_id, account_id)
            diagnosis = self._get(conn, "diagnoses", diagnosis_id, account_id)
            if diagnosis.profile_version_id != profile_version_id:
                raise Conflict("Diagnosis/profile mismatch")
            research = [self._get(conn, "research_items", rid, account_id) for rid in research_ids]
            rec = self._insert(conn, "topic_recommendations", account_id=account_id,
                               profile_version_id=profile_version_id, diagnosis_id=diagnosis_id,
                               not_recommended=not_recommended if not_recommended is not None else [])
            for item in research:
                conn.execute("INSERT INTO recommendation_evidence VALUES (?,?,?,?)",
                             (rec.id, item.id, account_id, item.model_dump_json()))
            for data in topics:
                topic = self._insert(conn, "topics", account_id=account_id, recommendation_id=rec.id,
                                     rank=data.rank, content=data.content)
                conn.executemany("INSERT INTO topic_evidence VALUES (?,?,?)",
                                 [(topic.id, rec.id, rid) for rid in data.research_ids])
            return rec

    def _topic_context(self, conn, account_id, topic_id):
        topic = self._get(conn, "topics", topic_id, account_id)
        rec = self._get(conn, "topic_recommendations", topic.recommendation_id, account_id)
        rows = conn.execute("""SELECT e.research_id,e.snapshot FROM topic_evidence t
            JOIN recommendation_evidence e ON e.recommendation_id=t.recommendation_id AND e.research_id=t.research_id
            WHERE t.topic_id=? ORDER BY e.research_id""", (topic_id,)).fetchall()
        return {"account_id": account_id, "profile_version_id": rec.profile_version_id,
                "diagnosis_id": rec.diagnosis_id, "recommendation_id": rec.id, "topic_id": topic.id,
                "research_ids": [r["research_id"] for r in rows],
                "research_snapshots": [json.loads(r["snapshot"]) for r in rows]}

    def topic_context(self, account_id: str, topic_id: str) -> dict:
        with closing(self.database.connect()) as conn:
            # Multiple related reads must see the same committed snapshot.
            conn.execute("BEGIN")
            return self._topic_context(conn, account_id, topic_id)

    def recommendation_evidence(self, account_id: str, recommendation_id: str) -> list[dict]:
        with closing(self.database.connect()) as conn:
            conn.execute("BEGIN")
            self._get(conn, "topic_recommendations", recommendation_id, account_id)
            return [json.loads(row[0]) for row in conn.execute(
                "SELECT snapshot FROM recommendation_evidence WHERE recommendation_id=? ORDER BY research_id", (recommendation_id,))]

    def _append_draft(self, conn, draft, content):
        version = conn.execute("SELECT COALESCE(MAX(version),0)+1 FROM draft_versions WHERE draft_id=?", (draft.id,)).fetchone()[0]
        evidence = self._topic_context(conn, draft.account_id, draft.topic_id)
        record = self._insert(conn, "draft_versions", account_id=draft.account_id, draft_id=draft.id,
                              topic_id=draft.topic_id, version=version, content=content.model_dump(), source_evidence=evidence)
        conn.executemany("INSERT INTO draft_version_evidence VALUES (?,?,?)",
                         [(record.id, draft.topic_id, rid) for rid in evidence["research_ids"]])
        conn.execute("UPDATE drafts SET latest_version_id=? WHERE id=?", (record.id, draft.id))
        return record

    def create_draft(self, account_id: str, topic_id: str, content: DraftContent):
        content = DraftContent.model_validate(content)
        with self._write() as conn:
            self._get(conn, "topics", topic_id, account_id)
            draft = self._insert(conn, "drafts", account_id=account_id, topic_id=topic_id, latest_version_id=None)
            self._append_draft(conn, draft, content)
            return self._get(conn, "drafts", draft.id, account_id)

    def save_draft_version(self, account_id: str, draft_id: str, content: DraftContent, *, expected_latest_id: str):
        content = DraftContent.model_validate(content)
        with self._write() as conn:
            draft = self._get(conn, "drafts", draft_id, account_id)
            if draft.latest_version_id != expected_latest_id:
                raise Conflict("Draft changed; reload before saving")
            return self._append_draft(conn, draft, content)

    def start_workflow(self, account_id: str, stage: str, *, model: str | None = None, retry_of: str | None = None):
        with self._write() as conn:
            self._get(conn, "accounts", account_id, account_id)
            workflow_id, retry_count = str(uuid4()), 0
            if retry_of is not None:
                previous = self._get(conn, "workflow_runs", retry_of, account_id)
                if previous.status != "failed" or previous.stage != stage:
                    raise Conflict("Only a failed run in the same stage can be retried")
                workflow_id, retry_count = previous.workflow_id, previous.retry_count + 1
            timestamp = now()
            return self._insert(conn, "workflow_runs", account_id=account_id, workflow_id=workflow_id,
                                stage=stage, status="running", model=model, started_at=timestamp,
                                completed_at=None, latency=None, error=None, retry_count=retry_count,
                                tokens=None, cost=None, usage=None)

    def finish_workflow(self, account_id: str, run_id: str, *, status: str,
                        error: str | None = None, usage: ProviderUsage | None = None) -> WorkflowRun:
        if status not in {"succeeded", "failed"} or (status == "failed" and not error) or (status == "succeeded" and error is not None):
            raise ValueError("Completion requires succeeded without error or failed with an error")
        if usage is not None:
            usage = ProviderUsage.model_validate(usage)
        with self._write() as conn:
            run = self._get(conn, "workflow_runs", run_id, account_id)
            if run.status != "running":
                raise Conflict("Workflow already completed")
            timestamp = now()
            latency = max(0.0, (datetime.fromisoformat(timestamp) - datetime.fromisoformat(run.started_at)).total_seconds())
            conn.execute("""UPDATE workflow_runs SET status=?,completed_at=?,latency=?,error=?,tokens=?,cost=?,usage=? WHERE id=?""",
                         (status, timestamp, latency, error, usage.tokens if usage else None,
                          usage.cost if usage else None, usage.model_dump_json() if usage else None, run_id))
            return self._get(conn, "workflow_runs", run_id, account_id)

    def delete(self, table: str, entity_id: str, *, account_id: str) -> None:
        """Delete aggregate roots; immutable versions/individual TOP3 members cannot be deleted."""
        self._table(table)
        if table in {"profile_versions", "draft_versions", "topics"}:
            raise Conflict("Delete the owning aggregate, not an individual version/topic")
        with self._write() as conn:
            self._get(conn, table, entity_id, account_id)
            conn.execute(f"DELETE FROM {table} WHERE id=?", (entity_id,))
