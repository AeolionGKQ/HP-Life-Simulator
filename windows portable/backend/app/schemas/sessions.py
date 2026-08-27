from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    era_id: str
    status: str
    state_version: int
    created_at: datetime
    updated_at: datetime


class SessionDetail(SessionRead):
    player_state: dict[str, Any]


class SessionRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SaveExport(BaseModel):
    schema_version: Literal["1.0"]
    exported_at: datetime
    session: SessionRead
    player_state: dict[str, Any]
    npc_states: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    turns: list[dict[str, Any]]
    journal_entries: list[dict[str, Any]]
    long_term_memories: list[dict[str, Any]]
    story_summaries: list[dict[str, Any]]
    story_arcs: list[dict[str, Any]]
