from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.prompts.turn import build_turn_messages
from backend.app.schemas.game import MemoryRequest, NarrativeResponse
from backend.app.services.turns import _request_response


def _extract_json_template(system_prompt: str, name: str) -> dict[str, Any]:
    start_marker = f"\n{name}_JSON_TEMPLATE_BEGIN\n"
    end_marker = f"\n{name}_JSON_TEMPLATE_END"
    assert start_marker in system_prompt
    assert end_marker in system_prompt
    template = system_prompt.split(start_marker, 1)[1].split(end_marker, 1)[0]
    return json.loads(template.strip())


def _build_messages() -> list[dict[str, str]]:
    return build_turn_messages(
        game_session=SimpleNamespace(
            id="session-1",
            era_id="second_generation",
            status="active",
            state_version=1,
        ),
        player_state=SimpleNamespace(state={}),
        npcs=[],
        relationships=[],
        recent_turns=[],
        memories=[],
        summaries=[],
        action={"kind": "choice", "choice_id": "start_story"},
    )


def test_turn_system_prompt_contains_parseable_response_templates() -> None:
    system_prompt = _build_messages()[0]["content"]

    narrative = _extract_json_template(system_prompt, "NARRATIVE")
    memory_request = _extract_json_template(system_prompt, "MEMORY_REQUEST")

    parsed_narrative = NarrativeResponse.model_validate(narrative)
    parsed_memory_request = MemoryRequest.model_validate(memory_request)

    assert parsed_narrative.response_type == "narrative"
    assert parsed_narrative.choices[-1].kind == "free_text"
    assert parsed_memory_request.response_type == "memory_request"
    assert "不要输出 Markdown" in system_prompt
    assert "不得省略必填字段" in system_prompt
    assert "禁止使用单引号、注释、尾随逗号、NaN 或 undefined" in system_prompt
    assert "模板边界标记不得输出" in system_prompt


class _SequencedProvider:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return self.responses[len(self.calls) - 1]


def _completion(content: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


@pytest.mark.asyncio
async def test_request_response_repairs_with_error_context_and_zero_temperature() -> None:
    valid_response = {
        "response_type": "narrative",
        "turn": {
            "title": "礼堂中的回声",
            "scene_type": "dialogue",
            "narrative": "烛光在长桌上轻轻摇曳。",
            "location_id": "great_hall",
            "time_advance_minutes": 5,
        },
        "choices": [
            {"id": "listen", "label": "仔细倾听", "kind": "action"},
            {"id": "ask", "label": "询问身边同学", "kind": "action"},
            {"id": "choice_other", "label": "其他", "kind": "free_text"},
        ],
        "state_proposals": {},
        "player_changes": {},
        "worldline": {
            "offset_rate": 0,
            "delta": 0,
            "reason": "尚未改变关键事件",
            "affected_nodes": [],
        },
        "events": [],
        "memory_update": {
            "summary": "玩家进入礼堂。",
            "create_long_term_memory": False,
            "memory": None,
            "resolved_memory_ids": [],
        },
        "self_check": {},
    }
    invalid_response = {
        **valid_response,
        "choices": [
            {"label": "缺少选项 ID", "kind": "action"},
            {"id": "ask", "label": "询问身边同学", "kind": "action"},
            {"id": "choice_other", "label": "其他", "kind": "free_text"},
        ],
    }
    provider = _SequencedProvider(
        [
            _completion(json.dumps(invalid_response, ensure_ascii=False)),
            _completion(json.dumps(valid_response, ensure_ascii=False)),
        ]
    )

    result = await _request_response(provider, _build_messages())

    assert isinstance(result, NarrativeResponse)
    assert len(provider.calls) == 2
    repair_call = provider.calls[1]
    assert repair_call["kwargs"] == {"temperature": 0}
    repair_instruction = repair_call["messages"][-1]["content"]
    assert "choices.0.id" in repair_instruction
    assert "NARRATIVE_JSON_TEMPLATE_BEGIN" in repair_instruction
    assert "MEMORY_REQUEST_JSON_TEMPLATE_BEGIN" in repair_instruction
