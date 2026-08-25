from __future__ import annotations

GRADE_IDS = {
    "not_enrolled",
    "year_1",
    "year_2",
    "year_3",
    "year_4",
    "year_5",
    "year_6",
    "year_7",
    "left_school",
}

PROMOTION_TARGETS = {
    "year_1": "year_2",
    "year_2": "year_3",
    "year_3": "year_4",
    "year_4": "year_5",
    "year_5": "year_6",
    "year_6": "year_7",
}

DEPARTURE_REASONS = {
    "graduated_after_newts",
    "left_after_owls",
    "dropout",
    "expelled",
    "medical_departure",
    "other_permanent_departure",
}

PROMOTION_REASON = "new_school_year_started"

PERMANENT_DEPARTURE_REASONS = {
    "dropout",
    "expelled",
    "medical_departure",
    "other_permanent_departure",
}

EXAM_GRADES = {"O", "E", "A", "P", "D", "T"}

HOUSE_IDS = {"gryffindor", "hufflepuff", "ravenclaw", "slytherin"}


def normalize_grade(school: dict[str, object]) -> str:
    grade = school.get("grade")
    if grade in GRADE_IDS:
        return str(grade)
    return "not_enrolled"
