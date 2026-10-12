"""Opt-in real API evaluation. Never run automatically or claim skipped cases passed."""

import asyncio
import os
import json
from pathlib import Path

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
    # Only synthetic inputs and adapter-screened output are retained, never config/keys.
    destination = os.environ.get("GROWTH_EVAL_OUTPUT_DIR")
    record = {"case": case_id, "input": profile, "model": config.model,
              "finish_reason": reply.finish_reason, "output_characters": len(reply.content),
              "structured_output": None, "schema_and_guard": "FAIL",
              "semantic_review": "PENDING"}
    try:
        result = parse_diagnosis(reply.content, fields)
        record.update(structured_output=result.model_dump(), schema_and_guard="PASS")
    except Exception:
        record["rejected_output"] = reply.content
        pytest.fail(f"{case_id}: live output failed schema/guard validation (raw output withheld)", pytrace=False)
    finally:
        if destination:
            folder = Path(destination)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{case_id}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
