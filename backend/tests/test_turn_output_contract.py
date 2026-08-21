from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from backend.app.prompts.turn import build_turn_messages
from backend.app.schemas.game import (
    ActionRequest,
    Choice,
    LongTermMemoryProposal,
    MemoryRequest,
    NarrativeResponse,
)
from backend.app.services.turns import (
    _normalize_memory_importance,
    _request_response,
)


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
    assert "resource_deltas" in system_prompt
    assert "dimension_deltas" in system_prompt
    assert "skill_experience_deltas" in system_prompt
    assert "经验达到 100 后，由程序自动将技能等级提升 1 并把经验清零" in system_prompt
    assert "current_date" in system_prompt
    assert "location_id" in system_prompt
    assert "不是必然成功" in system_prompt
    assert "奥利凡德魔杖店" in system_prompt
    assert "分院" in system_prompt
    assert "low、medium、high、fatal" in system_prompt
    assert "被朋友讨厌" in system_prompt
    assert "考试不及格" in system_prompt
    assert "memory.importance 必须是 1 到 10 之间的整数" in system_prompt
    assert "vital_deltas" not in system_prompt
    assert "attribute_deltas" not in system_prompt
    assert "fate_instruction" in system_prompt
    assert "干涉命运" in system_prompt
    assert "声望是程序掌握的总体社会印象" in system_prompt
    assert "单轮最多增加 10 点或减少 10 点" in system_prompt
    assert '"score": 整数' in system_prompt
    assert "高声望不能自动成功" in system_prompt
    assert "player_state.school.grade 是 left_school" in system_prompt
    assert "尽快离开" in system_prompt
    assert "返聘为教授" in system_prompt
    assert "声望达到 black_wizard 或 dark_paragon 时，程序会自动执行 expelled" in system_prompt
    assert "哈利·波特" in system_prompt
    assert "姓 + 小姐/先生" in system_prompt
    assert "中间名" in system_prompt
    assert "不能倒置" in system_prompt
    assert "当前世代主线是历史压力和因果背景，不是强制任务列表" in system_prompt
    assert "一轮最多主动推进一个主线焦点" in system_prompt
    assert "玩家拥有独立人生" in system_prompt
    assert "不得默认玩家认识所有原著人物" in system_prompt
    assert "羁绊系统统一描述" in system_prompt
    assert "relationship_creations" in system_prompt
    assert "每轮最多创建一个新 NPC" in system_prompt
    assert "NPC 年龄未知" in system_prompt
    assert "committed、adult_stage 和 marriage" in system_prompt


def test_turn_context_contains_layered_generation_background() -> None:
    messages = _build_messages()
    context = json.loads(
        messages[1]["content"].split("以下是本回合的权威状态和上下文：\n", 1)[1]
    )
    generation = context["generation"]

    assert generation["id"] == "second_generation"
    assert generation["era_frame"]["historical_mood"]
    assert "南瓜汁的甜腻" in generation["era_frame"]["core_atmosphere"]
    assert generation["mainline_phase"]["id"] == "letter_and_enrollment"
    assert generation["timeline_phase"]["phase_id"] == "pre_enrollment_summer"
    assert generation["freedom_rules"]
    assert generation["worldline_pressure"]["offset_rate"] == 0
    assert "worldline_rule" in generation["worldline_pressure"]


def test_fate_intervention_request_requires_exclusive_non_empty_instruction() -> None:
    request = ActionRequest(
        client_action_id="fate-1",
        expected_state_version=4,
        kind="fate_intervention",
        fate_instruction="  下一幕让无名书出现在禁书区。  ",
    )
    assert request.fate_instruction == "下一幕让无名书出现在禁书区。"

    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="fate-empty",
            expected_state_version=4,
            kind="fate_intervention",
            fate_instruction="   ",
        )
    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="fate-mixed",
            expected_state_version=4,
            kind="fate_intervention",
            choice_id="choice_1",
            fate_instruction="下一幕发生一件事",
        )
    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="ordinary",
            expected_state_version=4,
            kind="choice",
            choice_id="choice_1",
            fate_instruction="不应出现在普通行动中",
        )


