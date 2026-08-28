from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from backend.app.compat import HTTPException
from pydantic import ValidationError

from backend.app.prompts.turn import _recent_turns_to_context, build_turn_messages
from backend.app.schemas.game import (
    ActionRequest,
    Choice,
    LongTermMemoryProposal,
    MemoryRequest,
    NarrativeResponse,
)
from backend.app.services.turns import (
    _action_text,
    _build_action,
    _normalize_memory_importance,
    _refresh_npc_ages,
    _request_response,
    _resolve_selected_choice,
)


def _extract_json_template(system_prompt: str, name: str) -> dict[str, Any]:
    start_marker = f"\n{name}_JSON_TEMPLATE_BEGIN\n"
    end_marker = f"\n{name}_JSON_TEMPLATE_END"
    assert start_marker in system_prompt
    assert end_marker in system_prompt
    template = system_prompt.split(start_marker, 1)[1].split(end_marker, 1)[0]
    return json.loads(template.strip())


def _build_messages(
    state: dict[str, Any] | None = None,
    *,
    era_id: str = "second_generation",
    action: dict[str, Any] | None = None,
    recent_turns: list[Any] | None = None,
) -> list[dict[str, str]]:
    return build_turn_messages(
        game_session=SimpleNamespace(
            id="session-1",
            era_id=era_id,
            status="active",
            state_version=1,
        ),
        player_state=SimpleNamespace(state=state or {}),
        npcs=[],
        relationships=[],
        recent_turns=recent_turns or [],
        memories=[],
        summaries=[],
        action=action or {"kind": "choice", "choice_id": "start_story"},
    )


def test_modern_prompt_omits_course_system_context() -> None:
    state = {
        "school": {
            "grade": "year_4",
            "active_courses": ["charms"],
            "course_selection": {"status": "pending"},
            "course_history": [{"school_year": "2020-2021"}],
        },
        "skills": {
            "charms": {
                "id": "charms",
                "name": "咒语",
                "course_skill": True,
                "level": 1,
            },
            "wandwork": {
                "id": "wandwork",
                "name": "魔杖运用",
                "course_skill": False,
                "level": 1,
            },
            "expecto_patronum": {
                "id": "expecto_patronum",
                "name": "呼神护卫",
                "level": 1,
                "learned": True,
            },
        },
    }
    messages = _build_messages(state, era_id="modern")
    system_prompt = messages[0]["content"]
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert "课程" not in system_prompt
    assert "课程状态是程序权威" not in system_prompt
    assert "current_courses" not in context
    assert "course_catalog" not in context
    assert "course_rules" not in context
    assert "active_courses" not in context["player_state"]["school"]
    assert "course_history" not in context["player_state"]["school"]
    assert "charms" not in context["current_skills"]
    assert "wandwork" in context["current_skills"]
    assert "已学会【呼神护卫】" in system_prompt
    assert "角色未学会【呼神护卫】时无法召唤守护神" not in system_prompt


def test_second_generation_prompt_keeps_course_system_context() -> None:
    messages = _build_messages(
        {
            "school": {
                "grade": "year_3",
                "active_courses": ["charms"],
                "course_selection": {"status": "pending"},
            },
            "skills": {},
        },
    )
    system_prompt = messages[0]["content"]
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert "课程状态是程序权威" in system_prompt
    assert "current_courses" in context
    assert "course_catalog" in context
    assert "course_rules" in context
    assert context["current_courses"]["active_courses"] == ["charms"]


def test_dumbledore_prompt_keeps_courses_and_rich_era_background() -> None:
    messages = _build_messages(
        {
            "school": {
                "grade": "not_enrolled",
                "enrollment_started": False,
                "sorting_completed": False,
            },
            "current_context": {
                "current_date": "1892-07-01",
                "location_id": "godrics_hollow",
                "activity": "godrics_hollow",
            },
            "story_milestones": {
                "wand_obtained": False,
                "sorting_completed": False,
            },
            "skills": {},
        },
        era_id="dumbledore_era",
    )
    system_prompt = messages[0]["content"]
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert "课程状态是程序权威" in system_prompt
    assert "历史世代" in system_prompt
    assert "少年学生，不是校长" in system_prompt
    assert "【强约束与弱约束】" in system_prompt
    assert "generation.available_figures" in system_prompt
    assert "被标注为留白、争议、约某年、可创作或不得宣称官方的内容" in system_prompt
    assert "就要按架空历史推进" in system_prompt
    assert "【现代世代｜时间扰动规则】" not in system_prompt
    assert "现代世代不启用课程系统" not in system_prompt
    assert context["generation"]["id"] == "dumbledore_era"
    assert "煤油灯" in context["generation"]["era_background"]
    assert context["generation"]["available_figures"]
    assert any(item["npc_id"] == "albus_dumbledore" for item in context["generation"]["cast_index"])
    assert "current_courses" in context
    assert context["modern_context"] is None
    assert "【邓布利多时代｜直入终局】" not in system_prompt


