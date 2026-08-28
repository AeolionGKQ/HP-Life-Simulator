from types import SimpleNamespace
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.content.attributes import (
    DIMENSION_IDS,
    RESOURCE_IDS,
    initial_dimensions,
    initial_resources,
)
from backend.app.prompts.attributes import build_attribute_initialization_messages
from backend.app.rules.state import apply_turn_rules
from backend.app.schemas.game import NarrativeResponse
from backend.app.services.attributes import (
    ATTRIBUTE_GENERATION_TIMEOUT_SECONDS,
    _generation_abandoned,
)


def test_interrupted_generation_is_treated_as_abandoned() -> None:
    stale = datetime.now(timezone.utc) - timedelta(
        seconds=ATTRIBUTE_GENERATION_TIMEOUT_SECONDS + 1
    )

    assert _generation_abandoned({"status": "generating"}) is True
    assert _generation_abandoned({"started_at": ""}) is True
    assert _generation_abandoned({"started_at": "not-a-timestamp"}) is True
    assert _generation_abandoned({"started_at": stale.isoformat()}) is True


def test_running_generation_is_not_treated_as_abandoned() -> None:
    started_at = datetime.now(timezone.utc).isoformat()

    assert _generation_abandoned({"started_at": started_at}) is False


def _response(player_changes: dict) -> NarrativeResponse:
    return NarrativeResponse.model_validate({
        "response_type": "narrative",
        "turn": {
            "title": "属性测试",
            "scene_type": "encounter",
            "narrative": "测试剧情。",
            "current_date": "1991-07-01",
            "location_id": "home",
        },
        "choices": [
            {"id": "one", "label": "一", "kind": "action", "risk": "low"},
            {"id": "two", "label": "二", "kind": "action", "risk": "medium"},
            {"id": "choice_other", "label": "其他", "kind": "free_text", "risk": "low"},
        ],
        "state_proposals": {},
        "player_changes": player_changes,
        "worldline": {
            "offset_rate": 0,
            "delta": 0,
            "reason": "无变化",
            "affected_nodes": [],
        },
        "events": [],
        "memory_update": {},
        "self_check": {},
    })


def _state() -> dict:
    return {
        "resources": initial_resources(),
        "dimensions": {
            **initial_dimensions(),
            "willpower": {"value": 10, "max": 20, "base_max": 20},
        },
        "identity": {"age": 11, "birthday": "1980-03-12"},
        "current_context": {
            "datetime": "1991-07-01T09:00:00+00:00",
            "current_date": "1991-07-01",
        },
        "lifecycle": {"status": "normal"},
    }


def test_attribute_catalog_is_complete_and_has_no_old_attributes() -> None:
    assert RESOURCE_IDS == {"health", "mana", "sanity", "energy", "satiety"}
    assert DIMENSION_IDS == {
        "constitution",
        "intelligence",
        "willpower",
        "charisma",
        "magical_power",
    }


def test_resource_and_dimension_rules_clamp_and_audit() -> None:
    response = _response({
        "resource_deltas": [{
            "id": "mana",
            "delta": -120,
            "reason_code": "spell_cost",
            "reason": "施放大型魔法",
        }],
        "dimension_deltas": [{
            "id": "willpower",
            "delta": 5,
            "reason_code": "training",
            "reason": "完成训练",
        }],
    })
    state, changes = apply_turn_rules(_state(), [], response)
    assert state["resources"]["mana"]["value"] == 0
    assert state["dimensions"]["willpower"]["value"] == 11
    assert changes["resources"]["applied"][0]["delta"] == -100
    assert changes["dimensions"]["applied"][0]["proposed_delta"] == 5


def test_fractional_resource_and_dimension_changes_are_rounded() -> None:
    state = _state()
    state["resources"]["energy"] = {"value": 71.0, "max": 100.0}
    state["dimensions"]["constitution"] = {"value": 10.0, "max": 20.0}
    response = _response({
        "resource_deltas": [{
            "id": "energy",
            "delta": -0.123456,
            "reason_code": "rest",
            "reason": "短暂休息",
        }],
        "dimension_deltas": [{
            "id": "constitution",
            "delta": 0.123456,
            "reason_code": "training",
            "reason": "基础训练",
        }],
    })

    state, changes = apply_turn_rules(state, [], response)

    assert state["resources"]["energy"]["value"] == 70.8765
    assert changes["resources"]["applied"][0]["delta"] == -0.1235
    assert state["dimensions"]["constitution"]["value"] == 10.1235
    assert changes["dimensions"]["applied"][0]["delta"] == 0.1235


def test_inventory_removal_keeps_the_existing_item_name_for_audit() -> None:
    state = _state()
    state["inventory"] = [{
        "item_id": "sealed_box",
        "name": "无名旧盒",
        "description": "没有留下名称的旧盒子",
        "quantity": 1,
    }]
    response = _response({
        "inventory_remove": ["sealed_box"],
    })

    state, changes = apply_turn_rules(state, [], response)

    assert state["inventory"] == []
    assert changes["inventory"]["removed"][0]["item_id"] == "sealed_box"
    assert changes["inventory"]["removed"][0]["name"] == "无名旧盒"


