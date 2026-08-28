from __future__ import annotations

import json
from typing import Any

from backend.app.content.attributes import catalog_for_prompt
from backend.app.content.eras import get_era
from backend.app.models import GameSession, PlayerState


ATTRIBUTE_INITIALIZATION_PROTOCOL = """输出必须严格遵守以下 JSON 协议：
1. 只能输出一个 JSON 对象，不要输出 Markdown、代码围栏、解释或额外文字。
2. response_type 必须是 "attribute_initialization"。
3. resources 必须完整包含 health、mana、sanity、energy、satiety 五项。
4. dimensions 必须完整包含 constitution、intelligence、willpower、charisma、magical_power 五项。
5. 每项只能返回 id、value、max、reason；value 和 max 必须是数字。
6. 资源当前值必须在 0 到 max 之间，资源 max 不得超过目录的 absolute_max。
7. 维度当前值必须在 0 到 max 之间，维度 max 不得超过目录的 absolute_max。
8. 初始属性只能根据角色创建设定生成，不得生成剧情、选项、世界线、关系变化或长期记忆。
9. reason 必须简短说明该数值与角色设定之间的关系。

ATTRIBUTE_INITIALIZATION_JSON_TEMPLATE_BEGIN
{
  "response_type": "attribute_initialization",
  "schema_version": "1.2",
  "resources": [
    {"id": "health", "value": 100, "max": 100, "reason": "角色当前身体状况稳定"},
    {"id": "mana", "value": 100, "max": 100, "reason": "角色当前魔力储备稳定"},
    {"id": "sanity", "value": 100, "max": 100, "reason": "角色当前精神状态稳定"},
    {"id": "energy", "value": 100, "max": 100, "reason": "角色在故事开始时精力充足"},
    {"id": "satiety", "value": 100, "max": 100, "reason": "角色在故事开始时并不饥饿"}
  ],
  "dimensions": [
    {"id": "constitution", "value": 10, "max": 20, "reason": "根据角色的体格和童年经历评估"},
    {"id": "intelligence", "value": 10, "max": 20, "reason": "根据角色的学习倾向和经历评估"},
    {"id": "willpower", "value": 10, "max": 20, "reason": "根据角色的压力承受和价值观评估"},
    {"id": "charisma", "value": 10, "max": 20, "reason": "根据角色的外貌、表达和社交设定评估"},
    {"id": "magical_power", "value": 10, "max": 20, "reason": "根据角色的魔法天赋和背景评估"}
  ],
  "calibration_summary": "角色初始能力的整体概述",
  "self_check": {
    "all_ids_valid": true,
    "all_values_in_range": true,
    "based_on_character_setup": true
  }
}
ATTRIBUTE_INITIALIZATION_JSON_TEMPLATE_END"""


def build_attribute_initialization_messages(
    game_session: GameSession,
    player_state: PlayerState,
    *,
    adjustment_instruction: str = "",
) -> list[dict[str, str]]:
    era = get_era(game_session.era_id)
    state = player_state.state
    setup = state.get("setup", {})
    endgame_entry = state.get("endgame_entry") or {}
    life_stage = "adult_graduate" if endgame_entry else "student"
    patronus_learned = game_session.era_id == "modern" or bool(endgame_entry)
    patronus_instruction = (
        "当前开局已视为学会【呼神护卫】，选择的守护神形态可以作为已掌握技能的召唤形态；"
        "这不代表施放必然成功，也不额外给予属性奖励。"
        if patronus_learned
        else
        "守护神只是角色未来可能显现的形态，不能据此认定角色已经学会【呼神护卫】，也不能直接给予数值奖励。"
    )
    context = {
        "protocol": {"name": "hp_simulator_attribute_initialization", "version": "1.2"},
        "generation": {
            "id": era["id"],
            "name": era["name"],
            "years": era["years"],
            "mainline": era["mainline"],
        },
        "character_setup": {
            "identity": state.get("identity", {}),
            "appearance": state.get("appearance", {}),
            "family": state.get("family", {}),
            "background": state.get("background", {}),
            "personality": state.get("personality", {}),
            "values": state.get("values", {}),
            "wand": state.get("wand"),
            "magic_talents": state.get("magic_talents", []),
            "pet": state.get("pet"),
            "patronus": state.get("patronus"),
            "character_notes": state.get("character_notes"),
            "school": state.get("school", {}),
            "starting_context": state.get("current_context", {}),
            "setup_answers": setup.get("answers", {}),
            "life_stage": life_stage,
            "endgame_entry": endgame_entry,
        },
        "catalog": catalog_for_prompt(),
        "adjustment_instruction": adjustment_instruction.strip(),
    }
    system = (
        "你是《霍格沃兹人生模拟器》的角色属性校准器。"
        "当前任务只有一个：根据角色创建设定生成角色初始资源和五项长期维度。"
        "四个世代使用完全相同的属性规则，世代只影响时代背景和剧情主线。"
        "不要生成任何剧情，不要生成选项，不要修改关系、世界线、技能、词条或物品。"
        f"{patronus_instruction}"
        "character_setup.life_stage 说明角色当前的人生阶段："
        "student 表示刚入学或在校的少年，按同龄学生水准生成；"
        "adult_graduate 表示角色已经完成霍格沃茨七年教育、通过 N.E.W.T. 毕业并成年，"
        "必须按成长后的成年巫师水准生成——体质、意志、魅力和魔力都应明显高于十一岁新生，"
        "但仍要克制，不能给出接近上限或超越同代顶尖巫师的数值。"
        "所有属性必须覆盖完整目录，数值要克制、合理，并且理由必须能从角色设定中找到依据。"
        "如果 adjustment_instruction 非空，它是玩家对初始属性方向的偏好；"
        "应在不违反属性目录、数值上限和角色设定的前提下尽量遵守，不能把它当作直接修改数值的命令。"
        f"\n\n{ATTRIBUTE_INITIALIZATION_PROTOCOL}"
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "以下是角色创建完成后的权威设定：\n"
            + json.dumps(context, ensure_ascii=False, default=str),
        },
    ]
