import json

import pytest

from easel.growth.diagnosis_schema import FactLockError, ProfileFields, parse_diagnosis
from tests.evaluation.diagnosis_cases import cases


@pytest.mark.parametrize("case_id,profile,good,bad", cases(), ids=[c[0] for c in cases()])
def test_deterministic_diagnosis_case(case_id, profile, good, bad):
    fields = ProfileFields.model_validate(profile)
    assert parse_diagnosis(json.dumps(good, ensure_ascii=False), fields).confidence in {"low", "medium", "high"}
    with pytest.raises(FactLockError):
        parse_diagnosis(json.dumps(bad, ensure_ascii=False), fields)
