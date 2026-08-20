from __future__ import annotations

from typing import Any


RESOURCE_CATALOG: dict[str, dict[str, Any]] = {
    "health": {
        "name": "生命值",
        "kind": "core",
        "default_max": 100,
        "absolute_max": 200,
        "description": "角色的生命状态，归零会触发死亡结算。",
    },
    "mana": {
        "name": "魔力值",
        "kind": "core",
        "default_max": 100,
        "absolute_max": 200,
        "description": "当前可用于施法的魔法能量。",
    },
    "sanity": {
        "name": "精神值",
        "kind": "core",
        "default_max": 100,
        "absolute_max": 150,
        "description": "角色当前的精神稳定程度，归零会导致崩溃或昏迷。",
    },
    "energy": {
        "name": "精力",
        "kind": "auxiliary",
        "default_max": 100,
        "absolute_max": 100,
        "description": "当前可用于日常行动和训练的精力。",
    },
    "satiety": {
        "name": "饱食度",
        "kind": "auxiliary",
        "default_max": 100,
        "absolute_max": 100,
        "description": "当前饱腹程度，过低会影响精力和恢复。",
    },
}

DIMENSION_CATALOG: dict[str, dict[str, Any]] = {
    "constitution": {
        "name": "体质",
        "default_max": 20,
        "absolute_max": 30,
        "description": "身体强度、耐力、恢复能力和承受冲击的能力。",
    },
    "intelligence": {
        "name": "智力",
        "default_max": 20,
        "absolute_max": 30,
        "description": "理解、推理、记忆、学习和分析复杂信息的能力。",
    },
    "willpower": {
        "name": "精神强度",
        "default_max": 20,
        "absolute_max": 30,
        "description": "抵抗恐惧、压力、诱惑和精神攻击的能力。",
    },
    "charisma": {
        "name": "魅力",
        "default_max": 20,
        "absolute_max": 30,
        "description": "表达、建立信任、说服、安慰和影响社交气氛的能力。",
    },
    "magical_power": {
        "name": "魔力强度",
        "default_max": 20,
        "absolute_max": 30,
        "description": "能够调动、承受和控制的魔法能量规模。",
    },
}

RESOURCE_IDS = frozenset(RESOURCE_CATALOG)
DIMENSION_IDS = frozenset(DIMENSION_CATALOG)
INITIALIZATION_STATUS = frozenset({"pending", "generating", "ready", "failed"})
RESOURCE_REASON_CODES = frozenset({
    "injury",
    "healing",
    "spell_cost",
    "potion",
    "rest",
    "fear",
    "mental_attack",
    "fatigue",
    "hunger",
    "poison",
    "curse",
    "environment",
    "permanent_blessing",
    "magical_awakening",
    "ritual",
})
DIMENSION_REASON_CODES = frozenset({
    "training",
    "study",
    "practice",
    "meditation",
    "social_experience",
    "overcome_fear",
    "major_discovery",
    "age_growth",
    "permanent_injury",
    "long_term_illness",
    "curse",
    "magical_awakening",
    "ritual",
})


def initial_resources() -> dict[str, dict[str, int]]:
    return {
        resource_id: {
            "value": int(definition["default_max"]),
            "max": int(definition["default_max"]),
            "base_max": int(definition["default_max"]),
        }
        for resource_id, definition in RESOURCE_CATALOG.items()
    }


def initial_dimensions() -> dict[str, dict[str, int]]:
    return {
        dimension_id: {
            "value": 0,
            "max": int(definition["default_max"]),
            "base_max": int(definition["default_max"]),
        }
        for dimension_id, definition in DIMENSION_CATALOG.items()
    }


def catalog_for_prompt() -> dict[str, Any]:
    return {
        "resources": RESOURCE_CATALOG,
        "dimensions": DIMENSION_CATALOG,
    }
