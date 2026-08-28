from datetime import date

import pytest
from sqlalchemy import select

from backend.app.content.courses import (
    COURSE_CATALOG,
    FIRST_YEAR_REQUIRED_COURSE_IDS,
)
from backend.app.db.session import get_session_factory
from backend.app.main import create_app
from backend.app.models import GameSession, PlayerState, TurnRecord
from backend.app.rules.state import apply_turn_rules
from backend.app.schemas.game import NarrativeResponse
from backend.app.services.courses import get_courses_view
from fastapi.testclient import TestClient


def _response(
    current_date: str,
    *,
    grade: str | None = None,
    transition: dict | None = None,
    player_changes: dict | None = None,
    events: list[dict] | None = None,
) -> NarrativeResponse:
    return NarrativeResponse.model_validate(
        {
            "response_type": "narrative",
            "turn": {
                "title": "课程测试",
                "narrative": "测试剧情。",
                "current_date": current_date,
                "location_id": "hogwarts",
                "grade": grade,
                "school_transition": transition,
            },
            "choices": [],
            "player_changes": player_changes or {},
            "events": events or [],
            "worldline": {"offset_rate": 0},
        }
    )


def _enrolled_state() -> dict:
    return {
        "school": {
            "grade": "year_1",
            "house": "gryffindor",
            "enrollment_started": True,
            "school_year": "1991-1992",
            "grade_started_year": 1991,
            "last_grade_promotion_key": None,
            "last_course_progression_year": None,
            "term": "autumn",
            "active_courses": list(FIRST_YEAR_REQUIRED_COURSE_IDS),
            "elective_courses": [],
            "newt_courses": [],
            "course_selection": None,
            "course_history": [],
        },
        "skills": {
            course_id: {
                "id": course_id,
                "name": COURSE_CATALOG[course_id]["name"],
                "level": 0,
                "experience": 0,
                "source": "course",
                "course_id": course_id,
                "course_skill": True,
            }
            for course_id in FIRST_YEAR_REQUIRED_COURSE_IDS
        },
        "current_context": {
            "datetime": "1991-09-01T09:00:00+00:00",
            "current_date": "1991-09-01",
            "location_id": "hogwarts",
        },
        "identity": {},
    }


def test_parent_generation_auto_graduates_year_seven_after_1978() -> None:
    state = _enrolled_state()
    state["school"].update(
        {
            "grade": "year_7",
            "school_year": "1977-1978",
            "grade_started_year": 1977,
            "departure_reason": None,
        }
    )
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response("1978-07-01", grade="year_7"),
        era_id="parent_generation",
    )
    assert next_state["school"]["grade"] == "left_school"
    assert next_state["school"]["departure_reason"] == "graduated_after_newts"
    assert next_state["school"]["active_courses"] == []
    assert changes["school_grade"]["reason"] == "graduated_after_newts"


def test_parent_generation_does_not_overwrite_existing_non_graduation_departure() -> None:
    state = _enrolled_state()
    state["school"].update({"grade": "left_school", "departure_reason": "expelled"})
    next_state, _ = apply_turn_rules(
        state,
        [],
        _response("1978-07-01", grade="left_school"),
        era_id="parent_generation",
    )
    assert next_state["school"]["grade"] == "left_school"
    assert next_state["school"]["departure_reason"] == "expelled"


def test_enrollment_creates_first_year_courses_and_zero_level_skills() -> None:
    state = _enrolled_state()
    state["school"]["grade"] = "not_enrolled"
    state["school"]["enrollment_started"] = False
    state["school"]["sorting_completed"] = False
    state["school"]["active_courses"] = []
    state["skills"] = {}
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            "1991-09-01",
            grade="year_1",
            transition={
                "type": "enrollment",
                "from_grade": "not_enrolled",
                "to_grade": "year_1",
                "reason": "sorting_completed",
                "evidence": "分院仪式完成",
            },
            events=[{
                "type": "sorting_completed",
                "evidence": "分院仪式完成",
            }],
        ),
    )
    assert next_state["school"]["active_courses"] == list(FIRST_YEAR_REQUIRED_COURSE_IDS)
    assert all(
        next_state["skills"][course_id]["level"] == 0
        for course_id in FIRST_YEAR_REQUIRED_COURSE_IDS
    )
    assert "school_grade" in changes


