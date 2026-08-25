from __future__ import annotations

from typing import Any


ORIGIN_DEFINITIONS: dict[str, dict[str, str]] = {
    "pure_blood": {
        "label": "纯血家族",
        "setup_description": (
            "父母双方都是巫师。你从小熟悉会动的照片、猫头鹰邮递和魔法社会礼仪，"
            "也可能背负古老家族的声誉与偏见。"
        ),
    },
    "half_blood": {
        "label": "混血家庭",
        "setup_description": (
            "家庭同时连接魔法界与麻瓜世界。你对两边都不完全陌生，"
            "也常常要在两套生活方式之间寻找自己的位置。"
        ),
    },
    "muggle_born": {
        "label": "麻瓜出身",
        "setup_description": (
            "父母都是麻瓜。魔法曾以无法解释的意外出现在童年里，"
            "而霍格沃茨来信将第一次为这些怪事给出答案。"
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


def normalize_origin_id(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("origin_id") or value.get("id") or value.get("label")
    return ORIGIN_ALIASES.get(str(value or "").strip(), "custom")
