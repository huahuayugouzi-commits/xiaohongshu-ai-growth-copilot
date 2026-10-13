"""Explicit local Topics reproduction; secret-checked response artifacts only."""
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from easel.growth.database import Database
from easel.growth.topics import TopicRepository, parse_topics, recommend
from easel.growth.topic_model import TopicModel

async def main():
    p = argparse.ArgumentParser()
    p.add_argument('--account', required=True)
    p.add_argument('--label', required=True)
    p.add_argument('--save', action='store_true')
    args = p.parse_args()
    repo = TopicRepository(Database())
    items = repo.state(args.account)['research']
    ids = [r.id for r in items if r.confirmed_for_topic and (r.analysis or {}).get('status') == 'succeeded']
    with repo.database.connect() as conn:
        context = repo._context(conn, args.account, ids)
    report = {'profile_id': context['profile']['id'], 'diagnosis_id': context['diagnosis']['id'], 'research_ids': ids,
              'context_sha256': hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()}
    model = TopicModel()
    class Capture(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            body = json.loads(request.content)
            report.update(max_tokens=body['max_tokens'], prompt_chars=len(body['messages'][0]['content']), input_chars=len(body['messages'][1]['content']))
            async with httpx.AsyncHTTPTransport() as transport:
                response = await transport.handle_async_request(request)
                await response.aread()
            report['http_status'] = response.status_code
            data = response.json(); choice = data.get('choices', [{}])[0]
            content = choice.get('message', {}).get('content')
            sensitive = isinstance(content, str) and model.config.api_key in content
            report.update(finish_reason=choice.get('finish_reason'), sensitive_match=sensitive, content_is_text=isinstance(content, str))
            report['usage'] = {k:v for k,v in data.get('usage', {}).items() if k in ('prompt_tokens','completion_tokens','total_tokens') and isinstance(v,int)}
            if isinstance(content,str) and not sensitive:
                report['response_content'] = content
                try:
                    json.loads(content); report['json_pass'] = True
                    bundle = parse_topics(content, context)
                    report.update(schema_evidence_pass=True, topic_count=len(bundle.topics), reason_present=all(t.why_now for t in bundle.topics))
                except Exception as exc:
                    report['validation_error_type'] = type(exc).__name__
            return response
    model.transport = Capture()
    try:
        if args.save:
            rec = await recommend(repo, model, args.account, ids)
            fresh = TopicRepository(Database())
            topics = [t for t in fresh.state(args.account)['topics'] if t.recommendation_id == rec.id]
            evidence = [fresh.evidence(args.account,t.id) for t in topics]
            report.update(saved=True, persisted_count=len(topics), evidence_count=len(evidence), recommendation_id=rec.id)
        else:
            await model.recommend(context)
    except Exception as exc:
        report['exception_type'] = type(exc).__name__
    folder = Path(__file__).resolve().parents[3] / 'outputs' / 'topics-bad-case'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (Path(args.label).name + '.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'response_content'},ensure_ascii=False))

if __name__ == '__main__': asyncio.run(main())
