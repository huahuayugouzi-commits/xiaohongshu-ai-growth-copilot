"""Evidence-bound TOP 3 generation, separate from frozen Account/Research workflows."""
import asyncio
import json
from contextlib import closing
from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from .repository import GrowthRepository, Conflict, now


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Reference(Contract):
    research_id: str
    field: Literal['title', 'body', 'comment_samples']
    quote: str = Field(min_length=1, max_length=400)


class ProfileBasis(Contract):
    field: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=400)


class SuggestedTopic(Contract):
    rank: int = Field(strict=True, ge=1, le=3)
    title: str = Field(min_length=1, max_length=120)
    target_audience: str = Field(min_length=1, max_length=300)
    angle: str = Field(min_length=1, max_length=400)
    hook: str = Field(min_length=1, max_length=300)
    why_now: str = Field(min_length=1, max_length=500)
    priority_reason: str = Field(min_length=1, max_length=300)
    profile_basis: list[ProfileBasis] = Field(min_length=1, max_length=3)
    evidence: list[Reference] = Field(min_length=1, max_length=5)
    assumptions: list[str] = Field(min_length=1, max_length=5)
    risks: list[str] = Field(min_length=1, max_length=5)


class TopicBundle(Contract):
    topics: list[SuggestedTopic] = Field(min_length=3, max_length=3)
    not_recommended: list[str] = Field(max_length=5)


def parse_topics(content, context):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    if len(content) > 60000: raise ValueError('oversize')
    bundle = TopicBundle.model_validate(json.loads(content, object_pairs_hook=unique))
    if {t.rank for t in bundle.topics} != {1, 2, 3} or len({t.title for t in bundle.topics}) != 3:
        raise ValueError('duplicate_rank_or_title')
    sources = {r['id']: r for r in context['research']}
    fields = context['profile']['raw_input'].get('fields', context['profile']['raw_input'])
    for topic in bundle.topics:
        for basis in topic.profile_basis:
            original = fields.get(basis.field)
            if not isinstance(original, str) or basis.quote not in original:
                raise ValueError('unsupported_profile_quote')
        for evidence in topic.evidence:
            source = sources.get(evidence.research_id)
            if not source: raise ValueError('unknown_evidence_id')
            originals = source['comment_samples'] if evidence.field == 'comment_samples' else [source[evidence.field]]
            if not any(evidence.quote in text for text in originals): raise ValueError('unsupported_evidence_quote')
    return bundle


