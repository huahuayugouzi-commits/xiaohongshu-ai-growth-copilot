"""Account/Diagnosis-specific transactional operations; no generic write HTTP API."""

from contextlib import closing
from datetime import datetime
from uuid import uuid4

from .diagnosis_schema import AccountProfileInput, DiagnosisResult
from .models import ProviderUsage
from .repository import Conflict, GrowthRepository, encode, now


class AccountRepository(GrowthRepository):
    def save_account_profile(self, data: AccountProfileInput, account_id: str | None = None):
        with self._write() as conn:
            if account_id is None:
                if data.expected_current_id is not None:
                    raise Conflict("New account cannot refer to an existing profile")
                account = self._insert(conn, "accounts", name=data.name.strip(), creator_type=data.creator_type, current_profile_version_id=None)
                account_id = account.id
            else:
                account = self._get(conn, "accounts", account_id, account_id)
                if account.current_profile_version_id != data.expected_current_id:
                    raise Conflict("Profile changed; reload before saving")
            raw_input = {"fields": data.profile.model_dump(), "account": {"name": data.name.strip(), "creator_type": data.creator_type}}
            current = self._get(conn, "profile_versions", account.current_profile_version_id, account_id) if account.current_profile_version_id else None
            if current is None or current.raw_input != raw_input:
                version = 1 if current is None else current.version + 1
                current = self._insert(conn, "profile_versions", account_id=account_id, version=version, raw_input=raw_input)
                conn.execute("UPDATE accounts SET name=?,creator_type=?,current_profile_version_id=? WHERE id=?",
                             (data.name.strip(), data.creator_type, current.id, account_id))
            return self._get(conn, "accounts", account_id, account_id), current

    def begin_diagnosis(self, account_id, profile_id, model, retry_of=None):
        with self._write() as conn:
            account = self._get(conn, "accounts", account_id, account_id)
            profile = self._get(conn, "profile_versions", profile_id, account_id)
            if account.current_profile_version_id != profile_id:
                raise Conflict("Profile changed; save/reload the current profile first")
            active = conn.execute("""SELECT 1 FROM diagnosis_runs d JOIN workflow_runs w ON w.id=d.run_id
                WHERE d.account_id=? AND w.status='running'""", (account_id,)).fetchone()
            if active:
                raise Conflict("Diagnosis is already running; wait or mark an interrupted run failed")
            workflow_id, retry_count = str(uuid4()), 0
            if retry_of:
                previous = self._get(conn, "workflow_runs", retry_of, account_id)
                source = conn.execute("SELECT profile_version_id FROM diagnosis_runs WHERE run_id=?", (retry_of,)).fetchone()
                if previous.status != "failed" or previous.stage != "diagnosis" or not source or source[0] != profile_id:
                    raise Conflict("Retry must reference a failed diagnosis of this profile")
                workflow_id, retry_count = previous.workflow_id, previous.retry_count + 1
            run = self._insert(conn, "workflow_runs", account_id=account_id, workflow_id=workflow_id, stage="diagnosis",
                               status="running", model=model, started_at=now(), completed_at=None, latency=None,
                               error=None, retry_count=retry_count, tokens=None, cost=None, usage=None)
            conn.execute("INSERT INTO diagnosis_runs VALUES (?,?,?,NULL)", (run.id, account_id, profile_id))
            return account, profile, run

    def complete_diagnosis(self, account_id, run_id, result: DiagnosisResult, usage: ProviderUsage | None):
        with self._write() as conn:
            run = self._get(conn, "workflow_runs", run_id, account_id)
            source = conn.execute("SELECT profile_version_id FROM diagnosis_runs WHERE run_id=?", (run_id,)).fetchone()
            account = self._get(conn, "accounts", account_id, account_id)
            if run.status != "running" or not source or account.current_profile_version_id != source[0]:
                raise Conflict("Profile changed or workflow stopped; stale diagnosis was not saved")
            diagnosis = self._insert(conn, "diagnoses", account_id=account_id, profile_version_id=source[0], result=result.model_dump(), status="pending")
            conn.execute("UPDATE diagnosis_runs SET diagnosis_id=? WHERE run_id=?", (diagnosis.id, run.id))
            completed = now()
            latency = max(0.0, (datetime.fromisoformat(completed) - datetime.fromisoformat(run.started_at)).total_seconds())
            conn.execute("UPDATE workflow_runs SET status='succeeded',completed_at=?,latency=?,tokens=?,cost=?,usage=? WHERE id=?",
                         (completed, latency, usage.tokens if usage else None, usage.cost if usage else None,
                          usage.model_dump_json() if usage else None, run.id))
            return diagnosis

    def confirm_current_diagnosis(self, account_id, diagnosis_id):
        with self._write() as conn:
            diagnosis = self._get(conn, "diagnoses", diagnosis_id, account_id)
            account = self._get(conn, "accounts", account_id, account_id)
            latest = conn.execute("SELECT id FROM diagnoses WHERE account_id=? AND profile_version_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
                                  (account_id, account.current_profile_version_id)).fetchone()
            if diagnosis.profile_version_id != account.current_profile_version_id or not latest or latest[0] != diagnosis_id:
                raise Conflict("Only the latest diagnosis of the current profile can be confirmed")
            conn.execute("UPDATE diagnoses SET status='confirmed' WHERE id=?", (diagnosis_id,))
            return self._get(conn, "diagnoses", diagnosis_id, account_id)

    def projection_status(self, account_id, profile_id, diagnosis_id=None, *, status, error=None, relative_path=None):
        key = profile_id + ":" + (diagnosis_id or "input")
        with self._write() as conn:
            conn.execute("""INSERT INTO profile_projections VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET status=excluded.status,error=excluded.error,
                relative_path=excluded.relative_path,updated_at=excluded.updated_at""",
                         (key, account_id, profile_id, diagnosis_id, status, error, relative_path, now()))

    def state(self, account_id: str | None):
        with closing(self.database.connect()) as conn:
            conn.execute("BEGIN")
            accounts = [self._record("accounts", r) for r in conn.execute("SELECT * FROM accounts ORDER BY created_at,id")]
            if not accounts and account_id is None:
                return {"accounts": [], "account": None, "profiles": [], "diagnoses": [], "runs": [], "projections": [],
                        "current_profile": None, "current_diagnosis": None, "counts": {"research": 0, "topics": 0, "drafts": 0}, "next_step": "完成账号建档"}
            account = self._get(conn, "accounts", account_id or accounts[0].id, account_id or accounts[0].id)
            def records(table):
                return [self._record(table, row) for row in conn.execute(f"SELECT * FROM {table} WHERE account_id=? ORDER BY created_at DESC,id DESC", (account.id,))]
            profiles, diagnoses, runs = records("profile_versions"), records("diagnoses"), records("workflow_runs")
            profile = next((p for p in profiles if p.id == account.current_profile_version_id), None)
            diagnosis = next((d for d in diagnoses if d.profile_version_id == account.current_profile_version_id), None)
            projections = [dict(r) for r in conn.execute("SELECT * FROM profile_projections WHERE account_id=? ORDER BY updated_at DESC", (account.id,))]
            counts = {name: conn.execute(f"SELECT COUNT(*) FROM {table} WHERE account_id=?", (account.id,)).fetchone()[0]
                      for name, table in {"research": "research_items", "topics": "topics", "drafts": "drafts"}.items()}
            return {"accounts": accounts, "account": account, "profiles": profiles, "diagnoses": diagnoses, "runs": runs,
                    "current_profile": profile, "current_diagnosis": diagnosis, "counts": counts, "projections": projections,
                    "next_step": "完成账号建档" if profile is None else "生成账号诊断" if diagnosis is None else
                    "确认或调整定位" if diagnosis.status != "confirmed" else "下一步进入 Research（Coming Soon）"}
