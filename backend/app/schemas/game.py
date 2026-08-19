from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SetupOption(BaseModel):
    id: str
    label: str
    description: str = ""


class SetupStep(BaseModel):
    step: int = Field(ge=1, le=13)
    title: str
    description: str
    options: list[SetupOption] = []


class SetupView(BaseModel):
    current_step: int
    completed: bool
    steps_total: int = 13
    current: SetupStep
    answers: dict[str, Any]


class SetupAnswer(BaseModel):
    step: int = Field(ge=1, le=13)
    answer: Any


class SetupConfirm(BaseModel):
    confirmed: bool = True


class Choice(BaseModel):
    id: str
    label: str
    kind: str = "action"
    risk: str = "unknown"
    requires: list[str] = []
    effects_hint: str = ""


class WorldlineResponse(BaseModel):
    offset_rate: float = Field(ge=0, le=100)
    delta: float = 0
    reason: str = ""
    affected_nodes: list[str] = []


class MemoryUpdate(BaseModel):
    summary: str = ""
    create_long_term_memory: bool = False
    memory: dict[str, Any] | None = None
    resolved_memory_ids: list[str] = []


class NarrativeTurn(BaseModel):
    title: str
    scene_type: str = "dialogue"
    narrative: str
    location_id: str | None = None
    time_advance_minutes: int = Field(default=0, ge=0)


class NarrativeResponse(BaseModel):
    response_type: Literal["narrative"]
    turn: NarrativeTurn
    choices: list[Choice]
    state_proposals: dict[str, Any] = {}
    worldline: WorldlineResponse
    events: list[dict[str, Any]] = []
    memory_update: MemoryUpdate = MemoryUpdate()
    self_check: dict[str, Any] = {}


class MemoryRequest(BaseModel):
    response_type: Literal["memory_request"]
    memory_request: dict[str, Any]


class ActionRequest(BaseModel):
    client_action_id: str = Field(min_length=1, max_length=100)
    expected_state_version: int = Field(ge=0)
    kind: Literal["choice", "free_text", "fast_forward"] = "choice"
    choice_id: str | None = None
    free_text: str | None = Field(default=None, max_length=4000)


class TurnResponse(BaseModel):
    turn_id: str
    sequence: int
    response: NarrativeResponse
    state_version: int
    recalled_memory_ids: list[str] = []


class PlayerStateResponse(BaseModel):
    session_id: str
    state_version: int
    state: dict[str, Any]


class JournalRead(BaseModel):
    id: str
    turn_id: str | None
    entry_type: str
    title: str
    summary: str
    data: dict[str, Any]
    created_at: str


class RelationshipRead(BaseModel):
    source_id: str
    target_id: str
    state: dict[str, Any]


class NPCRead(BaseModel):
    npc_id: str
    is_original_character: bool
    state: dict[str, Any]


class MemoryRead(BaseModel):
    memory_id: str
    title: str
    summary: str
    event_type: str
    status: str
    importance: int
    time: str | None
    location_id: str | None
    actors: list[Any]
    keywords: list[Any]
    facts: list[Any]
    open_threads: list[Any]

