from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.content.bonds import normalize_relationship_state
from backend.app.models import NPCState, Relationship
from backend.app.rules.state import apply_turn_rules
from backend.app.schemas.game import (
    NarrativeResponse,
    PlayerChanges,
    RelationshipCreationProposal,
)
from backend.app.services.turns import _apply_relationship_creations


def _state(*, age: int = 11, current_date: str = "1991-07-01") -> dict:
    return {
        "identity": {"age": age},
        "current_context": {
            "datetime": f"{current_date}T09:00:00",
            "current_date": current_date,
            "location_id": "hogwarts_castle",
        },
        "school": {"grade": "not_enrolled"},
        "reputation": {"score": 0},
        "romance": {"status": "single"},
        "resources": {},
    }


def _response(
    relationship_deltas: list[dict],
    *,
    current_date: str = "1991-07-01",
) -> NarrativeResponse:
    return NarrativeResponse.model_validate(
        {
            "response_type": "narrative",
            "turn": {
                "title": "羁绊变化",
                "narrative": "玩家与对方进行了真实互动。",
                "current_date": current_date,
                "location_id": "hogwarts_castle",
                "grade": "not_enrolled",
                "school_transition": None,
            },
            "choices": [
                {
                    "id": "choice_other",
                    "label": "其他",
                    "kind": "free_text",
                    "risk": "low",
                }
            ],
            "player_changes": {
                "relationship_deltas": relationship_deltas,
            },
            "worldline": {"offset_rate": 0},
        }
    )


def _relationship(state: dict | None = None) -> Relationship:
    return Relationship(
        session_id="session",
        source_id="player",
        target_id="ivy_moore",
        state=state
        or {
            "affinity": 20,
            "trust": 10,
            "stage": "friend",
            "romance_state": "unavailable",
        },
    )


def test_legacy_romance_stage_is_normalized_to_canonical_fields() -> None:
    normalized = normalize_relationship_state(
        {
            "affinity": "25",
            "trust": "bad-value",
            "stage": "dating",
            "romance_state": "unavailable",
        },
        player_age=14,
    )

    assert normalized["affinity"] == 25
    assert normalized["trust"] == 0
    assert normalized["stage"] == "close_friend"
    assert normalized["romance_stage"] == "dating"


def test_relationship_schema_rejects_unknown_stage_and_large_delta() -> None:
    with pytest.raises(ValidationError):
        PlayerChanges.model_validate(
            {
                "relationship_deltas": [
                    {
                        "npc_id": "ivy_moore",
                        "affinity_delta": 99,
                        "stage": "soulmate",
                    }
                ]
            }
        )


def test_under_twelve_romance_is_queued_without_changing_stage() -> None:
    relationship = _relationship()
    next_state, changes = apply_turn_rules(
        _state(age=11),
        [relationship],
        _response(
            [
                {
                    "npc_id": "ivy_moore",
                    "romance_stage": "dating",
                    "reason": "双方表达了亲近意愿",
                    "evidence": "本轮进行了明确对话",
                }
            ]
        ),
        npc_ages={"ivy_moore": 11},
    )

    assert relationship.state["romance_stage"] == "locked"
    assert relationship.state["pending_unlocks"] == [
        {
            "romance_stage": "dating",
            "required_age": 12,
            "reason": "双方表达了亲近意愿",
        }
    ]
    assert next_state["romance"]["status"] == "single"
    assert not changes.get("relationship_rejections")


def test_numeric_relationship_change_requires_reason_and_evidence() -> None:
    relationship = _relationship()
    _, changes = apply_turn_rules(
        _state(age=11),
        [relationship],
        _response(
            [
                {
                    "npc_id": "ivy_moore",
                    "affinity_delta": 4,
                }
            ]
        ),
        npc_ages={"ivy_moore": 11},
    )

    assert relationship.state["affinity"] == 20
    assert changes["relationship_rejections"][0]["reason"] == (
        "relationship_change_missing_evidence"
    )


def test_two_minors_can_date_but_adult_minor_pair_is_rejected() -> None:
    minor_relationship = _relationship()
    state, _ = apply_turn_rules(
        _state(age=13),
        [minor_relationship],
        _response(
            [
                {
                    "npc_id": "ivy_moore",
                    "romance_stage": "dating",
                    "reason": "双方确认开始交往",
                    "evidence": "NPC 明确接受",
                }
            ]
        ),
        npc_ages={"ivy_moore": 13},
    )
    assert minor_relationship.state["romance_stage"] == "dating"
    assert state["romance"]["status"] == "dating"

    mixed_relationship = _relationship()
    _, changes = apply_turn_rules(
        _state(age=18),
        [mixed_relationship],
        _response(
            [
                {
                    "npc_id": "ivy_moore",
                    "romance_stage": "dating",
                    "reason": "模型提出恋爱",
                    "evidence": "本轮有互动",
                }
            ]
        ),
        npc_ages={"ivy_moore": 16},
    )
    assert mixed_relationship.state["romance_stage"] == "none"
    assert changes["relationship_rejections"][0]["reason"] == "romance_age_incompatible"


