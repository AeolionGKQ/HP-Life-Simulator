from fastapi.testclient import TestClient

from backend.app.core.config import LLMSettings, get_settings
from backend.app.main import create_app
from backend.app.providers.openai_compatible import OpenAICompatibleProvider


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
        ("亲世代", "1971–1978"),
        ("子世代", "1991–1998"),
        ("现代", "2020+"),
    ]
    assert all(era["mainline"] for era in eras)
    assert [era["id"] for era in eras if era["available"]] == ["second_generation"]


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
    timeout = captured["timeout"]
    assert getattr(timeout, "read") == 300

