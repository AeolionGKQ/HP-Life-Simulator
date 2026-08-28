from __future__ import annotations

import re
from copy import deepcopy
from datetime import date
from hashlib import sha1
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.content.bonds import current_age_for_npc
from backend.app.content.courses import (
    COURSE_CATALOG,
    FIRST_YEAR_REQUIRED_COURSE_IDS,
    SKILL_LEVEL_MIN,
    clamp_skill_level,
)
from backend.app.content.dumbledore_cast import (
    DUMBLEDORE_CAST,
    dumbledore_initial_friend_options,
)
from backend.app.content.modern_cast import MODERN_CAST
from backend.app.content.parent_cast import (
    PARENT_CAST,
    parent_initial_friend_options,
)
from backend.app.content.setup import (
    DUMBLEDORE_ENDGAME_STARTING_POINT_IDS,
    STARTING_POINT_IDS,
    get_setup_step,
)
from backend.app.content.eras import ERA_BY_ID, get_era
from backend.app.content.origins import normalize_origin_id
from backend.app.models import (
    GameSession,
    LongTermMemory,
    NPCState,
    PlayerState,
    Relationship,
)
from backend.app.schemas.game import SetupAnswer, SetupNavigate, SetupOption, SetupView


SETUP_FINAL_STEP = 18
BIRTHDAY_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

# 直入终局起点的角色已修完七年课程，课程技能从这个稳定水平起步。
GRADUATE_COURSE_SKILL_LEVEL = 5
PATRONUS_SKILL_ID = "expecto_patronum"

# 【直入终局】两个起点的权威时间与既定前史。日期落在 1899-08-31 而不是九月，
# 是为了让 ariana_fall 节点在第一回合仍是 active：坠落就发生在此刻，
# 下一回合跨进九月才切到 greater_good_aftermath 弧。
DUMBLEDORE_ENDGAME_STARTS: dict[str, dict[str, Any]] = {
    "godrics_hollow_1899_summer": {
        "current_date": "1899-07-10",
        "datetime": "1899-07-10T15:00:00+00:00",
        "period": "afternoon",
        "ariana_alive": True,
        "grindelwald_present": True,
        "worldline_reason": "直入终局：1899年夏，悲剧尚未发生",
        "premise": (
            "你与阿不思·邓布利多在霍格沃茨同窗七年，是彼此最信任的挚友。"
            "1899年毕业后，肯德拉·邓布利多在照顾阿利安娜时死于一次失控的魔法爆发，"
            "你陪阿不思一同回到戈德里克山谷。刚到山谷不久，"
            "被德姆斯特朗开除的盖勒特·格林德沃投奔他的姑婆巴希达·巴沙特，"
            "三个人的夏天从此开始。阿利安娜还活着，混战还没有发生。"
        ),
    },
    "godrics_hollow_1899_fall": {
        "current_date": "1899-08-31",
        "datetime": "1899-08-31T20:30:00+00:00",
        "period": "evening",
        "ariana_alive": False,
        "grindelwald_present": False,
        "worldline_reason": "直入终局：1899年夏，阿利安娜已经坠落",
        "premise": (
            "你与阿不思·邓布利多在霍格沃茨同窗七年，是彼此最信任的挚友。"
            "1899年毕业后你陪他回到戈德里克山谷，与投奔巴希达·巴沙特的盖勒特·格林德沃"
            "相处了一整个夏天：死亡圣器、更伟大的利益、两人以血立下的誓约，你都在场。"
            "最终你什么都没能改变。阿不福思反对他们带着阿利安娜远行，格林德沃对他施下钻心咒，"
            "阿不思介入，三人混战。就在刚刚，阿利安娜在乱咒中死去——没有人知道那道咒来自谁。"
            "阿不思跪在地上抱着妹妹，格林德沃夺门而逃。"
        ),
    },
}


