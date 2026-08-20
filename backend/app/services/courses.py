from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from backend.app.content.courses import (
    ADVANCED_COURSE_IDS,
    COURSE_CATALOG,
    clamp_skill_level,
    grade_number,
)
from backend.app.content.school import normalize_grade
from backend.app.models import GameSession, PlayerState
from backend.app.schemas.game import (
    CourseHistoryEntry,
    CourseOption,
    CourseResult,
    CourseSelection,
    CourseSkill,
    CourseSelectionRequest,
    CourseView,
)


def get_courses_view(
    game_session: GameSession,
    player_state: PlayerState,
) -> CourseView:
    school = player_state.state.get("school", {})
    if not isinstance(school, dict):
        school = {}
    grade = normalize_grade(school)
    active_ids = _string_list(school.get("active_courses"))
    selection = _selection_model(school.get("course_selection"))
    selected_ids = set(
        _string_list(school.get("elective_courses"))
        + _string_list(school.get("newt_courses"))
    )
    editable_phase = (
        selection.phase
        if selection is not None
        else _editable_phase(grade)
    )
    selection_ids = (
        selection.available_course_ids
        if selection is not None
        else _editable_course_ids(editable_phase, school)
    )
    return CourseView(
        session_id=game_session.id,
        state_version=game_session.state_version,
        grade=grade,
        school_year=str(school.get("school_year") or ""),
        term=str(school.get("term") or "summer"),
        active_courses=[
            _course_option(course_id, player_state.state, available=True)
            for course_id in active_ids
            if course_id in COURSE_CATALOG
        ],
        selection_options=[
            _course_option(
                course_id,
                player_state.state,
                available=_option_available(
                    course_id,
                    selection,
                    editable_phase,
                    selection_ids,
                ),
                unavailable_reason=None
                if _option_available(
                    course_id,
                    selection,
                    editable_phase,
                    selection_ids,
                )
                else "当前选课阶段不可选",
            )
            for course_id in selection_ids
            if course_id in COURSE_CATALOG
        ],
        editable_phase=editable_phase,
        elective_courses=_string_list(school.get("elective_courses")),
        newt_courses=_string_list(school.get("newt_courses")),
        skills=_course_skills(player_state.state),
        owl_results=_course_results(school.get("owl_results")),
        newt_results=_course_results(school.get("newt_results")),
        course_selection=selection,
        course_history=[
            CourseHistoryEntry.model_validate(item)
            for item in school.get("course_history", [])
            if isinstance(item, dict)
        ],
    )


def select_courses(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
    payload: CourseSelectionRequest,
) -> CourseView:
    if game_session.state_version != payload.expected_state_version:
        raise ValueError("存档已发生变化，请刷新后重试")
    state = deepcopy(player_state.state)
    school = state.setdefault("school", {})
    selection = school.get("course_selection")
    pending = isinstance(selection, dict) and selection.get("status") == "pending"
    phase = str(selection.get("phase")) if pending else _editable_phase(
        normalize_grade(school)
    )
    if phase not in {"elective", "newt"}:
        raise ValueError("当前年级没有可修改的课程")
    if phase != payload.selection_phase:
        raise ValueError("选课阶段与当前学籍不一致")
    course_ids = list(dict.fromkeys(str(item) for item in payload.course_ids))
    available_ids = set(
        _string_list(selection.get("available_course_ids"))
        if pending
        else _editable_course_ids(phase, school)
    )
    if any(course_id not in available_ids for course_id in course_ids):
        raise ValueError("包含当前阶段不可选的课程")
    minimum = int(selection.get("min_courses", 2 if phase == "elective" else 1))
    maximum = int(selection.get("max_courses", 3 if phase == "elective" else 5))
    if not minimum <= len(course_ids) <= maximum:
        raise ValueError(f"本阶段必须选择 {minimum} 至 {maximum} 门课程")

    target_key = "elective_courses" if phase == "elective" else "newt_courses"
    previous_ids = set(_string_list(school.get(target_key)))
    school[target_key] = course_ids
    active = [
        course_id
        for course_id in _string_list(school.get("active_courses"))
        if course_id in COURSE_CATALOG and course_id not in previous_ids
    ]
    for course_id in course_ids:
        if course_id not in active:
            active.append(course_id)
    school["active_courses"] = active
    school["course_selection"] = None
    school.setdefault("course_history", []).append(
        {
            "school_year": str(school.get("school_year") or ""),
            "grade": normalize_grade(school),
            "active_courses": list(active),
            "selected_courses": list(course_ids),
            "skill_progression": {},
        }
    )
    skills = state.setdefault("skills", {})
    for course_id in course_ids:
        course = COURSE_CATALOG[course_id]
        skill_id = course["skill_id"]
        existing = skills.get(skill_id)
        if isinstance(existing, dict):
            existing["course_skill"] = True
            existing["course_id"] = course_id
            existing.setdefault("source", "course")
            existing["level"] = clamp_skill_level(existing.get("level", 0))
        else:
            skills[skill_id] = {
                "id": skill_id,
                "name": course["name"],
                "description": course["description"],
                "level": 0,
                "experience": 0,
                "source": "course",
                "course_id": course_id,
                "course_skill": True,
            }
    player_state.state = state
    game_session.state_version += 1
    db.commit()
    db.refresh(player_state)
    db.refresh(game_session)
    return get_courses_view(game_session, player_state)


