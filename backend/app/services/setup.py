from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.content.setup import get_setup_step
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
        identity = {"name": identity}
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
    state["personality"] = {"primary": _normalize_answer(answers.get("6", "未设定"))}
    values = answers.get("7", "")
    state["values"] = {"description": values}
    state["wand"] = answers.get("8")
    state["skills"] = {
        _normalize_answer(answers.get("9", "魔法基础")): {
            "level": 10,
            "experience": 0,
        }
    }
    state["pet"] = answers.get("10")
    state["current_context"] = {
        "datetime": "1991-07-01T09:00:00+00:00",
        "period": "morning",
        "location_id": _normalize_answer(answers.get("12", "home")),
        "activity": "ready_for_first_scene",
    }
    state["school"]["year_level"] = 1
    state["school"]["school_year"] = "1991-1992"


def _normalize_answer(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("label") or value)
    return str(value)


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
                    "age": 11 if role == "学生" else 50,
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
