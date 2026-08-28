from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.content.attributes import initial_dimensions, initial_resources
from backend.app.content.eras import ERA_BY_ID
from backend.app.models import (
    GameSession,
    JournalEntry,
    LongTermMemory,
    NPCState,
    PlayerState,
    Relationship,
    StoryArc,
    StoryArcGenerationJob,
    StorySummary,
    TurnRecord,
)
from backend.app.schemas.sessions import SaveExport


def initial_player_state() -> dict[str, Any]:
    return {
        "setup": {
            "current_step": 1,
            "completed": False,
            "schema_version": 2,
            "answers": {},
        },
        "attribute_initialization": {
            "status": "pending",
            "schema_version": "1.2",
            "request_id": None,
            "completed_at": None,
            "source": None,
            "error": None,
            "calibration_summary": "",
        },
        "resources": initial_resources(),
        "dimensions": initial_dimensions(),
        "identity": {},
        "appearance": {},
        "family": {},
        "background": {},
        "personality": {},
        "values": {},
        "school": {
            "house": None,
            "grade": "not_enrolled",
            "enrollment_started": False,
            "sorting_completed": False,
            "school_year": "1991-1992",
            "grade_started_year": None,
            "last_grade_promotion_key": None,
            "last_course_progression_year": None,
            "term": "summer",
            "departure_reason": None,
            "owl_results": {},
            "newt_results": {},
            "elective_courses": [],
            "newt_courses": [],
            "active_courses": [],
            "course_selection": None,
            "course_history": [],
            "departure_notice": {
                "status": "none",
                "notice_id": None,
                "reason": None,
                "title": "",
                "message": "",
            },
        },
        "statuses": [],
        "skills": {},
        "magic_talents": [],
        "traits": [],
        "wand": None,
        "story_milestones": {
            "wand_obtained": False,
            "sorting_completed": False,
        },
        "currency": {"galleons": 0, "sickles": 0, "knuts": 0},
        "inventory": [],
        "pet": None,
        "current_context": {
            "datetime": "1991-07-01T09:00:00",
            "current_date": "1991-07-01",
            "period": "morning",
            "location_id": "home",
            "activity": "character_setup",
        },
        "reputation": {
            "score": 0,
            "level_id": "neutral",
            "level_name": "中立",
            "alignment": "中立倾向",
            "last_delta": 0,
            "last_reason": "",
        },
        "romance": {
            "status": "single",
            "active_relationship_ids": [],
            "primary_relationship_id": None,
            "pending_stage_unlocks": [],
        },
        "worldline": {
            "offset_rate": 0.0,
            "last_delta": 0.0,
            "reason": "角色尚未进入故事",
            "affected_nodes": [],
        },
        "known_secrets": [],
        "unlocks": {
            "cg": [],
            "achievements": [],
            "locations": [],
            "collections": [],
        },
        "notifications": [],
        "lifecycle": {"status": "normal"},
    }


def create_session(db: Session, name: str) -> GameSession:
    settings = get_settings()
    game_session = GameSession(name=name, era_id=settings.game.era_id)
    db.add(game_session)
    db.flush()
    db.add(
        PlayerState(
            session_id=game_session.id,
            state=initial_player_state(),
        )
    )
    db.commit()
    db.refresh(game_session)
    return game_session


def list_sessions(db: Session) -> list[GameSession]:
    statement = select(GameSession).order_by(GameSession.updated_at.desc())
    return list(db.scalars(statement))


def get_session(db: Session, session_id: str) -> GameSession | None:
    return db.get(GameSession, session_id)


def get_player_state(db: Session, session_id: str) -> PlayerState | None:
    statement = select(PlayerState).where(PlayerState.session_id == session_id)
    return db.scalar(statement)


def rename_session(db: Session, game_session: GameSession, name: str) -> GameSession:
    game_session.name = name
    db.commit()
    db.refresh(game_session)
    return game_session