def test_dumbledore_endgame_prompt_injects_endgame_rules() -> None:
    messages = _build_messages(
        {
            "school": {
                "grade": "left_school",
                "departure_reason": "graduated_after_newts",
                "enrollment_started": True,
                "sorting_completed": True,
            },
            "current_context": {
                "current_date": "1899-08-31",
                "location_id": "godrics_hollow",
                "activity": "godrics_hollow_1899_fall",
            },
            "story_milestones": {
                "wand_obtained": True,
                "sorting_completed": True,
            },
            "endgame_entry": {
                "starting_point": "godrics_hollow_1899_fall",
                "premise": "你与阿不思同窗七年，是挚友。",
                "ariana_alive": False,
                "grindelwald_present": False,
            },
            "skills": {
                "expecto_patronum": {
                    "id": "expecto_patronum",
                    "name": "呼神护卫",
                    "level": 1,
                    "learned": True,
                }
            },
        },
        era_id="dumbledore_era",
    )
    system_prompt = messages[0]["content"]
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert "【邓布利多时代｜直入终局】" in system_prompt
    assert "本规则覆盖" in system_prompt
    assert "不得指认杀死阿利安娜的咒语来自谁" in system_prompt
    assert "已学会【呼神护卫】" in system_prompt
    assert "角色未学会【呼神护卫】时无法召唤守护神" not in system_prompt
    assert "godrics_hollow_1899_fall" in system_prompt
    assert "分院仪式的当前节点" in system_prompt
    assert "【分院】剧情真正完成之前" not in system_prompt
    assert "在【奥利凡德魔杖店】剧情真正完成之前" not in system_prompt
    assert context["player_state"]["endgame_entry"]["ariana_alive"] is False
    assert context["generation"]["mainline_phase"]["id"] == "greater_good_summer"


def test_parent_prompt_keeps_courses_and_student_snape() -> None:
    messages = _build_messages(
        {
            "school": {
                "grade": "year_1",
                "enrollment_started": True,
                "sorting_completed": False,
                "active_courses": ["charms"],
            },
            "current_context": {
                "current_date": "1971-09-01",
                "location_id": "platform_nine_three_quarters",
                "activity": "platform_nine_three_quarters",
            },
            "story_milestones": {
                "wand_obtained": True,
                "sorting_completed": False,
            },
            "skills": {},
        },
        era_id="parent_generation",
    )
    system_prompt = messages[0]["content"]
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert "课程状态是程序权威" in system_prompt
    assert "作者资料与角色认知边界" in system_prompt
    assert "成年身份不自动等于凤凰社成员" in system_prompt
    assert "斯莱特林学生，不是魔药课教授" in system_prompt
    assert "【现代世代｜时间扰动规则】" not in system_prompt
    assert context["generation"]["id"] == "parent_generation"
    assert "摇滚乐" in context["generation"]["era_background"]
    snape = next(
        item for item in context["generation"]["cast_index"] if item["npc_id"] == "severus_snape"
    )
    assert "教授" in snape["must_not"][0]
    assert context["current_courses"]["active_courses"] == ["charms"]
    assert context["story_milestones"]["sorting_completed"] is False


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
    assert "location_name" in system_prompt
    assert 'location_id="ollivanders"' in system_prompt
    assert 'location_name="奥利凡德魔杖店"' in system_prompt
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
    assert "player_action.selected_choice" in system_prompt
    assert "不要把一个 choice_id 推测成另一个选项" in system_prompt
    assert "顶部界面已经单独显示当前日期和地点" in system_prompt
    assert "不要每轮使用" in system_prompt
    assert "narrative 必须是本回合完整、连贯、可读的剧情正文" in system_prompt
    assert "不要机械套用固定的开场" in system_prompt
    assert "重要事件不能为了节省字数被过度压缩" in system_prompt
    assert "recent_turns.state_changes 是程序已经实际应用的历史状态变化" in system_prompt
    assert "不能机械复制旧理由" in system_prompt


