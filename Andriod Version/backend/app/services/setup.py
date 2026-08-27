from __future__ import annotations

import re
from copy import deepcopy
from datetime import date
from hashlib import sha1
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.content.modern_cast import MODERN_CAST
from backend.app.content.setup import STARTING_POINT_IDS, get_setup_step
from backend.app.content.eras import ERA_BY_ID, get_era
from backend.app.content.origins import normalize_origin_id
from backend.app.models import (
    GameSession,
    NPCState,
    PlayerState,
    Relationship,
)
from backend.app.schemas.game import SetupAnswer, SetupNavigate, SetupOption, SetupView


SETUP_FINAL_STEP = 18
BIRTHDAY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def get_setup_view(game_session: GameSession, player_state: PlayerState) -> SetupView:
    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    current_step = (
        SETUP_FINAL_STEP
        if setup.get("completed")
        else min(int(setup.get("current_step", 1)), SETUP_FINAL_STEP)
    )
    current = get_setup_step(current_step)
    if game_session.era_id == "modern":
        current = _modern_setup_step(current)
    return SetupView(
        current_step=current_step,
        completed=bool(setup.get("completed", False)),
        current=current,
        answers=setup.get("answers", {}),
        era_id=game_session.era_id,
        attribute_initialization=state.get("attribute_initialization", {}),
    )


def save_setup_answer(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: SetupAnswer,
) -> SetupView:
    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    if payload.step != setup.get("current_step", 1):
        raise ValueError("只能提交当前角色创建步骤")
    if payload.step == 1:
        selected_era = str(payload.answer)
        era = ERA_BY_ID.get(selected_era)
        if era is None or not era["available"]:
            raise ValueError("当前版本尚未开放所选世代")
        game_session.era_id = selected_era
    if payload.step == 4:
        birthday = str(payload.answer).strip()
        if BIRTHDAY_PATTERN.fullmatch(birthday) is None:
            raise ValueError("请选择有效的生日日期")
        try:
            date.fromisoformat(birthday)
        except ValueError as exc:
            raise ValueError("请选择有效的生日日期") from exc
    if payload.step == 15 and str(payload.answer) not in {
        "gryffindor",
        "hufflepuff",
        "ravenclaw",
        "slytherin",
    }:
        raise ValueError("学院只能从四个学院中选择")
    if payload.step == 14:
        starting_point = _starting_point_id(payload.answer)
        if starting_point not in STARTING_POINT_IDS:
            raise ValueError("剧情起点只能从当前提供的预设节点中选择")
        if game_session.era_id == "modern" and starting_point != "platform_nine_three_quarters":
            raise ValueError("现代线第一版固定从2020年9月1日的九又四分之三站台开始")

    answers = setup.setdefault("answers", {})
    answers[str(payload.step)] = payload.answer
    if payload.step < SETUP_FINAL_STEP:
        setup["current_step"] = payload.step + 1
    player_state.state = state
    db.commit()
    db.refresh(player_state)
    return get_setup_view(game_session, player_state)


def navigate_setup_step(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: SetupNavigate,
) -> SetupView:
    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    if setup.get("completed"):
        raise ValueError("角色创建已经确认，不能返回修改")
    current_step = int(setup.get("current_step", 1))
    answers = setup.setdefault("answers", {})
    if payload.step >= current_step:
        raise ValueError("只能返回已经完成的角色创建步骤")
    if str(payload.step) not in answers:
        raise ValueError("该角色创建步骤尚未完成，不能返回")
    setup["current_step"] = payload.step
    player_state.state = state
    db.commit()
    db.refresh(player_state)
    return get_setup_view(game_session, player_state)


def confirm_setup(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
) -> SetupView:
    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    answers: dict[str, Any] = setup.setdefault("answers", {})
    initialization = state.get("attribute_initialization", {})
    if setup.get("completed") and initialization.get("status") == "ready":
        return get_setup_view(game_session, player_state)
    missing = [
        str(step)
        for step in range(1, SETUP_FINAL_STEP)
        if str(step) not in answers
    ]
    if missing:
        raise ValueError(f"角色创建尚未完成，缺少步骤：{', '.join(missing)}")
    setup["completed"] = True
    setup["current_step"] = SETUP_FINAL_STEP
    _materialize_player_state(state, answers, game_session.era_id)
    game_session.status = "initializing"
    player_state.state = state
    _seed_npcs_and_relationships(db, game_session.id, game_session.era_id)
    db.flush()
    seed_initial_friends(db, game_session.id, answers.get("13"), game_session.era_id)
    db.commit()
    db.refresh(player_state)
    db.refresh(game_session)
    return get_setup_view(game_session, player_state)


