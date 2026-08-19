from __future__ import annotations

from typing import Any

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
    TurnRecord,
)


def initial_player_state() -> dict[str, Any]:
    return {
        "setup": {
            "current_step": 1,
            "completed": False,
            "answers": {},
        },
        "identity": {},
        "appearance": {},
        "family": {},
        "background": {},
        "personality": {},
        "values": {},
        "school": {
            "house": None,
            "year_level": 1,
            "school_year": "1991-1992",
        },
        "vitals": {
            "hp": 100,
            "max_hp": 100,
            "mp": 100,
            "max_mp": 100,
            "sp": 100,
            "max_sp": 100,
            "energy": 100,
            "satiety": 100,
            "conditions": [],
        },
        "attributes": {
            "courage": 0,
            "wisdom": 0,
            "loyalty": 0,
            "ambition": 0,
        },
        "skills": {},
        "wand": None,
        "currency": {"galleons": 0, "sickles": 0, "knuts": 0},
        "inventory": [],
        "pet": None,
        "current_context": {
            "datetime": "1991-07-01T09:00:00",
            "period": "morning",
            "location_id": "home",
            "activity": "character_setup",
        },
        "reputation": {},
        "romance": {
            "status": "single",
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
    player_state = get_player_state(db, game_session.id)
    if player_state:
        db.delete(player_state)
    db.delete(game_session)
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

