"""Phase 3 field contracts and conservative, deterministic Fact Lock checks."""

import json
import re
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from .models import Contract

ShortText = Annotated[str, Field(max_length=3000)]
Statement = Annotated[str, Field(min_length=1, max_length=3000)]
Statements = Annotated[list[Statement], Field(max_length=20)]
UNDETERMINED = "待补充信息后确定"


class ProfileFields(Contract):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    occupation: ShortText = ""
    experience: ShortText = ""
    skills: ShortText = ""
    interests: ShortText = ""
    creator_goal: ShortText = ""
    target_audience: ShortText = ""
    content_assets: ShortText = ""
    bio: ShortText = ""
    current_positioning: ShortText = ""
    operation_duration: ShortText = ""
    current_problem: ShortText = ""


class AccountProfileInput(Contract):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Annotated[str, Field(min_length=1, max_length=100)]
    creator_type: Literal["new", "existing"]
    profile: ProfileFields
    expected_current_id: str | None = None


class Positioning(Contract):
    positioning: Statement
    target_audience: Statement
    core_value: Statement
    differentiation: Statement


class Pillar(Contract):
    name: Statement
    reason: Statement


class DiagnosisResult(Contract):
    positioning_hypothesis: Positioning
    content_pillars: Annotated[list[Pillar], Field(max_length=6)]
    strengths: Statements
    risks: Statements
    missing_information: Statements
    assumptions: Statements
    confidence: Literal["low", "medium", "high"]


class DiagnosisRequest(Contract):
    profile_version_id: str
    retry_of: str | None = None


class FactLockError(ValueError):
    """Only rule IDs, never provider output or personal input, go to errors/logs."""


def sparse(profile: ProfileFields) -> bool:
    return sum(bool(getattr(profile, k)) for k in (
        "occupation", "experience", "skills", "interests", "content_assets", "target_audience",
    )) < 2


def conflicting_constraints(profile: ProfileFields) -> bool:
    text = " ".join(profile.model_dump().values())
    return "不露脸" in text and "不分享个人经历" in text and "个人IP" in text


def validate_fact_lock(result: DiagnosisResult, profile: ProfileFields) -> None:
    """Reject known high-risk failures; not a claim of complete semantic verification.

    Strengths must quote supplied experience/assets/skills, never an aspiration.
    All positioning/pillars are presented as hypotheses, not verified facts.
    """
    facts = [getattr(profile, key) for key in ("occupation", "experience", "skills", "interests", "content_assets")]
    if any(not any(item in value for value in facts if value) for item in result.strengths):
        raise FactLockError("unsupported_strength")
    if sparse(profile) and (not result.missing_information or result.confidence != "low"
                           or result.positioning_hypothesis.positioning != UNDETERMINED
                           or result.positioning_hypothesis.target_audience != UNDETERMINED
                           or result.content_pillars):
        raise FactLockError("insufficient_information_requires_abstention")
    if conflicting_constraints(profile) and not any("冲突" in item or "约束" in item for item in result.risks):
        raise FactLockError("constraint_conflict_not_identified")
    text = json.dumps(result.model_dump(exclude={"missing_information"}), ensure_ascii=False)
    input_text = " ".join(profile.model_dump().values())
    # Missing-information requests may ask about an absent credential, not assert it.
    sensitive = r"(?:硕士|博士|本科|名校毕业|年入\s*\d+\s*万|月入\s*\d+\s*万|\d+\s*万?粉丝)"
    if any(term not in input_text for term in re.findall(sensitive, text)):
        raise FactLockError("unsupported_sensitive_fact")
    # No performance evidence object exists in Phase 3: no validation/causality claims.
    assertions = [result.positioning_hypothesis.model_dump(), [p.model_dump() for p in result.content_pillars], result.strengths]
    assertion_text = json.dumps(assertions, ensure_ascii=False)
    if re.search(r"已经验证|已验证有效|表现最好|一定.{0,8}(?:涨粉|爆款)|保证.{0,8}(?:涨粉|爆款)|必爆", assertion_text):
        raise FactLockError("unsupported_performance_claim")


def parse_diagnosis(content: str, profile: ProfileFields) -> DiagnosisResult:
    if len(content) > 60000:
        raise ValueError("response_too_large")
    def unique_keys(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError("duplicate_json_key")
            output[key] = value
        return output
    value = json.loads(content, object_pairs_hook=unique_keys)
    result = DiagnosisResult.model_validate(value)
    validate_fact_lock(result, profile)
    return result
