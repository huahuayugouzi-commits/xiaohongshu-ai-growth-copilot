"""Account isolation with deterministic models and a reopened SQLite connection."""
import asyncio
import pytest
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

from easel.growth.api import get_service
from easel.growth.database import Database
from easel.growth.models import AccountInput
from easel.growth.repository import GrowthRepository, NotFound
from easel.growth.topics import TopicRepository
from easel.growth.studio import generate_draft

support = run_path(str(Path(__file__).with_name('test_growth_studio.py')))
research = support['research']


def test_accounts_keep_separate_research_topics_drafts_after_reopen(research):
    client, repo, aid, app, topic = support['setup'](research)
    asyncio.run(generate_draft(repo, support['Fake'](), aid, topic.id))
    bid = repo.create_account(AccountInput(name='Isolation B', creator_type='new')).id
    paths = ['research', 'topics', 'studio']
    before = {p: client.get(f'/api/growth/accounts/{aid}/{p}').json() for p in paths}
    assert before['research'] and len(before['topics']['topics']) == 3
    assert before['studio']['drafts'] and before['studio']['versions']
    for reopen in (False, True):
        if reopen:
            fresh = GrowthRepository(Database(repo.database.path))
            app.dependency_overrides[get_service] = lambda: SimpleNamespace(repository=fresh)
        assert client.get(f'/api/growth/accounts/{bid}/research').json() == []
        btopics = client.get(f'/api/growth/accounts/{bid}/topics').json()
        assert btopics['account']['id'] == bid
        assert all(not btopics[key] for key in ('research', 'topics', 'recommendations', 'runs'))
        assert all(not v for v in client.get(f'/api/growth/accounts/{bid}/studio').json().values())
        for p in paths:
            assert client.get(f'/api/growth/accounts/{aid}/{p}').json() == before[p]
    rid = before['research'][0]['id']
    assert client.patch(f'/api/growth/accounts/{bid}/research/{rid}/confirmation', json={'confirmed_for_topic': True}).status_code == 404
    assert client.get(f'/api/growth/accounts/{bid}/topics/{topic.id}/evidence').status_code == 404
    assert all(row['account_id'] == aid for row in before['studio']['versions'])
    profile = repo.create_profile_version(bid, {'fields': {'skills': 'B only'}}, expected_current_id=None)
    diagnosis = repo.create_diagnosis(bid, profile.id, {})
    repo.confirm_diagnosis(bid, diagnosis.id)
    with pytest.raises(NotFound):
        TopicRepository(repo.database).begin(bid, [rid], 'fixture')
    with pytest.raises(NotFound):
        repo.begin(bid, topic.id, 'fixture')
    with pytest.raises(NotFound):
        repo.edit(bid, before['studio']['drafts'][0]['id'], before['studio']['versions'][0]['content'], before['studio']['versions'][0]['id'])
