from __future__ import annotations

from typing import Any


ORIGIN_DEFINITIONS: dict[str, dict[str, str]] = {
    "pure_blood": {
        "label": "纯血家族",
        "setup_description": (
            "父母双方都是巫师。你从小熟悉会动的照片、猫头鹰邮递和魔法社会礼仪，"
            "也可能背负古老家族的声誉与偏见。"
        ),
        "base_prompt": "来自巫师家庭，自幼熟悉魔法界的生活、礼仪与常识。",
        "pre_enrollment_prompt": (
            "已经熟知魔法界与魔法，会期待霍格沃兹的来信；"
            "在默认流程中通常由家人带着前往对角巷购买入学物品。"
        ),
    },
    "half_blood": {
        "label": "混血家庭",
        "setup_description": (
            "家庭同时连接魔法界与麻瓜世界。你对两边都不完全陌生，"
            "也常常要在两套生活方式之间寻找自己的位置。"
        ),
        "base_prompt": "家庭同时连接巫师社会与麻瓜社会，角色从小接触过两种生活方式。",
        "pre_enrollment_prompt": (
            "对魔法界与魔法有基础的认知，会期待霍格沃兹的来信；"
            "在默认流程中可以由家人或麦格教授带着前往对角巷，具体根据剧情决定。"
        ),
    },
    "muggle_born": {
        "label": "麻瓜出身",
        "setup_description": (
            "父母都是麻瓜。魔法曾以无法解释的意外出现在童年里，"
            "而霍格沃茨来信将第一次为这些怪事给出答案。"
        ),
        "base_prompt": "父母都是麻瓜，角色在收到霍格沃兹来信前一直生活在麻瓜社会。",
        "pre_enrollment_prompt": (
            "对魔法界与魔法毫无认知，不会期待霍格沃兹的来信；"
            "霍格沃兹的来信对角色来说应当是一个惊喜，回信后在默认流程中通常由麦格教授"
            "带着前往对角巷购买入学物品。"
        ),
    },
}


ORIGIN_ALIASES = {
    "pure_blood": "pure_blood",
    "纯血": "pure_blood",
    "纯血家族": "pure_blood",
    "half_blood": "half_blood",
    "混血": "half_blood",
    "混血家庭": "half_blood",
    "muggle_born": "muggle_born",
    "麻瓜": "muggle_born",
    "麻瓜出身": "muggle_born",
    "麻瓜家庭": "muggle_born",
}


CUSTOM_ORIGIN_ID = "custom"


def normalize_origin_id(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("origin_id") or value.get("id") or value.get("label")
    normalized = str(value or "").strip()
    return ORIGIN_ALIASES.get(normalized, CUSTOM_ORIGIN_ID)


def get_origin_definition(origin_id: str) -> dict[str, str] | None:
    return ORIGIN_DEFINITIONS.get(origin_id)
