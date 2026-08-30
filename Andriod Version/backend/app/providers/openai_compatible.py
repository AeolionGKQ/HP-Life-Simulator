from __future__ import annotations

import time
import json
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any

import httpx

from backend.app.core.config import LLMSettings, update_llm_thinking


GPT_5_6_MODELS = {
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
}

# 关闭思考没有统一标准，各家 OpenAI 兼容网关的字段不同：
# enable_thinking 覆盖通义/DashScope 与 vLLM，thinking 覆盖火山方舟与智谱，
# chat_template_kwargs 覆盖本地 vLLM/SGLang，reasoning 覆盖 OpenRouter。
# 多数服务会忽略不认识的字段；严格校验的服务会返回 400/422，此时按字段名裁剪后重试。
THINKING_DISABLE_FIELDS: dict[str, Any] = {
    "enable_thinking": False,
    "thinking": {"type": "disabled"},
    "chat_template_kwargs": {"enable_thinking": False},
    "reasoning": {"enabled": False},
}

PARAMETER_REJECTED_STATUS = (400, 422)


def thinking_disable_payload(fields: Sequence[str] | None) -> dict[str, Any]:
    """把字段名列表展开为请求体片段；None 表示使用全部已知字段。"""
    names = (
        list(THINKING_DISABLE_FIELDS)
        if fields is None
        else [name for name in fields if name in THINKING_DISABLE_FIELDS]
    )
    return {name: deepcopy(THINKING_DISABLE_FIELDS[name]) for name in names}


def rejected_thinking_fields(detail: str, sent: Sequence[str]) -> list[str]:
    """只有错误正文点名了我们发送的字段，才认定是这些字段被拒绝。

    必须按完整词匹配：`thinking` 是 `enable_thinking` 的子串，
    子串匹配会把没被点名的字段一起误删。前缀里排除 `.`，
    是为了不把 `chat_template_kwargs.enable_thinking` 这类嵌套路径
    误读成顶层的 `enable_thinking` 也被拒了。
    """
    lowered = (detail or "").lower()
    return [
        name
        for name in sent
        if re.search(rf"(?<![\w.]){re.escape(name.lower())}(?!\w)", lowered)
    ]


class OpenAICompatibleProvider:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        persist_thinking_fields: bool = True,
    ) -> None:
        self.settings = settings
        self.persist_thinking_fields = persist_thinking_fields


    @property
    def endpoint(self) -> str:
        return f"{self.settings.base_url}/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    def _base_payload(
        self,
        messages: list[dict[str, str]],
        temperature: float | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "stream": False,
        }
        if self.settings.model.strip().lower() not in GPT_5_6_MODELS:
            payload["temperature"] = (
                self.settings.temperature if temperature is None else temperature
            )
        if self.settings.supports_json_schema:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _active_thinking_fields(self) -> list[str]:
        if self.settings.enable_thinking:
            return []
        return list(thinking_disable_payload(self.settings.thinking_disable_fields))

    def _narrow_thinking_fields(self, fields: list[str]) -> None:
        """记住被服务拒绝后剩下的字段；全部被拒时放弃关闭思考。"""
        self.settings = self.settings.model_copy(
            update={
                "enable_thinking": not fields,
                "thinking_disable_fields": fields or None,
            }
        )
        if not self.persist_thinking_fields:
            return
        try:
            update_llm_thinking(
                enable_thinking=not fields,
                thinking_disable_fields=fields or None,
            )
        except (OSError, RuntimeError):
            # 配置写入失败不应阻断当前生成；下次请求会重新裁剪。
            pass

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        base = self._base_payload(messages, temperature)
        fields = self._active_thinking_fields()
        timeout = httpx.Timeout(self.settings.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            while True:
                payload = {**base, **thinking_disable_payload(fields)}
                response = await client.post(
                    self.endpoint,
                    headers=self._headers(),
                    json=payload,
                )
                if fields and response.status_code in PARAMETER_REJECTED_STATUS:
                    rejected = rejected_thinking_fields(response.text, fields)
                    if rejected:
                        fields = [name for name in fields if name not in rejected]
                        self._narrow_thinking_fields(fields)
                        continue
                    # 服务拒绝了却没点名字段，无法逐个裁剪。去掉全部思考字段再试一次：
                    # 成功就说明确实是它们引起的，放弃关闭思考也比让这一回合生成失败好。
                    plain = await client.post(
                        self.endpoint,
                        headers=self._headers(),
                        json=base,
                    )
                    if plain.is_success:
                        self._narrow_thinking_fields([])
                        return plain.json()
                response.raise_for_status()
                return response.json()

    async def probe_thinking_disable_fields(self) -> tuple[list[str], bool]:
        """探测服务接受哪些关闭思考的字段。

        返回 (可用字段, 是否完成验证)。验证失败时字段列表无意义，
        调用方应按全部字段处理，并依赖运行时裁剪兜底。
        """
        all_fields = list(THINKING_DISABLE_FIELDS)
        base = self._base_payload(
            [
                {"role": "system", "content": "只回复 OK，不要回复其他内容。"},
                {"role": "user", "content": "连接测试"},
            ],
            0,
        )
        timeout = httpx.Timeout(self.settings.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:

                async def attempt(probe_fields: Sequence[str]) -> Any:
                    return await client.post(
                        self.endpoint,
                        headers=self._headers(),
                        json={**base, **thinking_disable_payload(probe_fields)},
                    )

                fields = list(all_fields)
                while fields:
                    response = await attempt(fields)
                    if response.is_success:
                        return fields, True
                    if response.status_code not in PARAMETER_REJECTED_STATUS:
                        return all_fields, False
                    rejected = rejected_thinking_fields(response.text, fields)
                    if rejected:
                        fields = [name for name in fields if name not in rejected]
                        continue
                    # 服务拒绝了却没点名字段，只能逐个试。先确认它本身能用，
                    # 否则会把 Key 失效、模型名写错一类的错误
                    # 误判成「不接受关闭思考」，给玩家错误的提示。
                    baseline = await attempt([])
                    if not baseline.is_success:
                        return all_fields, False
                    accepted: list[str] = []
                    for name in fields:
                        single = await attempt([name])
                        if single.is_success:
                            accepted.append(name)
                    if len(accepted) <= 1:
                        return accepted, True
                    # 单个都能过却整组被拒，说明服务对字段组合另有限制，
                    # 只保留一个已验证可用的字段。
                    combined = await attempt(accepted)
                    if combined.is_success:
                        return accepted, True
                    return accepted[:1], True
                return [], True
        except httpx.RequestError:
            return all_fields, False


    async def test_connection(self) -> tuple[bool, str, int]:
        started = time.perf_counter()
        try:
            result = await self.chat_completion(
                [
                    {
                        "role": "system",
                        "content": "只回复 OK，不要回复其他内容。",
                    },
                    {"role": "user", "content": "连接测试"},
                ],
                temperature=0,
            )
            raw_content = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if isinstance(raw_content, str):
                content = raw_content.strip()
            elif raw_content is None:
                content = ""
            else:
                content = json.dumps(raw_content, ensure_ascii=False)
            message = "模型服务连接成功" if content else "模型服务已成功返回响应"
            success = True
        except httpx.HTTPStatusError as exc:
            message = f"模型服务返回 HTTP {exc.response.status_code}"
            success = False
        except httpx.RequestError:
            message = "无法连接到模型服务"
            success = False
        except (KeyError, TypeError, ValueError):
            message = "模型服务返回了无法解析的响应"
            success = False
        latency_ms = round((time.perf_counter() - started) * 1000)
        return success, message, latency_ms
