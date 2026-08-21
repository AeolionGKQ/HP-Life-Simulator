from datetime import date

import pytest

from backend.app.content.reputation import get_reputation_level, normalize_reputation
from backend.app.rules.state import apply_turn_rules
from backend.app.schemas.game import NarrativeResponse


def _response(delta: object = None) -> NarrativeResponse:
    proposals = {} if delta is None else {"reputation_deltas": delta}
    return NarrativeResponse.model_validate(
        {
            "response_type": "narrative",
            "turn": {
                "title": "声望测试",
                "narrative": "测试剧情。",
                "current_date": date(1991, 9, 1),
                "location_id": "hogwarts",
            },
            "choices": [],
            "player_changes": {},
            "state_proposals": proposals,
            "worldline": {"offset_rate": 0},
        }
    )


@pytest.mark.parametrize(
    ("score", "level_id"),
    [
        (-100, "dark_paragon"),
        (-81, "dark_paragon"),
        (-80, "black_wizard"),
        (-61, "black_wizard"),
        (-60, "dangerous"),
        (-31, "dangerous"),
        (-30, "suspicious"),
        (-11, "suspicious"),
        (-10, "neutral"),
        (10, "neutral"),
        (11, "kindly"),
        (30, "kindly"),
        (31, "trusted"),
        (60, "trusted"),
        (61, "white_wizard"),
        (80, "white_wizard"),
        (81, "light_paragon"),
        (100, "light_paragon"),
    ],
)
def test_reputation_levels_use_fixed_boundaries(score: int, level_id: str) -> None:
    assert get_reputation_level(score)["id"] == level_id


def test_reputation_normalization_does_not_turn_legacy_breakdowns_into_morality() -> None:
    normalized = normalize_reputation({"ravenclaw": 8, "academic": 3})

    assert normalized["score"] == 0
    assert normalized["level_id"] == "neutral"
    assert normalized["legacy_breakdown"] == {"ravenclaw": 8, "academic": 3}


def test_reputation_applies_delta_and_recomputes_level() -> None:
    state = {
        "reputation": {"score": 24},
        "current_context": {
            "datetime": "1991-09-01T09:00:00+00:00",
            "current_date": "1991-09-01",
            "location_id": "home",
        },
    }

    next_state, changes = apply_turn_rules(state, [], _response({"score": 8}))

    assert next_state["reputation"]["score"] == 32
    assert next_state["reputation"]["level_id"] == "trusted"
    assert next_state["reputation"]["last_delta"] == 8
    assert changes["reputation"]["applied_delta"] == 8
    assert changes["reputation"]["level_before"] == "kindly"
    assert changes["reputation"]["level_after"] == "trusted"


def test_reputation_clamps_single_turn_delta_and_total_score() -> None:
    state = {
        "reputation": {"score": 96},
        "current_context": {
            "datetime": "1991-09-01T09:00:00+00:00",
            "current_date": "1991-09-01",
            "location_id": "home",
        },
    }

    next_state, changes = apply_turn_rules(state, [], _response({"score": 25}))

    assert next_state["reputation"]["score"] == 100
    assert next_state["reputation"]["last_delta"] == 4
    assert changes["reputation"]["requested_delta"] == 25
    assert changes["reputation"]["applied_delta"] == 4


def test_reputation_rejects_unknown_keys_and_invalid_values_without_crashing() -> None:
    state = {
        "reputation": {"score": 0},
        "current_context": {
            "datetime": "1991-09-01T09:00:00+00:00",
            "current_date": "1991-09-01",
            "location_id": "home",
        },
    }

    next_state, changes = apply_turn_rules(
        state,
        [],
        _response({"morality": 8, "score": "bad"}),
    )

    assert next_state["reputation"]["score"] == 0
    assert {item["reason"] for item in changes["reputation"]["rejected"]} == {
        "unknown_reputation_key",
        "invalid_reputation_delta",
    }


def test_black_wizard_reputation_automatically_expelled_and_clears_courses() -> None:
    state = {
        "reputation": {"score": -60},
        "school": {
            "grade": "year_3",
            "house": "slytherin",
            "enrollment_started": True,
            "active_courses": ["charms"],
            "elective_courses": ["divination"],
            "newt_courses": [],
            "course_selection": None,
            "course_history": [],
        },
        "skills": {
            "charms": {
                "id": "charms",
                "name": "咒语",
                "level": 3,
                "experience": 40,
                "course_skill": True,
            },
        },
        "current_context": {
            "datetime": "1993-09-01T09:00:00+00:00",
            "current_date": "1993-09-01",
            "location_id": "hogwarts",
        },
    }

    next_state, changes = apply_turn_rules(state, [], _response({"score": -1}))

    school = next_state["school"]
    assert school["grade"] == "left_school"
    assert school["departure_reason"] == "expelled"
    assert school["active_courses"] == []
    assert school["elective_courses"] == []
    assert school["course_selection"] is None
    assert school["departure_notice"]["status"] == "pending"
    assert next_state["skills"]["charms"]["level"] == 3
    assert changes["automatic_expulsion"]["reason"] == "reputation_reached_black_wizard"