def get_setup_view(game_session: GameSession, player_state: PlayerState) -> SetupView:
    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    current_step = (
        SETUP_FINAL_STEP
        if setup.get("completed")
        else min(int(setup.get("current_step", 1)), SETUP_FINAL_STEP)
    )
    current = get_setup_step(current_step)
    current = _era_setup_step(current, game_session.era_id)
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
            raise ValueError("现代世代固定从2020年9月1日的九又四分之三站台开始")
        if game_session.era_id == "dumbledore_era" and starting_point not in {
            "godrics_hollow",
            *DUMBLEDORE_ENDGAME_STARTING_POINT_IDS,
        }:
            raise ValueError(
                "邓布利多时代只能选择1892年夏的戈德里克山谷，或【直入终局】中的1899年起点"
            )
        if (
            game_session.era_id != "dumbledore_era"
            and starting_point in DUMBLEDORE_ENDGAME_STARTING_POINT_IDS
        ):
            raise ValueError("直入终局起点只属于邓布利多时代")
        if game_session.era_id == "parent_generation" and starting_point != "platform_nine_three_quarters":
            raise ValueError("亲世代固定从1971年9月1日的九又四分之三站台开始")

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
    endgame_entry = state.get("endgame_entry") or {}
    _seed_npcs_and_relationships(
        db,
        game_session.id,
        game_session.era_id,
        endgame_entry=endgame_entry,
    )
    db.flush()
    seed_initial_friends(db, game_session.id, answers.get("13"), game_session.era_id)
    if endgame_entry:
        _seed_endgame_memories(db, game_session.id, endgame_entry)
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
    elif era_id == "dumbledore_era":
        if starting_point not in DUMBLEDORE_ENDGAME_STARTING_POINT_IDS:
            starting_point = "godrics_hollow"
    elif era_id == "parent_generation":
        starting_point = "platform_nine_three_quarters"
    era = get_era(era_id)
    era_start_year = int(str(era["years"]).split("–", 1)[0].replace("+", ""))
    starts_in_september = starting_point in {
        "platform_nine_three_quarters",
        "sorting_ceremony",
    }
    endgame_start = DUMBLEDORE_ENDGAME_STARTS.get(starting_point)
    starting_date = (
        date.fromisoformat(endgame_start["current_date"])
        if endgame_start
        else date(
            era_start_year,
            9 if starts_in_september else 7,
            1,
        )
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
            "godrics_hollow": "godrics_hollow",
            "godrics_hollow_1899_summer": "godrics_hollow",
            "godrics_hollow_1899_fall": "godrics_hollow",
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
    elif era_id == "dumbledore_era":
        if endgame_start:
            _materialize_dumbledore_endgame_state(state, starting_point, endgame_start)
        else:
            _materialize_dumbledore_state(state)
    elif era_id == "parent_generation":
        _materialize_parent_state(state)


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
    _mark_patronus_learned(state)


def _materialize_dumbledore_state(state: dict[str, Any]) -> None:
    """邓布利多时代固定从1892年夏的戈德里克山谷开始：录取通知书与魔杖等物品已到手，九月才入学。"""
    state["identity"]["age_band"] = (
        "minor" if int(state["identity"].get("age", 0)) < 18 else "adult"
    )
    wand = state.setdefault("wand", {})
    wand["obtained"] = True
    wand["status"] = "obtained"
    state["story_milestones"] = {
        **state.get("story_milestones", {}),
        "wand_obtained": True,
        "sorting_completed": False,
    }
    state["current_context"] = {
        "datetime": "1892-07-01T09:00:00+00:00",
        "current_date": "1892-07-01",
        "period": "morning",
        "location_id": "godrics_hollow",
        "activity": "godrics_hollow",
    }
    school = state.setdefault("school", {})
    school.update(
        {
            "grade": "not_enrolled",
            "enrollment_started": False,
            "sorting_completed": False,
            "school_year": "1892-1893",
            "grade_started_year": None,
            "last_grade_promotion_key": None,
            "last_course_progression_year": None,
            "term": "summer",
            "active_courses": [],
            "elective_courses": [],
            "course_selection": None,
            "course_history": [],
            "owl_results": {},
            "newt_results": {},
        }
    )
    state["worldline"] = {
        "offset_rate": 0.0,
        "last_delta": 0.0,
        "reason": "邓布利多时代刚从1892年夏的戈德里克山谷开始",
        "affected_nodes": [],
    }


def _materialize_dumbledore_endgame_state(
    state: dict[str, Any],
    starting_point: str,
    endgame_start: dict[str, Any],
) -> None:
    """【直入终局】：玩家已完成七年学业并毕业，直接站在1899年夏天的山谷里。"""
    state["identity"]["age_band"] = (
        "minor" if int(state["identity"].get("age", 0)) < 18 else "adult"
    )
    wand = state.setdefault("wand", {})
    wand["obtained"] = True
    wand["status"] = "obtained"
    state["story_milestones"] = {
        **state.get("story_milestones", {}),
        "wand_obtained": True,
        "sorting_completed": True,
    }
    state["current_context"] = {
        "datetime": endgame_start["datetime"],
        "current_date": endgame_start["current_date"],
        "period": endgame_start["period"],
        "location_id": "godrics_hollow",
        "activity": starting_point,
    }
    school = state.setdefault("school", {})
    school.update(
        {
            "grade": "left_school",
            "departure_reason": "graduated_after_newts",
            "enrollment_started": True,
            "sorting_completed": True,
            "school_year": "1898-1899",
            "grade_started_year": 1898,
            "last_grade_promotion_key": "1898-09",
            "last_course_progression_year": 1899,
            "term": "summer",
            "active_courses": [],
            "elective_courses": [],
            "course_selection": None,
            "course_history": [
                {
                    "school_year": "1898-1899",
                    "grade": "year_7",
                    "active_courses": [],
                    "selected_courses": [],
                    "skill_progression": {},
                }
            ],
            "owl_results": {},
            "newt_results": {},
        }
    )
    _seed_graduate_course_skills(state)
    _mark_patronus_learned(state)
    state["worldline"] = {
        "offset_rate": 0.0,
        "last_delta": 0.0,
        "reason": endgame_start["worldline_reason"],
        "affected_nodes": [],
    }
    state["endgame_entry"] = {
        "starting_point": starting_point,
        "current_date": endgame_start["current_date"],
        "premise": endgame_start["premise"],
        "ariana_alive": endgame_start["ariana_alive"],
        "grindelwald_present": endgame_start["grindelwald_present"],
    }


def _seed_graduate_course_skills(state: dict[str, Any]) -> None:
    """毕业生已经修完七年课程，按稳定水平播种课程技能。"""
    skills = state.setdefault("skills", {})
    if not isinstance(skills, dict):
        return
    for course_id in FIRST_YEAR_REQUIRED_COURSE_IDS:
        course = COURSE_CATALOG.get(course_id)
        if not course:
            continue
        skill_id = course["skill_id"]
        existing = skills.get(skill_id)
        level = GRADUATE_COURSE_SKILL_LEVEL
        if isinstance(existing, dict):
            level = max(level, clamp_skill_level(existing.get("level")))
        skills[skill_id] = {
            "id": skill_id,
            "name": course["name"],
            "description": course["description"],
            "level": level,
            "experience": 0,
            "source": "course",
            "course_id": course_id,
            "course_skill": True,
        }


def _mark_patronus_learned(state: dict[str, Any]) -> None:
    """现代线与邓布利多直入终局默认已经掌握呼神护卫。"""
    skills = state.setdefault("skills", {})
    if isinstance(skills, dict):
        skills[PATRONUS_SKILL_ID] = {
            "id": PATRONUS_SKILL_ID,
            "name": "呼神护卫",
            "description": "已经掌握召唤守护神的魔法",
            "level": 1,
            "experience": 0,
            "source": "opening_preset",
            "learned": True,
        }
    patronus = state.setdefault("patronus", {})
    patronus.update(
        {
            "status": "已学会【呼神护卫】",
            "learned": True,
            "summoning_requirement": "已满足：角色可以尝试施放【呼神护卫】召唤守护神",
        }
    )


def _materialize_parent_state(state: dict[str, Any]) -> None:
    """亲世代固定从1971年站台开局，分院完成前保持未入学状态。"""
    state["identity"]["age_band"] = (
        "minor" if int(state["identity"].get("age", 0)) < 18 else "adult"
    )
    state["story_milestones"] = {
        **state.get("story_milestones", {}),
        "wand_obtained": True,
        "sorting_completed": False,
    }
    state["current_context"] = {
        "datetime": "1971-09-01T10:30:00+00:00",
        "current_date": "1971-09-01",
        "period": "morning",
        "location_id": "platform_nine_three_quarters",
        "activity": "platform_nine_three_quarters",
    }
    school = state.setdefault("school", {})
    school.update(
        {
            "grade": "not_enrolled",
            "enrollment_started": False,
            "sorting_completed": False,
            "school_year": "1971-1972",
            "grade_started_year": None,
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
        "offset_rate": 0.0,
        "last_delta": 0.0,
        "reason": "亲世代刚从1971年的站台开始",
        "affected_nodes": [],
    }


def _era_setup_step(step: Any, era_id: str) -> Any:
    if step.step == 4:
        return _birthday_setup_step(step, era_id)
    if era_id == "modern":
        return _modern_setup_step(step)
    if era_id == "dumbledore_era":
        return _historical_setup_step(
            step,
            friend_items=dumbledore_initial_friend_options(),
            friend_description="从山谷邻里与未来同窗中选择一位或多位同行者，也可以输入自定义姓名。阿利安娜仍留在家中，不会与你一同入学；格林德沃尚不在英国，直到1899年夏才会走进山谷。",
            start_id="dumbledore_hollow_arrival",
            start_label="1892年夏·戈德里克山谷",
            start_description="你带着录取通知书、魔杖与宠物回到戈德里克山谷。先认识这座村庄，走近邓布利多一家，决定要以怎样的姿态迎接即将开始的霍格沃茨生活。",
            start_value="godrics_hollow",
            start_help=(
                "你可以从山谷的夏日与年轻的阿不思相识，在霍格沃茨度过七年并亲手塑造身边的关系；"
                "也可以跳过校园岁月，以已经毕业的成年巫师身份，直接介入1899年那个夏天的关键抉择。"
            ),
            start_title="剧情起点",
            start_category="常规开局",
            extra_options=[
                SetupOption(
                    id="dumbledore_endgame_before_fall",
                    label="1899年夏·阿利安娜死亡之前",
                    description=(
                        "你与阿不思并肩走过七年校园时光，如今一同回到戈德里克山谷。格林德沃带着耀眼的理想与危险的魅力来到这里，"
                        "你可以在裂痕扩大之前守住这个家，也可以帮助他们把“更伟大的利益”变成改写世界的道路。"
                    ),
                    value="godrics_hollow_1899_summer",
                    category="直入终局",
                ),
                SetupOption(
                    id="dumbledore_endgame_at_fall",
                    label="1899年夏·阿利安娜死亡之时",
                    description=(
                        "你与阿不思并肩走过那个夏天，却没能阻止命运在眼前崩裂。故事从阿利安娜倒下、格林德沃夺门而逃的瞬间开始，"
                        "你可以陪阿不思追查真相、阻止更大的灾难，也可以转身追随格林德沃驶向欧洲。"
                    ),
                    value="godrics_hollow_1899_fall",
                    category="直入终局",
                ),
            ],
        )
    if era_id == "parent_generation":
        return _historical_setup_step(
            step,
            friend_items=parent_initial_friend_options(),
            friend_description="从列车上与城堡里的年轻巫师中选择同行者，也可以输入自定义姓名。你可以与他们并肩成长、互相影响，在友谊、竞争与立场之间建立自己的关系。",
            start_id="parent_platform_arrival",
            start_label="1971年9月1日·九又四分之三站台",
            start_description="蒸汽从车头升起，唱片声与行李轮声混在一起。登上列车，去认识那些将与你共同长大的年轻人，也决定自己要成为怎样的同窗。",
            start_value="platform_nine_three_quarters",
            start_help="从九又四分之三站台登上开往霍格沃茨的列车，结识未来的朋友与对手。你可以参与他们的青春，也可以走出一条不被任何人预先写好的道路。",
        )
    return step


def _birthday_setup_step(step: Any, era_id: str) -> Any:
    recommended_year = {
        "dumbledore_era": 1881,
        "parent_generation": 1960,
        "second_generation": 1980,
        "modern": 2009,
    }.get(era_id)
    if recommended_year is None:
        return step
    era = get_era(era_id)
    extra = (
        "同一个出生年份也适用于【直入终局】起点：1881年出生的角色在1899年那个夏天正好十八岁、刚刚毕业。"
        if era_id == "dumbledore_era"
        else ""
    )
    return step.model_copy(
        update={
            "description": (
                f"{step.description} 当前世代将在{era['years']}展开；"
                f"若希望开局时刚好十一岁，推荐出生年份为{recommended_year}年。{extra}"
            )
        }
    )


def _historical_setup_step(
    step: Any,
    *,
    friend_items: list[dict[str, Any]],
    friend_description: str,
    start_id: str,
    start_label: str,
    start_description: str,
    start_value: str,
    start_help: str,
    start_title: str = "固定剧情起点",
    start_category: str = "",
    extra_options: list[SetupOption] | None = None,
) -> Any:
    if step.step == 13:
        options = [
            SetupOption(
                id=item["npc_id"],
                label=item["name"],
                description=item["role"],
                value=item["name"],
                appendable=True,
            )
            for item in friend_items
        ]
        return step.model_copy(
            update={
                "description": friend_description,
                "options": options,
            }
        )
    if step.step == 14:
        return step.model_copy(
            update={
                "title": start_title,
                "description": start_help,
                "options": [
                    SetupOption(
                        id=start_id,
                        label=start_label,
                        description=start_description,
                        value=start_value,
                        category=start_category,
                    ),
                    *(extra_options or []),
                ],
            }
        )
    return step


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
                "description": "现代世代从2020年9月1日的九又四分之三站台开始，列车即将驶向霍格沃茨。这是这一世代唯一的剧情起点。",
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
        "戈德里克山谷": "godrics_hollow",
        "1892年夏·戈德里克山谷": "godrics_hollow",
        "1899年夏·阿利安娜死亡之前": "godrics_hollow_1899_summer",
        "1899年夏·阿利安娜死亡之时": "godrics_hollow_1899_fall",
    }
    return mapping.get(normalized, normalized)


def _seed_npcs_and_relationships(
    db: Session,
    session_id: str,
    era_id: str = "second_generation",
    *,
    endgame_entry: dict[str, Any] | None = None,
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
    era_cast = _era_cast_items(era_id)
    if era_cast:
        npc_definitions = [
            (
                item["npc_id"],
                item["name"],
                item["role"],
                item["personality"],
            )
            for item in era_cast
        ]
    era_cast_by_id = {item["npc_id"]: item for item in era_cast}
    for npc_id, name, role, personality in npc_definitions:
        cast_info = era_cast_by_id.get(npc_id, {})
        is_student = _npc_is_student(role, era_id)
        if cast_info.get("initial_age") is not None:
            age = int(cast_info["initial_age"])
        elif era_id == "modern":
            age = int(modern_ages.get(npc_id, 14 if is_student else 50))
        else:
            age = int(student_ages.get(npc_id, 11) if is_student else 50)
        npc_state = {
            "name": name,
            "role": role,
            "personality": personality,
            "age": age,
            "age_band": "minor" if age < 18 else "adult",
            "location_id": str(
                cast_info.get("location_id")
                or (
                    "platform_nine_three_quarters"
                    if era_id in {"modern", "parent_generation"} and is_student
                    else "hogwarts" if role in {"教授", "校长"} else "unknown"
                )
            ),
            "schedule": [],
            "goals": list(cast_info.get("goals", [])),
            "fears": list(cast_info.get("fears", [])),
            "secrets": list(cast_info.get("secrets", [])),
            "emotion": "neutral",
            "origin": "preset",
            "age_reference_date": str(
                cast_info.get("age_reference_date")
                or _era_age_reference_date(era_id)
            ),
            "background": cast_info.get("background", ""),
            "current_life": cast_info.get("current_life", ""),
        }
        relation_state = {
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
        }
        if endgame_entry:
            _apply_endgame_npc_overrides(npc_id, npc_state, relation_state, endgame_entry)
        db.add(
            NPCState(
                session_id=session_id,
                npc_id=npc_id,
                is_original_character=True,
                state=npc_state,
            )
        )
        db.add(
            Relationship(
                session_id=session_id,
                source_id="player",
                target_id=npc_id,
                state=relation_state,
            )
        )


ENDGAME_RELATIONSHIPS: dict[str, dict[str, Any]] = {
    "albus_dumbledore": {
        "affinity": 74,
        "trust": 70,
        "stage": "close_friend",
        "bond_type": "friendship",
    },
    "elphias_doge": {
        "affinity": 46,
        "trust": 40,
        "stage": "friend",
        "bond_type": "friendship",
    },
    "aberforth_dumbledore": {
        "affinity": 24,
        "trust": 18,
        "stage": "acquaintance",
        "bond_type": "acquaintance",
    },
    "bathilda_bagshot": {
        "affinity": 22,
        "trust": 16,
        "stage": "acquaintance",
        "bond_type": "acquaintance",
    },
    "gellert_grindelwald": {
        "affinity": 20,
        "trust": 12,
        "stage": "acquaintance",
        "bond_type": "acquaintance",
    },
    "ariana_dumbledore": {
        "affinity": 26,
        "trust": 20,
        "stage": "acquaintance",
        "bond_type": "acquaintance",
    },
    "armando_dippet": {
        "affinity": 12,
        "trust": 10,
        "stage": "acquaintance",
        "bond_type": "acquaintance",
    },
}


def _apply_endgame_npc_overrides(
    npc_id: str,
    npc_state: dict[str, Any],
    relation_state: dict[str, Any],
    endgame_entry: dict[str, Any],
) -> None:
    """直入终局起点：把1899年夏天的既定处境写进 NPC 与关系种子。"""
    ariana_alive = bool(endgame_entry.get("ariana_alive"))
    grindelwald_present = bool(endgame_entry.get("grindelwald_present"))

    # 播种时就把年龄推到1899年，否则首回合之前面板会显示1892年的岁数。
    try:
        story_date = date.fromisoformat(str(endgame_entry.get("current_date")))
    except ValueError:
        story_date = None
    if story_date is not None:
        current_age = current_age_for_npc(npc_state, story_date)
        if current_age is not None:
            npc_state["age"] = current_age
            npc_state["age_band"] = "minor" if current_age < 18 else "adult"
            npc_state["age_reference_date"] = story_date.isoformat()


    if npc_id == "albus_dumbledore":
        npc_state["role"] = "1899年刚从霍格沃茨毕业的十八岁天才，不是校长"
        npc_state["location_id"] = "godrics_hollow"
        npc_state["current_life"] = (
            "他刚失去母亲，被迫留在山谷照顾妹妹。才华无处可去，怨愤压在礼貌之下；"
            "格林德沃的到来正好接住了他所有不甘。"
            if grindelwald_present
            else "阿利安娜刚刚死在他面前。他抱着妹妹跪在地上，理想、爱情和辩解同时崩塌。"
        )
    elif npc_id == "aberforth_dumbledore":
        npc_state["location_id"] = "godrics_hollow"
        npc_state["current_life"] = (
            "十五岁，仍在霍格沃茨就读，假期回家照顾姐姐。他公开反对哥哥和那个金发客人的远行计划。"
            if ariana_alive
            else "十五岁。他刚刚被钻心咒击中，又亲眼看着姐姐死去；他不会原谅任何人，包括自己。"
        )
    elif npc_id == "ariana_dumbledore":
        npc_state["location_id"] = "godrics_hollow"
        if ariana_alive:
            npc_state["current_life"] = (
                "母亲刚去世，家里只剩两个哥哥和一个陌生的金发客人。她比以往更容易被声音和争吵惊到。"
            )
        else:
            npc_state["life_status"] = "deceased"
            npc_state["location_id"] = "godrics_hollow_dumbledore_house"
            npc_state["current_life"] = (
                "她在1899年夏末的混战中死去，致命咒语来自谁始终没有答案。"
            )
    elif npc_id == "kendra_dumbledore":
        npc_state["life_status"] = "deceased"
        npc_state["current_life"] = (
            "1899年夏，她在照顾阿利安娜时死于一次失控的魔法爆发，葬在戈德里克山谷。"
        )
    elif npc_id == "percival_dumbledore":
        npc_state["life_status"] = "deceased"
    elif npc_id == "gellert_grindelwald":
        if grindelwald_present:
            npc_state["location_id"] = "godrics_hollow"
            npc_state["current_life"] = (
                "他借住在姑婆巴希达·巴沙特家，日夜与阿不思谈死亡圣器、保密法和更伟大的利益。"
                "你是这些谈话的第三个人。"
            )
        else:
            npc_state["location_id"] = "unknown"
            npc_state["presence"] = "fled_abroad"
            npc_state["current_life"] = (
                "阿利安娜死后他夺门而逃，已经离开英国。他手上仍有那份血盟，"
                "接下来会去欧洲寻找死亡圣器和追随者。"
            )
    elif npc_id == "bathilda_bagshot":
        npc_state["location_id"] = "godrics_hollow"

    preset = ENDGAME_RELATIONSHIPS.get(npc_id)
    if preset and not (npc_id == "ariana_dumbledore" and not ariana_alive):
        relation_state.update(preset)
        relation_state["origin"] = "endgame_preset"


def _seed_endgame_memories(
    db: Session,
    session_id: str,
    endgame_entry: dict[str, Any],
) -> None:
    """把七年同窗与1899年夏天的既定前史写成长期记忆，供每轮上下文承接。"""
    existing = db.scalar(
        select(LongTermMemory)
        .where(LongTermMemory.session_id == session_id)
        .limit(1)
    )
    if existing:
        return
    ariana_alive = bool(endgame_entry.get("ariana_alive"))
    entries: list[dict[str, Any]] = [
        {
            "memory_id": f"{session_id}:endgame_seven_years",
            "title": "霍格沃茨的七年与那位天才挚友",
            "summary": (
                "1892年至1899年，你与阿不思·邓布利多在霍格沃茨同窗七年，"
                "从课堂、图书馆到深夜的争论，逐渐成为彼此最信任的挚友。"
                "你见过他的才华，也见过他每次假期回家前突然收紧的沉默。"
            ),
            "event_type": "relationship",
            "time_text": "1892–1899年",
            "location_id": "hogwarts",
            "actors": ["player", "阿不思·邓布利多"],
            "keywords": ["霍格沃茨", "挚友", "阿不思", "七年"],
            "importance": 8,
        },
        {
            "memory_id": f"{session_id}:endgame_graduation",
            "title": "1899年毕业与母亲的死讯",
            "summary": (
                "1899年你与阿不思一同通过N.E.W.T.毕业。原本该是自由与远行的夏天，"
                "肯德拉·邓布利多却在照顾阿利安娜时死于一次失控的魔法爆发。"
                "阿不思取消了所有计划，你陪他回到戈德里克山谷。"
            ),
            "event_type": "important_event",
            "time_text": "1899年夏",
            "location_id": "godrics_hollow",
            "actors": ["player", "阿不思·邓布利多", "肯德拉·邓布利多"],
            "keywords": ["毕业", "N.E.W.T.", "肯德拉", "戈德里克山谷"],
            "importance": 9,
        },
        {
            "memory_id": f"{session_id}:endgame_grindelwald_summer",
            "title": "投奔巴沙特家的金发客人",
            "summary": (
                "被德姆斯特朗开除的盖勒特·格林德沃投奔姑婆巴希达·巴沙特，住进了山谷。"
                "他与阿不思一见如故，日夜谈死亡圣器、终结保密法和“为了更伟大的利益”，"
                "并以血立下永不彼此为敌的誓约。阿不福思一直反对他们带着阿利安娜远行。"
            ),
            "event_type": "important_event",
            "time_text": "1899年夏",
            "location_id": "godrics_hollow",
            "actors": [
                "player",
                "阿不思·邓布利多",
                "盖勒特·格林德沃",
                "阿不福思·邓布利多",
            ],
            "keywords": ["格林德沃", "死亡圣器", "更伟大的利益", "血盟"],
            "importance": 9,
        },
    ]
    if not ariana_alive:
        entries.append(
            {
                "memory_id": f"{session_id}:endgame_ariana_fall",
                "title": "混战与阿利安娜的死",
                "summary": (
                    "阿不福思当面质问那两个人的远行计划，格林德沃对他施下钻心咒，"
                    "阿不思介入，三人在屋里混战。阿利安娜死在乱咒之中——"
                    "没有任何人能确定那道致命咒语来自谁。格林德沃夺门而逃，"
                    "阿不思抱着妹妹跪在地上。你在场，什么都没能改变。"
                ),
                "event_type": "important_event",
                "time_text": "1899年8月31日",
                "location_id": "godrics_hollow",
                "actors": [
                    "player",
                    "阿不思·邓布利多",
                    "阿不福思·邓布利多",
                    "盖勒特·格林德沃",
                    "阿利安娜·邓布利多",
                ],
                "keywords": ["混战", "钻心咒", "阿利安娜", "死亡", "逃离"],
                "importance": 10,
            }
        )
    for entry in entries:
        db.add(
            LongTermMemory(
                session_id=session_id,
                status="open",
                facts=[],
                open_threads=[],
                resolved_threads=[],
                source_turn_ids=[],
                related_data={"origin": "endgame_preset"},
                **entry,
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
        "阿不思·邓布利多": "albus_dumbledore",
        "阿不福思·邓布利多": "aberforth_dumbledore",
        "埃尔菲亚斯·多吉": "elphias_doge",
        "詹姆·波特": "james_potter",
        "小天狼星·布莱克": "sirius_black",
        "莱姆斯·卢平": "remus_lupin",
        "彼得·佩迪鲁": "peter_pettigrew",
        "莉莉·伊万斯": "lily_evans",
        "西弗勒斯·斯内普": "severus_snape",
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
                    "age_reference_date": _era_age_reference_date(era_id),
                    "location_id": "unknown",
                    "schedule": [],
                    "goals": [],
                    "fears": [],
                    "secrets": [],
                    "emotion": "friendly",
                    "origin": "player_created",
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


def _era_cast_items(era_id: str) -> tuple[dict[str, Any], ...] | list[dict[str, Any]]:
    if era_id == "modern":
        return MODERN_CAST
    if era_id == "dumbledore_era":
        return DUMBLEDORE_CAST
    if era_id == "parent_generation":
        return PARENT_CAST
    return []


def _era_age_reference_date(era_id: str) -> str:
    if era_id == "modern":
        return "2020-09-01"
    if era_id == "dumbledore_era":
        return "1892-07-01"
    if era_id == "parent_generation":
        return "1971-09-01"
    return "1991-07-01"


def _npc_is_student(role: str, era_id: str) -> bool:
    if role == "学生":
        return True
    if era_id == "modern" and "学生" in role:
        return True
    if era_id == "parent_generation" and "学生" in role:
        return True
    if era_id == "dumbledore_era" and "少年" in role:
        return True
    return False
