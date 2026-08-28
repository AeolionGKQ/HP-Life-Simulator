from __future__ import annotations

import json
import re
import httpx
from copy import deepcopy
from datetime import date
from hashlib import sha1
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.content.bonds import (
    age_band,
    current_age_for_npc,
    normalize_relationship_state,
    safe_bounded_int,
)
from backend.app.content.parent_cast import parent_adult_profile
from backend.app.models import (
    GameSession,
    JournalEntry,
    LongTermMemory,
    NPCState,
    PlayerState,
    Relationship,
    TurnRecord,
)
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.prompts.turn import TURN_OUTPUT_PROTOCOL, build_turn_messages
from backend.app.rules.state import apply_turn_rules, refresh_romance_summary
from backend.app.rules.timeline import apply_timeline_effect
from backend.app.schemas.game import (
    ActionRequest,
    AppliedPlayerChanges,
    Choice,
    MemoryRequest,
    NarrativeResponse,
    TurnResponse,
)
from backend.app.services.memory import get_memories_by_ids, recall_memories
from backend.app.services.story_arcs import (
    build_story_arc_context,
    ensure_story_arc_job,
    is_story_arc_blocking,
    schedule_story_arc_job,
)


class TurnGenerationError(RuntimeError):
    pass


def _memory_snapshot(memory: LongTermMemory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "memory_id": memory.memory_id,
        "session_id": memory.session_id,
        "title": memory.title,
        "summary": memory.summary,
        "event_type": memory.event_type,
        "status": memory.status,
        "importance": memory.importance,
        "time_text": memory.time_text,
        "location_id": memory.location_id,
        "actors": deepcopy(memory.actors),
        "keywords": deepcopy(memory.keywords),
        "facts": deepcopy(memory.facts),
        "open_threads": deepcopy(memory.open_threads),
        "resolved_threads": deepcopy(memory.resolved_threads),
        "source_turn_ids": deepcopy(memory.source_turn_ids),
        "related_data": deepcopy(memory.related_data),
    }


def _capture_turn_state_snapshot(
    db: Session,
    session_id: str,
    player_state: PlayerState,
    npcs: list[NPCState],
    relationships: list[Relationship],
) -> dict[str, Any]:
    memories = list(
        db.scalars(
            select(LongTermMemory).where(LongTermMemory.session_id == session_id)
        )
    )
    return {
        "player_state": deepcopy(player_state.state),
        "npcs": [
            {
                "id": npc.id,
                "npc_id": npc.npc_id,
                "is_original_character": npc.is_original_character,
                "state": deepcopy(npc.state),
            }
            for npc in npcs
        ],
        "relationships": [
            {
                "id": relationship.id,
                "source_id": relationship.source_id,
                "target_id": relationship.target_id,
                "state": deepcopy(relationship.state),
            }
            for relationship in relationships
        ],
        "memories": [_memory_snapshot(memory) for memory in memories],
    }


def _snapshot_prompt_objects(
    snapshot: dict[str, Any],
) -> tuple[
    SimpleNamespace,
    list[SimpleNamespace],
    list[SimpleNamespace],
    list[SimpleNamespace],
]:
    player_state = SimpleNamespace(state=deepcopy(snapshot["player_state"]))
    npcs = [
        SimpleNamespace(
            npc_id=item["npc_id"],
            is_original_character=item["is_original_character"],
            state=deepcopy(item["state"]),
        )
        for item in snapshot.get("npcs", [])
    ]
    relationships = [
        SimpleNamespace(
            source_id=item["source_id"],
            target_id=item["target_id"],
            state=deepcopy(item["state"]),
        )
        for item in snapshot.get("relationships", [])
    ]
    memories = [
        SimpleNamespace(**deepcopy(item))
        for item in snapshot.get("memories", [])
    ]
    return player_state, npcs, relationships, memories


def _restore_turn_state_snapshot(
    db: Session,
    player_state: PlayerState,
    snapshot: dict[str, Any],
) -> None:
    player_state.state = deepcopy(snapshot["player_state"])

    snapshot_npcs = {
        item["id"]: item
        for item in snapshot.get("npcs", [])
        if isinstance(item, dict) and item.get("id")
    }
    current_npcs = list(
        db.scalars(
            select(NPCState).where(NPCState.session_id == player_state.session_id)
        )
    )
    current_npc_ids = {npc.id for npc in current_npcs}
    for npc in current_npcs:
        saved = snapshot_npcs.get(npc.id)
        if saved is None:
            db.delete(npc)
            continue
        npc.npc_id = saved["npc_id"]
        npc.is_original_character = saved["is_original_character"]
        npc.state = deepcopy(saved["state"])
    for npc_id, saved in snapshot_npcs.items():
        if npc_id not in current_npc_ids:
            db.add(
                NPCState(
                    id=npc_id,
                    session_id=player_state.session_id,
                    npc_id=saved["npc_id"],
                    is_original_character=saved["is_original_character"],
                    state=deepcopy(saved["state"]),
                )
            )

    snapshot_relationships = {
        item["id"]: item
        for item in snapshot.get("relationships", [])
        if isinstance(item, dict) and item.get("id")
    }
    current_relationships = list(
        db.scalars(
            select(Relationship).where(
                Relationship.session_id == player_state.session_id
            )
        )
    )
    current_relationship_ids = {relationship.id for relationship in current_relationships}
    for relationship in current_relationships:
        saved = snapshot_relationships.get(relationship.id)
        if saved is None:
            db.delete(relationship)
            continue
        relationship.source_id = saved["source_id"]
        relationship.target_id = saved["target_id"]
        relationship.state = deepcopy(saved["state"])
    for relationship_id, saved in snapshot_relationships.items():
        if relationship_id not in current_relationship_ids:
            db.add(
                Relationship(
                    id=relationship_id,
                    session_id=player_state.session_id,
                    source_id=saved["source_id"],
                    target_id=saved["target_id"],
                    state=deepcopy(saved["state"]),
                )
            )

    snapshot_memories = {
        item["id"]: item
        for item in snapshot.get("memories", [])
        if isinstance(item, dict) and item.get("id")
    }
    current_memories = list(
        db.scalars(
            select(LongTermMemory).where(
                LongTermMemory.session_id == player_state.session_id
            )
        )
    )
    current_memory_ids = {memory.id for memory in current_memories}
    memory_fields = (
        "memory_id",
        "title",
        "summary",
        "event_type",
        "status",
        "importance",
        "time_text",
        "location_id",
        "actors",
        "keywords",
        "facts",
        "open_threads",
        "resolved_threads",
        "source_turn_ids",
        "related_data",
    )
    for memory in current_memories:
        saved = snapshot_memories.get(memory.id)
        if saved is None:
            db.delete(memory)
            continue
        for field in memory_fields:
            setattr(memory, field, deepcopy(saved[field]))
    for memory_id, saved in snapshot_memories.items():
        if memory_id not in current_memory_ids:
            db.add(
                LongTermMemory(
                    id=memory_id,
                    session_id=player_state.session_id,
                    memory_id=saved["memory_id"],
                    title=saved["title"],
                    summary=saved["summary"],
                    event_type=saved["event_type"],
                    status=saved["status"],
                    importance=saved["importance"],
                    time_text=saved["time_text"],
                    location_id=saved["location_id"],
                    actors=deepcopy(saved["actors"]),
                    keywords=deepcopy(saved["keywords"]),
                    facts=deepcopy(saved["facts"]),
                    open_threads=deepcopy(saved["open_threads"]),
                    resolved_threads=deepcopy(saved["resolved_threads"]),
                    source_turn_ids=deepcopy(saved["source_turn_ids"]),
                    related_data=deepcopy(saved["related_data"]),
                )
            )