def _materialize_player_state(
    state: dict[str, Any],
    answers: dict[str, Any],
    era_id: str,
) -> None:
    birthday = _normalize_answer(answers.get("4", "1980-09-01"))
    starting_point = _starting_point_id(answers.get("14"))
    is_modern = era_id == "modern"
    if is_modern:
        starting_point = "platform_nine_three_quarters"
    era = get_era(era_id)
    era_start_year = int(str(era["years"]).split("–", 1)[0].replace("+", ""))
    starts_in_september = starting_point in {
        "platform_nine_three_quarters",
        "sorting_ceremony",
    }
    starting_date = date(
        era_start_year,
        9 if starts_in_september else 7,
        1,
    )
    state["identity"] = {
        "name": _normalize_answer(answers.get("2", "未命名巫师")),
        "gender": _normalize_answer(answers.get("3", "未设定")),
        "birthday": birthday,
        "age": _age_on_date(birthday, starting_date),
    }
    appearance = answers.get("5", {})
    state["appearance"] = (
        appearance if isinstance(appearance, dict) else {"description": appearance}
    )
    family = answers.get("6", "未设定")
    family_text = _normalize_answer(family)
    state["family"] = {
        "origin_id": normalize_origin_id(family),
        "bloodline": family_text,
        "description": "你的家族背景将在故事中逐渐展开。",
    }
    childhood = answers.get("7", "")
    state["background"] = {
        "childhood_experiences": childhood
        if isinstance(childhood, list)
        else [str(childhood)],
    }
    personality_values = _split_multi_answer(answers.get("8", "未设定"))
    state["personality"] = {
        "traits": personality_values,
        "primary": personality_values[0] if personality_values else "未设定",
    }
    values = answers.get("9", "")
    state["values"] = {"description": values}
    wand_obtained = starting_point in {
        "platform_nine_three_quarters",
        "sorting_ceremony",
    }
    state["wand"] = {
        "description": answers.get("10"),
        "obtained": wand_obtained,
        "status": "obtained" if wand_obtained else "not_obtained",
    }
    state["story_milestones"] = {
        "wand_obtained": wand_obtained,
        "sorting_completed": False,
    }
    talent_values = _split_multi_answer(answers.get("11", "魔法基础"))
    state["magic_talents"] = [
        {
            "id": _stable_content_id(value),
            "name": value,
            "description": "",
        }
        for value in talent_values
    ]
    state["skills"] = {
        _stable_content_id(value): {
            "name": value,
            "level": 1,
            "experience": 0,
            "source": "initial_magic_talent",
        }
        for value in talent_values
    }
    state["pet"] = {"description": answers.get("12")}
    state["patronus"] = {
        "form": _normalize_answer(answers.get("16", "未设定")),
        "status": "潜在守护神形态",
        "summoning_requirement": "仅在技能中已掌握【呼神护卫】后才可召唤",
    }
    state["character_notes"] = {
        "description": _normalize_answer(answers.get("17", "")).strip(),
    }
    state["current_context"] = {
        "datetime": (
            f"{era_start_year:04d}-09-01T17:30:00+00:00"
            if starting_point == "sorting_ceremony"
            else f"{era_start_year:04d}-09-01T10:30:00+00:00"
            if starting_point == "platform_nine_three_quarters"
            else f"{era_start_year:04d}-07-01T09:00:00+00:00"
        ),
        "current_date": (
            f"{era_start_year:04d}-09-01"
            if starts_in_september
            else f"{era_start_year:04d}-07-01"
        ),
        "period": "evening" if starting_point == "sorting_ceremony" else "morning",
        "location_id": {
            "before_first_letter": "home",
            "diagon_alley": "diagon_alley",
            "platform_nine_three_quarters": "platform_nine_three_quarters",
            "sorting_ceremony": "hogwarts_great_hall",
        }.get(starting_point, "home"),
        "activity": starting_point,
    }
    school = state.setdefault("school", {})
    school["grade"] = "not_enrolled"
    school["enrollment_started"] = False
    school["sorting_completed"] = False
    state["school"]["school_year"] = f"{era_start_year}-{era_start_year + 1}"
    school["grade_started_year"] = None
    school["last_grade_promotion_key"] = None
    school["last_course_progression_year"] = None
    school["term"] = "autumn" if starts_in_september else "summer"
    school["newt_courses"] = []
    school["course_selection"] = None
    school["course_history"] = []
    school["active_courses"] = []
    school["elective_courses"] = []
    school["owl_results"] = {}
    school["newt_results"] = {}
    state["school"]["house"] = _normalize_answer(answers.get("15", "未分院"))
    if is_modern:
        _materialize_modern_state(state, answers)