def test_choice_id_is_resolved_to_the_previous_turn_choice() -> None:
    payload = ActionRequest(
        client_action_id="action-1",
        expected_state_version=2,
        kind="choice",
        choice_id="choice_2",
    )
    latest = SimpleNamespace(
        llm_response={
            "choices": [
                {
                    "id": "choice_1",
                    "label": "跑去山谷找布丽安娜",
                    "kind": "action",
                    "risk": "low",
                },
                {
                    "id": "choice_2",
                    "label": "拆开信封认真读一遍录取说明",
                    "kind": "action",
                    "risk": "medium",
                },
                {
                    "id": "choice_other",
                    "label": "其他",
                    "kind": "free_text",
                    "risk": "low",
                },
            ]
        }
    )

    selected = _resolve_selected_choice(payload, latest)
    assert selected is not None
    assert selected["id"] == "choice_2"
    assert selected["label"] == "拆开信封认真读一遍录取说明"
    assert _action_text(payload, selected) == "choice_2 拆开信封认真读一遍录取说明"
    assert _build_action(payload, selected)["instruction"] == (
        "玩家明确选择了：拆开信封认真读一遍录取说明"
    )


def test_invalid_choice_id_is_rejected_before_model_generation() -> None:
    payload = ActionRequest(
        client_action_id="action-2",
        expected_state_version=2,
        kind="choice",
        choice_id="choice_old",
    )
    latest = SimpleNamespace(
        llm_response={
            "choices": [
                {
                    "id": "choice_1",
                    "label": "观察周围",
                    "kind": "action",
                    "risk": "low",
                },
            ]
        }
    )

    with pytest.raises(HTTPException) as error:
        _resolve_selected_choice(payload, latest)
    assert error.value.status_code == 409


def test_start_story_and_free_text_keep_their_special_action_semantics() -> None:
    start_payload = ActionRequest(
        client_action_id="action-3",
        expected_state_version=0,
        kind="choice",
        choice_id="start_story",
    )
    start_choice = _resolve_selected_choice(start_payload, None)
    assert start_choice is not None
    assert start_choice["label"] == "踏入魔法世界"
    with pytest.raises(HTTPException) as start_error:
        _resolve_selected_choice(start_payload, SimpleNamespace(llm_response={}))
    assert start_error.value.status_code == 409

    free_text_payload = ActionRequest(
        client_action_id="action-4",
        expected_state_version=2,
        kind="free_text",
        choice_id="choice_other",
        free_text="去找父母",
    )
    assert _resolve_selected_choice(free_text_payload, None) is None
    assert _action_text(free_text_payload) == "choice_other 去找父母"


def test_recent_turn_context_only_repeats_scene_metadata_when_it_changes() -> None:
    def turn(
        sequence: int,
        current_date: str,
        location_id: str,
        location_name: str,
        state_changes: dict[str, Any] | None = None,
    ) -> Any:
        return SimpleNamespace(
            sequence=sequence,
            action={"kind": "choice", "choice_id": f"choice_{sequence}"},
            narrative=f"第 {sequence} 轮正文",
            llm_response={
                "turn": {
                    "title": f"节点 {sequence}",
                    "scene_type": "dialogue",
                    "current_date": current_date,
                    "location_id": location_id,
                    "location_name": location_name,
                }
            },
            memory_update={},
            authoritative_changes={"visible": state_changes or {}},
        )

    contexts = _recent_turns_to_context(
        [
            turn(
                1,
                "1991-07-01",
                "home",
                "维洛拉家族古堡",
                {
                    "relationship_deltas": [
                        {
                            "npc_id": "ivy_moore",
                            "affinity_delta": -2,
                            "trust_delta": -1,
                            "reason": "连续忽视她的提醒",
                            "evidence": "本轮对话中再次打断了她",
                        }
                    ]
                },
            ),
            turn(2, "1991-07-01", "home", "维洛拉家族古堡"),
            turn(3, "1991-07-01", "dragon_valley", "龙谷"),
        ]
    )

    assert contexts[0]["scene_date"] == "1991-07-01"
    assert contexts[0]["scene_location_id"] == "home"
    assert contexts[0]["state_changes"]["relationship_deltas"][0]["reason"] == (
        "连续忽视她的提醒"
    )
    assert "scene_date" not in contexts[1]
    assert "scene_location_id" not in contexts[1]
    assert contexts[2]["scene_location_id"] == "dragon_valley"
    assert contexts[2]["scene_location_name"] == "龙谷"


