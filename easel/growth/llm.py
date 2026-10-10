"""No-tool compatible adapter with private local .env configuration."""

from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

from .database import PROJECT_ROOT
from .diagnosis_schema import DiagnosisResult, ProfileFields
from .models import ProviderUsage

SKILL_DIR = PROJECT_ROOT / "skills" / "growth" / "diagnosis"


class ModelError(Exception):
    pass


@dataclass
class ModelReply:
    content: str
    usage: ProviderUsage | None = None


@dataclass
class ModelConfig:
    base_url: str
    model: str
    api_key: str = field(repr=False)

    @classmethod
    def from_environment(cls):
        # Fixed repository-local path, no upward discovery or variable interpolation.
        # Do not mutate os.environ: legacy subprocesses must not inherit this key.
        try:
            local = dotenv_values(PROJECT_ROOT / ".env", interpolate=False, verbose=False)
        except (OSError, UnicodeError):
            local = {}
        def value(name):
            return os.environ.get(name, local.get(name) or "")
        return cls(value("GROWTH_LLM_BASE_URL").strip().rstrip("/"),
                   value("GROWTH_LLM_MODEL").strip(), value("GROWTH_LLM_API_KEY"))

    @property
    def ready(self):
        try:
            url = urlsplit(self.base_url)
            return bool(self.model and self.api_key and url.hostname and not url.username and not url.password
                        and not url.query and not url.fragment
                        and (url.scheme == "https" or (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"})))
        except ValueError:
            return False


def messages(account: dict, profile: ProfileFields) -> list[dict]:
    prompt = (SKILL_DIR / "prompt.md").read_text(encoding="utf-8")
    rules = (SKILL_DIR / "rules.md").read_text(encoding="utf-8")
    examples = (SKILL_DIR / "examples.json").read_text(encoding="utf-8")
    return [
        {"role": "system", "content": prompt + "\n" + rules + "\nOutput JSON Schema:\n"
         + json.dumps(DiagnosisResult.model_json_schema(), ensure_ascii=False) + "\nExamples (not user facts):\n" + examples},
        {"role": "user", "content": json.dumps({"account": account, "profile": profile.model_dump()}, ensure_ascii=False)},
    ]


def provider_usage(payload: dict) -> ProviderUsage | None:
    raw = payload.get("usage")
    if not isinstance(raw, dict):
        return None
    # Whitelist numerical usage only. Never persist arbitrary provider metadata/key echoes.
    clean = {k: v for k, v in raw.items() if k in {"prompt_tokens", "completion_tokens", "total_tokens"}
             and type(v) is int and v >= 0}
    cost = raw.get("cost")
    if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
        clean["cost"] = cost
    return ProviderUsage(source="provider_response.usage", tokens=clean.get("total_tokens"),
                         cost=clean.get("cost"), raw=clean)


class CompatibleModel:
    def __init__(self, config: ModelConfig | None = None, transport=None):
        self.config = config or ModelConfig.from_environment()
        self.transport = transport  # Test dependency injection only; no production mock switch.

    @property
    def model_name(self):
        return self.config.model or None

    async def diagnose(self, account: dict, profile: ProfileFields) -> ModelReply:
        if not self.config.ready:
            raise ModelError("模型未配置：请在项目本地 .env 设置 GROWTH_LLM_BASE_URL、GROWTH_LLM_MODEL、GROWTH_LLM_API_KEY 并重启后端。")
        try:
            async with httpx.AsyncClient(timeout=90, transport=self.transport, follow_redirects=False) as client:
                response = await client.post(self.config.base_url + "/chat/completions", headers={
                    "Authorization": "Bearer " + self.config.api_key,
                }, json={"model": self.config.model, "messages": messages(account, profile),
                         "response_format": {"type": "json_object"}, "temperature": 0.2, "max_tokens": 3000})
                if response.status_code >= 300:
                    raise ModelError("模型服务请求失败，请检查后端模型配置或稍后重试。")
                if len(response.content) > 250000:
                    raise ModelError("模型响应过大，未保存诊断。")
                payload = response.json()
                content = payload["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise ValueError("not_text")
                # A provider must never be able to echo the credential into stored/displayed output.
                if self.config.api_key in content:
                    raise ModelError("模型响应包含敏感配置内容，已拒绝保存。")
                return ModelReply(content, provider_usage(payload))
        except httpx.TimeoutException:
            raise ModelError("模型请求超时，未保存诊断；可以手动重试。") from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise ModelError("模型响应无法读取，未保存诊断；请检查兼容接口。") from None
