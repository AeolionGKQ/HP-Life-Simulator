from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import LLMSettings, get_settings
from backend.app.main import create_app
from backend.app.providers.openai_compatible import (
    OpenAICompatibleProvider,
    rejected_thinking_fields,
)


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_llm_config_status_does_not_expose_key() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/config/llm")
    assert response.status_code == 200
    body = response.json()
    assert "api_key" not in body
    assert body["api_key_present"] is True


def test_four_eras_match_world_bible() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/content/eras")
    assert response.status_code == 200
    eras = response.json()
    assert [(era["name"], era["years"]) for era in eras] == [
        ("邓布利多时代", "1892–1899"),
        ("亲世代", "1971–1981+"),
        ("子世代", "1991–1998"),
        ("现代", "2020+"),
    ]
    assert all(era["mainline"] for era in eras)
    assert [era["id"] for era in eras if era["available"]] == [
        "dumbledore_era",
        "parent_generation",
        "second_generation",
        "modern",
    ]


async def test_llm_connection_formats_object_content(monkeypatch) -> None:
    async def fake_completion(self, messages, **kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": {"status": "ok"},
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleProvider, "chat_completion", fake_completion)
    provider = OpenAICompatibleProvider(get_settings().llm)
    success, message, _ = await provider.test_connection()
    assert success is True
    assert message == "模型服务连接成功"


async def test_chat_completion_omits_max_tokens_by_default(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["timeout"] = kwargs["timeout"]

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, endpoint: str, *, headers: dict[str, str], json: dict[str, object]) -> FakeResponse:
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleProvider(
        LLMSettings(
            base_url="https://example.com",
            api_key="test-key",
            model="test-model",
            timeout_seconds=300,
        )
    )

    await provider.chat_completion([{"role": "user", "content": "test"}])

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "max_tokens" not in payload
    assert payload["temperature"] == 0.8
    timeout = captured["timeout"]
    assert getattr(timeout, "read") == 300


@pytest.mark.parametrize(
    "model",
    [
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "  GPT-5.6-LUNA  ",
    ],
)
async def test_chat_completion_omits_temperature_for_gpt_5_6_family(
    monkeypatch,
    model: str,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self,
            endpoint: str,
            *,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            captured["payload"] = json
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", FakeClient)
    provider = OpenAICompatibleProvider(
        LLMSettings(
            base_url="https://api.openai.com",
            api_key="test-key",
            model=model,
            temperature=0.8,
        )
    )

    await provider.chat_completion(
        [{"role": "user", "content": "test"}],
        temperature=0,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "temperature" not in payload


def _capture_payload_client(captured: dict[str, object], script=None):
    """script 为 (status_code, body_text) 列表，按调用顺序返回；默认一直成功。"""
    calls: list[dict[str, object]] = []
    captured["calls"] = calls

    class FakeResponse:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text

        @property
        def is_success(self) -> bool:
            return 200 <= self.status_code < 300

        def raise_for_status(self) -> None:
            if not self.is_success:
                raise AssertionError(f"unexpected raise_for_status {self.status_code}")

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "{}"}}]}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self,
            endpoint: str,
            *,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            captured["payload"] = json
            calls.append(json)
            if script and len(calls) <= len(script):
                status_code, text = script[len(calls) - 1]
                return FakeResponse(status_code, text)
            return FakeResponse(200, "")

    return FakeClient


def _thinking_provider(
    *,
    enable_thinking: bool,
    thinking_disable_fields: list[str] | None = None,
) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        LLMSettings(
            base_url="https://example.com",
            api_key="test-key",
            model="test-model",
            enable_thinking=enable_thinking,
            thinking_disable_fields=thinking_disable_fields,
        ),
        persist_thinking_fields=False,
    )


