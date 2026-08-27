from backend.app.rules.timeline import apply_timeline_effect
from backend.app.schemas.game import NarrativeResponse


def _response(
    *,
    delta: float = 0,
    touches_time_causality: bool = False,
    changed_facts: list[str] | None = None,
    consequence_applied: str | None = None,
) -> NarrativeResponse:
    return NarrativeResponse.model_validate(
        {
            "response_type": "narrative",
            "turn": {
                "title": "时间扰动测试",
                "scene_type": "encounter",
                "narrative": "测试剧情继续展开。",
                "current_date": "2020-09-01",
                "location_id": "platform_nine_three_quarters",
                "location_name": "九又四分之三站台",
            },
            "choices": [],
            "worldline": {"offset_rate": 0},
            "timeline_effect": {
                "touches_time_causality": touches_time_causality,
                "changed_facts": changed_facts or [],
                "proposed_disturbance_delta": delta,
                "consequence_applied": consequence_applied,
                "reason": "测试时间因果变化",
                "evidence": "测试事实已经发生",
            },
        }
    )


def test_ordinary_action_cannot_increase_modern_disturbance() -> None:
    state = {
        "worldline": {
            "mode": "temporal_disturbance",
            "temporal_disturbance": 4,
            "temporal_stability": 98,
            "triggered_thresholds": [],
        }
    }

    result = apply_timeline_effect(
        "modern",
        state,
        _response(
            delta=18,
            touches_time_causality=True,
            changed_facts=["模型声称课堂改变了历史"],
        ),
        action={"kind": "free_text", "text": "去上课并和同学聊天"},
    )

    assert result["temporal_disturbance"] == 4
    assert result["temporal_stability"] == 98
    assert result["triggered_thresholds"] == []
    assert result["pending_consequence"] is None


def test_causal_action_is_capped_and_triggers_threshold_once() -> None:
    state = {
        "worldline": {
            "mode": "temporal_disturbance",
            "temporal_disturbance": 4,
            "temporal_stability": 98,
            "triggered_thresholds": [],
        }
    }
    response = _response(
        delta=80,
        touches_time_causality=True,
        changed_facts=["玩家启动时间转换器并改变了历史锚点"],
    )

    result = apply_timeline_effect(
        "modern",
        state,
        response,
        action={"kind": "free_text", "text": "启动时间转换器，回到过去"},
    )

    assert result["temporal_disturbance"] == 24
    assert result["temporal_stability"] == 88
    assert result["triggered_thresholds"] == [10]
    assert result["pending_consequence"]["consequence_family"] == "object_history_conflict"
    assert response.timeline_effect.proposed_disturbance_delta == 80

    repeated = apply_timeline_effect(
        "modern",
        {
            "worldline": {
                **result,
                "temporal_disturbance": 24,
            }
        },
        _response(
            delta=0,
            touches_time_causality=True,
            consequence_applied="object_history_conflict",
        ),
        action={"kind": "free_text", "text": "观察时间转换器"},
    )

    assert repeated["triggered_thresholds"] == [10]
    assert repeated["pending_consequence"] is None
    assert repeated["delta"] == 0


def test_negative_change_requires_repair_action() -> None:
    response = _response(
        delta=-40,
        touches_time_causality=True,
        changed_facts=["时间转换器造成的裂缝已被修复"],
    )

    result = apply_timeline_effect(
        "modern",
        {
            "worldline": {
                "temporal_disturbance": 20,
                "temporal_stability": 90,
                "triggered_thresholds": [10],
            }
        },
        response,
        action={"kind": "free_text", "text": "修复时间线"},
    )

    assert result["temporal_disturbance"] == 5
    assert result["temporal_stability"] == 93.75
    assert result["delta"] == -15


def test_second_generation_keeps_legacy_worldline_response() -> None:
    response = _response(delta=12)

    result = apply_timeline_effect(
        "second_generation",
        {"worldline": {"offset_rate": 3}},
        response,
        action={"kind": "free_text", "text": "调查城堡"},
    )

    assert result == response.worldline.model_dump(mode="json")
