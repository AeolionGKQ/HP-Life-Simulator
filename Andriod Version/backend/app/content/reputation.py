from __future__ import annotations

import math
from typing import Any


REPUTATION_MIN = -100
REPUTATION_MAX = 100
REPUTATION_TURN_LIMIT = 10

REPUTATION_LEVELS = (
    {
        "id": "dark_paragon",
        "name": "黑暗典范",
        "min": -100,
        "max": -81,
        "alignment": "强烈偏向黑巫师",
        "description": "声名极其恶劣，接近被整个社会视为重大威胁。",
    },
    {
        "id": "black_wizard",
        "name": "黑巫师",
        "min": -80,
        "max": -61,
        "alignment": "偏向黑巫师",
        "description": "公开被视为危险的黑巫师或黑魔法倾向者。",
    },
    {
        "id": "dangerous",
        "name": "危险人物",
        "min": -60,
        "max": -31,
        "alignment": "偏向黑暗",
        "description": "被认为可能伤害他人或为了目的不择手段。",
    },
    {
        "id": "suspicious",
        "name": "可疑倾向",
        "min": -30,
        "max": -11,
        "alignment": "轻微负面",
        "description": "行为动机不稳定，别人会多问一句、多观察一步。",
    },
    {
        "id": "neutral",
        "name": "中立",
        "min": -10,
        "max": 10,
        "alignment": "中立倾向",
        "description": "尚无明确的善恶或阵营印象。",
    },
    {
        "id": "kindly",
        "name": "友善倾向",
        "min": 11,
        "max": 30,
        "alignment": "轻微正面",
        "description": "通常被看作善意、愿意合作，但还没有形成强烈公众声誉。",
    },
    {
        "id": "trusted",
        "name": "正直可靠",
        "min": 31,
        "max": 60,
        "alignment": "正面倾向",
        "description": "多数普通巫师愿意相信其动机。",
    },
    {
        "id": "white_wizard",
        "name": "白巫师",
        "min": 61,
        "max": 80,
        "alignment": "偏向白巫师",
        "description": "明显站在正义和保护弱者的一侧。",
    },
    {
        "id": "light_paragon",
        "name": "光明典范",
        "min": 81,
        "max": 100,
        "alignment": "强烈偏向白巫师",
        "description": "被普遍认为是极其正直、可靠且愿意保护他人的巫师。",
    },
)

_DEFAULT_REPUTATION = {
    "score": 0,
    "level_id": "neutral",
    "level_name": "中立",
    "alignment": "中立倾向",
    "last_delta": 0,
    "last_reason": "",
}


def clamp_reputation_score(value: Any) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError, OverflowError):
        numeric = 0
    return max(REPUTATION_MIN, min(REPUTATION_MAX, numeric))


def get_reputation_level(score: Any) -> dict[str, Any]:
    normalized = clamp_reputation_score(score)
    for level in REPUTATION_LEVELS:
        if level["min"] <= normalized <= level["max"]:
            return dict(level)
    return dict(REPUTATION_LEVELS[4])


def normalize_reputation(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    raw_score = raw.get("score")
    if raw_score is None and isinstance(raw.get("morality"), (int, float)):
        raw_score = raw["morality"]
    score = clamp_reputation_score(raw_score)
    level = get_reputation_level(score)
    last_delta = raw.get("last_delta", 0)
    if isinstance(last_delta, bool) or not isinstance(last_delta, (int, float)):
        last_delta = 0
    if isinstance(last_delta, float) and not math.isfinite(last_delta):
        last_delta = 0
    normalized = {
        "score": score,
        "level_id": level["id"],
        "level_name": level["name"],
        "alignment": level["alignment"],
        "last_delta": max(-REPUTATION_TURN_LIMIT, min(REPUTATION_TURN_LIMIT, int(last_delta))),
        "last_reason": str(raw.get("last_reason") or ""),
    }
    legacy = {
        key: item
        for key, item in raw.items()
        if key not in {
            "score",
            "morality",
            "level_id",
            "level_name",
            "alignment",
            "last_delta",
            "last_reason",
        }
    }
    if legacy:
        normalized["legacy_breakdown"] = legacy
    return normalized


def reputation_summary(value: Any) -> dict[str, Any]:
    normalized = normalize_reputation(value)
    level = get_reputation_level(normalized["score"])
    return {
        "score": normalized["score"],
        "range": [REPUTATION_MIN, REPUTATION_MAX],
        "level_id": level["id"],
        "level_name": level["name"],
        "alignment": level["alignment"],
        "description": level["description"],
        "last_delta": normalized["last_delta"],
        "last_reason": normalized["last_reason"],
    }