def test_reshape_fate_request_requires_exclusive_non_empty_instruction() -> None:
    request = ActionRequest(
        client_action_id="reshape-1",
        expected_state_version=4,
        kind="reshape_fate",
        reshape_instruction="  让这一幕的悬念更缓慢地展开。  ",
    )
    assert request.reshape_instruction == "让这一幕的悬念更缓慢地展开。"

    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="reshape-empty",
            expected_state_version=4,
            kind="reshape_fate",
            reshape_instruction="   ",
        )
    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="reshape-mixed",
            expected_state_version=4,
            kind="reshape_fate",
            free_text="普通行动",
            reshape_instruction="重写这一幕",
        )
    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="reshape-fate-mixed",
            expected_state_version=4,
            kind="reshape_fate",
            fate_instruction="下一幕发生一件事",
            reshape_instruction="重写这一幕",
        )
    with pytest.raises(ValidationError):
        ActionRequest(
            client_action_id="ordinary-reshape",
            expected_state_version=4,
            kind="choice",
            choice_id="choice_1",
            reshape_instruction="不应出现在普通行动中",
        )


@pytest.mark.parametrize("risk", ["low", "medium", "high", "fatal"])
def test_choice_accepts_only_the_four_risk_levels(risk: str) -> None:
    assert Choice(id="choice", label="行动", risk=risk).risk == risk


def test_choice_rejects_unknown_risk_level() -> None:
    with pytest.raises(ValidationError):
        Choice(id="choice", label="行动", risk="unknown")


def test_long_term_memory_requires_numeric_importance() -> None:
    assert LongTermMemoryProposal(summary="重要事件", importance=8).importance == 8
    with pytest.raises(ValidationError):
        LongTermMemoryProposal(summary="重要事件", importance="major")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("major", 8),
        ("high", 8),
        ("critical", 10),
        ("重要", 8),
        ("9", 9),
        (99, 10),
        (-4, 1),
        ("not-a-level", 5),
        (True, 5),
    ],
)
def test_memory_importance_fallback_never_raises(value: Any, expected: int) -> None:
    assert _normalize_memory_importance(value) == expected


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
            "current_date": "1991-09-01",
            "location_id": "great_hall",
        },
        "choices": [
            {"id": "listen", "label": "仔细倾听", "kind": "action", "risk": "low"},
            {"id": "ask", "label": "询问身边同学", "kind": "action", "risk": "medium"},
            {"id": "choice_other", "label": "其他", "kind": "free_text", "risk": "low"},
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
            {"label": "缺少选项 ID", "kind": "action", "risk": "low"},
            {"id": "ask", "label": "询问身边同学", "kind": "action", "risk": "medium"},
            {"id": "choice_other", "label": "其他", "kind": "free_text", "risk": "low"},
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


@pytest.mark.asyncio
async def test_request_response_repairs_text_memory_importance() -> None:
    valid_response = _extract_json_template(
        _build_messages()[0]["content"],
        "NARRATIVE",
    )
    valid_response["memory_update"] = {
        "summary": "玩家发现了密室入口。",
        "create_long_term_memory": True,
        "memory": {
            "summary": "玩家发现了密室入口。",
            "importance": 8,
        },
        "resolved_memory_ids": [],
    }
    invalid_response = deepcopy(valid_response)
    invalid_response["memory_update"]["memory"]["importance"] = "major"
    provider = _SequencedProvider([
        _completion(json.dumps(invalid_response, ensure_ascii=False)),
        _completion(json.dumps(valid_response, ensure_ascii=False)),
    ])

    result = await _request_response(provider, _build_messages())

    assert isinstance(result, NarrativeResponse)
    assert result.memory_update.memory is not None
    assert result.memory_update.memory.importance == 8
    assert len(provider.calls) == 2
    assert "memory_update.memory.importance" in provider.calls[1]["messages"][-1]["content"]
