"""Local opt-in reproduction of one reported Research failure; never log credentials."""
import asyncio
import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from easel.growth.database import Database
from easel.growth.research_analysis import ResearchModel, ResearchAnalysisRepository, snapshot, parse_card, analyze_item

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--account', required=True)
    parser.add_argument('--item', required=True)
    parser.add_argument('--label', default='original')
    parser.add_argument('--save-workflow', action='store_true')
    args = parser.parse_args()
    ACCOUNT, ITEM = args.account, args.item
    repo = ResearchAnalysisRepository(Database())
    item = repo.get('research_items', ITEM, account_id=ACCOUNT)
    source = snapshot(item)
    model = ResearchModel()
    report = {'item_id': ITEM, 'body_chars': len(source['body']),
              'comment_count': len(source['comment_samples']),
              'comment_chars': sum(map(len, source['comment_samples']))}
    class Capture(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            body = json.loads(request.content)
            report.update(max_tokens=body['max_tokens'], prompt_chars=len(body['messages'][0]['content']),
                          input_chars=len(body['messages'][1]['content']))
            async with httpx.AsyncHTTPTransport() as transport:
                response = await transport.handle_async_request(request)
                await response.aread()
            data = response.json()
            choice = data.get('choices', [{}])[0]
            content = choice.get('message', {}).get('content')
            sensitive = isinstance(content, str) and model.config.api_key in content
            report.update(finish_reason=choice.get('finish_reason'), content_is_text=isinstance(content, str),
                          sensitive_match=sensitive, output_chars=len(content) if isinstance(content, str) else None)
            report['usage'] = {k:v for k,v in data.get('usage', {}).items()
                               if k in ('prompt_tokens', 'completion_tokens', 'total_tokens') and isinstance(v, int)}
            # Keep raw content only after exact secret guard; never save headers/config.
            if isinstance(content, str) and not sensitive:
                report['response_content'] = content
                try:
                    parsed = json.loads(content)
                    report['json_valid'] = True
                    report['fields'] = list(parsed) if isinstance(parsed, dict) else []
                    parse_card(content, source)
                    report['schema_evidence_pass'] = True
                except Exception as exc:
                    report['validation_error_type'] = type(exc).__name__
            return response
    model.transport = Capture()
    try:
        if '--save-workflow' in sys.argv:
            saved = await analyze_item(repo, model, ACCOUNT, ITEM)
            report.update(status=saved.analysis['status'], run_id=saved.analysis['run_id'])
        else:
            await model.analyze(source)
            report['adapter_pass'] = True
    except Exception as exc:
        report['exception_type'] = type(exc).__name__
    folder = Path(__file__).resolve().parents[3] / 'outputs' / 'research-bad-case'
    folder.mkdir(parents=True, exist_ok=True)
    name = Path(args.label).name + '.json'
    (folder / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'response_content'}, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