def test_story_milestone_events_unlock_wand_and_sorting_state() -> None:
    state = _enrolled_state()
    state["school"]["grade"] = "not_enrolled"
    state["school"]["enrollment_started"] = False
    state["school"]["sorting_completed"] = False
    state["wand"] = {
        "description": "冬青木，独角兽毛",
        "obtained": False,
        "status": "not_obtained",
    }
    state["story_milestones"] = {
        "wand_obtained": False,
        "sorting_completed": False,
    }
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            "1991-07-10",
            events=[
                {
                    "type": "wand_obtained",
                    "evidence": "奥利凡德完成试杖后，角色正式获得这根魔杖。",
                },
                {
                    "type": "sorting_completed",
                    "evidence": "分院帽完成分院并宣布学院归属。",
                },
            ],
        ),
    )

    assert next_state["wand"]["obtained"] is True
    assert next_state["wand"]["status"] == "obtained"
    assert next_state["school"]["sorting_completed"] is True
    assert next_state["story_milestones"] == {
        "wand_obtained": True,
        "sorting_completed": True,
    }
    assert [item["type"] for item in changes["story_milestones"]["applied"]] == [
        "wand_obtained",
        "sorting_completed",
    ]


def test_june_progression_is_idempotent_and_does_not_change_grade() -> None:
    state = _enrolled_state()
    progressed, changes = apply_turn_rules(
        state,
        [],
        _response("1992-06-01", grade="year_1"),
    )
    repeated, repeated_changes = apply_turn_rules(
        progressed,
        [],
        _response("1992-06-02", grade="year_1"),
    )
    assert progressed["school"]["grade"] == "year_1"
    assert progressed["skills"]["charms"]["level"] == 1
    assert changes["course_skills"]["applied"]["charms"] == 1
    assert repeated["skills"]["charms"]["level"] == 1
    assert "course_skills" not in repeated_changes


def test_departure_clears_current_courses_and_skips_june_progression() -> None:
    state = _enrolled_state()
    state["school"]["elective_courses"] = ["divination"]
    state["school"]["newt_courses"] = ["alchemy"]
    state["school"]["course_selection"] = {
        "status": "pending",
        "phase": "elective",
        "min_courses": 2,
        "max_courses": 3,
        "available_course_ids": ["divination"],
    }
    state["school"]["course_history"] = [{"school_year": "1990-1991"}]

    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            "1992-06-01",
            grade="left_school",
            transition={
                "type": "departure",
                "from_grade": "year_1",
                "to_grade": "left_school",
                "reason": "dropout",
                "evidence": "玩家明确申请退学并完成离校手续。",
            },
        ),
    )

    school = next_state["school"]
    assert school["grade"] == "left_school"
    assert school["active_courses"] == []
    assert school["elective_courses"] == []
    assert school["newt_courses"] == []
    assert school["course_selection"] is None
    assert school["course_history"] == [{"school_year": "1990-1991"}]
    assert next_state["skills"]["charms"]["level"] == 0
    assert "course_skills" not in changes
    assert set(changes["courses_cleared"]) == {
        "active_courses",
        "elective_courses",
        "newt_courses",
        "course_selection",
    }


def test_left_school_legacy_courses_do_not_progress_in_june() -> None:
    state = _enrolled_state()
    state["school"]["grade"] = "left_school"
    state["skills"]["charms"]["level"] = 4

    next_state, changes = apply_turn_rules(
        state,
        [],
        _response("1993-06-01", grade="left_school"),
    )

    assert next_state["school"]["active_courses"] == []
    assert next_state["skills"]["charms"]["level"] == 4
    assert "course_skills" not in changes


@pytest.mark.parametrize(
    "era_id",
    ["dumbledore_era", "parent_generation", "second_generation"],
)
def test_left_school_course_view_keeps_the_departure_grade(era_id: str) -> None:
    state = _enrolled_state()
    state["school"]["grade"] = "left_school"
    state["school"]["active_courses"] = []

    game_session = GameSession(
        id="left-school-course-view",
        name="离校课程面板测试",
        era_id=era_id,
        state_version=3,
    )
    player_state = PlayerState(
        session_id=game_session.id,
        state=state,
    )

    courses = get_courses_view(game_session, player_state)

    assert courses.grade == "left_school"
    assert courses.active_courses == []