def _materialize_modern_state(
    state: dict[str, Any],
    answers: dict[str, Any],
) -> None:
    """将通用角色答案收束到现代线固定的四年级开局。"""
    state["identity"]["age_band"] = (
        "minor" if int(state["identity"].get("age", 0)) < 18 else "adult"
    )
    state["story_milestones"] = {
        **state.get("story_milestones", {}),
        "wand_obtained": True,
        "sorting_completed": True,
    }
    state["current_context"] = {
        "datetime": "2020-09-01T10:30:00+00:00",
        "current_date": "2020-09-01",
        "period": "morning",
        "location_id": "platform_nine_three_quarters",
        "activity": "platform_nine_three_quarters",
    }
    school = state.setdefault("school", {})
    school.update(
        {
            "grade": "year_4",
            "enrollment_started": True,
            "sorting_completed": True,
            "school_year": "2020-2021",
            "grade_started_year": 2020,
            "last_grade_promotion_key": None,
            "last_course_progression_year": None,
            "term": "autumn",
            "active_courses": [],
            "elective_courses": [],
            "course_selection": None,
            "course_history": [],
            "owl_results": {},
            "newt_results": {},
        }
    )
    state["worldline"] = {
        "mode": "temporal_disturbance",
        "offset_rate": 0.0,
        "delta": 0.0,
        "last_delta": 0.0,
        "reason": "现代线刚从2020年的站台开始",
        "temporal_disturbance": 0.0,
        "temporal_stability": 100.0,
        "last_source": None,
        "triggered_thresholds": [],
        "current_timeline_id": "original_2020",
        "memory_status": "original",
        "affected_nodes": [],
    }
    state["modern_arc"] = {
        "phase_id": "modern_school_arrival",
        "temporal_clue_level": 0,
        "albus_trust": 0,
        "scorpius_trust": 0,
        "rose_trust": 0,
        "delphi_suspicion": 0,
        "time_turner_status": "unknown",
        "cedric_anchor_status": "untouched",
    }


def _modern_setup_step(step: Any) -> Any:
    if step.step == 13:
        modern_options = [
                SetupOption(
                    id=item["npc_id"],
                    label=item["name"],
                    description=item["role"],
                    value=item["name"],
                    appendable=True,
                )
            for item in MODERN_CAST
            if "学生" in item["role"]
        ]
        return step.model_copy(
            update={
                "description": "可选择现代线同期生作为初始好友，也可以输入自定义姓名。",
                "options": modern_options,
            }
        )
    if step.step == 14:
        return step.model_copy(
            update={
                "title": "固定剧情起点",
                "description": "现代线第一版统一从2020年9月1日、九又四分之三站台驶向霍格沃茨的列车前开始。",
                "options": [
                    SetupOption(
                        id="modern_platform_arrival",
                        label="2020年9月1日·九又四分之三站台",
                        description="蒸汽、行李车和即将出发的列车构成现代线的共同开场。",
                        value="platform_nine_three_quarters",
                    )
                ],
            }
        )
    return step


def _normalize_answer(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("label") or value)
    return str(value)


