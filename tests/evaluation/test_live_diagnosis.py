"""Opt-in real API evaluation. Never run automatically or claim skipped cases passed."""

import asyncio
import os

import pytest

from easel.growth.diagnosis_schema import ProfileFields, parse_diagnosis
from easel.growth.llm import CompatibleModel, ModelConfig
from tests.evaluation.diagnosis_cases import cases


@pytest.mark.skipif(os.environ.get("GROWTH_LIVE_EVAL") != "1", reason="Real model evaluation requires explicit GROWTH_LIVE_EVAL=1 and local credentials")
@pytest.mark.parametrize("case_id,profile,good,bad", cases(), ids=[c[0] for c in cases()])
def test_live_diagnosis_guard_contract(case_id, profile, good, bad):
    config = ModelConfig.from_environment()
    assert config.ready, "Configure the three GROWTH_LLM environment variables locally"
    fields = ProfileFields.model_validate(profile)
    reply = asyncio.run(CompatibleModel(config).diagnose({"name": "Evaluation fixture", "creator_type": "new"}, fields))
    # No raw output/credentials are logged. These checks are not a complete human semantic review.
    try:
        parse_diagnosis(reply.content, fields)
    except Exception:
        pytest.fail(f"{case_id}: live output failed schema/guard validation (raw output withheld)", pytrace=False)