def test_course_view_accepts_legacy_short_graduation_history() -> None:
    state = _enrolled_state()
    state["school"]["grade"] = "left_school"
    state["school"]["active_courses"] = []
    state["school"]["course_history"] = [{
        "year": 1899,
        "grade": "year_7",
        "note": "早期存档的简略毕业记录",
    }]

    game_session = GameSession(
        id="legacy-endgame-course-view",
        name="旧终局存档课程面板测试",
        era_id="dumbledore_era",
        state_version=3,
    )
    player_state = PlayerState(
        session_id=game_session.id,
        state=state,
    )

    courses = get_courses_view(game_session, player_state)

    assert courses.grade == "left_school"
    assert courses.course_history[0].school_year == "1898-1899"
    assert courses.course_history[0].grade == "year_7"


def test_september_promotion_is_idempotent_and_opens_elective_selection() -> None:
    state = _enrolled_state()
    state["school"]["grade"] = "year_2"
    state["school"]["grade_started_year"] = 1991
    state["school"]["active_courses"] = [
        course_id for course_id in FIRST_YEAR_REQUIRED_COURSE_IDS
        if course_id != "flying"
    ]
    promoted, changes = apply_turn_rules(
        state,
        [],
        _response("1993-09-01", grade="year_3"),
    )
    assert promoted["school"]["grade"] == "year_3"
    assert promoted["school"]["last_grade_promotion_key"] == "year_2:year_3:1993"
    assert promoted["school"]["course_selection"]["phase"] == "elective"
    assert changes["school_grade"]["reason"] == "new_school_year_started"

    repeated, repeated_changes = apply_turn_rules(
        promoted,
        [],
        _response("1993-09-02", grade="year_3"),
    )
    assert repeated["school"]["grade"] == "year_3"
    assert repeated["school"]["course_selection"]["phase"] == "elective"
    assert "school_grade" not in repeated_changes


def test_model_cannot_create_course_skill_but_can_clamp_regular_skill() -> None:
    state = _enrolled_state()
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            "1991-09-02",
            grade="year_1",
            player_changes={
                "skill_add": [
                    {
                        "id": "potions",
                        "name": "魔药",
                        "description": "不应由模型创建",
                        "level": 10,
                    },
                    {
                        "id": "wandless_magic",
                        "name": "无杖魔法",
                        "description": "普通技能",
                        "level": 99,
                    },
                ],
                "skill_deltas": {"charms": 99, "wandless_magic": 99},
            },
        ),
    )
    assert "potions" not in changes["skills_entries"]["added"]
    assert next_state["skills"]["charms"]["level"] == 10
    assert next_state["skills"]["wandless_magic"]["level"] == 10
    assert next_state["skills"]["potions"]["level"] == 0


def test_skill_experience_accumulates_and_levels_up_alongside_direct_growth() -> None:
    state = _enrolled_state()
    state["skills"]["charms"]["level"] = 2
    state["skills"]["charms"]["experience"] = 90
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            "1991-09-02",
            grade="year_1",
            player_changes={
                "skill_deltas": {"charms": 1},
                "skill_experience_deltas": {"charms": 15},
            },
        ),
    )
    assert next_state["skills"]["charms"]["level"] == 4
    assert next_state["skills"]["charms"]["experience"] == 0
    assert changes["skills"]["charms"] == 2
    experience_change = changes["skill_experience"]["applied"][0]
    assert experience_change["experience_before"] == 90
    assert experience_change["experience_after"] == 0
    assert experience_change["leveled_up"] is True
    assert experience_change["overflow_discarded"] == 5