def _age_on_date(birthday: str, current_date: date) -> int:
    birth_date = date.fromisoformat(birthday)
    age = current_date.year - birth_date.year
    if (current_date.month, current_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(0, age)


def _split_multi_answer(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = str(value or "").replace("，", ",").split(",")
    result: list[str] = []
    for raw_value in raw_values:
        normalized = str(raw_value).strip()
        if normalized and normalized not in result:
            result.append(normalized)
    return result or ["未设定"]


def _stable_content_id(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "_")
        .replace("·", "_")
        .replace("：", "_")
        .replace(":", "_")
    )


def _starting_point_id(value: Any) -> str:
    normalized = _normalize_answer(value)
    mapping = {
        "owl_letter_arrival": "before_first_letter",
        "before_letter": "before_first_letter",
        "收到霍格沃茨来信之前": "before_first_letter",
        "第一次踏入对角巷": "diagon_alley",
        "九又四分之三站台": "platform_nine_three_quarters",
        "分院时": "sorting_ceremony",
    }
    return mapping.get(normalized, normalized)


def _seed_npcs_and_relationships(
    db: Session,
    session_id: str,
    era_id: str = "second_generation",
) -> None:
    existing = db.scalar(
        select(NPCState).where(NPCState.session_id == session_id).limit(1)
    )
    if existing:
        return
    npc_definitions = [
        (
            "harry_potter",
            "哈利·波特",
            "学生",
            "勇敢、忠诚、容易把危险扛到自己身上",
        ),
        (
            "ron_weasley",
            "罗恩·韦斯莱",
            "学生",
            "热情、幽默、重视朋友，也有自己的不安全感",
        ),
        (
            "hermione_granger",
            "赫敏·格兰杰",
            "学生",
            "聪慧、认真、重视规则和真正的正义",
        ),
        (
            "draco_malfoy",
            "德拉科·马尔福",
            "学生",
            "骄傲、敏锐、被家族期待束缚",
        ),
        (
            "ginny_weasley",
            "金妮·韦斯莱",
            "学生",
            "机敏、坚韧、逐渐找到自己的声音",
        ),
        (
            "neville_longbottom",
            "纳威·隆巴顿",
            "学生",
            "善良、谨慎，在压力中慢慢成长",
        ),
        (
            "luna_lovegood",
            "卢娜·洛夫古德",
            "学生",
            "想象力独特、坦率，不轻易被旁人的判断动摇",
        ),
        (
            "fred_weasley",
            "弗雷德·韦斯莱",
            "学生",
            "大胆、幽默，热衷把规则变成恶作剧素材",
        ),
        (
            "george_weasley",
            "乔治·韦斯莱",
            "学生",
            "观察敏锐、幽默，和弗雷德有极佳默契",
        ),
        (
            "cedric_diggory",
            "塞德里克·迪戈里",
            "学生",
            "正直谦逊，重视公平竞争和学院荣誉",
        ),
        (
            "albus_dumbledore",
            "阿不思·邓布利多",
            "教授",
            "睿智、克制，习惯把更大的秘密藏在沉默之后",
        ),
        (
            "minerva_mcgonagall",
            "米勒娃·麦格",
            "教授",
            "严肃、公正，愿意保护认真学习的学生",
        ),
        (
            "severus_snape",
            "西弗勒斯·斯内普",
            "教授",
            "冷峻、苛刻，情绪和记忆都藏得很深",
        ),
    ]
    student_ages = {
        "ginny_weasley": 10,
        "luna_lovegood": 10,
        "fred_weasley": 13,
        "george_weasley": 13,
        "cedric_diggory": 14,
    }
    if era_id == "modern":
        npc_definitions = [
            (
                item["npc_id"],
                item["name"],
                item["role"],
                item["personality"],
            )
            for item in MODERN_CAST
        ]
    modern_cast_by_id = {
        item["npc_id"]: item for item in MODERN_CAST
    } if era_id == "modern" else {}
    modern_ages = {
        "albus_potter": 14,
        "scorpius_malfoy": 14,
        "rose_granger_weasley": 14,
        "polly_chapman": 14,
        "karl_jenkins": 14,
        "craig_bowker_junior": 14,
        "delphini": 24,
        "harry_potter": 40,
        "draco_malfoy": 40,
        "hermione_granger": 41,
        "minerva_mcgonagall": 80,
        "amos_diggory": 60,
        "cedric_diggory": 19,
    }
    for npc_id, name, role, personality in npc_definitions:
        modern_info = modern_cast_by_id.get(npc_id, {})
        is_student = role == "学生" or (
            era_id == "modern" and "学生" in role
        )
        age_reference_date = "2020-09-01" if era_id == "modern" else "1991-07-01"
        db.add(
            NPCState(
                session_id=session_id,
                npc_id=npc_id,
                is_original_character=True,
                state={
                    "name": name,
                    "role": role,
                    "personality": personality,
                    "age": (
                        modern_ages.get(npc_id, 14)
                        if era_id == "modern"
                        else student_ages.get(npc_id, 11) if is_student else 50
                    ),
                    "age_band": "minor" if (
                        modern_ages.get(npc_id, 14) if era_id == "modern"
                        else student_ages.get(npc_id, 11) if is_student else 50
                    ) < 18 else "adult",
                    "location_id": (
                        "platform_nine_three_quarters"
                        if era_id == "modern" and is_student
                        else "hogwarts" if role in {"教授", "校长"} else "unknown"
                    ),
                    "schedule": [],
                    "goals": list(modern_info.get("goals", [])),
                    "fears": list(modern_info.get("fears", [])),
                    "secrets": [],
                    "emotion": "neutral",
                    "origin": "preset",
                    "age_reference_date": age_reference_date,
                },
            )
        )
        db.add(
            Relationship(
                session_id=session_id,
                source_id="player",
                target_id=npc_id,
                state={
                    "affinity": 0,
                    "trust": 0,
                    "stage": "stranger",
                    "bond_type": "potential",
                    "romance_state": "unavailable",
                    "romance_stage": "none",
                    "known_secrets": [],
                    "recent_interaction_ids": [],
                    "pending_unlocks": [],
                    "origin": "preset",
                },
            )
        )


def seed_initial_friends(
    db: Session,
    session_id: str,
    raw_answer: Any,
    era_id: str = "second_generation",
) -> None:
    selected_names = [
        value.strip()
        for value in str(raw_answer or "").replace("，", ",").split(",")
        if value.strip() and value.strip() != "没有预设好友"
    ]
    if not selected_names:
        return
    existing_npcs = {
        str(item.state.get("name")): item
        for item in db.scalars(
            select(NPCState).where(NPCState.session_id == session_id)
        )
    }
    npc_aliases = {
        "哈利·波特": "harry_potter",
        "罗恩·韦斯莱": "ron_weasley",
        "赫敏·格兰杰": "hermione_granger",
        "德拉科·马尔福": "draco_malfoy",
        "纳威·隆巴顿": "neville_longbottom",
        "金妮·韦斯莱": "ginny_weasley",
        "卢娜·洛夫古德": "luna_lovegood",
        "弗雷德·韦斯莱": "fred_weasley",
        "乔治·韦斯莱": "george_weasley",
        "塞德里克·迪戈里": "cedric_diggory",
        "阿不思·西弗勒斯·波特": "albus_potter",
        "斯科皮·马尔福": "scorpius_malfoy",
        "罗丝·格兰杰-韦斯莱": "rose_granger_weasley",
        "波莉·查普曼": "polly_chapman",
        "卡尔·詹金斯": "karl_jenkins",
        "克雷格·鲍克二世": "craig_bowker_junior",
    }
    existing_relationships = {
        item.target_id: item
        for item in db.scalars(
            select(Relationship).where(
                Relationship.session_id == session_id,
                Relationship.source_id == "player",
            )
        )
    }
    for name in selected_names:
        npc = existing_npcs.get(name)
        if npc is None and name in npc_aliases:
            npc = next(
                (
                    item
                    for item in existing_npcs.values()
                    if item.npc_id == npc_aliases[name]
                ),
                None,
            )
        if npc is None:
            digest = sha1(
                f"{session_id}:{name}".encode("utf-8"),
                usedforsecurity=False,
            ).hexdigest()[:12]
            npc_id = f"custom_friend_{digest}"
            npc = NPCState(
                session_id=session_id,
                npc_id=npc_id,
                is_original_character=False,
                state={
                    "name": name,
                    "role": "学生",
                    "personality": "由玩家在创建角色时设定的童年好友",
                    "age": 14 if era_id == "modern" else 11,
                    "age_band": "minor",
                    "age_reference_date": (
                        "2020-09-01" if era_id == "modern" else "1991-07-01"
                    ),
                    "location_id": "unknown",
                    "schedule": [],
                    "goals": [],
                    "fears": [],
                    "secrets": [],
                    "emotion": "friendly",
                    "origin": "player_created",
                    "age_reference_date": "1991-07-01",
                },
            )
            db.add(npc)
            db.flush()
            existing_npcs[name] = npc
        relationship = existing_relationships.get(npc.npc_id)
        if relationship is None:
            relationship = Relationship(
                session_id=session_id,
                source_id="player",
                target_id=npc.npc_id,
                state={},
            )
            db.add(relationship)
            existing_relationships[npc.npc_id] = relationship
        relationship.state = {
            **relationship.state,
            "affinity": max(20, int(relationship.state.get("affinity", 0))),
            "trust": max(10, int(relationship.state.get("trust", 0))),
            "stage": "friend",
            "bond_type": "friendship",
            "romance_state": relationship.state.get("romance_state", "unavailable"),
            "romance_stage": relationship.state.get("romance_stage", "none"),
            "known_secrets": relationship.state.get("known_secrets", []),
            "recent_interaction_ids": relationship.state.get(
                "recent_interaction_ids", []
            ),
            "pending_unlocks": relationship.state.get("pending_unlocks", []),
            "origin": relationship.state.get("origin", "player_created"),
        }