def test_selected_choice_is_present_in_the_model_context() -> None:
    payload = ActionRequest(
        client_action_id="action-5",
        expected_state_version=2,
        kind="choice",
        choice_id="choice_1",
    )
    selected = {
        "id": "choice_1",
        "label": "认真读完录取说明",
        "kind": "action",
        "risk": "low",
        "requires": [],
        "effects_hint": "",
        "effects": {"gains": [], "losses": [], "note": ""},
    }
    messages = _build_messages(action=_build_action(payload, selected))
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert context["player_action"]["selected_choice"]["label"] == "认真读完录取说明"
    assert context["player_action"]["instruction"] == "玩家明确选择了：认真读完录取说明"
    assert "timeline" not in context
    assert context["player_state"].get("current_context", {}) == {}


def test_custom_origin_uses_reasoned_magic_world_knowledge_rule() -> None:
    messages = _build_messages(
        {
            "family": {
                "bloodline": "火龙化成人",
                "description": "曾在偏远山谷生活。",
            },
            "background": {
                "childhood_experiences": ["见过巫师施法"],
            },
            "character_notes": {
                "description": "保留龙形记忆，但以人类身份生活。",
            },
            "current_context": {
                "current_date": "1991-07-01",
                "location_id": "home",
                "activity": "before_first_letter",
            },
        }
    )
    system_prompt = messages[0]["content"]
    context = json.loads(messages[1]["content"].split("\n", 1)[1])

    assert "不是三种预设出身之一" in system_prompt
    assert "收到来信→前往对角巷→霍格沃兹特快→学校" in system_prompt
    assert "不能因为自定义出身而跳转到另一个剧情起点" in system_prompt
    assert "出身背景不得改变玩家选择的四种剧情起点" in system_prompt
    assert "activity=before_first_letter" in system_prompt
    assert "1991-07-01" in system_prompt
    assert "来自巫师家庭，自幼熟悉魔法界的生活、礼仪与常识。" not in system_prompt
    assert "家庭同时连接巫师社会与麻瓜社会，角色从小接触过两种生活方式。" not in system_prompt
    assert "父母都是麻瓜，角色在收到霍格沃兹来信前一直生活在麻瓜社会。" not in system_prompt
    assert context["player_state"]["family"]["bloodline"] == "火龙化成人"
    assert context["player_state"]["current_context"]["activity"] == "before_first_letter"


@pytest.mark.parametrize(
    ("origin_id", "base_prompt", "pre_enrollment_prompt"),
    [
        (
            "pure_blood",
            "来自巫师家庭，自幼熟悉魔法界的生活、礼仪与常识。",
            "已经熟知魔法界与魔法，会期待霍格沃兹的来信",
        ),
        (
            "half_blood",
            "家庭同时连接巫师社会与麻瓜社会，角色从小接触过两种生活方式。",
            "对魔法界与魔法有基础的认知，会期待霍格沃兹的来信",
        ),
        (
            "muggle_born",
            "父母都是麻瓜，角色在收到霍格沃兹来信前一直生活在麻瓜社会。",
            "对魔法界与魔法毫无认知，不会期待霍格沃兹的来信",
        ),
    ],
)
def test_preset_origin_prompt_contains_persistent_and_pre_enrollment_rules(
    origin_id: str,
    base_prompt: str,
    pre_enrollment_prompt: str,
) -> None:
    system_prompt = _build_messages(
        {
            "family": {
                "origin_id": origin_id,
                "bloodline": origin_id,
            },
            "school": {
                "grade": "not_enrolled",
                "enrollment_started": False,
                "sorting_completed": False,
            },
        }
    )[0]["content"]

    assert base_prompt in system_prompt
    assert pre_enrollment_prompt in system_prompt
    assert "默认叙事依据，不是强制剧情脚本" in system_prompt