def test_impossible_pending_romance_is_removed() -> None:
    relationship = _relationship(
        {
            "affinity": 20,
            "trust": 10,
            "stage": "friend",
            "romance_stage": "locked",
            "pending_unlocks": [
                {
                    "romance_stage": "dating",
                    "required_age": 12,
                    "reason": "等待年龄条件",
                }
            ],
        }
    )
    apply_turn_rules(
        _state(age=18),
        [relationship],
        _response([]),
        npc_ages={"ivy_moore": 11},
    )

    assert relationship.state["romance_stage"] == "none"
    assert relationship.state["pending_unlocks"] == []


def test_social_stage_requires_threshold_and_single_step() -> None:
    relationship = _relationship(
        {"affinity": 0, "trust": 0, "stage": "stranger"}
    )
    _, changes = apply_turn_rules(
        _state(age=11),
        [relationship],
        _response(
            [
                {
                    "npc_id": "ivy_moore",
                    "affinity_delta": 5,
                    "trust_delta": 5,
                    "stage": "acquaintance",
                    "reason": "第一次认真交谈",
                    "evidence": "双方交换了姓名",
                }
            ]
        ),
        npc_ages={"ivy_moore": 11},
    )
    assert relationship.state["stage"] == "acquaintance"
    assert changes["relationships"][0]["after"]["affinity"] == 5

    relationship.state = {
        **relationship.state,
        "affinity": 60,
        "trust": 50,
        "stage": "acquaintance",
    }
    _, changes = apply_turn_rules(
        _state(age=11),
        [relationship],
        _response(
            [
                {
                    "npc_id": "ivy_moore",
                    "stage": "close_friend",
                    "reason": "模型试图跨级",
                    "evidence": "一次普通谈话",
                }
            ]
        ),
        npc_ages={"ivy_moore": 11},
    )
    assert relationship.state["stage"] == "acquaintance"
    assert changes["relationship_rejections"][0]["reason"] == "social_stage_skip"


def test_age_uses_current_turn_date_without_one_turn_delay() -> None:
    state = _state(age=11, current_date="1992-08-31")
    state["identity"]["birthday"] = "1980-09-01"
    next_state, _ = apply_turn_rules(
        state,
        [],
        _response([], current_date="1992-09-01"),
    )

    assert next_state["identity"]["age"] == 12


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)


def test_model_can_create_one_new_npc_and_player_bond() -> None:
    db = _FakeSession()
    proposal = RelationshipCreationProposal.model_validate(
        {
            "character": {
                "name": "艾薇·摩尔",
                "role": "学生",
                "age": 11,
                "age_band": "minor",
                "location_id": "library",
                "personality": "谨慎、喜欢观察",
                "appearance": "深色卷发",
            },
            "bond": {
                "bond_type": "friendship",
                "affinity_delta": 6,
                "trust_delta": 5,
                "stage": "acquaintance",
                "romance_stage": "none",
            },
            "reason": "玩家帮助她找回课本。",
            "evidence": "双方在图书馆进行了持续对话。",
        }
    )

    result = _apply_relationship_creations(
        db,  # type: ignore[arg-type]
        "session",
        "action",
        [proposal],
        date(1991, 9, 3),
        [],
        [],
    )

    assert len(result["created"]) == 1
    assert result["created"][0]["npc_id"].startswith("model_npc_")
    relationship = result["relationships"][0]
    assert relationship.source_id == "player"
    assert relationship.state["stage"] == "acquaintance"
    assert relationship.state["romance_stage"] == "none"
    npc = next(item for item in db.added if isinstance(item, NPCState))
    assert npc.state["origin"] == "model_created"


def test_duplicate_generated_npc_is_rejected() -> None:
    db = _FakeSession()
    existing = NPCState(
        session_id="session",
        npc_id="existing_ivy",
        is_original_character=False,
        state={"name": "艾薇·摩尔", "aliases": [], "age": 11},
    )
    proposal = RelationshipCreationProposal.model_validate(
        {
            "character": {"name": "艾薇 摩尔", "age": 11},
            "reason": "再次出现",
            "evidence": "同一个人",
        }
    )

    result = _apply_relationship_creations(
        db,  # type: ignore[arg-type]
        "session",
        "action",
        [proposal],
        date(1991, 9, 4),
        [existing],
        [],
    )

    assert result["created"] == []
    assert result["rejected"][0]["reason"] == "relationship_duplicate"
