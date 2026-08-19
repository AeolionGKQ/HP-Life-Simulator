from __future__ import annotations

import json
import re
import httpx
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models import (
    GameSession,
    JournalEntry,
    LongTermMemory,
    NPCState,
    PlayerState,
    Relationship,
    StorySummary,
    TurnRecord,
)
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.prompts.turn import TURN_OUTPUT_PROTOCOL, build_turn_messages
from backend.app.rules.state import apply_turn_rules
from backend.app.schemas.game import (
    ActionRequest,
    Choice,
    MemoryRequest,
    NarrativeResponse,
    PlayerChanges,
    TurnResponse,
)
from backend.app.services.memory import get_memories_by_ids, recall_memories


class TurnGenerationError(RuntimeError):
    pass


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
            risk="unknown",
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
                "location_id": normalized.get("location_id"),
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


def _action_text(payload: ActionRequest) -> str:
    return " ".join(
        item
        for item in (
            payload.choice_id or "",
            payload.free_text or "",
        )
        if item
    )


async def generate_turn(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: ActionRequest,
) -> TurnResponse:
    settings = get_settings()
    if game_session.status != "active":
        raise HTTPException(status_code=409, detail="当前存档尚未进入可行动状态")

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

    npcs = list(
        db.scalars(select(NPCState).where(NPCState.session_id == game_session.id))
    )
    relationships = list(
        db.scalars(
            select(Relationship).where(Relationship.session_id == game_session.id)
        )
    )
    summaries = list(
        db.scalars(
            select(StorySummary)
            .where(StorySummary.session_id == game_session.id)
            .order_by(StorySummary.updated_at.desc())
        )
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
    current_context = player_state.state.get("current_context", {})
    action = payload.model_dump()
    action_text = _action_text(payload)
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
    response.worldline.offset_rate = max(
        settings.game.worldline_min,
        min(settings.game.worldline_max, response.worldline.offset_rate),
    )
    response.worldline.delta = response.worldline.offset_rate - previous_offset

    state, authoritative_changes = apply_turn_rules(
        player_state.state,
        relationships,
        response,
    )
    state["worldline"] = response.worldline.model_dump()
    player_state.state = state
    visible_changes = _visible_changes(authoritative_changes)
    response.applied_changes = PlayerChanges.model_validate(visible_changes)
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
        llm_response=response.model_dump(),
        proposed_changes=response.state_proposals,
        authoritative_changes={
            **authoritative_changes,
            "visible": visible_changes,
            "worldline": response.worldline.model_dump(),
        },
        memory_update=response.memory_update.model_dump(),
        worldline=response.worldline.model_dump(),
        prompt_version="v1-turn-memory",
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
    if response.memory_update.summary:
        db.add(
            JournalEntry(
                session_id=game_session.id,
                turn_id=turn.id,
                entry_type="turn",
                title=response.turn.title,
                summary=response.memory_update.summary,
                data={"sequence": sequence},
            )
        )
    db.commit()
    db.refresh(turn)
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
    return {
        "inventory_add": inventory.get("added", []),
        "inventory_remove": inventory.get("removed_ids", []),
        "status_add": statuses.get("added", []),
        "status_remove": statuses.get("removed", []),
        "skill_add": [
            {"id": skill_id, "name": skill_id}
            for skill_id in skill_entries.get("added", [])
        ],
        "skill_remove": skill_entries.get("removed", []),
        "skill_deltas": changes.get("skills", {}),
        "trait_add": traits.get("added", []),
        "trait_remove": traits.get("removed", []),
        "vital_deltas": changes.get("vitals", {}),
        "attribute_deltas": changes.get("attributes", {}),
        "reputation_deltas": changes.get("reputation", {}),
        "relationship_deltas": changes.get("relationships", []),
    }


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
            importance=max(1, min(10, int(proposed.get("importance", 5)))),
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


def _limit_recent_turns(
    turns: list[TurnRecord],
    token_limit: int,
) -> list[TurnRecord]:
    """按粗略 token 估算裁剪最早的回合，保留完整回合边界。"""
    approximate_char_limit = token_limit * 4
    selected: list[TurnRecord] = []
    used = 0
    for turn in reversed(turns):
        turn_size = len(turn.narrative or "") + len(
            json.dumps(turn.llm_response, ensure_ascii=False, default=str)
        )
        if selected and used + turn_size > approximate_char_limit:
            break
        selected.append(turn)
        used += turn_size
    selected.reverse()
    return selected