def _course_option(
    course_id: str,
    state: dict[str, Any],
    *,
    available: bool,
    unavailable_reason: str | None = None,
) -> CourseOption:
    course = COURSE_CATALOG[course_id]
    skill = state.get("skills", {}).get(course["skill_id"], {})
    return CourseOption(
        id=course_id,
        name=course["name"],
        description=course["description"],
        category=course["category"],
        available=available,
        unavailable_reason=unavailable_reason,
        skill_id=course["skill_id"],
        skill_level=clamp_skill_level(skill.get("level", 0)),
    )


def _course_skills(state: dict[str, Any]) -> list[CourseSkill]:
    skills = state.get("skills", {})
    result = []
    for course in COURSE_CATALOG.values():
        skill = skills.get(course["skill_id"])
        if not isinstance(skill, dict) or not skill.get("course_skill"):
            continue
        result.append(
            CourseSkill(
                id=course["skill_id"],
                name=course["name"],
                description=course["description"],
                level=clamp_skill_level(skill.get("level", 0)),
                experience=int(skill.get("experience", 0) or 0),
                source=str(skill.get("source") or "course"),
                course_id=course["id"],
            )
        )
    return result


def _course_results(raw: Any) -> list[CourseResult]:
    if not isinstance(raw, dict):
        return []
    return [
        CourseResult(
            id=course_id,
            name=COURSE_CATALOG.get(course_id, {}).get("name", course_id),
            grade=str(result),
        )
        for course_id, result in raw.items()
    ]


def _selection_model(raw: Any) -> CourseSelection | None:
    if not isinstance(raw, dict) or raw.get("status") != "pending":
        return None
    return CourseSelection.model_validate(raw)


def _option_available(
    course_id: str,
    selection: CourseSelection | None,
    editable_phase: str | None,
    editable_ids: list[str],
) -> bool:
    if selection is not None:
        return course_id in selection.available_course_ids
    return editable_phase is not None and course_id in editable_ids


def _editable_phase(grade: str) -> str | None:
    number = grade_number(grade)
    if 3 <= number <= 5:
        return "elective"
    if number >= 6 and number <= 7:
        return "newt"
    return None


def _editable_course_ids(phase: str | None, school: dict[str, Any]) -> list[str]:
    if phase == "elective":
        return [
            course_id
            for course_id, course in COURSE_CATALOG.items()
            if course["category"] == "elective"
        ]
    if phase == "newt":
        owl_results = school.get("owl_results", {})
        if not isinstance(owl_results, dict):
            return []
        available = [
            str(course_id)
            for course_id, result in owl_results.items()
            if course_id in COURSE_CATALOG
            and COURSE_CATALOG[course_id].get("newt_required")
            and str(result) in {"O", "E", "A"}
        ]
        if available:
            return available + [
                course_id
                for course_id in ADVANCED_COURSE_IDS
                if course_id not in available
                and _has_owl_threshold(
                    owl_results,
                    COURSE_CATALOG[course_id].get("owl_required"),
                )
            ]
    return []


def _has_owl_threshold(results: dict[str, Any], threshold: str | None) -> bool:
    if threshold is None:
        return True
    rank = {"T": 0, "D": 1, "P": 2, "A": 3, "E": 4, "O": 5}
    return any(rank.get(str(value), -1) >= rank[threshold] for value in results.values())


def _string_list(raw: Any) -> list[str]:
    return [str(item) for item in raw] if isinstance(raw, list) else []
