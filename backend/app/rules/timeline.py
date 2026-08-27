from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from backend.app.schemas.game import NarrativeResponse


MODERN_THRESHOLDS: tuple[int, ...] = (10, 25, 45, 65, 85, 100)
MODERN_CONSEQUENCES: dict[int, str] = {
    10: "object_history_conflict",
    25: "character_memory_conflict",
    45: "location_echo",
    65: "historical_fissure",
    85: "reality_split",
    100: "temporal_disaster",
}

_CAUSAL_ACTION_TERMS = (
    "时间转换器",
    "时间旅行",
    "穿越",
    "回到过去",
    "改变历史",
    "拯救塞德里克",
    "携带异时",
    "带回过去",
    "启动时间",
    "破坏时间",
    "time turner",
    "time travel",
    "cedric",
)
_REPAIR_ACTION_TERMS = (
    "修复时间",
    "修复历史",
    "稳定时间线",
    "关闭时间转换器",
    "归还异时",
    "repair timeline",
    "restore timeline",
)


def timeline_display_name(era_id: str) -> str:
    return "时间扰动" if era_id == "modern" else "世界线"


def initial_timeline_state(era_id: str) -> dict[str, Any]:
    if era_id == "modern":
        return {
            "mode": "temporal_disturbance",
            "temporal_disturbance": 0.0,
            "temporal_stability": 100.0,
            "last_source": None,
            "triggered_thresholds": [],
            "current_timeline_id": "original_2020",
            "memory_status": "original",
            "affected_nodes": [],
            "pending_consequence": None,
        }
    return {
        "offset_rate": 0.0,
        "last_delta": 0.0,
        "reason": "角色尚未进入故事",
        "affected_nodes": [],
    }


def apply_timeline_effect(
    era_id: str,
    state: dict[str, Any],
    response: NarrativeResponse,
    *,
    action: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """裁决模型提出的时间变化；子世代仍完整保留旧世界线语义。"""
    if era_id != "modern":
        return response.worldline.model_dump(mode="json")

    previous = state.get("worldline", {})
    previous = previous if isinstance(previous, dict) else {}
    try:
        previous_disturbance = float(previous.get("temporal_disturbance", 0))
    except (TypeError, ValueError):
        previous_disturbance = 0.0
    try:
        previous_stability = float(previous.get("temporal_stability", 100))
    except (TypeError, ValueError):
        previous_stability = 100.0

    effect = response.timeline_effect
    effect_data = effect.model_dump(mode="json") if effect is not None else {}
    changed_facts = effect_data.get("changed_facts", [])
    changed_facts = (
        [str(item) for item in changed_facts[:8]]
        if isinstance(changed_facts, list)
        else []
    )
    action_text = json.dumps(action or {}, ensure_ascii=False).lower()
    has_repair_action = any(term.lower() in action_text for term in _REPAIR_ACTION_TERMS)
    has_causal_action = (
        any(term.lower() in action_text for term in _CAUSAL_ACTION_TERMS)
        or has_repair_action
    )
    touches_causality = bool(effect_data.get("touches_time_causality"))
    try:
        proposed_delta = float(effect_data.get("proposed_disturbance_delta", 0))
    except (TypeError, ValueError):
        proposed_delta = 0.0

    accepted_delta = 0.0
    if touches_causality and changed_facts and has_causal_action:
        accepted_delta = max(-15.0, min(20.0, proposed_delta))
        if accepted_delta < 0 and not has_repair_action:
            accepted_delta = 0.0
    if not has_causal_action:
        accepted_delta = 0.0

    disturbance = max(0.0, min(100.0, previous_disturbance + accepted_delta))
    triggered = {
        int(value)
        for value in previous.get("triggered_thresholds", [])
        if str(value).isdigit()
    }
    newly_triggered = [
        threshold
        for threshold in MODERN_THRESHOLDS
        if previous_disturbance < threshold <= disturbance
        and threshold not in triggered
    ]
    triggered.update(newly_triggered)

    pending = deepcopy(previous.get("pending_consequence"))
    consequence_applied = None
    reported_consequence = str(effect_data.get("consequence_applied") or "")
    if isinstance(pending, dict) and pending.get("threshold") is not None:
        expected_consequence = str(pending.get("consequence_family") or "")
        if reported_consequence == expected_consequence:
            consequence_applied = expected_consequence
            pending = None
    if newly_triggered:
        threshold = newly_triggered[0]
        pending = {
            "type": "temporal_threshold",
            "threshold": threshold,
            "consequence_family": MODERN_CONSEQUENCES[threshold],
            "cause": str(effect_data.get("reason") or effect_data.get("evidence") or ""),
            "must_appear_next_turn": True,
        }

    stability_delta = -abs(accepted_delta) * 0.5 if accepted_delta > 0 else abs(accepted_delta) * 0.25
    stability = max(0.0, min(100.0, previous_stability + stability_delta))
    if disturbance < 25:
        memory_status = "original"
    elif disturbance < 65:
        memory_status = "blurred"
    elif disturbance < 85:
        memory_status = "conflicted"
    else:
        memory_status = "fractured"

    if response.timeline_effect is not None:
        response.timeline_effect.consequence_applied = consequence_applied
        response.timeline_effect.proposed_disturbance_delta = proposed_delta
    return {
        "mode": "temporal_disturbance",
        "offset_rate": 0.0,
        "delta": accepted_delta,
        "last_delta": accepted_delta,
        "reason": str(effect_data.get("reason") or "本回合没有确认新的时间因果变化"),
        "temporal_disturbance": disturbance,
        "temporal_stability": stability,
        "last_source": (
            str(effect_data.get("evidence") or effect_data.get("reason") or "")
            if accepted_delta
            else previous.get("last_source")
        ),
        "triggered_thresholds": sorted(triggered),
        "current_timeline_id": previous.get("current_timeline_id", "original_2020"),
        "memory_status": memory_status,
        "affected_nodes": (
            list(dict.fromkeys(
                list(previous.get("affected_nodes", [])) + list(effect_data.get("affected_nodes", []))
            ))[:8]
            if isinstance(effect_data.get("affected_nodes", []), list)
            else list(previous.get("affected_nodes", []))[:8]
        ),
        "pending_consequence": pending,
    }