def test_skill_experience_only_increases_existing_non_maxed_skills() -> None:
    state = _enrolled_state()
    state["skills"]["charms"]["level"] = 10
    state["skills"]["potions"]["experience"] = 20
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            "1991-09-02",
            grade="year_1",
            player_changes={
                "skill_experience_deltas": {
                    "charms": 10,
                    "potions": -5,
                    "unknown_skill": 30,
                    "herbology": 25,
                },
            },
        ),
    )
    assert next_state["skills"]["charms"]["experience"] == 0
    assert next_state["skills"]["potions"]["experience"] == 20
    assert next_state["skills"]["herbology"]["experience"] == 25
    assert "unknown_skill" not in next_state["skills"]
    rejected_reasons = {
        item["reason"] for item in changes["skill_experience"]["rejected"]
    }
    assert rejected_reasons == {
        "skill_already_at_max_level",
        "experience_only_increases",
        "skill_not_learned",
    }


def test_course_api_writes_selection_without_turn_record() -> None:
    app = create_app()
    with get_session_factory()() as db:
        game_session = GameSession(name="课程 API 测试", era_id="second_generation")
        db.add(game_session)
        db.flush()
        player_state = PlayerState(session_id=game_session.id, state=_enrolled_state())
        player_state.state["school"]["grade"] = "year_3"
        player_state.state["school"]["course_selection"] = {
            "status": "pending",
            "phase": "elective",
            "min_courses": 2,
            "max_courses": 3,
            "available_course_ids": [
                "arithmancy",
                "muggle_studies",
                "divination",
                "ancient_runes",
                "care_of_magical_creatures",
            ],
        }
        db.add(player_state)
        db.commit()
        session_id = game_session.id
        state_version = game_session.state_version

    with TestClient(app) as client:
        view = client.get(f"/api/sessions/{session_id}/courses")
        assert view.status_code == 200
        assert view.json()["course_selection"]["status"] == "pending"
        selected = client.put(
            f"/api/sessions/{session_id}/courses",
            json={
                "expected_state_version": state_version,
                "selection_phase": "elective",
                "course_ids": ["arithmancy", "ancient_runes"],
            },
        )
        assert selected.status_code == 200, selected.text
        assert selected.json()["course_selection"] is None
        assert selected.json()["state_version"] == state_version + 1

    with get_session_factory()() as db:
        persisted = db.scalar(
            select(PlayerState).where(PlayerState.session_id == session_id)
        )
        assert persisted is not None
        assert persisted.state["skills"]["arithmancy"]["level"] == 0
        assert db.scalar(
            select(TurnRecord).where(TurnRecord.session_id == session_id)
        ) is None
        db.delete(db.get(GameSession, session_id))
        db.delete(persisted)
        db.commit()


def test_modern_course_api_is_disabled() -> None:
    app = create_app()
    with get_session_factory()() as db:
        game_session = GameSession(name="现代线无课程测试", era_id="modern")
        db.add(game_session)
        db.flush()
        player_state = PlayerState(session_id=game_session.id, state=_enrolled_state())
        db.add(player_state)
        db.commit()
        session_id = game_session.id

    with TestClient(app) as client:
        view = client.get(f"/api/sessions/{session_id}/courses")
        assert view.status_code == 409
        assert view.json()["detail"] == "现代世代不启用课程系统"
        selected = client.put(
            f"/api/sessions/{session_id}/courses",
            json={
                "expected_state_version": 0,
                "selection_phase": "elective",
                "course_ids": ["divination", "ancient_runes"],
            },
        )
        assert selected.status_code == 409
        assert selected.json()["detail"] == "现代世代不启用课程系统"

    with get_session_factory()() as db:
        persisted = db.scalar(
            select(PlayerState).where(PlayerState.session_id == session_id)
        )
        db.delete(db.get(GameSession, session_id))
        db.delete(persisted)
        db.commit()


def test_modern_turn_does_not_open_or_progress_courses() -> None:
    state = _enrolled_state()
    state["school"].update(
        {
            "grade": "year_2",
            "school_year": "2020-2021",
            "grade_started_year": 2020,
            "active_courses": ["charms"],
            "course_selection": None,
        }
    )
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response("2021-09-01", grade="year_3"),
        era_id="modern",
    )

    assert next_state["school"]["grade"] == "year_3"
    assert next_state["school"]["active_courses"] == []
    assert next_state["school"]["course_selection"] is None
    assert next_state["school"]["course_history"] == []
    assert not any(
        key in changes
        for key in ("school_exams", "course_progression", "course_selection")
    )
