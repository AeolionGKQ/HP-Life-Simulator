from __future__ import annotations

import time
from typing import Any

import httpx

from backend.app.core.config import LLMSettings


class OpenAICompatibleProvider:
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    @property
    def endpoint(self) -> str:
        return f"{self.settings.base_url}/v1/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": (
                self.settings.temperature if temperature is None else temperature
            ),
            "max_tokens": max_tokens or self.settings.max_output_tokens,
            "stream": False,
        }
        if self.settings.supports_json_schema:
            payload["response_format"] = {"type": "json_object"}
        timeout = httpx.Timeout(self.settings.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self.endpoint,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

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
                max_tokens=8,
                temperature=0,
            )
            content = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            message = content or "模型已返回响应"
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