async def test_thinking_enabled_by_default_keeps_payload_unchanged(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr("httpx.AsyncClient", _capture_payload_client(captured))

    assert LLMSettings(
        base_url="https://example.com", api_key="k", model="m"
    ).enable_thinking is True
    await _thinking_provider(enable_thinking=True).chat_completion(
        [{"role": "user", "content": "test"}]
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    for key in ("enable_thinking", "thinking", "chat_template_kwargs", "reasoning"):
        assert key not in payload


async def test_disabled_thinking_adds_vendor_switches(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr("httpx.AsyncClient", _capture_payload_client(captured))

    await _thinking_provider(enable_thinking=False).chat_completion(
        [{"role": "user", "content": "test"}]
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["enable_thinking"] is False
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["reasoning"] == {"enabled": False}


def test_llm_config_status_reports_thinking_flag() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/config/llm")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["enable_thinking"], bool)
    assert body["enable_thinking"] is get_settings().llm.enable_thinking


async def test_rejected_thinking_field_is_dropped_and_request_retried(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(
            captured,
            script=[(400, "Unrecognized request argument supplied: enable_thinking")],
        ),
    )

    provider = _thinking_provider(enable_thinking=False)
    await provider.chat_completion([{"role": "user", "content": "test"}])

    calls = captured["calls"]
    assert isinstance(calls, list)
    assert len(calls) == 2
    assert "enable_thinking" in calls[0]
    assert "enable_thinking" not in calls[1]
    assert calls[1]["thinking"] == {"type": "disabled"}
    assert provider.settings.thinking_disable_fields == [
        "thinking",
        "chat_template_kwargs",
        "reasoning",
    ]
    assert provider.settings.enable_thinking is False


async def test_all_fields_rejected_gives_up_on_disabling_thinking(monkeypatch) -> None:
    captured: dict[str, object] = {}
    rejection = (
        400,
        "invalid parameters: enable_thinking, thinking, chat_template_kwargs, reasoning",
    )
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(captured, script=[rejection]),
    )

    provider = _thinking_provider(enable_thinking=False)
    await provider.chat_completion([{"role": "user", "content": "test"}])

    calls = captured["calls"]
    assert isinstance(calls, list)
    assert len(calls) == 2
    for key in ("enable_thinking", "thinking", "chat_template_kwargs", "reasoning"):
        assert key not in calls[1]
    assert provider.settings.enable_thinking is True
    assert provider.settings.thinking_disable_fields is None


async def test_unrelated_400_keeps_thinking_fields_and_raises(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(
            captured,
            script=[(400, "invalid api key"), (400, "invalid api key")],
        ),
    )

    provider = _thinking_provider(enable_thinking=False)
    with pytest.raises(AssertionError):
        await provider.chat_completion([{"role": "user", "content": "test"}])

    calls = captured["calls"]
    assert isinstance(calls, list)
    # 第二次是去掉思考字段的兜底探路，它也失败说明与思考字段无关。
    assert len(calls) == 2
    for key in ("enable_thinking", "thinking", "chat_template_kwargs", "reasoning"):
        assert key not in calls[1]
    assert provider.settings.enable_thinking is False
    assert provider.settings.thinking_disable_fields is None


async def test_vague_400_falls_back_to_dropping_all_thinking_fields(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(captured, script=[(400, "invalid request body")]),
    )

    provider = _thinking_provider(enable_thinking=False)
    await provider.chat_completion([{"role": "user", "content": "test"}])

    calls = captured["calls"]
    assert isinstance(calls, list)
    assert len(calls) == 2
    for key in ("enable_thinking", "thinking", "chat_template_kwargs", "reasoning"):
        assert key not in calls[1]
    assert provider.settings.enable_thinking is True
    assert provider.settings.thinking_disable_fields is None


def test_nested_field_path_does_not_drop_top_level_field() -> None:
    rejected = rejected_thinking_fields(
        "unknown field chat_template_kwargs.enable_thinking",
        ["enable_thinking", "thinking", "chat_template_kwargs", "reasoning"],
    )
    assert rejected == ["chat_template_kwargs"]


async def test_probe_returns_accepted_subset(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(
            captured,
            script=[(422, "unknown field enable_thinking and chat_template_kwargs")],
        ),
    )

    accepted, verified = await _thinking_provider(
        enable_thinking=False
    ).probe_thinking_disable_fields()

    assert verified is True
    assert accepted == ["thinking", "reasoning"]


async def test_probe_reports_unverified_for_unrelated_error(monkeypatch) -> None:
    captured: dict[str, object] = {}
    unrelated = (400, "context length exceeded")
    monkeypatch.setattr(
        "httpx.AsyncClient",
        # 整组被拒后不带字段的基线请求也失败，说明问题不在思考字段。
        _capture_payload_client(captured, script=[unrelated, unrelated]),
    )

    accepted, verified = await _thinking_provider(
        enable_thinking=False
    ).probe_thinking_disable_fields()

    assert verified is False
    assert accepted == [
        "enable_thinking",
        "thinking",
        "chat_template_kwargs",
        "reasoning",
    ]


async def test_probe_isolates_fields_one_by_one_when_error_is_vague(monkeypatch) -> None:
    captured: dict[str, object] = {}
    vague = (400, "invalid request body")
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(
            captured,
            script=[
                vague,        # 四个字段一起发 -> 被拒且没点名
                (200, ""),    # 不带字段的基线 -> 服务本身可用
                vague,        # enable_thinking 单发 -> 不认
                (200, ""),    # thinking 单发 -> 可用
                vague,        # chat_template_kwargs 单发 -> 不认
                (200, ""),    # reasoning 单发 -> 可用
                (200, ""),    # 两个可用字段合并复验
            ],
        ),
    )

    accepted, verified = await _thinking_provider(
        enable_thinking=False
    ).probe_thinking_disable_fields()

    assert verified is True
    assert accepted == ["thinking", "reasoning"]
    calls = captured["calls"]
    assert isinstance(calls, list)
    assert len(calls) == 7


async def test_probe_keeps_single_field_when_combination_is_rejected(monkeypatch) -> None:
    captured: dict[str, object] = {}
    vague = (400, "invalid request body")
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(
            captured,
            script=[vague] + [(200, "")] * 5 + [vague],
        ),
    )

    accepted, verified = await _thinking_provider(
        enable_thinking=False
    ).probe_thinking_disable_fields()

    assert verified is True
    # 四个字段单发都能过、合并却被拒，只保留第一个已验证可用的字段。
    assert accepted == ["enable_thinking"]


async def test_probe_reports_no_usable_field_when_every_single_probe_fails(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    vague = (400, "invalid request body")
    monkeypatch.setattr(
        "httpx.AsyncClient",
        _capture_payload_client(
            captured,
            script=[vague, (200, ""), vague, vague, vague, vague],
        ),
    )

    accepted, verified = await _thinking_provider(
        enable_thinking=False
    ).probe_thinking_disable_fields()

    assert verified is True
    assert accepted == []