def _format_validation_error(exc: ValidationError) -> str:
    details = []
    for error in exc.errors(include_url=False)[:5]:
        field_path = ".".join(str(part) for part in error["loc"])
        details.append(f"{field_path}: {error['msg']}")
    return "; ".join(details)


def _extract_json(content: str) -> dict[str, Any]:
    candidate = content.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise TurnGenerationError("模型返回的内容不是合法 JSON") from exc
    if not isinstance(parsed, dict):
        raise TurnGenerationError("模型返回的 JSON 顶层必须是对象")
    return parsed


def _parse_response(
    raw: dict[str, Any],
    *,
    default_offset_rate: float = 0.0,
) -> NarrativeResponse | MemoryRequest:
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TurnGenerationError("模型响应缺少 choices.message.content") from exc
    parsed = _extract_json(content)
    response_type = parsed.get("response_type")
    if response_type == "memory_request":
        try:
            return MemoryRequest.model_validate(parsed)
        except ValidationError as exc:
            detail = _format_validation_error(exc)
            raise TurnGenerationError(
                f"模型的记忆查阅请求字段不完整：{detail}"
            ) from exc
    if response_type != "narrative":
        raise TurnGenerationError("模型响应的 response_type 无效")
    parsed = _normalize_narrative_payload(parsed, default_offset_rate)
    try:
        response = NarrativeResponse.model_validate(parsed)
    except ValidationError as exc:
        detail = _format_validation_error(exc)
        raise TurnGenerationError(
            f"模型的剧情结构字段不完整或类型错误：{detail}"
        ) from exc
    normal_choices = [choice for choice in response.choices if choice.kind != "free_text"]
    free_choice = next(
        (choice for choice in reversed(response.choices) if choice.kind == "free_text"),
        None,
    )
    if len(normal_choices) < 2:
        normal_choices.extend(
            [
                Choice(
                    id="choice_observe",
                    label="先观察周围环境，再决定下一步",
                    kind="action",
                    risk="low",
                ),
                Choice(
                    id="choice_return",
                    label="暂时退开，寻找更安全的处理方式",
                    kind="action",
                    risk="low",
                ),
            ][: 2 - len(normal_choices)]
        )
    response.choices = normal_choices + [
        free_choice
        or Choice(
            id="choice_other",
            label="其他",
            kind="free_text",
            risk="low",
        )
    ]
    return response


def _normalize_narrative_payload(
    payload: dict[str, Any],
    default_offset_rate: float,
) -> dict[str, Any]:
    """兼容不同 OpenAI-compatible 模型对字段别名和可选字段的输出。"""
    normalized = dict(payload)
    if "turn" not in normalized:
        scene = normalized.get("scene")
        if isinstance(scene, dict):
            normalized["turn"] = scene
        else:
            normalized["turn"] = {
                "title": str(normalized.get("title") or "新的故事节点"),
                "scene_type": str(normalized.get("scene_type") or "dialogue"),
                "narrative": str(
                    normalized.get("narrative")
                    or normalized.get("description")
                    or scene
                    or "故事继续向前展开。"
                ),
                "current_date": normalized.get("current_date") or normalized.get("date"),
                "location_id": normalized.get("location_id") or "unknown",
                "location_name": normalized.get("location_name")
                or normalized.get("location")
                or "",
                "time_advance_minutes": int(
                    normalized.get("time_advance_minutes")
                    or normalized.get("time_advance")
                    or 0
                ),
            }
    turn = dict(normalized["turn"])
    turn.setdefault("title", str(normalized.get("title") or "新的故事节点"))
    turn.setdefault("scene_type", str(normalized.get("scene_type") or "dialogue"))
    turn.setdefault(
        "narrative",
        str(
            normalized.get("narrative")
            or turn.get("text")
            or turn.get("description")
            or ""
        ),
    )
    if "current_date" not in turn:
        turn["current_date"] = (
            turn.get("date")
            or normalized.get("current_date")
            or normalized.get("date")
        )
    turn.setdefault("location_id", normalized.get("location_id") or "unknown")
    turn.setdefault(
        "location_name",
        normalized.get("location_name") or normalized.get("location") or turn.get("location") or "",
    )
    if "time_advance_minutes" not in turn:
        turn["time_advance_minutes"] = int(
            turn.get("time_advance") or normalized.get("time_advance") or 0
        )
    normalized["turn"] = turn

    choices = normalized.get("choices") or normalized.get("options") or []
    normalized["choices"] = [
        {
            **choice,
            "label": str(
                choice.get("label")
                or choice.get("text")
                or choice.get("description")
                or choice.get("id")
                or "继续",
            ),
            "kind": choice.get("kind") or (
                "free_text" if str(choice.get("id", "")).lower() in {"other", "choice_other"} else "action"
                ),
            "risk": _normalize_choice_risk(choice.get("risk")),
            "effects": _normalize_choice_effects(
                choice.get("effects") or choice.get("potential_changes")
            ),
        }
        for choice in choices
        if isinstance(choice, dict)
    ]
    worldline = normalized.get("worldline")
    if not isinstance(worldline, dict):
        worldline = {}
    normalized["worldline"] = {
        "offset_rate": worldline.get(
            "offset_rate",
            worldline.get("rate", default_offset_rate),
        ),
        "delta": worldline.get("delta", 0),
        "reason": worldline.get("reason", "本轮未提供新的世界线偏移说明"),
        "affected_nodes": worldline.get("affected_nodes", []),
    }
    raw_changes = (
        normalized.get("player_changes")
        or normalized.get("changes")
        or normalized.get("state_changes")
        or normalized.get("state_proposals")
        or {}
    )
    normalized["player_changes"] = _normalize_player_changes(raw_changes)
    normalized["state_proposals"] = normalized["player_changes"]
    normalized.setdefault("memory_update", normalized.get("memory") or {})
    normalized.setdefault("events", [])
    normalized.setdefault("self_check", {})
    return normalized