def delete_session(db: Session, game_session: GameSession) -> None:
    session_id = game_session.id
    # Delete dependent rows in foreign-key order so no orphaned save data remains.
    for model in (
        JournalEntry,
        LongTermMemory,
        StoryArcGenerationJob,
        StoryArc,
        StorySummary,
        Relationship,
        NPCState,
        TurnRecord,
        PlayerState,
    ):
        db.execute(delete(model).where(model.session_id == session_id))
    db.execute(delete(GameSession).where(GameSession.id == session_id))
    db.commit()


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def export_session(db: Session, game_session: GameSession) -> SaveExport:
    session_id = game_session.id
    player_state = get_player_state(db, session_id)
    if player_state is None:
        raise ValueError("角色状态不存在")

    turns = list_turns(db, session_id)
    return SaveExport.model_validate(
        {
            "schema_version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session": {
                "id": game_session.id,
                "name": game_session.name,
                "era_id": game_session.era_id,
                "status": game_session.status,
                "state_version": game_session.state_version,
                "created_at": _serialize_datetime(game_session.created_at),
                "updated_at": _serialize_datetime(game_session.updated_at),
            },
            "player_state": player_state.state,
            "npc_states": [
                {
                    "npc_id": item.npc_id,
                    "is_original_character": item.is_original_character,
                    "state": item.state,
                }
                for item in list_npcs(db, session_id)
            ],
            "relationships": [
                {
                    "source_id": item.source_id,
                    "target_id": item.target_id,
                    "state": item.state,
                }
                for item in list_relationships(db, session_id)
            ],
            "turns": [
                {
                    "id": item.id,
                    "sequence": item.sequence,
                    "client_action_id": item.client_action_id,
                    "action_type": item.action_type,
                    "action": item.action,
                    "response_type": item.response_type,
                    "narrative": item.narrative,
                    "llm_response": item.llm_response,
                    "proposed_changes": item.proposed_changes,
                    "authoritative_changes": item.authoritative_changes,
                    "memory_update": item.memory_update,
                    "worldline": item.worldline,
                    "prompt_version": item.prompt_version,
                    "model_name": item.model_name,
                    "state_version_before": item.state_version_before,
                    "state_version_after": item.state_version_after,
                    "created_at": _serialize_datetime(item.created_at),
                }
                for item in turns
            ],
            "journal_entries": [
                {
                    "turn_id": item.turn_id,
                    "entry_type": item.entry_type,
                    "title": item.title,
                    "summary": item.summary,
                    "data": item.data,
                    "created_at": _serialize_datetime(item.created_at),
                }
                for item in list_journal(db, session_id)
            ],
            "long_term_memories": [
                {
                    "title": item.title,
                    "summary": item.summary,
                    "event_type": item.event_type,
                    "status": item.status,
                    "importance": item.importance,
                    "time_text": item.time_text,
                    "location_id": item.location_id,
                    "actors": item.actors,
                    "keywords": item.keywords,
                    "facts": item.facts,
                    "open_threads": item.open_threads,
                    "resolved_threads": item.resolved_threads,
                    "source_turn_ids": item.source_turn_ids,
                    "related_data": item.related_data,
                    "created_at": _serialize_datetime(item.created_at),
                    "updated_at": _serialize_datetime(item.updated_at),
                }
                for item in list_memories(db, session_id)
            ],
            "story_summaries": [
                {
                    "scope": item.scope,
                    "scope_key": item.scope_key,
                    "summary": item.summary,
                    "causal_chain": item.causal_chain,
                    "open_threads": item.open_threads,
                    "covered_turn_start": item.covered_turn_start,
                    "covered_turn_end": item.covered_turn_end,
                    "version": item.version,
                    "updated_at": _serialize_datetime(item.updated_at),
                }
                for item in db.scalars(
                    select(StorySummary).where(StorySummary.session_id == session_id)
                )
            ],
            "story_arcs": [
                {
                    "scope_key": item.scope_key,
                    "status": item.status,
                    "title": item.title,
                    "summary": item.summary,
                    "causal_chain": item.causal_chain,
                    "open_threads": item.open_threads,
                    "key_characters": item.key_characters,
                    "key_locations": item.key_locations,
                    "keywords": item.keywords,
                    "important_turns": item.important_turns,
                    "source_turn_ids": item.source_turn_ids,
                    "covered_turn_start": item.covered_turn_start,
                    "covered_turn_end": item.covered_turn_end,
                    "version": item.version,
                    "updated_at": _serialize_datetime(item.updated_at),
                }
                for item in db.scalars(
                    select(StoryArc).where(StoryArc.session_id == session_id)
                )
            ],
        }
    )


