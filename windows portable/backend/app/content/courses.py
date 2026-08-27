from __future__ import annotations

from typing import Any


SKILL_LEVEL_MIN = 0
SKILL_LEVEL_MAX = 10
SKILL_EXPERIENCE_MIN = 0
SKILL_EXPERIENCE_MAX = 100

CORE_COURSE_IDS = (
    "transfiguration",
    "charms",
    "potions",
    "history_of_magic",
    "defence_against_dark_arts",
    "astronomy",
    "herbology",
)
FIRST_YEAR_REQUIRED_COURSE_IDS = (*CORE_COURSE_IDS, "flying")
ELECTIVE_COURSE_IDS = (
    "arithmancy",
    "muggle_studies",
    "divination",
    "ancient_runes",
    "care_of_magical_creatures",
)
ADVANCED_COURSE_IDS = ("alchemy", "apparition")

COURSE_CATALOG: dict[str, dict[str, Any]] = {
    "transfiguration": {
        "id": "transfiguration",
        "name": "变形术",
        "description": "研究改变物体形态与性质的魔法。",
        "category": "core",
        "skill_id": "transfiguration",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "charms": {
        "id": "charms",
        "name": "咒语",
        "description": "学习施放、控制和组合各种实用咒语。",
        "category": "core",
        "skill_id": "charms",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "potions": {
        "id": "potions",
        "name": "魔药",
        "description": "学习魔药材料、配比、熬制与辨识。",
        "category": "core",
        "skill_id": "potions",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "history_of_magic": {
        "id": "history_of_magic",
        "name": "魔法史",
        "description": "了解魔法界的重要历史、制度与冲突。",
        "category": "core",
        "skill_id": "history_of_magic",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "defence_against_dark_arts": {
        "id": "defence_against_dark_arts",
        "name": "黑魔法防御术",
        "description": "学习识别、抵御和应对黑魔法与危险生物。",
        "category": "core",
        "skill_id": "defence_against_dark_arts",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "astronomy": {
        "id": "astronomy",
        "name": "天文学",
        "description": "观察星象并理解天体与魔法世界的联系。",
        "category": "core",
        "skill_id": "astronomy",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "herbology": {
        "id": "herbology",
        "name": "草药学",
        "description": "认识、培育和处理具有魔法性质的植物。",
        "category": "core",
        "skill_id": "herbology",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "flying": {
        "id": "flying",
        "name": "飞行课",
        "description": "学习基础飞行、扫帚控制与空中安全。",
        "category": "required",
        "skill_id": "flying",
        "available_from_grade": "year_1",
        "owl_required": None,
        "newt_required": False,
    },
    "arithmancy": {
        "id": "arithmancy",
        "name": "算术占卜",
        "description": "用数字、模式与魔法规律分析潜在结果。",
        "category": "elective",
        "skill_id": "arithmancy",
        "available_from_grade": "year_3",
        "owl_required": "E",
        "newt_required": True,
    },
    "muggle_studies": {
        "id": "muggle_studies",
        "name": "麻瓜研究",
        "description": "系统了解麻瓜社会、文化与生活方式。",
        "category": "elective",
        "skill_id": "muggle_studies",
        "available_from_grade": "year_3",
        "owl_required": "A",
        "newt_required": True,
    },
    "divination": {
        "id": "divination",
        "name": "占卜",
        "description": "研究预兆、象征与窥见可能未来的方法。",
        "category": "elective",
        "skill_id": "divination",
        "available_from_grade": "year_3",
        "owl_required": "A",
        "newt_required": True,
    },
    "ancient_runes": {
        "id": "ancient_runes",
        "name": "古代魔文研究",
        "description": "解读古代魔法文字、符号和遗留法术。",
        "category": "elective",
        "skill_id": "ancient_runes",
        "available_from_grade": "year_3",
        "owl_required": "E",
        "newt_required": True,
    },
    "care_of_magical_creatures": {
        "id": "care_of_magical_creatures",
        "name": "神奇动物保护",
        "description": "学习辨识、照料和安全接触神奇动物。",
        "category": "elective",
        "skill_id": "care_of_magical_creatures",
        "available_from_grade": "year_3",
        "owl_required": "A",
        "newt_required": True,
    },
    "alchemy": {
        "id": "alchemy",
        "name": "炼金术",
        "description": "研究物质转化、魔法反应与炼金原理。",
        "category": "advanced",
        "skill_id": "alchemy",
        "available_from_grade": "year_6",
        "owl_required": "O",
        "newt_required": True,
    },
    "apparition": {
        "id": "apparition",
        "name": "幻影移形",
        "description": "在成年资格和指导下学习安全的空间转移。",
        "category": "advanced",
        "skill_id": "apparition",
        "available_from_grade": "year_6",
        "owl_required": "E",
        "newt_required": True,
    },
}


def get_course(course_id: str) -> dict[str, Any] | None:
    return COURSE_CATALOG.get(course_id)


def clamp_skill_level(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        numeric = SKILL_LEVEL_MIN
    return max(SKILL_LEVEL_MIN, min(SKILL_LEVEL_MAX, numeric))


def course_skill_ids(course_ids: list[str] | tuple[str, ...]) -> set[str]:
    return {
        COURSE_CATALOG[course_id]["skill_id"]
        for course_id in course_ids
        if course_id in COURSE_CATALOG
    }


def grade_number(grade: str) -> int:
    if grade.startswith("year_"):
        try:
            return int(grade.removeprefix("year_"))
        except ValueError:
            pass
    return 0


def passed_owl_grade(result: str | None) -> bool:
    return result in {"O", "E", "A"}
