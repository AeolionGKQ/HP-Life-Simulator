from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SetupOption(BaseModel):
    id: str
    label: str
    description: str = ""
    value: str | None = None
    category: str = ""
    appendable: bool = False
    available: bool = True


class SetupStep(BaseModel):
    step: int = Field(ge=1, le=18)
    title: str
    description: str
    options: list[SetupOption] = []
    selection_mode: Literal["single", "append", "text", "confirm"] = "single"


class SetupView(BaseModel):
    current_step: int
    completed: bool
    steps_total: int = 18
    era_id: str = ""
    current: SetupStep
    answers: dict[str, Any]
    attribute_initialization: dict[str, Any] = {}


class SetupAnswer(BaseModel):
    step: int = Field(ge=1, le=17)
    answer: Any


class SetupConfirm(BaseModel):
    confirmed: bool = True


RESOURCE_ID = Literal["health", "mana", "sanity", "energy", "satiety"]
DIMENSION_ID = Literal[
    "constitution",
    "intelligence",
    "willpower",
    "charisma",
    "magical_power",
]


class ResourceDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: RESOURCE_ID
    delta: float
    reason_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)


class DimensionDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: DIMENSION_ID
    delta: float
    reason_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)


class ResourceCapDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: RESOURCE_ID
    delta: float
    reason_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    permanent: bool = True


class DimensionCapDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: DIMENSION_ID
    delta: float
    reason_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=500)
    permanent: bool = True


class InitialResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: RESOURCE_ID
    value: float
    max: float
    reason: str = Field(min_length=1, max_length=500)


class InitialDimension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: DIMENSION_ID
    value: float
    max: float
    reason: str = Field(min_length=1, max_length=500)


class AttributeInitializationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_type: Literal["attribute_initialization"]
    schema_version: Literal["1.2"]
    resources: list[InitialResource]
    dimensions: list[InitialDimension]
    calibration_summary: str = ""
    self_check: dict[str, Any] = {}


class TraitEntry(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    polarity: Literal["positive", "negative"] = "positive"
    source: str = ""
    reason: str = ""


class ChoiceEffect(BaseModel):
    id: str = ""
    name: str
    type: Literal[
        "item",
        "status",
        "skill",
        "trait",
        "resource",
        "dimension",
        "resource_cap",
        "dimension_cap",
        "relationship",
    ]
    direction: Literal["gain", "loss", "change"]
    description: str = ""


class ChoiceEffects(BaseModel):
    gains: list[ChoiceEffect] = []
    losses: list[ChoiceEffect] = []
    note: str = ""


class PlayerChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inventory_add: list[dict[str, Any]] = []
    inventory_remove: list[str] = []
    status_add: list[dict[str, Any]] = []
    status_remove: list[str] = []
    skill_add: list[dict[str, Any]] = []
    skill_remove: list[str] = []
    skill_deltas: dict[str, int] = {}
    skill_experience_deltas: dict[str, int] = {}
    course_skill_deltas: dict[str, int] = {}
    trait_add: list[TraitEntry] = []
    trait_remove: list[str] = []
    resource_deltas: list[ResourceDelta] = []
    dimension_deltas: list[DimensionDelta] = []
    resource_cap_deltas: list[ResourceCapDelta] = []
    dimension_cap_deltas: list[DimensionCapDelta] = []
    reputation_deltas: dict[str, int] = {}
    relationship_deltas: list[dict[str, Any]] = []


GRADE_ID = Literal[
    "not_enrolled",
    "year_1",
    "year_2",
    "year_3",
    "year_4",
    "year_5",
    "year_6",
    "year_7",
    "left_school",
]


class SchoolTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["enrollment", "promotion", "departure"]
    from_grade: GRADE_ID
    to_grade: GRADE_ID
    reason: Literal[
        "sorting_completed",
        "new_school_year_started",
        "graduated_after_newts",
        "left_after_owls",
        "dropout",
        "expelled",
        "medical_departure",
        "other_permanent_departure",
    ]
    evidence: str = Field(min_length=1, max_length=500)


class Choice(BaseModel):
    id: str
    label: str
    kind: str = "action"
    risk: Literal["low", "medium", "high", "fatal"]
    requires: list[str] = []
    effects_hint: str = ""
    effects: ChoiceEffects = ChoiceEffects()


class WorldlineResponse(BaseModel):
    offset_rate: float = Field(ge=0, le=100)
    delta: float = 0
    reason: str = ""
    affected_nodes: list[str] = []


class LongTermMemoryProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str | None = None
    title: str = ""
    summary: str = Field(min_length=1)
    event_type: str = "important_event"
    status: str = "open"
    importance: int = Field(default=5, ge=1, le=10, strict=True)
    time: str | None = None
    location_id: str | None = None
    actors: list[str] = []
    keywords: list[str] = []
    facts: list[str] = []
    open_threads: list[str] = []
    resolved_threads: list[str] = []
    related_data: dict[str, Any] = {}


class MemoryUpdate(BaseModel):
    summary: str = ""
    create_long_term_memory: bool = False
    memory: LongTermMemoryProposal | None = None
    resolved_memory_ids: list[str] = []

    @model_validator(mode="after")
    def require_memory_when_creating(self) -> MemoryUpdate:
        if self.create_long_term_memory and self.memory is None:
            raise ValueError("创建长期记忆时 memory 不能为空")
        return self


class NarrativeTurn(BaseModel):
    title: str
    scene_type: str = "dialogue"
    narrative: str
    current_date: date
    location_id: str
    grade: GRADE_ID | None = None
    school_transition: SchoolTransition | None = None
    time_advance_minutes: int = Field(default=0, ge=0)


class NarrativeResponse(BaseModel):
    response_type: Literal["narrative"]
    turn: NarrativeTurn
    choices: list[Choice]
    state_proposals: dict[str, Any] = {}
    player_changes: PlayerChanges = PlayerChanges()
    applied_changes: PlayerChanges = PlayerChanges()
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


class CourseOption(BaseModel):
    id: str
    name: str
    description: str
    category: str
    available: bool
    unavailable_reason: str | None = None
    skill_id: str
    skill_level: int = Field(ge=0, le=10)


class CourseSkill(BaseModel):
    id: str
    name: str
    description: str = ""
    level: int = Field(ge=0, le=10)
    experience: int = Field(default=0, ge=0, le=100)
    source: str = "course"
    course_id: str


class CourseSelection(BaseModel):
    status: Literal["pending", "completed"] | None = None
    phase: Literal["elective", "newt"] | None = None
    min_courses: int = Field(default=0, ge=0)
    max_courses: int = Field(default=0, ge=0)
    available_course_ids: list[str] = []


class CourseResult(BaseModel):
    id: str
    name: str
    grade: str


class CourseHistoryEntry(BaseModel):
    school_year: str
    grade: GRADE_ID
    active_courses: list[str] = []
    selected_courses: list[str] = []
    skill_progression: dict[str, int] = {}


class CourseView(BaseModel):
    session_id: str
    state_version: int
    grade: GRADE_ID
    school_year: str
    term: str
    active_courses: list[CourseOption]
    selection_options: list[CourseOption] = []
    editable_phase: Literal["elective", "newt"] | None = None
    elective_courses: list[str]
    newt_courses: list[str]
    skills: list[CourseSkill]
    owl_results: list[CourseResult] = []
    newt_results: list[CourseResult] = []
    course_selection: CourseSelection | None = None
    course_history: list[CourseHistoryEntry] = []


class CourseSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(ge=0)
    selection_phase: Literal["elective", "newt"]
    course_ids: list[str] = Field(min_length=1, max_length=5)


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