@pytest.mark.parametrize(
    ("origin_id", "base_prompt", "pre_enrollment_prompt"),
    [
        (
            "pure_blood",
            "来自巫师家庭，自幼熟悉魔法界的生活、礼仪与常识。",
            "已经熟知魔法界与魔法，会期待霍格沃兹的来信",
        ),
        (
            "half_blood",
            "家庭同时连接巫师社会与麻瓜社会，角色从小接触过两种生活方式。",
            "对魔法界与魔法有基础的认知，会期待霍格沃兹的来信",
        ),
        (
            "muggle_born",
            "父母都是麻瓜，角色在收到霍格沃兹来信前一直生活在麻瓜社会。",
            "对魔法界与魔法毫无认知，不会期待霍格沃兹的来信",
        ),
    ],
)
def test_preset_origin_pre_enrollment_rules_are_removed_after_sorting(
    origin_id: str,
    base_prompt: str,
    pre_enrollment_prompt: str,
) -> None:
    system_prompt = _build_messages(
        {
            "family": {
                "origin_id": origin_id,
                "bloodline": origin_id,
            },
            "school": {
                "grade": "year_1",
                "enrollment_started": True,
                "sorting_completed": True,
            },
        }
    )[0]["content"]

    assert base_prompt in system_prompt
    assert pre_enrollment_prompt not in system_prompt
    assert "【分院前出身背景｜默认流程】" not in system_prompt


def test_custom_origin_pre_enrollment_rules_are_removed_after_sorting() -> None:
    system_prompt = _build_messages(
        {
            "family": {
                "origin_id": "custom",
                "bloodline": "火龙化成人",
            },
            "school": {
                "grade": "year_1",
                "enrollment_started": True,
                "sorting_completed": True,
            },
        }
    )[0]["content"]

    assert "【分院前自定义出身推理｜默认流程】" not in system_prompt
    assert "收信→前往对角巷→霍格沃兹特快→学校" not in system_prompt
    assert "【出身基础介绍｜持续有效】" not in system_prompt


@pytest.mark.parametrize(
    ("wand_obtained", "sorting_completed"),
    [(True, False), (False, True), (True, True)],
)
def test_milestone_rules_are_removed_independently(
    wand_obtained: bool,
    sorting_completed: bool,
) -> None:
    system_prompt = _build_messages(
        {
            "wand": {
                "description": "冬青木，独角兽毛",
                "obtained": wand_obtained,
                "status": "obtained" if wand_obtained else "not_obtained",
            },
                "story_milestones": {
                    "wand_obtained": wand_obtained,
                    "sorting_completed": sorting_completed,
                },
                "family": {
                    "origin_id": "half_blood",
                    "bloodline": "混血家庭",
                },
                "school": {
                "grade": "not_enrolled",
                "enrollment_started": False,
                "sorting_completed": sorting_completed,
            },
        }
    )[0]["content"]

    wand_rule = "player_state.story_milestones.wand_obtained 当前为 false"
    sorting_rule = "player_state.story_milestones.sorting_completed 当前为 false"
    assert (wand_rule in system_prompt) is (not wand_obtained)
    assert (sorting_rule in system_prompt) is (not sorting_completed)
    assert "家庭同时连接巫师社会与麻瓜社会，角色从小接触过两种生活方式。" in system_prompt


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
    assert "calendar_date" not in generation["timeline_phase"]
    assert "calendar_year" not in generation["timeline_phase"]
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


def test_refresh_npc_ages_freezes_deceased_characters() -> None:
    alive = SimpleNamespace(
        npc_id="albus_dumbledore",
        state={"age": 18, "age_reference_date": "1899-08-31"},
    )
    deceased = SimpleNamespace(
        npc_id="ariana_dumbledore",
        state={
            "age": 14,
            "age_reference_date": "1899-08-31",
            "life_status": "deceased",
        },
    )

    ages = _refresh_npc_ages([alive, deceased], date(1905, 1, 1))

    assert ages["albus_dumbledore"] == 24
    assert alive.state["age"] == 24
    assert ages["ariana_dumbledore"] == 14
    assert deceased.state["age"] == 14
    assert deceased.state["age_reference_date"] == "1899-08-31"


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