def _normalize_choice_risk(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    aliases = {
        "低": "low",
        "中": "medium",
        "高": "high",
        "致命": "fatal",
    }
    return aliases.get(normalized, normalized)


def _normalize_choice_effects(raw_effects: Any) -> dict[str, Any]:
    if not isinstance(raw_effects, dict):
        return {"gains": [], "losses": [], "note": ""}
    result: dict[str, Any] = {
        "gains": raw_effects.get("gains")
        or raw_effects.get("acquire")
        or raw_effects.get("obtained")
        or [],
        "losses": raw_effects.get("losses")
        or raw_effects.get("lose")
        or raw_effects.get("lost")
        or [],
        "note": str(raw_effects.get("note") or ""),
    }
    for direction in ("gains", "losses"):
        normalized_effects = []
        for effect in result[direction]:
            if not isinstance(effect, dict):
                continue
            normalized_effects.append(
                {
                    **effect,
                    "name": str(effect.get("name") or effect.get("label") or "未知变化"),
                    "type": effect.get("type") or "item",
                    "direction": effect.get("direction") or (
                        "gain" if direction == "gains" else "loss"
                    ),
                    "description": str(
                        effect.get("description") or effect.get("reason") or ""
                    ),
                }
            )
        result[direction] = normalized_effects
    return result


def _normalize_player_changes(raw_changes: Any) -> dict[str, Any]:
    if not isinstance(raw_changes, dict):
        return {}
    changes = dict(raw_changes)
    aliases = {
        "items_add": "inventory_add",
        "items_remove": "inventory_remove",
        "statuses_add": "status_add",
        "statuses_remove": "status_remove",
        "skills_add": "skill_add",
        "skills_remove": "skill_remove",
        "traits_add": "trait_add",
        "traits_remove": "trait_remove",
    }
    for source, target in aliases.items():
        if target not in changes and source in changes:
            changes[target] = changes[source]
    normalized_traits = []
    for trait in changes.get("trait_add", []) or []:
        if not isinstance(trait, dict):
            continue
        name = str(trait.get("name") or trait.get("label") or "")
        trait_id = str(
            trait.get("id")
            or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            or f"trait_{uuid4().hex[:8]}"
        )
        normalized_traits.append(
            {
                **trait,
                "id": trait_id,
                "name": name,
                "description": str(
                    trait.get("description")
                    or trait.get("effect")
                    or trait.get("reason")
                    or "该词条的具体作用由当前剧情决定。"
                ),
                "polarity": (
                    "negative"
                    if str(trait.get("polarity", "positive")).lower()
                    in {"negative", "负面", "negative_trait"}
                    else "positive"
                ),
            }
        )
    changes["trait_add"] = normalized_traits
    return changes


START_STORY_CHOICE = {
    "id": "start_story",
    "label": "踏入魔法世界",
    "kind": "action",
    "risk": "low",
    "requires": [],
    "effects_hint": "",
    "effects": {
        "gains": [],
        "losses": [],
        "note": "",
    },
}


def _resolve_selected_choice(
    payload: ActionRequest,
    latest: TurnRecord | None,
) -> dict[str, Any] | None:
    """将客户端提交的 choice_id 解析为上一节点中的完整选项。"""
    if payload.kind != "choice":
        return None
    if not payload.choice_id:
        raise HTTPException(status_code=409, detail="请选择有效的剧情选项")
    if payload.choice_id == "start_story":
        if latest is not None:
            raise HTTPException(status_code=409, detail="开始剧情选项已失效，请刷新后重试")
        return deepcopy(START_STORY_CHOICE)
    if latest is None:
        raise HTTPException(status_code=409, detail="当前没有可供选择的剧情节点")

    raw_response = latest.llm_response
    choices = raw_response.get("choices") if isinstance(raw_response, dict) else None
    if not isinstance(choices, list):
        raise HTTPException(status_code=409, detail="当前剧情节点缺少可用选项，请刷新后重试")
    selected = next(
        (
            choice
            for choice in choices
            if isinstance(choice, dict)
            and str(choice.get("id") or "") == payload.choice_id
        ),
        None,
    )
    if selected is None:
        raise HTTPException(status_code=409, detail="所选剧情选项已失效，请刷新后重试")
    try:
        selected_choice = Choice.model_validate(selected)
    except ValidationError as exc:
        raise HTTPException(status_code=409, detail="当前剧情选项格式无效，请刷新后重试") from exc
    if selected_choice.kind == "free_text":
        raise HTTPException(status_code=409, detail="请在自由行动输入框中提交其他行动")
    return selected_choice.model_dump(mode="json")


def _build_action(
    payload: ActionRequest,
    selected_choice: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = payload.model_dump()
    if selected_choice is not None:
        action["selected_choice"] = deepcopy(selected_choice)
        action["instruction"] = f"玩家明确选择了：{selected_choice['label']}"
    return action


def _action_text(
    payload: ActionRequest,
    selected_choice: dict[str, Any] | None = None,
) -> str:
    selected_label = (
        str(selected_choice.get("label") or "")
        if isinstance(selected_choice, dict)
        else ""
    )
    return " ".join(
        item
        for item in (
            payload.choice_id or "",
            selected_label,
            payload.free_text or "",
            payload.fate_instruction or "",
            payload.reshape_instruction or "",
        )
        if item
    )


async def _reshape_latest_turn(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: ActionRequest,
) -> TurnResponse:
    settings = get_settings()
    if is_story_arc_blocking(db, game_session.id):
        raise HTTPException(status_code=409, detail="故事弧正在整理，请稍候再提交剧情")
    existing = db.scalar(
        select(TurnRecord).where(
            TurnRecord.session_id == game_session.id,
            TurnRecord.client_action_id == payload.client_action_id,
        )
    )
    if existing:
        response = NarrativeResponse.model_validate(existing.llm_response)
        return TurnResponse(
            turn_id=existing.id,
            sequence=existing.sequence,
            response=response,
            state_version=existing.state_version_after,
        )
    if game_session.state_version != payload.expected_state_version:
        raise HTTPException(status_code=409, detail="存档已发生变化，请刷新后重试")
    course_selection = player_state.state.get("school", {}).get("course_selection")
    if isinstance(course_selection, dict) and course_selection.get("status") == "pending":
        raise HTTPException(status_code=409, detail="请先完成当前学年的课程选择")
    if player_state.state.get("school", {}).get("departure_notice", {}).get("status") == "pending":
        raise HTTPException(status_code=409, detail="请先确认离校通知")
    if player_state.state.get("lifecycle", {}).get("status") == "dead":
        raise HTTPException(status_code=409, detail="当前角色已经无法重塑命运")

    latest = db.scalar(
        select(TurnRecord)
        .where(TurnRecord.session_id == game_session.id)
        .order_by(TurnRecord.sequence.desc())
        .limit(1)
    )
    if latest is None:
        raise HTTPException(status_code=409, detail="当前还没有可以重塑的剧情节点")
    authoritative = latest.authoritative_changes
    snapshot = authoritative.get("state_snapshot") if isinstance(authoritative, dict) else None
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("player_state"), dict):
        raise HTTPException(
            status_code=409,
            detail="当前剧情节点缺少可撤销状态快照，请先推进到新节点后再使用重塑命运",
        )

    original_response = NarrativeResponse.model_validate(latest.llm_response)
    prompt_player_state, prompt_npcs, prompt_relationships, prompt_memories = (
        _snapshot_prompt_objects(snapshot)
    )
    recent_turns = list(
        db.scalars(
            select(TurnRecord)
            .where(TurnRecord.session_id == game_session.id)
            .order_by(TurnRecord.sequence.desc())
            .limit(settings.game.recent_narrative_turns)
        )
    )
    recent_turns.reverse()
    recent_turns = _limit_recent_turns(
        recent_turns,
        settings.game.recent_turn_token_limit,
    )
    story_context = build_story_arc_context(
        db,
        game_session.id,
        action_text=_action_text(payload),
        location_id=prompt_player_state.state.get("current_context", {}).get("location_id"),
        actor_ids=[npc.npc_id for npc in prompt_npcs],
    )
    summaries = story_context["story_arcs"]
    action = payload.model_dump()
    action["node_to_reshape"] = {
        "sequence": latest.sequence,
        "turn": original_response.turn.model_dump(mode="json"),
        "choices": [
            choice.model_dump(mode="json")
            for choice in original_response.choices
        ],
    }
    action["reshape_base_state"] = deepcopy(snapshot["player_state"])
    previous_offset = float(
        snapshot["player_state"].get("worldline", {}).get("offset_rate", 0.0)
    )
    provider = OpenAICompatibleProvider(settings.llm)
    messages = build_turn_messages(
        game_session=game_session,
        player_state=prompt_player_state,
        npcs=prompt_npcs,
        relationships=prompt_relationships,
        recent_turns=recent_turns,
        memories=prompt_memories,
        summaries=summaries,
        pending_turn_summaries=story_context["pending_turn_summaries"],
        action=action,
    )
    parsed_response = await _request_response(
        provider,
        messages,
        default_offset_rate=previous_offset,
    )
    recalled_ids = [memory.memory_id for memory in prompt_memories]
    if isinstance(parsed_response, MemoryRequest):
        requested_ids = parsed_response.memory_request.get("memory_ids", [])
        if not isinstance(requested_ids, list):
            raise TurnGenerationError("memory_request.memory_ids 必须是数组")
        requested_ids = [str(memory_id) for memory_id in requested_ids][
            : settings.game.memory_request_limit
        ]
        memory_by_id = {
            memory.memory_id: memory
            for memory in prompt_memories
        }
        requested_memories = [
            memory_by_id[memory_id]
            for memory_id in requested_ids
            if memory_id in memory_by_id
        ]
        messages = build_turn_messages(
            game_session=game_session,
            player_state=prompt_player_state,
            npcs=prompt_npcs,
            relationships=prompt_relationships,
            recent_turns=recent_turns,
            memories=prompt_memories + requested_memories,
            summaries=summaries,
            pending_turn_summaries=story_context["pending_turn_summaries"],
            action=action,
        )
        parsed_response = await _request_response(
            provider,
            messages,
            default_offset_rate=previous_offset,
        )
        if isinstance(parsed_response, MemoryRequest):
            raise TurnGenerationError("模型在一次补查后仍未返回正式剧情")

    response = parsed_response
    response.turn.current_date = original_response.turn.current_date
    response.turn.location_id = original_response.turn.location_id
    response.turn.location_name = original_response.turn.location_name
    if game_session.era_id != "modern":
        response.worldline.offset_rate = max(
            settings.game.worldline_min,
            min(settings.game.worldline_max, response.worldline.offset_rate),
        )
        response.worldline.delta = response.worldline.offset_rate - previous_offset

    _restore_turn_state_snapshot(db, player_state, snapshot)
    npcs = list(
        db.scalars(select(NPCState).where(NPCState.session_id == game_session.id))
    )
    relationships = list(
        db.scalars(
            select(Relationship).where(Relationship.session_id == game_session.id)
        )
    )
    accepted_date = _accepted_story_date(
        player_state.state,
        _parse_story_date(response.turn.current_date),
    )
    npc_ages = _refresh_npc_ages(npcs, accepted_date, era_id=game_session.era_id)
    state, authoritative_changes = apply_turn_rules(
        player_state.state,
        relationships,
        response,
        npc_ages=npc_ages,
        era_id=game_session.era_id,
    )
    creation_result = _apply_relationship_creations(
        db,
        game_session.id,
        payload.client_action_id,
        response.player_changes.relationship_creations,
        accepted_date,
        npcs,
        relationships,
    )
    if creation_result["created"]:
        relationships.extend(creation_result["relationships"])
        authoritative_changes["relationship_creations"] = creation_result["accepted"]
        authoritative_changes["relationships_created"] = creation_result["created"]
        authoritative_changes["relationship_creation_rejections"] = creation_result[
            "rejected"
        ]
        refresh_romance_summary(state, relationships)
    elif creation_result["rejected"]:
        authoritative_changes["relationship_creation_rejections"] = creation_result[
            "rejected"
        ]
    if game_session.era_id == "modern":
        authoritative_worldline = apply_timeline_effect(
            game_session.era_id,
            state,
            response,
            action=action,
        )
        response.worldline.offset_rate = 0.0
        response.worldline.delta = authoritative_worldline["delta"]
        response.worldline.reason = authoritative_worldline["reason"]
        response.worldline.affected_nodes = authoritative_worldline["affected_nodes"]
    else:
        authoritative_worldline = response.worldline.model_dump(mode="json")
    state["worldline"] = authoritative_worldline
    if state.get("lifecycle", {}).get("status") == "dead":
        game_session.status = "ended"
    player_state.state = state
    visible_changes = _visible_changes(authoritative_changes)
    response.applied_changes = AppliedPlayerChanges.model_validate(visible_changes)
    state_version_before = game_session.state_version
    game_session.state_version += 1
    latest.client_action_id = payload.client_action_id
    latest.action_type = payload.kind
    latest.action = action
    latest.response_type = response.response_type
    latest.narrative = response.turn.narrative
    latest.llm_response = response.model_dump(mode="json")
    latest.proposed_changes = response.state_proposals
    latest.authoritative_changes = {
        **authoritative_changes,
        "state_snapshot": snapshot,
        "reshape_fate": {
            "replaced": True,
            "state_restored": True,
            "state_reapplied_once": True,
            "previous_sequence": latest.sequence,
        },
        "visible": visible_changes,
        "worldline": authoritative_worldline,
    }
    latest.memory_update = response.memory_update.model_dump()
    latest.worldline = authoritative_worldline
    latest.prompt_version = "v1.8-reshape"
    latest.model_name = settings.llm.model
    latest.state_version_before = state_version_before
    latest.state_version_after = game_session.state_version
    _persist_memory_update(
        db,
        game_session.id,
        latest.id,
        response.memory_update.model_dump(),
    )
    journal = db.scalar(
        select(JournalEntry).where(JournalEntry.turn_id == latest.id)
    )
    journal_summary = (
        response.memory_update.summary.strip()
        or response.turn.narrative[:200]
    )
    if journal:
        journal.title = response.turn.title
        journal.summary = journal_summary
        journal.data = {"sequence": latest.sequence}
    else:
        db.add(
            JournalEntry(
                session_id=game_session.id,
                turn_id=latest.id,
                entry_type="turn",
                title=response.turn.title,
                summary=journal_summary,
                data={"sequence": latest.sequence},
            )
        )
    db.commit()
    db.refresh(latest)
    return TurnResponse(
        turn_id=latest.id,
        sequence=latest.sequence,
        response=response,
        state_version=latest.state_version_after,
        recalled_memory_ids=recalled_ids,
    )


async def generate_turn(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: ActionRequest,
) -> TurnResponse:
    settings = get_settings()
    initialization_status = player_state.state.get(
        "attribute_initialization", {}
    ).get("status")
    if game_session.status != "active" or initialization_status != "ready":
        raise HTTPException(status_code=409, detail="当前存档尚未进入可行动状态")

    if is_story_arc_blocking(db, game_session.id):
        raise HTTPException(status_code=409, detail="故事弧正在整理，请稍候再提交剧情")

    if payload.kind == "reshape_fate":
        return await _reshape_latest_turn(db, game_session, player_state, payload)

    existing = db.scalar(
        select(TurnRecord).where(
            TurnRecord.session_id == game_session.id,
            TurnRecord.client_action_id == payload.client_action_id,
        )
    )
    if existing:
        response = NarrativeResponse.model_validate(existing.llm_response)
        return TurnResponse(
            turn_id=existing.id,
            sequence=existing.sequence,
            response=response,
            state_version=existing.state_version_after,
        )
    if game_session.state_version != payload.expected_state_version:
        raise HTTPException(status_code=409, detail="存档已发生变化，请刷新后重试")
    course_selection = player_state.state.get("school", {}).get("course_selection")
    if isinstance(course_selection, dict) and course_selection.get("status") == "pending":
        raise HTTPException(status_code=409, detail="请先完成当前学年的课程选择")

    latest_turn = None
    if payload.kind == "choice":
        latest_turn = db.scalar(
            select(TurnRecord)
            .where(TurnRecord.session_id == game_session.id)
            .order_by(TurnRecord.sequence.desc())
            .limit(1)
        )
    selected_choice = _resolve_selected_choice(payload, latest_turn)
    action = _build_action(payload, selected_choice)
    current_context = player_state.state.get("current_context", {})
    npcs = list(
        db.scalars(select(NPCState).where(NPCState.session_id == game_session.id))
    )
    relationships = list(
        db.scalars(
            select(Relationship).where(Relationship.session_id == game_session.id)
        )
    )
    state_snapshot = _capture_turn_state_snapshot(
        db,
        game_session.id,
        player_state,
        npcs,
        relationships,
    )
    _refresh_npc_ages(
        npcs,
        _parse_story_date(current_context.get("current_date")),
        era_id=game_session.era_id,
    )
    story_context = build_story_arc_context(
        db,
        game_session.id,
        action_text=_action_text(payload, selected_choice),
        location_id=current_context.get("location_id"),
        actor_ids=[npc.npc_id for npc in npcs],
    )
    summaries = story_context["story_arcs"]
    recent_turns = list(
        db.scalars(
            select(TurnRecord)
            .where(TurnRecord.session_id == game_session.id)
            .order_by(TurnRecord.sequence.desc())
            .limit(settings.game.recent_narrative_turns)
        )
    )
    recent_turns.reverse()
    recent_turns = _limit_recent_turns(
        recent_turns,
        settings.game.recent_turn_token_limit,
    )
    action_text = _action_text(payload, selected_choice)
    actor_ids = [npc.npc_id for npc in npcs]
    memories = recall_memories(
        db,
        game_session.id,
        action_text=action_text,
        location_id=current_context.get("location_id"),
        actor_ids=actor_ids,
    )
    provider = OpenAICompatibleProvider(settings.llm)
    messages = build_turn_messages(
        game_session=game_session,
        player_state=player_state,
        npcs=npcs,
        relationships=relationships,
        recent_turns=recent_turns,
        memories=memories,
        summaries=summaries,
        pending_turn_summaries=story_context["pending_turn_summaries"],
        action=action,
    )
    previous_offset = float(
        player_state.state.get("worldline", {}).get("offset_rate", 0.0)
    )
    parsed_response = await _request_response(
        provider,
        messages,
        default_offset_rate=previous_offset,
    )
    recalled_ids = [memory.memory_id for memory in memories]

    if isinstance(parsed_response, MemoryRequest):
        requested_ids = parsed_response.memory_request.get("memory_ids", [])
        if not isinstance(requested_ids, list):
            raise TurnGenerationError("memory_request.memory_ids 必须是数组")
        requested_ids = [str(memory_id) for memory_id in requested_ids][
            : settings.game.memory_request_limit
        ]
        requested_memories = get_memories_by_ids(
            db,
            game_session.id,
            requested_ids,
        )
        recalled_ids.extend(
            memory.memory_id
            for memory in requested_memories
            if memory.memory_id not in recalled_ids
        )
        messages = build_turn_messages(
            game_session=game_session,
            player_state=player_state,
            npcs=npcs,
            relationships=relationships,
            recent_turns=recent_turns,
            memories=memories + requested_memories,
            summaries=summaries,
            pending_turn_summaries=story_context["pending_turn_summaries"],
            action=action,
        )
        parsed_response = await _request_response(
            provider,
            messages,
            default_offset_rate=previous_offset,
        )
        if isinstance(parsed_response, MemoryRequest):
            raise TurnGenerationError("模型在一次补查后仍未返回正式剧情")

    response = parsed_response
    if game_session.era_id != "modern":
        response.worldline.offset_rate = max(
            settings.game.worldline_min,
            min(settings.game.worldline_max, response.worldline.offset_rate),
        )
        response.worldline.delta = response.worldline.offset_rate - previous_offset

    accepted_date = _accepted_story_date(
        player_state.state,
        response.turn.current_date,
    )
    npc_ages = _refresh_npc_ages(npcs, accepted_date, era_id=game_session.era_id)
    state, authoritative_changes = apply_turn_rules(
        player_state.state,
        relationships,
        response,
        npc_ages=npc_ages,
        era_id=game_session.era_id,
    )
    creation_result = _apply_relationship_creations(
        db,
        game_session.id,
        payload.client_action_id,
        response.player_changes.relationship_creations,
        accepted_date,
        npcs,
        relationships,
    )
    if creation_result["created"]:
        relationships.extend(creation_result["relationships"])
        authoritative_changes["relationship_creations"] = creation_result["accepted"]
        authoritative_changes["relationships_created"] = creation_result["created"]
        authoritative_changes["relationship_creation_rejections"] = creation_result[
            "rejected"
        ]
        refresh_romance_summary(state, relationships)
    elif creation_result["rejected"]:
        authoritative_changes["relationship_creation_rejections"] = creation_result[
            "rejected"
        ]
    if game_session.era_id == "modern":
        authoritative_worldline = apply_timeline_effect(
            game_session.era_id,
            state,
            response,
            action=action,
        )
        response.worldline.offset_rate = 0.0
        response.worldline.delta = authoritative_worldline["delta"]
        response.worldline.reason = authoritative_worldline["reason"]
        response.worldline.affected_nodes = authoritative_worldline["affected_nodes"]
    else:
        authoritative_worldline = response.worldline.model_dump(mode="json")
    state["worldline"] = authoritative_worldline
    lifecycle_status = state.get("lifecycle", {}).get("status")
    if lifecycle_status == "dead":
        game_session.status = "ended"
    player_state.state = state
    visible_changes = _visible_changes(authoritative_changes)
    response.applied_changes = AppliedPlayerChanges.model_validate(visible_changes)
    game_session.state_version += 1
    sequence = (
        db.scalar(
            select(TurnRecord.sequence)
            .where(TurnRecord.session_id == game_session.id)
            .order_by(TurnRecord.sequence.desc())
            .limit(1)
        )
        or 0
    ) + 1
    turn = TurnRecord(
        session_id=game_session.id,
        sequence=sequence,
        client_action_id=payload.client_action_id,
        action_type=payload.kind,
        action=action,
        response_type=response.response_type,
        narrative=response.turn.narrative,
        llm_response=response.model_dump(mode="json"),
        proposed_changes=response.state_proposals,
        authoritative_changes={
            **authoritative_changes,
            "state_snapshot": state_snapshot,
            "visible": visible_changes,
            "worldline": authoritative_worldline,
        },
        memory_update=response.memory_update.model_dump(),
        worldline=authoritative_worldline,
        prompt_version="v1.8-milestones",
        model_name=settings.llm.model,
        state_version_before=payload.expected_state_version,
        state_version_after=game_session.state_version,
    )
    db.add(turn)
    db.flush()
    _persist_memory_update(
        db,
        game_session.id,
        turn.id,
        response.memory_update.model_dump(),
    )
    db.add(
        JournalEntry(
            session_id=game_session.id,
            turn_id=turn.id,
            entry_type="turn",
            title=response.turn.title,
            summary=(
                response.memory_update.summary.strip()
                or (response.turn.narrative or "")[:200]
                or response.turn.title
            ),
            data={"sequence": sequence},
        )
    )
    db.commit()
    db.refresh(turn)
    job = ensure_story_arc_job(db, game_session.id)
    if job is not None:
        schedule_story_arc_job(job.id)
    return TurnResponse(
        turn_id=turn.id,
        sequence=turn.sequence,
        response=response,
        state_version=turn.state_version_after,
        recalled_memory_ids=recalled_ids,
    )


def _visible_changes(changes: dict[str, Any]) -> dict[str, Any]:
    inventory = changes.get("inventory", {})
    statuses = changes.get("statuses", {})
    traits = changes.get("traits", {})
    skill_entries = changes.get("skills_entries", {})
    reputation = changes.get("reputation", {})
    reputation_delta = (
        reputation.get("applied_delta")
        if isinstance(reputation, dict)
        else None
    )
    return {
        "inventory_add": inventory.get("added", []),
        "inventory_remove": inventory.get("removed", inventory.get("removed_ids", [])),
        "status_add": statuses.get("added", []),
        "status_remove": statuses.get("removed", []),
        "skill_add": [
            {"id": skill_id, "name": skill_id}
            for skill_id in skill_entries.get("added", [])
        ],
        "skill_remove": skill_entries.get("removed", []),
        "skill_deltas": changes.get("skills", {}),
        "skill_experience_deltas": {
            item["skill_id"]: item["gained"]
            for item in changes.get("skill_experience", {}).get("applied", [])
        },
        "course_skill_deltas": changes.get("course_skills", {}).get("applied", {}),
        "trait_add": traits.get("added", []),
        "trait_remove": traits.get("removed", []),
        "resource_deltas": [
            {
                "id": item["id"],
                "delta": item["delta"],
                "reason_code": item["reason_code"],
                "reason": item["reason"],
            }
            for item in changes.get("resources", {}).get("applied", [])
        ],
        "dimension_deltas": [
            {
                "id": item["id"],
                "delta": item["delta"],
                "reason_code": item["reason_code"],
                "reason": item["reason"],
            }
            for item in changes.get("dimensions", {}).get("applied", [])
        ],
        "resource_cap_deltas": changes.get("resource_caps", {}).get("applied", []),
        "dimension_cap_deltas": changes.get("dimension_caps", {}).get("applied", []),
        "reputation_deltas": (
            {"score": int(reputation_delta)}
            if isinstance(reputation_delta, (int, float))
            and not isinstance(reputation_delta, bool)
            and reputation_delta
            else {}
        ),
        "relationship_deltas": changes.get("relationships", []),
        "relationship_creations": changes.get("relationship_creations", []),
    }


def _parse_story_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return date(1991, 7, 1)


def _accepted_story_date(
    state: dict[str, Any],
    requested_date: date,
) -> date:
    current_context = state.get("current_context", {})
    current_date = _parse_story_date(
        current_context.get("current_date")
        if isinstance(current_context, dict)
        else None
    )
    return max(current_date, requested_date)


def _refresh_npc_ages(
    npcs: list[NPCState],
    story_date: date,
    *,
    era_id: str | None = None,
) -> dict[str, int | None]:
    ages: dict[str, int | None] = {}
    for npc in npcs:
        npc_state = dict(npc.state) if isinstance(npc.state, dict) else {}
        if npc_state.get("life_status") == "deceased":
            # 已故人物不再随剧情日期长大，年龄停在去世时的记录上。
            ages[npc.npc_id] = npc_state.get("age")
            continue
        current_age = current_age_for_npc(npc_state, story_date)
        if current_age is not None:
            npc_state["age"] = current_age
            npc_state["age_band"] = age_band(current_age)
            npc_state.setdefault("age_reference_date", story_date.isoformat())
            if era_id == "parent_generation":
                adult_profile = parent_adult_profile(npc.npc_id, story_date)
                if adult_profile:
                    npc_state.update(
                        {
                            "role": adult_profile["role"],
                            "current_life": adult_profile["current_life"],
                            "appearance_conditions": adult_profile[
                                "appearance_conditions"
                            ],
                            "life_stage": "adult",
                        }
                    )
            npc.state = npc_state
        ages[npc.npc_id] = current_age
    return ages


def _apply_relationship_creations(
    db: Session,
    session_id: str,
    action_id: str,
    proposals: list[Any],
    current_date: date,
    npcs: list[NPCState],
    relationships: list[Relationship],
) -> dict[str, Any]:
    created: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    new_relationships: list[Relationship] = []
    if not proposals:
        return {
            "accepted": accepted,
            "created": created,
            "rejected": rejected,
            "relationships": new_relationships,
        }

    existing_names: dict[str, NPCState] = {}
    for npc in npcs:
        npc_state = npc.state if isinstance(npc.state, dict) else {}
        names = [npc_state.get("name", ""), *npc_state.get("aliases", [])]
        for name in names:
            key = _normalize_person_name(name)
            if key:
                existing_names[key] = npc
    if len(proposals) > 1:
        rejected.extend(
            {
                "reason": "relationship_creation_limit_exceeded",
                "proposal": proposal.model_dump(mode="json"),
            }
            for proposal in proposals[1:]
        )
    proposal = proposals[0]
    character = proposal.character
    character_data = character.model_dump(mode="json")
    name_key = _normalize_person_name(character_data["name"])
    if not name_key:
        rejected.append({"reason": "relationship_name_empty"})
    elif name_key in existing_names:
        rejected.append(
            {
                "reason": "relationship_duplicate",
                "name": character_data["name"],
                "existing_npc_id": existing_names[name_key].npc_id,
            }
        )
    elif not proposal.reason.strip() or not proposal.evidence.strip():
        rejected.append(
            {
                "reason": "relationship_creation_missing_evidence",
                "name": character_data["name"],
            }
        )
    else:
        digest = sha1(
            f"{session_id}:{name_key}".encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:12]
        npc_id = f"model_npc_{digest}"
        npc_state = {
            "name": character_data["name"],
            "role": character_data["role"],
            "age": character_data["age"],
            "birthday": character_data["birthday"],
            "age_band": (
                age_band(character_data["age"])
                if character_data["age"] is not None
                else character_data["age_band"]
            ),
            "age_reference_date": current_date.isoformat(),
            "location_id": character_data["location_id"],
            "personality": character_data["personality"],
            "appearance": character_data["appearance"],
            "goals": character_data["goals"],
            "fears": character_data["fears"],
            "secrets": [],
            "emotion": "neutral",
            "aliases": character_data["aliases"],
            "origin": "model_created",
            "created_action_id": action_id,
        }
        npc = NPCState(
            session_id=session_id,
            npc_id=npc_id,
            is_original_character=False,
            state=npc_state,
        )
        bond = proposal.bond.model_dump(mode="json")
        affinity = safe_bounded_int(
            bond.get("affinity_delta"),
            minimum=0,
            maximum=10,
        )
        trust = safe_bounded_int(
            bond.get("trust_delta"),
            minimum=0,
            maximum=10,
        )
        stage = (
            "acquaintance"
            if bond["stage"] == "acquaintance" and (affinity >= 5 or trust >= 5)
            else "stranger"
        )
        if bond["stage"] not in {"stranger", "acquaintance"}:
            rejected.append(
                {
                    "reason": "new_relationship_social_stage_downgraded",
                    "name": character_data["name"],
                    "requested_stage": bond["stage"],
                    "applied_stage": stage,
                }
            )
        if bond["romance_stage"] not in {"none", "locked"}:
            rejected.append(
                {
                    "reason": "new_relationship_romance_stage_downgraded",
                    "name": character_data["name"],
                    "requested_stage": bond["romance_stage"],
                    "applied_stage": "none",
                }
            )
        relation = Relationship(
            session_id=session_id,
            source_id="player",
            target_id=npc_id,
            state=normalize_relationship_state(
                {
                    "affinity": affinity,
                    "trust": trust,
                    "stage": stage,
                    "bond_type": bond["bond_type"],
                    "romance_stage": "none",
                    "known_since": current_date.isoformat(),
                    "last_interaction_date": current_date.isoformat(),
                    "last_change": {
                        "affinity_delta": affinity,
                        "trust_delta": trust,
                        "reason": proposal.reason,
                    },
                    "origin": "model_created",
                },
                current_date=current_date.isoformat(),
            ),
        )
        db.add(npc)
        db.add(relation)
        npcs.append(npc)
        new_relationships.append(relation)
        accepted.append(proposal.model_dump(mode="json"))
        created.append(
            {
                "npc_id": npc_id,
                "name": character_data["name"],
                "stage": stage,
                "bond_type": bond["bond_type"],
                "reason": proposal.reason,
            }
        )
    return {
        "accepted": accepted,
        "created": created,
        "rejected": rejected,
        "relationships": new_relationships,
    }


def _normalize_person_name(value: Any) -> str:
    return re.sub(r"[\s·•,，。.!！？?_\-]+", "", str(value or "")).casefold()


async def _request_response(
    provider: OpenAICompatibleProvider,
    messages: list[dict[str, str]],
    *,
    default_offset_rate: float = 0.0,
) -> NarrativeResponse | MemoryRequest:
    try:
        raw_response = await provider.chat_completion(messages)
    except httpx.HTTPStatusError as exc:
        raise TurnGenerationError(
            f"模型服务返回 HTTP {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise TurnGenerationError("无法连接模型服务，请检查本地配置和网络") from exc
    try:
        return _parse_response(raw_response, default_offset_rate=default_offset_rate)
    except TurnGenerationError as first_error:
        repair_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "第一次生成没有通过结构校验，请根据同一上下文从头重新生成本回合。\n"
                    f"校验失败原因：{first_error}\n"
                    "不要解释错误，不要复述规则，只返回符合以下协议的一个 JSON 对象。\n\n"
                    f"{TURN_OUTPUT_PROTOCOL}"
                ),
            },
        ]
        try:
            repaired_response = await provider.chat_completion(
                repair_messages,
                temperature=0,
            )
        except httpx.HTTPStatusError as exc:
            raise TurnGenerationError(
                f"模型服务返回 HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise TurnGenerationError("模型修复请求无法连接服务") from exc
        try:
            return _parse_response(
                repaired_response,
                default_offset_rate=default_offset_rate,
            )
        except TurnGenerationError as repair_error:
            raise TurnGenerationError(
                f"模型连续两次未返回合法剧情结构：{repair_error}"
            ) from first_error


def _persist_memory_update(
    db: Session,
    session_id: str,
    turn_id: str,
    update: dict[str, Any],
) -> None:
    for memory_id in update.get("resolved_memory_ids", []):
        memory = db.scalar(
            select(LongTermMemory).where(
                LongTermMemory.session_id == session_id,
                LongTermMemory.memory_id == memory_id,
            )
        )
        if memory:
            memory.status = "resolved"
    if not update.get("create_long_term_memory"):
        return
    proposed = update.get("memory")
    if not isinstance(proposed, dict) or not proposed.get("summary"):
        return
    memory_id = str(proposed.get("memory_id") or f"MEM-{uuid4().hex[:12]}")
    existing = db.scalar(
        select(LongTermMemory).where(LongTermMemory.memory_id == memory_id)
    )
    if existing:
        existing.summary = str(proposed["summary"])
        existing.source_turn_ids = list(
            dict.fromkeys([*existing.source_turn_ids, turn_id])
        )
        return
    db.add(
        LongTermMemory(
            memory_id=memory_id,
            session_id=session_id,
            title=str(proposed.get("title") or proposed["summary"][:80]),
            summary=str(proposed["summary"]),
            event_type=str(proposed.get("event_type") or "important_event"),
            status=str(proposed.get("status") or "open"),
            importance=_normalize_memory_importance(proposed.get("importance", 5)),
            time_text=proposed.get("time"),
            location_id=proposed.get("location_id"),
            actors=proposed.get("actors") or [],
            keywords=proposed.get("keywords") or [],
            facts=proposed.get("facts") or [],
            open_threads=proposed.get("open_threads") or [],
            resolved_threads=proposed.get("resolved_threads") or [],
            source_turn_ids=[turn_id],
            related_data=proposed.get("related_data") or {},
        )
    )


def _normalize_memory_importance(value: Any) -> int:
    """将不可信的模型输出归一化为 1 到 10 的长期记忆重要度。"""
    if isinstance(value, bool):
        return 5
    if isinstance(value, (int, float)):
        try:
            numeric = int(value)
        except (OverflowError, ValueError):
            return 5
        return max(1, min(10, numeric))

    normalized = str(value or "").strip().lower()
    aliases = {
        "minor": 2,
        "low": 3,
        "medium": 5,
        "moderate": 5,
        "major": 8,
        "high": 8,
        "critical": 10,
        "次要": 2,
        "低": 3,
        "中": 5,
        "重要": 8,
        "高": 8,
        "关键": 10,
    }
    if normalized in aliases:
        return aliases[normalized]
    try:
        return max(1, min(10, int(float(normalized))))
    except (OverflowError, ValueError):
        return 5


def _limit_recent_turns(
    turns: list[TurnRecord],
    token_limit: int,
) -> list[TurnRecord]:
    """按粗略 token 估算裁剪最早的回合，保留完整回合边界。"""
    approximate_char_limit = token_limit * 4
    selected: list[TurnRecord] = []
    used = 0
    for turn in reversed(turns):
        response = turn.llm_response if isinstance(turn.llm_response, dict) else {}
        turn_data = response.get("turn", {}) if isinstance(response, dict) else {}
        memory_update = turn.memory_update if isinstance(turn.memory_update, dict) else {}
        compact_context = {
            "sequence": turn.sequence,
            "action": turn.action,
            "title": turn_data.get("title"),
            "scene_type": turn_data.get("scene_type"),
            "current_date": turn_data.get("current_date"),
            "location_id": turn_data.get("location_id"),
            "narrative": turn.narrative,
            "summary": memory_update.get("summary") or (turn.narrative or "")[:200],
            "state_changes": (
                turn.authoritative_changes.get("visible", {})
                if isinstance(turn.authoritative_changes, dict)
                else {}
            ),
        }
        turn_size = len(json.dumps(compact_context, ensure_ascii=False, default=str))
        if selected and used + turn_size > approximate_char_limit:
            break
        selected.append(turn)
        used += turn_size
    selected.reverse()
    return selected