@pytest.mark.parametrize(
    "era_id",
    ["dumbledore_era", "parent_generation", "second_generation", "modern"],
)
def test_shared_skill_item_and_trait_rules_run_in_both_eras(era_id: str) -> None:
    state = _state()
    state["skills"] = {
        "wandwork": {
            "id": "wandwork",
            "name": "魔杖运用",
            "description": "基础魔杖运用",
            "level": 1,
            "experience": 0,
        }
    }
    next_state, changes = apply_turn_rules(
        state,
        [],
        _response(
            {
                "skill_deltas": {"wandwork": 2},
                "inventory_add": [
                    {
                        "item_id": "test_item",
                        "name": "测试物品",
                        "description": "跨世代测试物品",
                        "quantity": 1,
                    }
                ],
                "trait_add": [
                    {
                        "id": "test_trait",
                        "name": "测试词条",
                        "description": "跨世代测试词条",
                        "polarity": "positive",
                        "reason": "测试",
                    }
                ],
            }
        ),
        era_id=era_id,
    )

    assert next_state["skills"]["wandwork"]["level"] == 3
    assert next_state["inventory"][0]["item_id"] == "test_item"
    assert next_state["traits"][0]["id"] == "test_trait"
    assert "wandwork" in changes["skills"]
    assert changes["inventory"]["added"][0]["item_id"] == "test_item"
    assert changes["traits"]["added"][0]["id"] == "test_trait"


def test_health_zero_causes_death_and_sanity_zero_causes_collapse() -> None:
    death, _ = apply_turn_rules(
        _state(),
        [],
        _response({
            "resource_deltas": [{
                "id": "health",
                "delta": -100,
                "reason_code": "injury",
                "reason": "致命伤",
            }]
        }),
    )
    assert death["lifecycle"]["status"] == "dead"

    collapsed, _ = apply_turn_rules(
        _state(),
        [],
        _response({
            "resource_deltas": [{
                "id": "sanity",
                "delta": -100,
                "reason_code": "mental_attack",
                "reason": "精神攻击",
            }]
        }),
    )
    assert collapsed["lifecycle"]["status"] == "collapsed"


def test_story_date_and_location_are_persisted_without_allowing_date_regression() -> None:
    response = _response({})
    response.turn.current_date = date(1991, 9, 3)
    response.turn.location_id = "hogwarts_library"
    state, changes = apply_turn_rules(_state(), [], response)
    assert state["current_context"]["current_date"] == "1991-09-03"
    assert state["current_context"]["location_id"] == "hogwarts_library"
    assert changes["date"]["after"] == "1991-09-03"
    assert changes["location_id"] == "hogwarts_library"

    response.turn.current_date = date(1991, 6, 30)
    state, changes = apply_turn_rules(state, [], response)
    assert state["current_context"]["current_date"] == "1991-09-03"
    assert changes["date_rejected"]["reason"] == "story_date_cannot_move_backwards"


@pytest.mark.parametrize(
    "era_id",
    ["dumbledore_era", "parent_generation", "second_generation", "modern"],
)
def test_attribute_initialization_prompt_uses_same_protocol_for_every_era(
    era_id: str,
) -> None:
    messages = build_attribute_initialization_messages(
        SimpleNamespace(id="session", era_id=era_id),
        SimpleNamespace(state={
            "setup": {"answers": {}},
            "identity": {},
            "appearance": {},
            "family": {},
            "background": {},
            "personality": {},
            "values": {},
            "magic_talents": [],
        }),
    )
    system = messages[0]["content"]
    assert "四个世代使用完全相同的属性规则" in system
    assert "resource_deltas" not in system
    assert "vital_deltas" not in system
    if era_id == "modern":
        assert "当前开局已视为学会【呼神护卫】" in system
        assert "守护神只是角色未来可能显现的形态" not in system
    else:
        assert "守护神只是角色未来可能显现的形态" in system


def test_attribute_initialization_prompt_includes_optional_adjustment_preference() -> None:
    messages = build_attribute_initialization_messages(
        SimpleNamespace(id="session", era_id="second_generation"),
        SimpleNamespace(state={"setup": {"answers": {}}}),
        adjustment_instruction="体质和意志稍高，但不要让属性过于极端",
    )

    assert "体质和意志稍高" in messages[1]["content"]
    assert "玩家对初始属性方向的偏好" in messages[0]["content"]
    assert "不能把它当作直接修改数值的命令" in messages[0]["content"]


def test_dumbledore_endgame_attribute_prompt_marks_patronus_learned() -> None:
    messages = build_attribute_initialization_messages(
        SimpleNamespace(id="session", era_id="dumbledore_era"),
        SimpleNamespace(
            state={
                "setup": {"answers": {}},
                "endgame_entry": {
                    "starting_point": "godrics_hollow_1899_summer",
                },
            }
        ),
    )
    system = messages[0]["content"]
    assert "当前开局已视为学会【呼神护卫】" in system
    assert "守护神只是角色未来可能显现的形态" not in system


def test_attribute_initialization_prompt_keeps_empty_adjustment_backward_compatible() -> None:
    messages = build_attribute_initialization_messages(
        SimpleNamespace(id="session", era_id="second_generation"),
        SimpleNamespace(state={"setup": {"answers": {}}}),
    )

    assert '"adjustment_instruction": ""' in messages[1]["content"]