def _import_name(name: str) -> str:
    suffix = "（导入）"
    return f"{name[: 200 - len(suffix)]}{suffix}"


def import_session(db: Session, payload: SaveExport) -> GameSession:
    session_data = payload.session
    era_id = (
        session_data.era_id
        if session_data.era_id in ERA_BY_ID
        else "second_generation"
    )
    imported_player_state = _normalize_imported_player_state(
        payload.player_state,
        era_id,
    )
    game_session = GameSession(
        name=_import_name(session_data.name),
        era_id=era_id,
        rule_version="v1",
        content_version="v1",
        status=session_data.status,
        state_version=session_data.state_version,
    )
    db.add(game_session)
    db.flush()

    db.add(PlayerState(session_id=game_session.id, state=imported_player_state))

    for item in payload.npc_states:
        db.add(
            NPCState(
                session_id=game_session.id,
                npc_id=str(item["npc_id"]),
                is_original_character=bool(item.get("is_original_character", True)),
                state=dict(item.get("state", {})),
            )
        )
    for item in payload.relationships:
        db.add(
            Relationship(
                session_id=game_session.id,
                source_id=str(item["source_id"]),
                target_id=str(item["target_id"]),
                state=dict(item.get("state", {})),
            )
        )

    turn_id_map: dict[str, str] = {}
    for item in payload.turns:
        old_id = str(item.get("id", ""))
        new_id = str(uuid4())
        if old_id:
            turn_id_map[old_id] = new_id
        db.add(
            TurnRecord(
                id=new_id,
                session_id=game_session.id,
                sequence=int(item["sequence"]),
                client_action_id=(
                    f"import-{uuid4()}" if item.get("client_action_id") else None
                ),
                action_type=str(item["action_type"]),
                action=dict(item.get("action", {})),
                response_type=item.get("response_type"),
                narrative=item.get("narrative"),
                llm_response=dict(item.get("llm_response", {})),
                proposed_changes=dict(item.get("proposed_changes", {})),
                authoritative_changes=dict(item.get("authoritative_changes", {})),
                memory_update=dict(item.get("memory_update", {})),
                worldline=dict(item.get("worldline", {})),
                prompt_version=item.get("prompt_version"),
                model_name=item.get("model_name"),
                state_version_before=int(item["state_version_before"]),
                state_version_after=int(item["state_version_after"]),
            )
        )

    for item in payload.journal_entries:
        old_turn_id = item.get("turn_id")
        db.add(
            JournalEntry(
                session_id=game_session.id,
                turn_id=turn_id_map.get(str(old_turn_id)) if old_turn_id else None,
                entry_type=str(item["entry_type"]),
                title=str(item["title"]),
                summary=str(item["summary"]),
                data=dict(item.get("data", {})),
            )
        )
    for item in payload.long_term_memories:
        db.add(
            LongTermMemory(
                memory_id=f"import-{uuid4()}",
                session_id=game_session.id,
                title=str(item["title"]),
                summary=str(item["summary"]),
                event_type=str(item["event_type"]),
                status=str(item.get("status", "open")),
                importance=int(item.get("importance", 5)),
                time_text=item.get("time_text"),
                location_id=item.get("location_id"),
                actors=list(item.get("actors", [])),
                keywords=list(item.get("keywords", [])),
                facts=list(item.get("facts", [])),
                open_threads=list(item.get("open_threads", [])),
                resolved_threads=list(item.get("resolved_threads", [])),
                source_turn_ids=[
                    turn_id_map.get(str(turn_id), str(turn_id))
                    for turn_id in item.get("source_turn_ids", [])
                ],
                related_data=dict(item.get("related_data", {})),
            )
        )
    for item in payload.story_summaries:
        db.add(
            StorySummary(
                session_id=game_session.id,
                scope=str(item["scope"]),
                scope_key=str(item["scope_key"]),
                summary=str(item.get("summary", "")),
                causal_chain=list(item.get("causal_chain", [])),
                open_threads=list(item.get("open_threads", [])),
                covered_turn_start=item.get("covered_turn_start"),
                covered_turn_end=item.get("covered_turn_end"),
                version=int(item.get("version", 1)),
            )
        )
    for item in payload.story_arcs:
        imported_source_turn_ids = [
            turn_id_map.get(str(turn_id), str(turn_id))
            for turn_id in item.get("source_turn_ids", [])
        ]
        covered_turn_start = item.get("covered_turn_start")
        covered_turn_end = item.get("covered_turn_end")
        db.add(
            StoryArc(
                session_id=game_session.id,
                scope_key=str(item["scope_key"]),
                status=str(item.get("status", "ready")),
                title=str(item["title"]),
                summary=str(item["summary"]),
                causal_chain=list(item.get("causal_chain", [])),
                open_threads=list(item.get("open_threads", [])),
                key_characters=list(item.get("key_characters", [])),
                key_locations=list(item.get("key_locations", [])),
                keywords=list(item.get("keywords", [])),
                important_turns=list(item.get("important_turns", [])),
                source_turn_ids=imported_source_turn_ids,
                covered_turn_start=covered_turn_start,
                covered_turn_end=covered_turn_end,
                version=int(item.get("version", 1)),
            )
        )
        if (
            str(item.get("status", "ready")) == "ready"
            and covered_turn_start is not None
            and covered_turn_end is not None
        ):
            db.add(
                StoryArcGenerationJob(
                    session_id=game_session.id,
                    status="ready",
                    request_id=f"import-arc-{uuid4()}",
                    source_turn_start=int(covered_turn_start),
                    source_turn_end=int(covered_turn_end),
                    source_turn_ids=imported_source_turn_ids,
                    source_state_version=session_data.state_version,
                    attempt=1,
                    completed_at=datetime.now(timezone.utc),
                )
            )

    db.commit()
    db.refresh(game_session)
    return game_session


