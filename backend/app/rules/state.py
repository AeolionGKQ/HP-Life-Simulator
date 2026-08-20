from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.app.models import Relationship
from backend.app.content.attributes import (
    DIMENSION_CATALOG,
    DIMENSION_IDS,
    DIMENSION_REASON_CODES,
    RESOURCE_CATALOG,
    RESOURCE_IDS,
    RESOURCE_REASON_CODES,
)
from backend.app.content.school import (
    EXAM_GRADES,
    GRADE_IDS,
    HOUSE_IDS,
    PERMANENT_DEPARTURE_REASONS,
    PROMOTION_TARGETS,
    normalize_grade,
)
from backend.app.content.courses import (
    ADVANCED_COURSE_IDS,
    COURSE_CATALOG,
    CORE_COURSE_IDS,
    ELECTIVE_COURSE_IDS,
    FIRST_YEAR_REQUIRED_COURSE_IDS,
    SKILL_EXPERIENCE_MAX,
    SKILL_EXPERIENCE_MIN,
    SKILL_LEVEL_MAX,
    SKILL_LEVEL_MIN,
    clamp_skill_level,
    course_skill_ids,
    grade_number,
)
from backend.app.schemas.game import NarrativeResponse


def apply_turn_rules(
    state: dict[str, Any],
    relationships: list[Relationship],
    response: NarrativeResponse,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """应用模型提出的可验证变化，返回新状态和审计差异。"""
    next_state = deepcopy(state)
    proposals = response.player_changes.model_dump()
    if not any(proposals.values()) and response.state_proposals:
        proposals = deepcopy(response.state_proposals)
    changes: dict[str, Any] = {}

    context = next_state.setdefault("current_context", {})
    old_datetime = _parse_datetime(context.get("datetime"))
    old_date = _parse_date(context.get("current_date"), old_datetime.date())
    requested_date = response.turn.current_date
    if requested_date < old_date:
        current_date = old_date
        changes["date_rejected"] = {
            "requested": requested_date.isoformat(),
            "kept": old_date.isoformat(),
            "reason": "story_date_cannot_move_backwards",
        }
    else:
        current_date = requested_date
    context["current_date"] = current_date.isoformat()
    advance_minutes = response.turn.time_advance_minutes
    if advance_minutes:
        new_datetime = old_datetime + timedelta(minutes=advance_minutes)
        new_datetime = new_datetime.replace(
            year=current_date.year,
            month=current_date.month,
            day=current_date.day,
        )
        context["datetime"] = new_datetime.isoformat()
        context["period"] = _period(new_datetime.hour)
        changes["time_advance_minutes"] = advance_minutes
    else:
        context["datetime"] = old_datetime.replace(
            year=current_date.year,
            month=current_date.month,
            day=current_date.day,
        ).isoformat()
        if current_date != old_date:
            changes["date"] = {
                "before": old_date.isoformat(),
                "after": current_date.isoformat(),
            }
    context["location_id"] = response.turn.location_id
    if response.turn.location_id != state.get("current_context", {}).get("location_id"):
        changes["location_id"] = response.turn.location_id
    _update_age(next_state, old_datetime, changes)
    _apply_school_exam_events(next_state, response.events, changes)
    _apply_grade_transition(next_state, response, current_date, changes)
    _apply_course_year_end(next_state, current_date, changes)

    _apply_resource_caps(next_state, proposals.get("resource_cap_deltas"), changes)
    _apply_dimension_caps(next_state, proposals.get("dimension_cap_deltas"), changes)
    _apply_resource_deltas(next_state, proposals.get("resource_deltas"), changes)
    _apply_dimension_deltas(next_state, proposals.get("dimension_deltas"), changes)
    _apply_skills(next_state, proposals.get("skill_deltas"), changes)
    _apply_skill_entries(next_state, proposals, changes)
    _apply_skill_experience(
        next_state,
        proposals.get("skill_experience_deltas"),
        changes,
    )
    _apply_statuses(next_state, proposals, changes)
    _apply_traits(next_state, proposals, changes)
    _apply_reputation(next_state, proposals.get("reputation_deltas"), changes)
    _apply_inventory(next_state, proposals, changes)
    _apply_relationships(next_state, relationships, proposals, changes)
    _apply_lifecycle(next_state, changes)
    response.turn.grade = normalize_grade(next_state.setdefault("school", {}))
    return next_state, changes


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime(1991, 7, 1, 9, tzinfo=timezone.utc)


def _parse_date(value: Any, fallback: date) -> date:
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback


def _period(hour: int) -> str:
    if hour < 6:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    if hour < 22:
        return "evening"
    return "night"


def _apply_school_exam_events(
    state: dict[str, Any],
    events: list[dict[str, Any]],
    changes: dict[str, Any],
) -> None:
    school = state.setdefault("school", {})
    current_grade = normalize_grade(school)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type") or event.get("event_type")
        if event_type not in {"owl_completed", "newt_completed"}:
            continue
        expected_grade = "year_5" if event_type == "owl_completed" else "year_7"
        if current_grade != expected_grade:
            rejected.append({"event": event, "reason": "exam_not_available_in_current_grade"})
            continue
        raw_results = event.get("results")
        if not isinstance(raw_results, dict) or not raw_results:
            rejected.append({"event": event, "reason": "exam_results_required"})
            continue
        results = {
            str(course): str(grade)
            for course, grade in raw_results.items()
            if str(course).strip() and str(grade) in EXAM_GRADES
        }
        if not results or len(results) != len(raw_results):
            rejected.append({"event": event, "reason": "invalid_exam_results"})
            continue
        result_key = "owl_results" if event_type == "owl_completed" else "newt_results"
        completed_key = "owl_completed" if event_type == "owl_completed" else "newt_completed"
        school[result_key] = results
        school[completed_key] = True
        applied.append({"type": event_type, "results": results})
    if applied or rejected:
        changes["school_exams"] = {"applied": applied, "rejected": rejected}


def _apply_grade_transition(
    state: dict[str, Any],
    response: NarrativeResponse,
    current_date: date,
    changes: dict[str, Any],
) -> None:
    school = state.setdefault("school", {})
    current_grade = normalize_grade(school)
    school["grade"] = current_grade
    if current_grade != "not_enrolled":
        school["enrollment_started"] = True
    else:
        school.setdefault("enrollment_started", False)

    requested_grade = response.turn.grade
    transition = response.turn.school_transition
    if requested_grade is None:
        requested_grade = current_grade
    if transition is None:
        if requested_grade != current_grade:
            if (
                requested_grade == PROMOTION_TARGETS.get(current_grade)
                and current_date.month == 9
            ):
                _auto_promote_on_new_school_year(
                    state,
                    school,
                    current_grade,
                    current_date,
                    changes,
                )
            else:
                _reject_grade(
                    changes,
                    current_grade,
                    requested_grade,
                    "grade_mismatch_without_transition",
                )
        else:
            _auto_promote_on_new_school_year(
                state,
                school,
                current_grade,
                current_date,
                changes,
            )
        return

    if transition.from_grade != current_grade:
        _reject_grade(
            changes,
            current_grade,
            requested_grade,
            "transition_from_grade_mismatch",
        )
        return
    if transition.to_grade != requested_grade:
        _reject_grade(
            changes,
            current_grade,
            requested_grade,
            "transition_target_mismatch",
        )
        return
    if current_grade == "left_school":
        _reject_grade(changes, current_grade, requested_grade, "left_school_is_terminal")
        return

    rejection = _grade_transition_rejection(
        school,
        current_grade,
        requested_grade,
        transition.type,
        transition.reason,
        current_date,
    )
    if rejection:
        _reject_grade(changes, current_grade, requested_grade, rejection)
        return

    school["grade"] = requested_grade
    if transition.type == "enrollment":
        school["enrollment_started"] = True
        school["departure_reason"] = None
        school["grade_started_year"] = current_date.year
        school["last_grade_promotion_key"] = None
        _open_first_year_courses(state, school, current_date.year, changes)
    elif transition.type == "promotion":
        school["school_year"] = f"{current_date.year}-{current_date.year + 1}"
        school["departure_reason"] = None
        school["grade_started_year"] = current_date.year
        school["last_grade_promotion_key"] = (
            f"{current_grade}:{requested_grade}:{current_date.year}"
        )
        _apply_grade_course_structure(state, school, requested_grade, changes)
    else:
        school["departure_reason"] = transition.reason
    changes["school_grade"] = {
        "before": current_grade,
        "after": requested_grade,
        "type": transition.type,
        "reason": transition.reason,
    }


def _grade_transition_rejection(
    school: dict[str, Any],
    current_grade: str,
    requested_grade: str,
    transition_type: str,
    reason: str,
    current_date: date,
) -> str | None:
    if transition_type == "enrollment":
        if (
            current_grade != "not_enrolled"
            or requested_grade != "year_1"
            or reason != "sorting_completed"
            or school.get("house") not in HOUSE_IDS
        ):
            return "invalid_enrollment_transition"
        return None

    if transition_type == "promotion":
        expected = PROMOTION_TARGETS.get(current_grade)
        if requested_grade in GRADE_IDS and requested_grade.startswith("year_"):
            requested_number = int(requested_grade.removeprefix("year_"))
            current_number = (
                int(current_grade.removeprefix("year_"))
                if current_grade.startswith("year_")
                else 0
            )
            if requested_number < current_number:
                return "grade_regression_not_allowed"
            if requested_number > current_number + 1:
                return "grade_skip_not_allowed"
        if requested_grade != expected:
            return "grade_skip_not_allowed"
        if reason != "new_school_year_started" or current_date.month != 9:
            return "promotion_requires_new_school_year"
        started_year = school.get("grade_started_year")
        if not isinstance(started_year, int) or current_date.year <= started_year:
            return "promotion_already_applied_this_school_year"
        promotion_key = f"{current_grade}:{requested_grade}:{current_date.year}"
        if school.get("last_grade_promotion_key") == promotion_key:
            return "promotion_already_applied_this_school_year"
        if current_grade == "year_5" and not _exam_completed(school, "owl"):
            return "promotion_requires_owl_completion"
        return None

    if transition_type != "departure" or requested_grade != "left_school":
        return "transition_target_mismatch"
    if reason == "graduated_after_newts":
        if current_grade != "year_7" or not _exam_completed(school, "newt"):
            return "graduation_requires_newt_completion"
        return None
    if reason == "left_after_owls":
        if current_grade != "year_5" or not _exam_completed(school, "owl"):
            return "left_after_owls_requires_owl_completion"
        return None
    if reason in PERMANENT_DEPARTURE_REASONS and current_grade.startswith("year_"):
        return None
    return "transition_target_mismatch"


def _auto_promote_on_new_school_year(
    state: dict[str, Any],
    school: dict[str, Any],
    current_grade: str,
    current_date: date,
    changes: dict[str, Any],
) -> None:
    target_grade = PROMOTION_TARGETS.get(current_grade)
    started_year = school.get("grade_started_year")
    if (
        target_grade is None
        or current_date.month != 9
        or not isinstance(started_year, int)
        or current_date.year <= started_year
    ):
        return
    promotion_key = f"{current_grade}:{target_grade}:{current_date.year}"
    if school.get("last_grade_promotion_key") == promotion_key:
        return
    if current_grade == "year_5" and not _exam_completed(school, "owl"):
        changes["school_grade_rejected"] = {
            "requested": target_grade,
            "kept": current_grade,
            "reason": "promotion_requires_owl_completion",
        }
        return
    school["grade"] = target_grade
    school["school_year"] = f"{current_date.year}-{current_date.year + 1}"
    school["grade_started_year"] = current_date.year
    school["last_grade_promotion_key"] = promotion_key
    school["departure_reason"] = None
    _apply_grade_course_structure(state, school, target_grade, changes)
    changes["school_grade"] = {
        "before": current_grade,
        "after": target_grade,
        "type": "promotion",
        "reason": "new_school_year_started",
    }


def _open_first_year_courses(
    state: dict[str, Any],
    school: dict[str, Any],
    year: int,
    changes: dict[str, Any],
) -> None:
    if school.get("active_courses"):
        return
    school["active_courses"] = list(FIRST_YEAR_REQUIRED_COURSE_IDS)
    school["term"] = "autumn"
    _ensure_course_skills(state, school, changes)


def _apply_grade_course_structure(
    state: dict[str, Any],
    school: dict[str, Any],
    grade: str,
    changes: dict[str, Any],
) -> None:
    number = grade_number(grade)
    if number == 2:
        school["active_courses"] = list(
            course_id
            for course_id in school.get("active_courses", [])
            if course_id in CORE_COURSE_IDS
        )
    elif number == 3 and school.get("course_selection") is None:
        school["course_selection"] = {
            "status": "pending",
            "phase": "elective",
            "min_courses": 2,
            "max_courses": 3,
            "available_course_ids": list(ELECTIVE_COURSE_IDS),
        }
    elif number == 6 and school.get("course_selection") is None:
        school["course_selection"] = {
            "status": "pending",
            "phase": "newt",
            "min_courses": 1,
            "max_courses": 5,
            "available_course_ids": _available_newt_courses(school),
        }
    _ensure_course_skills(state, school, changes)


def _available_newt_courses(school: dict[str, Any]) -> list[str]:
    owl_results = school.get("owl_results", {})
    if not isinstance(owl_results, dict):
        return []
    available = []
    for course_id, result in owl_results.items():
        course = COURSE_CATALOG.get(str(course_id))
        if course and course.get("newt_required") and result in {"O", "E", "A"}:
            available.append(str(course_id))
    for course_id in ADVANCED_COURSE_IDS:
        course = COURSE_CATALOG[course_id]
        if course_id not in available and _has_owl_threshold(owl_results, course["owl_required"]):
            available.append(course_id)
    return available


def _has_owl_threshold(results: dict[str, Any], threshold: str | None) -> bool:
    if threshold is None:
        return True
    rank = {"T": 0, "D": 1, "P": 2, "A": 3, "E": 4, "O": 5}
    return any(rank.get(str(value), -1) >= rank[threshold] for value in results.values())


def _ensure_course_skills(
    state: dict[str, Any],
    school: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    skills = state.setdefault("skills", {}) if state else None
    if skills is None:
        return
    for course_id in school.get("active_courses", []):
        course = COURSE_CATALOG.get(course_id)
        if not course:
            continue
        skill_id = course["skill_id"]
        skills.setdefault(
            skill_id,
            {
                "id": skill_id,
                "name": course["name"],
                "description": course["description"],
                "level": SKILL_LEVEL_MIN,
                "experience": 0,
                "source": "course",
                "course_id": course_id,
                "course_skill": True,
            },
        )


def _apply_course_year_end(
    state: dict[str, Any],
    current_date: date,
    changes: dict[str, Any],
) -> None:
    school = state.setdefault("school", {})
    school["term"] = "summer" if current_date.month == 6 else (
        "autumn" if current_date.month >= 9 else school.get("term", "summer")
    )
    if current_date.month != 6:
        return
    if school.get("last_course_progression_year") == current_date.year:
        return
    skills = state.setdefault("skills", {})
    progression: dict[str, int] = {}
    for course_id in school.get("active_courses", []):
        course = COURSE_CATALOG.get(course_id)
        if not course:
            continue
        skill_id = course["skill_id"]
        skill = skills.get(skill_id)
        if not isinstance(skill, dict):
            continue
        before = clamp_skill_level(skill.get("level", 0))
        after = clamp_skill_level(before + 1)
        skill["level"] = after
        progression[skill_id] = after - before
    school["last_course_progression_year"] = current_date.year
    school.setdefault("course_history", []).append(
        {
            "school_year": school.get("school_year", ""),
            "grade": normalize_grade(school),
            "active_courses": list(school.get("active_courses", [])),
            "selected_courses": list(
                school.get("elective_courses", [])
                + school.get("newt_courses", [])
            ),
            "skill_progression": progression,
        }
    )
    changes["course_skills"] = {
        "year": current_date.year,
        "applied": progression,
        "reason": "june_course_year_end",
    }


def _exam_completed(school: dict[str, Any], exam: str) -> bool:
    return school.get(f"{exam}_completed") is True or bool(
        school.get(f"{exam}_results")
    )


def _reject_grade(
    changes: dict[str, Any],
    current_grade: str,
    requested_grade: str,
    reason: str,
) -> None:
    changes["school_grade_rejected"] = {
        "requested": requested_grade,
        "kept": current_grade,
        "reason": reason,
    }


def _bounded_delta(raw_delta: Any) -> float | None:
    if isinstance(raw_delta, bool) or not isinstance(raw_delta, (int, float)):
        return None
    if raw_delta != raw_delta or raw_delta in {float("inf"), float("-inf")}:
        return None
    return float(raw_delta)


def _apply_resource_caps(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, list):
        return
    resources = state.setdefault("resources", {})
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in deltas:
        if not isinstance(item, dict) or item.get("id") not in RESOURCE_IDS:
            rejected.append({"item": item, "reason": "unknown_resource"})
            continue
        if not item.get("permanent", True):
            rejected.append({"item": item, "reason": "cap_change_must_be_permanent"})
            continue
        delta = _bounded_delta(item.get("delta"))
        if delta is None or item.get("reason_code") not in RESOURCE_REASON_CODES:
            rejected.append({"item": item, "reason": "invalid_delta"})
            continue
        resource_id = str(item["id"])
        resource = resources.setdefault(resource_id, {})
        before = float(resource.get("max", RESOURCE_CATALOG[resource_id]["default_max"]))
        maximum = float(RESOURCE_CATALOG[resource_id]["absolute_max"])
        after = max(1.0, min(maximum, before + delta))
        resource["max"] = after
        if float(resource.get("value", 0)) > after:
            resource["value"] = after
        applied.append({
            "id": resource_id,
            "before": before,
            "after": after,
            "delta": after - before,
            "reason_code": str(item.get("reason_code", "")),
            "reason": str(item.get("reason", "")),
        })
    if applied or rejected:
        changes["resource_caps"] = {"applied": applied, "rejected": rejected}


def _apply_dimension_caps(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, list):
        return
    dimensions = state.setdefault("dimensions", {})
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in deltas:
        if not isinstance(item, dict) or item.get("id") not in DIMENSION_IDS:
            rejected.append({"item": item, "reason": "unknown_dimension"})
            continue
        if not item.get("permanent", True):
            rejected.append({"item": item, "reason": "cap_change_must_be_permanent"})
            continue
        delta = _bounded_delta(item.get("delta"))
        if delta is None or item.get("reason_code") not in DIMENSION_REASON_CODES:
            rejected.append({"item": item, "reason": "invalid_delta"})
            continue
        dimension_id = str(item["id"])
        dimension = dimensions.setdefault(dimension_id, {})
        before = float(dimension.get("max", DIMENSION_CATALOG[dimension_id]["default_max"]))
        maximum = float(DIMENSION_CATALOG[dimension_id]["absolute_max"])
        after = max(1.0, min(maximum, before + delta))
        dimension["max"] = after
        if float(dimension.get("value", 0)) > after:
            dimension["value"] = after
        applied.append({
            "id": dimension_id,
            "before": before,
            "after": after,
            "delta": after - before,
            "reason_code": str(item.get("reason_code", "")),
            "reason": str(item.get("reason", "")),
        })
    if applied or rejected:
        changes["dimension_caps"] = {"applied": applied, "rejected": rejected}


def _apply_resource_deltas(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, list):
        return
    resources = state.setdefault("resources", {})
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for item in deltas:
        if not isinstance(item, dict) or item.get("id") not in RESOURCE_IDS:
            rejected.append({"item": item, "reason": "unknown_resource"})
            continue
        delta = _bounded_delta(item.get("delta"))
        if delta is None or item.get("reason_code") not in RESOURCE_REASON_CODES:
            rejected.append({"item": item, "reason": "invalid_delta"})
            continue
        resource_id = str(item["id"])
        resource = resources.setdefault(
            resource_id,
            {
                "value": RESOURCE_CATALOG[resource_id]["default_max"],
                "max": RESOURCE_CATALOG[resource_id]["default_max"],
                "base_max": RESOURCE_CATALOG[resource_id]["default_max"],
            },
        )
        before = float(resource.get("value", 0))
        maximum = float(resource.get("max", RESOURCE_CATALOG[resource_id]["default_max"]))
        after = max(0.0, min(maximum, before + delta))
        resource["value"] = after
        applied.append({
            "id": resource_id,
            "before": before,
            "after": after,
            "delta": after - before,
            "reason_code": str(item.get("reason_code", "")),
            "reason": str(item.get("reason", "")),
        })
    if applied or rejected:
        changes["resources"] = {"applied": applied, "rejected": rejected}


def _apply_dimension_deltas(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, list):
        return
    dimensions = state.setdefault("dimensions", {})
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    changed_count = 0
    for item in deltas:
        if not isinstance(item, dict) or item.get("id") not in DIMENSION_IDS:
            rejected.append({"item": item, "reason": "unknown_dimension"})
            continue
        delta = _bounded_delta(item.get("delta"))
        if delta is None or item.get("reason_code") not in DIMENSION_REASON_CODES:
            rejected.append({"item": item, "reason": "invalid_delta"})
            continue
        if changed_count >= 3:
            rejected.append({"item": item, "reason": "turn_dimension_limit"})
            continue
        dimension_id = str(item["id"])
        dimension = dimensions.setdefault(
            dimension_id,
            {
                "value": 0,
                "max": DIMENSION_CATALOG[dimension_id]["default_max"],
                "base_max": DIMENSION_CATALOG[dimension_id]["default_max"],
            },
        )
        before = float(dimension.get("value", 0))
        maximum = float(dimension.get("max", DIMENSION_CATALOG[dimension_id]["default_max"]))
        limit = 2.0 if str(item.get("reason_code", "")) in {
            "major_discovery",
            "permanent_injury",
            "long_term_illness",
            "magical_awakening",
            "ritual",
        } else 1.0
        bounded = max(-limit, min(limit, delta))
        after = max(0.0, min(maximum, before + bounded))
        dimension["value"] = after
        changed_count += 1
        applied.append({
            "id": dimension_id,
            "before": before,
            "after": after,
            "delta": after - before,
            "proposed_delta": delta,
            "reason_code": str(item.get("reason_code", "")),
            "reason": str(item.get("reason", "")),
        })
    if applied or rejected:
        changes["dimensions"] = {"applied": applied, "rejected": rejected}


def _apply_skills(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, dict):
        return
    skills = state.setdefault("skills", {})
    course_skill_id_set = course_skill_ids(
        list(COURSE_CATALOG.keys())
    )
    applied: dict[str, int] = {}
    rejected: list[dict[str, Any]] = []
    for skill_id, raw_delta in deltas.items():
        if isinstance(raw_delta, bool) or not isinstance(raw_delta, (int, float)):
            continue
        normalized_id = _stable_id(skill_id)
        skill = skills.get(normalized_id)
        if normalized_id in course_skill_id_set and not isinstance(skill, dict):
            rejected.append(
                {"skill_id": normalized_id, "reason": "course_skill_not_enrolled"}
            )
            continue
        if not isinstance(skill, dict):
            skill = {
                "id": normalized_id,
                "name": normalized_id,
                "level": SKILL_LEVEL_MIN,
                "experience": 0,
                "source": "model_delta",
            }
            skills[normalized_id] = skill
        before = clamp_skill_level(skill.get("level", SKILL_LEVEL_MIN))
        after = clamp_skill_level(before + int(raw_delta))
        skill["level"] = after
        applied[normalized_id] = after - before
    if applied:
        changes["skills"] = applied
    if rejected:
        changes["skills_rejected"] = rejected


def _apply_skill_experience(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, dict):
        return
    skills = state.setdefault("skills", {})
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw_skill_id, raw_delta in deltas.items():
        skill_id = _stable_id(raw_skill_id)
        if (
            not skill_id
            or isinstance(raw_delta, bool)
            or not isinstance(raw_delta, (int, float))
        ):
            rejected.append(
                {"skill_id": skill_id, "reason": "invalid_experience_delta"}
            )
            continue
        delta = int(raw_delta)
        if delta <= 0:
            rejected.append(
                {
                    "skill_id": skill_id,
                    "proposed_delta": delta,
                    "reason": "experience_only_increases",
                }
            )
            continue
        skill = skills.get(skill_id)
        if not isinstance(skill, dict):
            rejected.append(
                {"skill_id": skill_id, "reason": "skill_not_learned"}
            )
            continue
        before_level = clamp_skill_level(skill.get("level", SKILL_LEVEL_MIN))
        before_experience = _normalize_skill_experience(
            skill.get("experience", SKILL_EXPERIENCE_MIN)
        )
        skill["level"] = before_level
        skill["experience"] = before_experience
        if before_level >= SKILL_LEVEL_MAX:
            rejected.append(
                {
                    "skill_id": skill_id,
                    "proposed_delta": delta,
                    "reason": "skill_already_at_max_level",
                }
            )
            continue

        total = before_experience + delta
        leveled_up = total >= SKILL_EXPERIENCE_MAX
        after_level = before_level + 1 if leveled_up else before_level
        after_experience = SKILL_EXPERIENCE_MIN if leveled_up else total
        skill["level"] = after_level
        skill["experience"] = after_experience
        if leveled_up:
            level_changes = changes.setdefault("skills", {})
            level_changes[skill_id] = level_changes.get(skill_id, 0) + 1
        applied.append(
            {
                "skill_id": skill_id,
                "gained": delta,
                "experience_before": before_experience,
                "experience_after": after_experience,
                "level_before": before_level,
                "level_after": after_level,
                "leveled_up": leveled_up,
                "overflow_discarded": max(
                    0,
                    total - SKILL_EXPERIENCE_MAX,
                ) if leveled_up else 0,
            }
        )
    if applied or rejected:
        changes["skill_experience"] = {
            "applied": applied,
            "rejected": rejected,
        }


def _normalize_skill_experience(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        numeric = SKILL_EXPERIENCE_MIN
    return max(
        SKILL_EXPERIENCE_MIN,
        min(SKILL_EXPERIENCE_MAX - 1, numeric),
    )


def _apply_skill_entries(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    skills = state.setdefault("skills", {})
    added: list[str] = []
    rejected: list[dict[str, Any]] = []
    for item in proposals.get("skill_add", []) or []:
        if not isinstance(item, dict):
            continue
        skill_id = _stable_id(item.get("id") or item.get("skill_id") or item.get("name"))
        if not skill_id:
            continue
        course = COURSE_CATALOG.get(skill_id)
        if course is not None:
            rejected.append(
                {"skill_id": skill_id, "reason": "course_skill_program_managed"}
            )
            continue
        current = skills.setdefault(
            skill_id,
            {
                "name": item.get("name") or skill_id,
            "level": SKILL_LEVEL_MIN,
                "experience": 0,
                "description": item.get("description", ""),
            },
        )
        current["name"] = item.get("name") or current.get("name") or skill_id
        current["description"] = item.get("description") or current.get(
            "description", ""
        )
        current["level"] = max(
            clamp_skill_level(current.get("level", SKILL_LEVEL_MIN)),
            clamp_skill_level(item.get("level", 1)),
        )
        added.append(skill_id)
    removed: list[str] = []
    for raw_id in proposals.get("skill_remove", []) or []:
        skill_id = _stable_id(raw_id)
        if skill_id in skills and skill_id not in course_skill_ids(list(COURSE_CATALOG)):
            del skills[skill_id]
            removed.append(skill_id)
        elif skill_id in course_skill_ids(list(COURSE_CATALOG)):
            rejected.append(
                {"skill_id": skill_id, "reason": "course_skill_program_managed"}
            )
    if added or removed or rejected:
        changes["skills_entries"] = {
            "added": added,
            "removed": removed,
            "rejected": rejected,
        }


def _apply_statuses(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    statuses = state.setdefault("statuses", [])
    by_id = {
        str(item.get("id")): item
        for item in statuses
        if isinstance(item, dict) and item.get("id")
    }
    added: list[dict[str, Any]] = []
    for item in proposals.get("status_add", []) or []:
        if not isinstance(item, dict):
            continue
        status_id = _stable_id(item.get("id") or item.get("name"))
        if not status_id:
            continue
        value = {
            "id": status_id,
            "name": item.get("name") or status_id,
            "description": item.get("description") or item.get("effect", ""),
            "severity": item.get("severity", "normal"),
            "duration_minutes": item.get("duration_minutes"),
        }
        by_id[status_id] = value
        added.append(value)
    removed: list[str] = []
    for raw_id in proposals.get("status_remove", []) or []:
        status_id = _stable_id(raw_id)
        if status_id in by_id:
            del by_id[status_id]
            removed.append(status_id)
    state["statuses"] = list(by_id.values())
    if added or removed:
        changes["statuses"] = {"added": added, "removed": removed}


def _apply_traits(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    traits = state.setdefault("traits", [])
    by_id = {
        str(item.get("id")): item
        for item in traits
        if isinstance(item, dict) and item.get("id")
    }
    added: list[dict[str, Any]] = []
    for item in (proposals.get("trait_add", []) or [])[:2]:
        if not isinstance(item, dict):
            continue
        trait_id = _stable_id(item.get("id") or item.get("name"))
        name = str(item.get("name") or "")
        description = str(item.get("description") or "")
        if not trait_id or not name or not description:
            continue
        trait = {
            "id": trait_id,
            "name": name,
            "description": description,
            "polarity": (
                "negative" if item.get("polarity") == "negative" else "positive"
            ),
            "source": item.get("source", ""),
            "reason": item.get("reason", ""),
        }
        by_id[trait_id] = trait
        added.append(trait)
    removed: list[str] = []
    for raw_id in proposals.get("trait_remove", []) or []:
        trait_id = _stable_id(raw_id)
        if trait_id in by_id:
            del by_id[trait_id]
            removed.append(trait_id)
    state["traits"] = list(by_id.values())
    if added or removed:
        changes["traits"] = {"added": added, "removed": removed}


def _stable_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def _apply_reputation(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, dict):
        return
    reputation = state.setdefault("reputation", {})
    applied: dict[str, int] = {}
    for key, raw_delta in deltas.items():
        if not isinstance(raw_delta, (int, float)):
            continue
        before = int(reputation.get(key, 0))
        reputation[key] = max(-100, min(100, before + int(raw_delta)))
        applied[key] = reputation[key] - before
    if applied:
        changes["reputation"] = applied


def _apply_inventory(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    inventory = state.setdefault("inventory", [])
    added = proposals.get("inventory_add", [])
    removed = proposals.get("inventory_remove", [])
    added_items = []
    if isinstance(added, list):
        for item in added:
            if not isinstance(item, dict):
                continue
            item_id = _stable_id(item.get("item_id") or item.get("id") or item.get("name"))
            if not item_id:
                continue
            normalized_item = {
                **item,
                "item_id": item_id,
                "name": item.get("name") or item_id,
                "description": item.get("description") or item.get("effect", ""),
                "quantity": max(1, int(item.get("quantity", 1))),
            }
            existing = next(
                (
                    current
                    for current in inventory
                    if isinstance(current, dict)
                    and current.get("item_id") == item_id
                ),
                None,
            )
            if existing is not None:
                existing["quantity"] = int(existing.get("quantity", 1)) + normalized_item["quantity"]
            else:
                inventory.append(normalized_item)
            added_items.append(normalized_item)
    removed_ids = {
        _stable_id(item.get("item_id") or item.get("id") or item.get("name"))
        if isinstance(item, dict)
        else _stable_id(item)
        for item in removed
        if (isinstance(item, (dict, str)) and item)
    } if isinstance(removed, list) else set()
    if removed_ids:
        state["inventory"] = [
            item
            for item in inventory
            if str(item.get("item_id")) not in removed_ids
        ]
    if added_items or removed_ids:
        changes["inventory"] = {
            "added": added_items,
            "removed_ids": sorted(removed_ids),
        }


def _apply_relationships(
    state: dict[str, Any],
    relationships: list[Relationship],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    deltas = proposals.get("relationship_deltas")
    if not isinstance(deltas, list):
        return
    player_age = int(state.get("identity", {}).get("age", 10))
    by_npc = {relationship.target_id: relationship for relationship in relationships}
    applied: list[dict[str, Any]] = []
    for item in deltas:
        if not isinstance(item, dict):
            continue
        npc_id = str(item.get("npc_id", ""))
        relationship = by_npc.get(npc_id)
        if relationship is None:
            continue
        relation_state = deepcopy(relationship.state)
        before = {
            "affinity": int(relation_state.get("affinity", 0)),
            "trust": int(relation_state.get("trust", 0)),
            "stage": relation_state.get("stage", "stranger"),
        }
        relation_state["affinity"] = max(
            0,
            min(100, before["affinity"] + int(item.get("affinity_delta", 0))),
        )
        relation_state["trust"] = max(
            0,
            min(100, before["trust"] + int(item.get("trust_delta", 0))),
        )
        requested_stage = item.get("stage")
        if requested_stage:
            requested_stage = str(requested_stage)
            if _stage_allowed(requested_stage, player_age):
                relation_state["stage"] = requested_stage
            else:
                pending = relation_state.setdefault("pending_stage_unlocks", [])
                requirement = 12 if requested_stage in {"dating", "romance"} else 18
                if not any(
                    item.get("stage") == requested_stage
                    for item in pending
                    if isinstance(item, dict)
                ):
                    pending.append(
                        {"stage": requested_stage, "required_age": requirement}
                    )
        _release_pending_stage(relation_state, player_age)
        relationship.state = relation_state
        applied.append(
            {
                "npc_id": npc_id,
                "before": before,
                "after": {
                    "affinity": relation_state["affinity"],
                    "trust": relation_state["trust"],
                    "stage": relation_state["stage"],
                },
            }
        )
    if applied:
        changes["relationships"] = applied


def _stage_allowed(stage: str, player_age: int) -> bool:
    if stage in {"dating", "romance"}:
        return player_age >= 12
    if stage in {"committed", "adult_stage", "marriage"}:
        return player_age >= 18
    return True


def _release_pending_stage(relation_state: dict[str, Any], player_age: int) -> None:
    pending = relation_state.get("pending_stage_unlocks", [])
    if not isinstance(pending, list):
        return
    remaining = []
    for item in pending:
        if not isinstance(item, dict):
            continue
        required_age = int(item.get("required_age", 99))
        if player_age >= required_age:
            relation_state["stage"] = str(item.get("stage", relation_state.get("stage")))
        else:
            remaining.append(item)
    relation_state["pending_stage_unlocks"] = remaining


def _update_age(
    state: dict[str, Any],
    current_datetime: datetime,
    changes: dict[str, Any],
) -> None:
    identity = state.setdefault("identity", {})
    birthday = identity.get("birthday")
    if not isinstance(birthday, str):
        return
    try:
        birth_date = datetime.fromisoformat(birthday).date()
    except ValueError:
        return
    new_age = current_datetime.date().year - birth_date.year
    if (current_datetime.month, current_datetime.day) < (
        birth_date.month,
        birth_date.day,
    ):
        new_age -= 1
    old_age = identity.get("age")
    identity["age"] = max(0, new_age)
    if old_age != identity["age"]:
        changes["age"] = {"before": old_age, "after": identity["age"]}


def _apply_lifecycle(state: dict[str, Any], changes: dict[str, Any]) -> None:
    health = state.get("resources", {}).get("health", {}).get("value")
    sanity = state.get("resources", {}).get("sanity", {}).get("value")
    lifecycle = state.setdefault("lifecycle", {})
    previous = lifecycle.get("status", "normal")
    if isinstance(health, (int, float)) and health <= 0:
        lifecycle["status"] = "dead"
        lifecycle["ending"] = {
            "type": "death",
            "reason": "生命值归零",
        }
    elif isinstance(sanity, (int, float)) and sanity <= 0:
        lifecycle["status"] = "collapsed"
        lifecycle["ending"] = None
    elif previous in {"collapsed", "unconscious"}:
        sanity_max = state.get("resources", {}).get("sanity", {}).get("max", 100)
        if isinstance(sanity, (int, float)) and sanity >= float(sanity_max) * 0.2:
            lifecycle["status"] = "normal"
            lifecycle["ending"] = None
    if lifecycle.get("status") != previous:
        changes["lifecycle"] = {
            "before": previous,
            "after": lifecycle.get("status"),
        }