class TopicRepository(GrowthRepository):
    def _context(self, conn, account_id, research_ids):
        if not 3 <= len(research_ids) <= 5 or len(set(research_ids)) != len(research_ids):
            raise Conflict('Select 3–5 distinct references')
        account = self._get(conn, 'accounts', account_id, account_id)
        if not account.current_profile_version_id: raise Conflict('Profile required')
        profile = self._get(conn, 'profile_versions', account.current_profile_version_id, account_id)
        row = conn.execute('SELECT id FROM diagnoses WHERE account_id=? AND profile_version_id=? ORDER BY created_at DESC,id DESC LIMIT 1',
                           (account_id, profile.id)).fetchone()
        if not row: raise Conflict('Diagnosis required')
        diagnosis = self._get(conn, 'diagnoses', row[0], account_id)
        if diagnosis.status != 'confirmed': raise Conflict('Confirm current diagnosis')
        research = [self._get(conn, 'research_items', rid, account_id) for rid in research_ids]
        for item in research:
            if not item.confirmed_for_topic or not item.analysis or item.analysis.get('status') != 'succeeded':
                raise Conflict('References must be analyzed and confirmed')
        return {'account': account.model_dump(), 'profile': profile.model_dump(),
                'diagnosis': diagnosis.model_dump(), 'research': [r.model_dump() for r in research]}

    def begin(self, account_id, research_ids, model, retry_of=None):
        with self._write() as conn:
            context = self._context(conn, account_id, research_ids)
            if len(json.dumps(context, ensure_ascii=False)) > 100000:
                raise Conflict('Selected context too large; shorten references')
            if conn.execute("SELECT 1 FROM workflow_runs WHERE account_id=? AND stage='topic_recommendation' AND status='running'", (account_id,)).fetchone():
                raise Conflict('Recommendation already running')
            workflow_id, retry_count = str(uuid4()), 0
            if retry_of:
                prior = self._get(conn, 'workflow_runs', retry_of, account_id)
                if prior.stage != 'topic_recommendation' or prior.status != 'failed': raise Conflict('Invalid retry')
                workflow_id, retry_count = prior.workflow_id, prior.retry_count + 1
            stamp = now()
            run = self._insert(conn, 'workflow_runs', account_id=account_id, workflow_id=workflow_id,
                stage='topic_recommendation', status='running', model=model, started_at=stamp,
                completed_at=None, latency=None, error=None, retry_count=retry_count, tokens=None, cost=None, usage=None)
            return run, context

    def complete(self, account_id, run_id, context, bundle, usage):
        with self._write() as conn:
            run = self._get(conn, 'workflow_runs', run_id, account_id)
            if run.status != 'running' or run.stage != 'topic_recommendation': raise Conflict('Run stopped')
            current = self._context(conn, account_id, [r['id'] for r in context['research']])
            if current != context: raise Conflict('Context changed; reject stale recommendation')
            rec = self._insert(conn, 'topic_recommendations', account_id=account_id,
                profile_version_id=context['profile']['id'], diagnosis_id=context['diagnosis']['id'],
                not_recommended=bundle.not_recommended)
            for source in context['research']:
                conn.execute('INSERT INTO recommendation_evidence VALUES (?,?,?,?)',
                             (rec.id, source['id'], account_id, json.dumps(source, ensure_ascii=False)))
            for suggestion in sorted(bundle.topics, key=lambda t: t.rank):
                content = suggestion.model_dump(exclude={'rank'})
                content['workflow_run_id'] = run_id
                topic = self._insert(conn, 'topics', account_id=account_id, recommendation_id=rec.id,
                                     rank=suggestion.rank, content=content)
                ids = sorted({e.research_id for e in suggestion.evidence})
                conn.executemany('INSERT INTO topic_evidence VALUES (?,?,?)', [(topic.id, rec.id, rid) for rid in ids])
            stamp = now(); latency = max(0, (datetime.fromisoformat(stamp) - datetime.fromisoformat(run.started_at)).total_seconds())
            conn.execute("UPDATE workflow_runs SET status='succeeded',completed_at=?,latency=?,tokens=?,cost=?,usage=? WHERE id=?",
                         (stamp, latency, usage.tokens if usage else None, usage.cost if usage else None,
                          usage.model_dump_json() if usage else None, run_id))
            return rec

    def state(self, account_id):
        with closing(self.database.connect()) as conn:
            conn.execute('BEGIN')
            account = self._get(conn, 'accounts', account_id, account_id)
            def rows(table, where='', args=()):
                return [self._record(table, r) for r in conn.execute(
                    f'SELECT * FROM {table} WHERE account_id=? {where} ORDER BY created_at DESC,id DESC', (account_id, *args))]
            recs = rows('topic_recommendations')
            return {'account': account, 'recommendations': recs, 'topics': rows('topics'),
                    'runs': rows('workflow_runs', 'AND stage=?', ('topic_recommendation',)),
                    'research': rows('research_items')}

    def evidence(self, account_id, topic_id):
        with closing(self.database.connect()) as conn:
            conn.execute('BEGIN')
            context = self._topic_context(conn, account_id, topic_id)
            return {**context,
                    'profile': self._get(conn, 'profile_versions', context['profile_version_id'], account_id),
                    'diagnosis': self._get(conn, 'diagnoses', context['diagnosis_id'], account_id)}

    def interrupt(self, account_id, run_id):
        run = self.get('workflow_runs', run_id, account_id=account_id)
        if run.stage != 'topic_recommendation': raise Conflict('Wrong stage')
        return self.finish_workflow(account_id, run_id, status='failed', error='用户标记选题任务中断，可重试。')


class TopicFailure(Exception):
    pass


async def recommend(repo, model, account_id, research_ids, retry_of=None):
    from .llm import ModelError
    run, context = repo.begin(account_id, research_ids, model.model_name, retry_of)
    usage = None
    try:
        reply = await model.recommend(context); usage = reply.usage
        bundle = parse_topics(reply.content, context)
        return repo.complete(account_id, run.id, context, bundle, usage)
    except (Exception, asyncio.CancelledError) as exc:
        message = str(exc) if isinstance(exc, ModelError) else '选题未通过结构/证据校验，或账号/参考内容已变化；未保存选题，请刷新重试。'
        if repo.get('workflow_runs', run.id, account_id=account_id).status == 'running':
            repo.finish_workflow(account_id, run.id, status='failed', error=message, usage=usage)
        if isinstance(exc, asyncio.CancelledError): raise
        raise TopicFailure(message) from None
