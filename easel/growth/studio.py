"""Small versioned draft workflow built on the existing Growth tables."""
import asyncio
import json
from contextlib import closing
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from .models import DraftContent
from .repository import GrowthRepository, Conflict, now
from .llm import ModelError
from .topics import Reference


class EditableDraft(DraftContent):
    title: str = Field(min_length=1, max_length=120)
    hook: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=6000)
    cta: str = Field(max_length=300)
    tags: list[str] = Field(max_length=10)
    cover_text: str = Field(max_length=120)
    visual_suggestions: list[str] = Field(max_length=5)
    facts_to_verify: list[str] = Field(min_length=1, max_length=10)


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    draft: EditableDraft
    evidence: list[Reference] = Field(min_length=1, max_length=5)


def parse_draft(content, context):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise ValueError('duplicate_key')
            result[k] = v
        return result
    if len(content) > 40000: raise ValueError('oversize')
    result = DraftOutput.model_validate(json.loads(content, object_pairs_hook=unique))
    # V0.1 auto-drafts are neutral proposals, never a fabricated user autobiography.
    prose = '\n'.join(getattr(result.draft, k) for k in ('title', 'hook', 'body', 'cta', 'cover_text'))
    if any(word in prose for word in ('我', '本人', '笔者')):
        raise ValueError('unverified_first_person')
    sources = {s['id']: s for s in context['evidence']['research_snapshots']}
    for ref in result.evidence:
        source = sources.get(ref.research_id)
        if source is None: raise ValueError('unknown_source')
        texts = source['comment_samples'] if ref.field == 'comment_samples' else [source[ref.field]]
        if not any(ref.quote in text for text in texts): raise ValueError('unsupported_quote')
    return result


class StudioRepository(GrowthRepository):
    def _context(self, conn, aid, tid):
        evidence = self._topic_context(conn, aid, tid)
        account = self._get(conn, 'accounts', aid, aid)
        profile = self._get(conn, 'profile_versions', evidence['profile_version_id'], aid)
        diagnosis = self._get(conn, 'diagnoses', evidence['diagnosis_id'], aid)
        latest = conn.execute('SELECT id FROM diagnoses WHERE account_id=? AND profile_version_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (aid, profile.id)).fetchone()
        if account.current_profile_version_id != profile.id or diagnosis.status != 'confirmed' or not latest or latest[0] != diagnosis.id:
            raise Conflict('Topic belongs to an old or unconfirmed positioning')
        return {'topic': self._get(conn, 'topics', tid, aid).model_dump(),
                'profile': profile.model_dump(), 'diagnosis': diagnosis.model_dump(), 'evidence': evidence}

    def begin(self, aid, tid, model, retry_of=None):
        with self._write() as conn:
            context = self._context(conn, aid, tid)
            if conn.execute("SELECT 1 FROM workflow_runs WHERE account_id=? AND stage='content_creation' AND status='running'", (aid,)).fetchone():
                raise Conflict('Draft generation running')
            workflow_id, retry = str(uuid4()), 0
            if retry_of:
                old = self._get(conn, 'workflow_runs', retry_of, aid)
                if old.stage != 'content_creation' or old.status != 'failed': raise Conflict('Invalid retry')
                workflow_id, retry = old.workflow_id, old.retry_count + 1
            run = self._insert(conn, 'workflow_runs', account_id=aid, workflow_id=workflow_id, stage='content_creation',
                status='running', model=model, started_at=now(), completed_at=None, latency=None, error=None,
                retry_count=retry, tokens=None, cost=None, usage=None)
            return run, context

    def complete(self, aid, run_id, context, output, usage):
        with self._write() as conn:
            run = self._get(conn, 'workflow_runs', run_id, aid)
            if run.status != 'running' or run.stage != 'content_creation': raise Conflict('Run stopped')
            tid = context['topic']['id']
            if self._context(conn, aid, tid) != context: raise Conflict('Context changed')
            draft = self._insert(conn, 'drafts', account_id=aid, topic_id=tid, latest_version_id=None)
            self._append_draft(conn, draft, output.draft)
            stamp = now(); latency = max(0, (datetime.fromisoformat(stamp)-datetime.fromisoformat(run.started_at)).total_seconds())
            conn.execute("UPDATE workflow_runs SET status='succeeded',completed_at=?,latency=?,tokens=?,cost=?,usage=? WHERE id=?",
                         (stamp, latency, usage.tokens if usage else None, usage.cost if usage else None,
                          usage.model_dump_json() if usage else None, run_id))
            return self._get(conn, 'drafts', draft.id, aid)

    def state(self, aid):
        with closing(self.database.connect()) as conn:
            conn.execute('BEGIN')
            self._get(conn, 'accounts', aid, aid)
            def rows(table):
                return [self._record(table, row) for row in conn.execute(f'SELECT * FROM {table} WHERE account_id=? ORDER BY created_at DESC,id DESC', (aid,))]
            return {'topics': rows('topics'), 'drafts': rows('drafts'), 'versions': rows('draft_versions'),
                    'runs': [r for r in rows('workflow_runs') if r.stage == 'content_creation']}

    def edit(self, aid, did, content, expected):
        return self.save_draft_version(aid, did, content, expected_latest_id=expected)

    def interrupt(self, aid, rid):
        run = self.get('workflow_runs', rid, account_id=aid)
        if run.stage != 'content_creation': raise Conflict('Wrong stage')
        return self.finish_workflow(aid, rid, status='failed', error='用户标记草稿生成中断，晚到结果不会保存。')


class DraftFailure(Exception): pass


async def generate_draft(repo, model, aid, tid, retry_of=None):
    run, context = repo.begin(aid, tid, model.model_name, retry_of)
    usage = None
    try:
        reply = await model.generate(context); usage = reply.usage
        return repo.complete(aid, run.id, context, parse_draft(reply.content, context), usage)
    except (Exception, asyncio.CancelledError) as exc:
        if isinstance(exc, ModelError): usage = getattr(exc, 'usage', usage)
        message = str(exc) if isinstance(exc, ModelError) else '草稿未通过结构/引用校验，或定位已变化；未保存，请刷新检查。'
        if isinstance(exc, ValueError) and str(exc) == 'unverified_first_person':
            message = 'AI 草稿包含未经核实的第一人称自述，未保存；初稿须为中性的待验证方案。'
        if repo.get('workflow_runs', run.id, account_id=aid).status == 'running':
            repo.finish_workflow(aid, run.id, status='failed', error=message, usage=usage)
        if isinstance(exc, asyncio.CancelledError): raise
        raise DraftFailure(message) from None
