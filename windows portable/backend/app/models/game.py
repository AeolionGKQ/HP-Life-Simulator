from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


def empty_dict() -> dict[str, Any]:
    return {}


def empty_list() -> list[Any]:
    return []


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    era_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    content_version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="setup", nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class PlayerState(Base):
    __tablename__ = "player_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("game_sessions.id"), unique=True, nullable=False
    )
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=empty_dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class NPCState(Base):
    __tablename__ = "npc_states"
    __table_args__ = (
        Index("ix_npc_session_npc_id", "session_id", "npc_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    npc_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_original_character: Mapped[bool] = mapped_column(default=True, nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=empty_dict, nullable=False)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        Index(
            "ix_relationship_session_source_target",
            "session_id",
            "source_id",
            "target_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=empty_dict, nullable=False)


class TurnRecord(Base):
    __tablename__ = "turn_records"
    __table_args__ = (
        Index(
            "ix_turn_session_client_action",
            "session_id",
            "client_action_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    client_action_id: Mapped[str | None] = mapped_column(String(100))
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[dict[str, Any]] = mapped_column(JSON, default=empty_dict, nullable=False)
    response_type: Mapped[str | None] = mapped_column(String(40))
    narrative: Mapped[str | None] = mapped_column(Text)
    llm_response: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=empty_dict, nullable=False
    )
    proposed_changes: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=empty_dict, nullable=False
    )
    authoritative_changes: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=empty_dict, nullable=False
    )
    memory_update: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=empty_dict, nullable=False
    )
    worldline: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=empty_dict, nullable=False
    )
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(200))
    state_version_before: Mapped[int] = mapped_column(Integer, nullable=False)
    state_version_after: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    turn_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("turn_records.id"))
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=empty_dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class LongTermMemory(Base):
    __tablename__ = "long_term_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    time_text: Mapped[str | None] = mapped_column(String(100))
    location_id: Mapped[str | None] = mapped_column(String(100))
    actors: Mapped[list[Any]] = mapped_column(JSON, default=empty_list, nullable=False)
    keywords: Mapped[list[Any]] = mapped_column(JSON, default=empty_list, nullable=False)
    facts: Mapped[list[Any]] = mapped_column(JSON, default=empty_list, nullable=False)
    open_threads: Mapped[list[Any]] = mapped_column(JSON, default=empty_list, nullable=False)
    resolved_threads: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    source_turn_ids: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    related_data: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=empty_dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class StorySummary(Base):
    __tablename__ = "story_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    causal_chain: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    open_threads: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    covered_turn_start: Mapped[int | None] = mapped_column(Integer)
    covered_turn_end: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class StoryArc(Base):
    __tablename__ = "story_arcs"
    __table_args__ = (
        Index("ix_story_arc_session_scope_key", "session_id", "scope_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    scope_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ready", nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    causal_chain: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    open_threads: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    key_characters: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    key_locations: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    keywords: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    important_turns: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    source_turn_ids: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    covered_turn_start: Mapped[int | None] = mapped_column(Integer)
    covered_turn_end: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class StoryArcGenerationJob(Base):
    __tablename__ = "story_arc_generation_jobs"
    __table_args__ = (
        Index(
            "ix_story_arc_job_session_range",
            "session_id",
            "source_turn_start",
            "source_turn_end",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("game_sessions.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_turn_start: Mapped[int] = mapped_column(Integer, nullable=False)
    source_turn_end: Mapped[int] = mapped_column(Integer, nullable=False)
    source_turn_ids: Mapped[list[Any]] = mapped_column(
        JSON, default=empty_list, nullable=False
    )
    source_state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
