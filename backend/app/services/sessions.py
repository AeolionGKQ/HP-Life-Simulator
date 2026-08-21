from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.content.attributes import initial_dimensions, initial_resources
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
        "letters": [],
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
        StorySummary,
        Relationship,
        NPCState,
        TurnRecord,
        PlayerState,
    ):
        db.execute(delete(model).where(model.session_id == session_id))
    db.execute(delete(GameSession).where(GameSession.id == session_id))
    db.commit()


def list_journal(db: Session, session_id: str) -> list[JournalEntry]:
    return list(
        db.scalars(
            select(JournalEntry)
            .where(JournalEntry.session_id == session_id)
            .order_by(JournalEntry.created_at.desc())
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

