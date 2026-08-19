from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.content.setup import get_setup_step
from backend.app.content.eras import get_era
from backend.app.models import (
    GameSession,
    NPCState,
    PlayerState,
    Relationship,
)
from backend.app.schemas.game import SetupAnswer, SetupView


def get_setup_view(game_session: GameSession, player_state: PlayerState) -> SetupView:
    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    current_step = min(int(setup.get("current_step", 1)), 13)
    return SetupView(
        current_step=current_step,
        completed=bool(setup.get("completed", False)),
        current=get_setup_step(current_step),
        answers=setup.get("answers", {}),
    )


def save_setup_answer(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: SetupAnswer,
) -> SetupView:
    if payload.step != player_state.state.get("setup", {}).get("current_step", 1):
        raise ValueError("只能提交当前角色创建步骤")
    if payload.step == 1:
        selected_era = str(payload.answer)
        era = get_era(selected_era)
        if (
            selected_era != game_session.era_id
            or not era["available"]
        ):
            raise ValueError("当前版本尚未开放所选世代")

    state = deepcopy(player_state.state)
    setup = state.setdefault("setup", {})
    answers = setup.setdefault("answers", {})
    answers[str(payload.step)] = payload.answer
    if payload.step < 13:
        setup["current_step"] = payload.step + 1
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
    missing = [str(step) for step in range(1, 13) if str(step) not in answers]
    if missing:
        raise ValueError(f"角色创建尚未完成，缺少步骤：{', '.join(missing)}")
    setup["completed"] = True
    setup["current_step"] = 13
    _materialize_player_state(state, answers)
    game_session.status = "active"
    game_session.state_version += 1
    player_state.state = state
    _seed_npcs_and_relationships(db, game_session.id)
    db.flush()
    seed_initial_friends(db, game_session.id, answers.get("11"))
    db.commit()
    db.refresh(player_state)
    db.refresh(game_session)
    return get_setup_view(game_session, player_state)


def _materialize_player_state(
    state: dict[str, Any],
    answers: dict[str, Any],
) -> None:
    identity = answers.get("2", {})
    if isinstance(identity, str):
        identity = _parse_labeled_identity(identity)
    state["identity"] = {
        "name": identity.get("name", "未命名巫师"),
        "gender": identity.get("gender", "未设定"),
        "birthday": identity.get("birthday", "1980-09-01"),
        "sexuality": identity.get("sexuality", "未设定"),
        "age": 10,
    }
    appearance = answers.get("3", {})
    state["appearance"] = (
        appearance if isinstance(appearance, dict) else {"description": appearance}
    )
    family = answers.get("4", "未设定")
    state["family"] = {
        "bloodline": _normalize_answer(family),
        "description": "你的家族背景将在故事中逐渐展开。",
    }
    childhood = answers.get("5", "")
    state["background"] = {
        "childhood_experiences": childhood
        if isinstance(childhood, list)
        else [str(childhood)],
    }
    personality_values = _split_multi_answer(answers.get("6", "未设定"))
    state["personality"] = {
        "traits": personality_values,
        "primary": personality_values[0] if personality_values else "未设定",
    }
    values = answers.get("7", "")
    state["values"] = {"description": values}
    state["wand"] = {"description": answers.get("8")}
    talent_values = _split_multi_answer(answers.get("9", "魔法基础"))
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
            "level": 10,
            "experience": 0,
            "source": "initial_magic_talent",
        }
        for value in talent_values
    }
    state["pet"] = {"description": answers.get("10")}
    starting_point = _starting_point_id(answers.get("12"))
    state["current_context"] = {
        "datetime": "1991-09-01T17:30:00+00:00"
        if starting_point == "sorting_ceremony"
        else "1991-07-01T09:00:00+00:00",
        "period": "evening" if starting_point == "sorting_ceremony" else "morning",
        "location_id": {
            "before_first_letter": "home",
            "diagon_alley": "diagon_alley",
            "platform_nine_three_quarters": "platform_nine_three_quarters",
            "sorting_ceremony": "hogwarts_great_hall",
        }.get(starting_point, "home"),
        "activity": starting_point,
    }
    state["school"]["year_level"] = 1
    state["school"]["school_year"] = "1991-1992"


def _normalize_answer(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("label") or value)
    return str(value)


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


def _parse_labeled_identity(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    labels = {
        "姓名": "name",
        "性别": "gender",
        "生日": "birthday",
        "性取向": "sexuality",
    }
    for segment in value.replace("，", ",").split(","):
        segment = segment.strip()
        matched = False
        for label, key in labels.items():
            prefix_options = (f"{label}:", f"{label}：")
            if segment.startswith(prefix_options):
                result[key] = segment.split(":", 1)[-1].split("：", 1)[-1].strip()
                matched = True
                break
        if not matched and segment and "name" not in result:
            result["name"] = segment
    return result


def _starting_point_id(value: Any) -> str:
    normalized = _normalize_answer(value)
    mapping = {
        "收到霍格沃茨来信之前": "before_first_letter",
        "第一次踏入对角巷": "diagon_alley",
        "九又四分之三站台": "platform_nine_three_quarters",
        "分院时": "sorting_ceremony",
    }
    return mapping.get(normalized, normalized)


def _seed_npcs_and_relationships(db: Session, session_id: str) -> None:
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
    for npc_id, name, role, personality in npc_definitions:
        db.add(
            NPCState(
                session_id=session_id,
                npc_id=npc_id,
                is_original_character=True,
                state={
                    "name": name,
                    "role": role,
                    "personality": personality,
                    "age": student_ages.get(npc_id, 11) if role == "学生" else 50,
                    "location_id": "hogwarts" if role == "教授" else "unknown",
                    "schedule": [],
                    "goals": [],
                    "fears": [],
                    "secrets": [],
                    "emotion": "neutral",
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
                    "romance_state": "unavailable",
                    "known_secrets": [],
                    "recent_interaction_ids": [],
                },
            )
        )


def seed_initial_friends(
    db: Session,
    session_id: str,
    raw_answer: Any,
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
                    "age": 11,
                    "location_id": "unknown",
                    "schedule": [],
                    "goals": [],
                    "fears": [],
                    "secrets": [],
                    "emotion": "friendly",
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
            "romance_state": relationship.state.get("romance_state", "unavailable"),
            "known_secrets": relationship.state.get("known_secrets", []),
            "recent_interaction_ids": relationship.state.get(
                "recent_interaction_ids", []
            ),
        }