def _normalize_imported_player_state(
    player_state: dict[str, Any],
    era_id: str,
) -> dict[str, Any]:
    """把旧存档和错误时代标记收束到可安全解释的状态。"""
    state = deepcopy(player_state)
    if era_id == "modern":
        return state

    # 现代字段不能进入子世代提示词；offset_rate 仍保留给旧世界线逻辑。
    state.pop("modern_arc", None)
    worldline = state.get("worldline")
    if isinstance(worldline, dict):
        state["worldline"] = {
            key: value
            for key, value in worldline.items()
            if key
            not in {
                "mode",
                "temporal_disturbance",
                "temporal_stability",
                "last_source",
                "triggered_thresholds",
                "current_timeline_id",
                "memory_status",
            }
        }
    return state


def list_journal(db: Session, session_id: str) -> list[JournalEntry]:
    return list(
        db.scalars(
            select(JournalEntry)
            .outerjoin(TurnRecord, JournalEntry.turn_id == TurnRecord.id)
            .where(JournalEntry.session_id == session_id)
            .order_by(
                TurnRecord.sequence.desc().nullslast(),
                JournalEntry.created_at.desc(),
                JournalEntry.id.desc(),
            )
        )
    )


def list_relationships(db: Session, session_id: str) -> list[Relationship]:
    return list(
        db.scalars(
            select(Relationship)
            .where(Relationship.session_id == session_id)
            .order_by(Relationship.source_id, Relationship.target_id)
        )
    )


def list_npcs(db: Session, session_id: str) -> list[NPCState]:
    return list(
        db.scalars(
            select(NPCState)
            .where(NPCState.session_id == session_id)
            .order_by(NPCState.npc_id)
        )
    )


def list_memories(db: Session, session_id: str) -> list[LongTermMemory]:
    return list(
        db.scalars(
            select(LongTermMemory)
            .where(LongTermMemory.session_id == session_id)
            .order_by(LongTermMemory.updated_at.desc())
        )
    )


def list_turns(db: Session, session_id: str) -> list[TurnRecord]:
    return list(
        db.scalars(
            select(TurnRecord)
            .where(TurnRecord.session_id == session_id)
            .order_by(TurnRecord.sequence.asc())
        )
    )

