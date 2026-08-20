from __future__ import annotations

import json
from typing import Any

from backend.app.models import (
    GameSession,
    LongTermMemory,
    NPCState,
    PlayerState,
    Relationship,
    StorySummary,
    TurnRecord,
)
from backend.app.content.eras import get_era
from backend.app.content.attributes import catalog_for_prompt
from backend.app.content.school import normalize_grade
from backend.app.content.courses import COURSE_CATALOG, SKILL_LEVEL_MAX, SKILL_LEVEL_MIN


TURN_OUTPUT_PROTOCOL = """输出必须严格遵守以下 JSON 协议：
1. 整条回复只能包含一个 JSON 对象；不要输出 Markdown、代码围栏、解释、前言或结语。
2. 所有键名和字符串必须使用双引号。禁止使用单引号、注释、尾随逗号、NaN 或 undefined。
3. 必须输出合法 JSON 原生类型：数字不能写成字符串，布尔值只能是 true/false，空值只能是 null。
4. 不得省略必填字段。没有内容时仍要按模板返回空数组 []、空对象 {} 或 null。
5. response_type 只能是 "narrative" 或 "memory_request"，并且只能选择下面一个模板返回。
6. 返回前在内部检查 JSON 可解析性、必填字段、字段类型和 choices 顺序；不要输出检查过程。
7. NARRATIVE_JSON_TEMPLATE_BEGIN/END 和 MEMORY_REQUEST_JSON_TEMPLATE_BEGIN/END 只是模板边界标记，模板边界标记不得输出。

正式剧情必须使用下面的完整形状。choices 至少包含两个 action，最后一个必须是 free_text：
NARRATIVE_JSON_TEMPLATE_BEGIN
{
  "response_type": "narrative",
  "turn": {
    "title": "本回合标题",
    "scene_type": "dialogue",
    "narrative": "本回合完整剧情正文",
    "current_date": "1991-09-01",
    "location_id": "current_location",
    "grade": "not_enrolled",
    "school_transition": null
  },
  "choices": [
    {
      "id": "choice_1",
      "label": "第一个明确行动",
      "kind": "action",
      "risk": "low",
      "requires": [],
      "effects_hint": "",
      "effects": {
        "gains": [],
        "losses": [],
        "note": ""
      }
    },
    {
      "id": "choice_2",
      "label": "第二个明确行动",
      "kind": "action",
      "risk": "medium",
      "requires": [],
      "effects_hint": "",
      "effects": {
        "gains": [],
        "losses": [],
        "note": ""
      }
    },
    {
      "id": "choice_other",
      "label": "其他",
      "kind": "free_text",
      "risk": "low",
      "requires": [],
      "effects_hint": "",
      "effects": {
        "gains": [],
        "losses": [],
        "note": ""
      }
    }
  ],
  "state_proposals": {},
  "player_changes": {
    "inventory_add": [],
    "inventory_remove": [],
    "status_add": [],
    "status_remove": [],
    "skill_add": [],
    "skill_remove": [],
    "skill_deltas": {},
    "skill_experience_deltas": {},
    "trait_add": [],
    "trait_remove": [],
    "resource_deltas": [],
    "dimension_deltas": [],
    "resource_cap_deltas": [],
    "dimension_cap_deltas": [],
    "reputation_deltas": {},
    "relationship_deltas": []
  },
  "worldline": {
    "offset_rate": 0,
    "delta": 0,
    "reason": "本回合世界线变化原因",
    "affected_nodes": []
  },
  "events": [],
  "memory_update": {
    "summary": "本回合简短摘要",
    "create_long_term_memory": false,
    "memory": null,
    "resolved_memory_ids": []
  },
  "self_check": {
    "json_only": true,
    "required_fields_present": true
  }
}
NARRATIVE_JSON_TEMPLATE_END

只有在现有上下文不足以确认旧事件时，才使用下面的记忆查阅形状；不要混入 narrative 字段：
MEMORY_REQUEST_JSON_TEMPLATE_BEGIN
{
  "response_type": "memory_request",
  "memory_request": {
    "memory_ids": [],
    "reason": "需要查阅这些记忆的原因"
  }
}
MEMORY_REQUEST_JSON_TEMPLATE_END"""

PRE_ENROLLMENT_RULES = """当前角色尚未完成入学，必须遵守以下入学前约束：
玩家在角色创建阶段选择的魔杖和学院只是未来设定或倾向，不代表已经获得魔杖或完成分院。
在【奥利凡德魔杖店】剧情点之前，角色没有魔杖，不能使用魔杖施法、以魔杖完成动作或把魔杖当作已持有物品；
即使角色创建时已经选择了魔杖，也必须等奥利凡德相关剧情实际发生后再获得。
在【分院】剧情点之前，角色没有学院归属，不能进入学院公共休息室、以学院身份行动或使用学院声望；
即使角色创建时已经选择了学院，也必须等分院剧情实际完成后再视为已分院。
必须根据 player_state.family.bloodline 判断入学前认知：纯血和混血家庭知道魔法界与霍格沃茨并期待来信；
麻瓜家庭不知道魔法界与霍格沃茨，也不应预先知道或期待霍格沃茨来信。"""

PATRONUS_RULES = """角色创建时选择的守护神形态会保存在 player_state.patronus 中，但这只是角色潜在的守护神形态。
角色未学会【呼神护卫】时无法召唤守护神；只有 player_state.skills 明确记录已经掌握该技能后才可召唤。
不能因为已经选择守护神形态，就让角色提前施放【呼神护卫】、召出银色动物或拥有该技能。"""

GRADE_AND_COURSE_RULES = """school.grade 是程序掌握的权威年级，合法值只有 not_enrolled、year_1 至 year_7、left_school。
每轮必须在 turn.grade 返回本回合结束后的年级；没有学籍变化时必须与上下文中的当前权威年级完全一致，
并返回 school_transition=null。不得通过 player_changes、state_proposals 或叙事文字直接修改学籍。
只有发生正式入学、九月新学期升年级或永久离校时才返回 school_transition。
入学只能是 not_enrolled -> year_1，type=enrollment，reason=sorting_completed，且必须已经实际完成分院。
升年级只能逐级前进，type=promotion，reason=new_school_year_started，且只能在九月新学期开始时发生；
六月只进行当前 active_courses 的课程技能年度结算，不改变角色年级、学年或学籍起始年份；
五年级升六年级还必须已经完成 O.W.L.。禁止跳级、降级或从 left_school 返回学校。
正常毕业只能是 year_7 -> left_school，type=departure，reason=graduated_after_newts，并且已完成 N.E.W.T.。
五年级完成 O.W.L. 后可以 reason=left_after_owls 离校；辍学、开除、长期伤病或其他永久离校分别使用
dropout、expelled、medical_departure、other_permanent_departure。临时回家、假期或短期休学不改变年级。
完成 O.W.L. 时在 events 中返回 {"type":"owl_completed","results":{"课程稳定ID":"O/E/A/P/D/T"}}；
完成 N.E.W.T. 时返回同形状的 newt_completed 事件。考试成绩必须是 O、E、A、P、D、T 之一。
一年级基础课程包括变形术、咒语、魔药、魔法史、黑魔法防御术、天文学、草药学和飞行课；
二年级只能修七门核心课程；三年级首次进入时由程序打开选修窗口，必须选择 2 至 3 门：
算术占卜、麻瓜研究、占卜、古代魔文研究、神奇动物保护。
五年级进行 O.W.L.；六、七年级只能继续满足 O.W.L. 门槛的高年级课程；七年级进行 N.E.W.T.。
不得让低年级角色常规修读 N.E.W.T. 课程；炼金术等专业课程只可在最后两年且学校确实开课时出现。"""


def build_turn_messages(
    *,
    game_session: GameSession,
    player_state: PlayerState,
    npcs: list[NPCState],
    relationships: list[Relationship],
    recent_turns: list[TurnRecord],
    memories: list[LongTermMemory],
    summaries: list[StorySummary],
    action: dict[str, Any],
) -> list[dict[str, str]]:
    school = player_state.state.get("school", {})
    if not isinstance(school, dict):
        school = {}
    current_grade = normalize_grade(school)
    enrollment_started = bool(school.get("enrollment_started", current_grade != "not_enrolled"))
    system = """你是《霍格沃兹人生模拟器》的剧情主持人。
你只负责原创叙事、扮演 NPC、提出选项和提取长期事件记忆。
必须尊重用户行动，不得替玩家选择。
当前结构化状态是权威事实，不得凭空修改。
player_state.character_notes 是玩家对角色的自由补充设定。每轮叙事、行动判定和 NPC 互动都要尊重这些信息，
但补充设定不能绕过技能、资源、年龄、前置剧情和程序权威状态，也不能保证玩家行动成功。
玩家点击的选项和自由输入的行动都不是必然成功。你必须综合资源、五项长期维度、状态、词条、技能、装备、年龄、
关系、NPC 当前态度、环境、行动难度和既有剧情判断结果；结果可以成功、部分成功、失败或暂时没有实质结果。
失败必须如实写入叙事，可以造成合理的资源、状态、物品、关系影响、引发惩罚、改变后续选项或推动不同剧情；
不要为了迎合玩家而强行成功，也不要让失败直接抹除玩家选择。生成后续剧情和 NPC 态度时，必须继续综合这些因素。
每轮必须在 turn.current_date 返回当前剧情日期，格式严格为 YYYY-MM-DD；日期不能早于上下文中的上一轮日期。
每轮必须在 turn.location_id 返回当前剧情地点 ID；如果地点改变，返回新地点，否则重复上一轮地点。
不要返回具体时分，也不要使用 time_advance_minutes；日期推进由 current_date 的绝对日期负责。
上下文中的 generation.generation_mainline 是当前世代的长期剧情锚点。每轮推进都要与该主线保持时代和因果关联；
可以因玩家选择改变具体结局，但不得无故跳离该世代、遗忘核心冲突或引入其他世代的主线人物与事件。
只返回符合协议的 JSON，不要使用 Markdown 代码围栏。
每次只能返回 response_type 为 narrative 或 memory_request 的一种结果。
正式 narrative 必须包含 choices，最后一个选项必须是 kind 为 free_text 的“其他”。
每个 choices 项都必须返回 risk，且只能是 low、medium、high、fatal 之一，分别代表低、中、高、致命。
风险不仅指受伤或死亡，也包括被朋友讨厌、被教授发现、受到处分、考试不及格、损失机会、关系恶化等潜在后果。
风险等级由你结合当前场景自行判断；risk 中只返回等级，不要附带原因或解释。
如果某个选项会获得或失去物品、状态、技能或词条，必须在该选项的 effects.gains 或 effects.losses 中明确写出名称和说明；不要隐藏这些后果。
世界线偏移率必须返回 0 到 100 之间的数值。
player_changes 只能使用以下字段：inventory_add、inventory_remove、status_add、
status_remove、skill_add、skill_remove、skill_deltas、skill_experience_deltas、trait_add、trait_remove、
resource_deltas、dimension_deltas、resource_cap_deltas、dimension_cap_deltas、
reputation_deltas、relationship_deltas。
所有变化都填写相对变化量或明确的新增/移除对象，不要直接覆盖程序状态。
resource_deltas 只允许 health、mana、sanity、energy、satiety，并且每项必须包含
id、delta、reason_code、reason。dimension_deltas 只允许 constitution、intelligence、
willpower、charisma、magical_power，并且每项必须包含 id、delta、reason_code、reason。
施法只减少 mana，不减少 magical_power；普通受伤只减少 health，不减少 constitution；
恐惧或精神攻击通常只减少 sanity，只有长期创伤才可能减少 willpower。
属性目录和每项说明以本回合上下文中的 attribute_catalog 为唯一标准，不得新增其他属性。
resource_cap_deltas 和 dimension_cap_deltas 只用于明确的永久性奇遇、仪式、觉醒或长期损伤，
每项必须包含 permanent=true、id、delta、reason_code、reason。
资源 reason_code 只能使用 injury、healing、spell_cost、potion、rest、fear、mental_attack、
fatigue、hunger、poison、curse、environment、permanent_blessing、magical_awakening、ritual。
维度 reason_code 只能使用 training、study、practice、meditation、social_experience、
overcome_fear、major_discovery、age_growth、permanent_injury、long_term_illness、curse、
magical_awakening、ritual。
新增物品必须包含 item_id、name、description；新增状态必须包含 id、name、description；
新增技能必须包含 id、name、description；新增词条必须包含 id、name、description、
polarity（positive 或 negative）以及获得原因 reason。
skill_deltas 用于剧情明确要求直接改变技能等级的情况；技能等级范围为 0—10。
skill_experience_deltas 用于向当前已经存在的技能增加经验，形状为 {"技能稳定ID": 正整数}；
经验只能增加，禁止返回 0 或负数，也不能为尚未学会的技能增加经验。
技能经验范围为 0—100；经验达到 100 后，由程序自动将技能等级提升 1 并把经验清零。
模型不得自行换算等级、清零经验或在同一次成长中重复返回等价的 skill_deltas。
直接等级提升与经验成长可以并存，但必须分别对应剧情中真实发生的不同成长依据。
词条是稀有的长期状态，只有在训练成果、重大奇遇、关键选择或剧情必要时才增减；
普通对话和普通移动不要频繁生成词条。每回合最多新增两个词条。
relationship_deltas 中使用 npc_id、affinity_delta、trust_delta 和可选 stage。
不要绕过年龄限制设置恋爱阶段。
当 memory_update.create_long_term_memory=true 时，memory 必须包含非空 summary；
memory.importance 必须是 1 到 10 之间的整数，禁止返回 major、minor、high、low 等文字等级。
长期记忆可使用 memory_id、title、summary、event_type、status、importance、time、location_id、
actors、keywords、facts、open_threads、resolved_threads、related_data；没有内容的列表和对象使用 [] 或 {}。
如果现有摘要不足以确认旧事件，先返回 memory_request；每个回合最多请求一次查阅。"""
    system = f"""{system}

{GRADE_AND_COURSE_RULES}

课程状态是程序权威。课程目录、active_courses、elective_courses、newt_courses、
course_selection 和 course_history 只能由程序与玩家课程 API 修改。
模型不得通过 player_changes、state_proposals、events 或叙事文字添加、删除或替换课程。
模型不得使用 skill_add 创建课程技能；skill_deltas 和 skill_experience_deltas
只能作用于当前状态中已经存在且合法的技能。
课程技能的等级范围严格为 {SKILL_LEVEL_MIN}—{SKILL_LEVEL_MAX}，退课后技能保留但不再参加六月自然成长。

{PATRONUS_RULES}"""
    if not enrollment_started:
        system = f"{system}\n\n{PRE_ENROLLMENT_RULES}"
    system = f"{system}\n\n{TURN_OUTPUT_PROTOCOL}"

    era = get_era(game_session.era_id)
    context = {
        "session": {
            "id": game_session.id,
            "era_id": game_session.era_id,
            "status": game_session.status,
            "state_version": game_session.state_version,
        },
        "generation": {
            "id": era["id"],
            "name": era["name"],
            "years": era["years"],
            "generation_mainline": era["mainline"],
        },
        "player_state": player_state.state,
        "school_rules": {
            "current_grade": current_grade,
            "enrollment_started": enrollment_started,
            "grade_is_program_authoritative": True,
        },
        "current_courses": {
            "active_courses": school.get("active_courses", []),
            "elective_courses": school.get("elective_courses", []),
            "newt_courses": school.get("newt_courses", []),
            "course_selection": school.get("course_selection"),
            "school_year": school.get("school_year"),
            "term": school.get("term"),
        },
        "course_catalog": COURSE_CATALOG,
        "course_rules": {
            "course_state_is_program_authoritative": True,
            "model_can_modify_courses": False,
            "skill_level_range": [SKILL_LEVEL_MIN, SKILL_LEVEL_MAX],
            "june_progression": "active_courses_only",
        },
        "timeline": {
            "previous_date": (
                player_state.state.get("current_context", {}).get("current_date")
                or str(player_state.state.get("current_context", {}).get("datetime", ""))[:10]
            ),
            "previous_location_id": player_state.state.get("current_context", {}).get(
                "location_id", "unknown"
            ),
            "rule": "只返回 YYYY-MM-DD 日期；地点使用稳定的 location_id；日期不得倒退。",
        },
        "current_traits": player_state.state.get("traits", []),
        "current_statuses": player_state.state.get("statuses", []),
        "current_skills": player_state.state.get("skills", {}),
        "current_inventory": player_state.state.get("inventory", []),
        "resources": player_state.state.get("resources", {}),
        "dimensions": player_state.state.get("dimensions", {}),
        "attribute_catalog": catalog_for_prompt(),
        "protocol": {"name": "hp_simulator_turn", "version": "1.4"},
        "npcs": [
            {
                "npc_id": npc.npc_id,
                "is_original_character": npc.is_original_character,
                "state": npc.state,
            }
            for npc in npcs
        ],
        "relationships": [
            {
                "source_id": relationship.source_id,
                "target_id": relationship.target_id,
                "state": relationship.state,
            }
            for relationship in relationships
        ],
        "recent_turns": [
            {
                "sequence": turn.sequence,
                "action": turn.action,
                "narrative": turn.narrative,
                "llm_response": turn.llm_response,
                "memory_update": turn.memory_update,
            }
            for turn in recent_turns
        ],
        "long_term_memories": [_memory_to_context(memory) for memory in memories],
        "story_summaries": [
            {
                "scope": summary.scope,
                "scope_key": summary.scope_key,
                "summary": summary.summary,
                "causal_chain": summary.causal_chain,
                "open_threads": summary.open_threads,
            }
            for summary in summaries
        ],
        "player_action": action,
    }
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "以下是本回合的权威状态和上下文：\n"
            + json.dumps(context, ensure_ascii=False, default=str),
        },
    ]


def _memory_to_context(memory: LongTermMemory) -> dict[str, Any]:
    return {
        "memory_id": memory.memory_id,
        "title": memory.title,
        "summary": memory.summary,
        "event_type": memory.event_type,
        "status": memory.status,
        "importance": memory.importance,
        "time": memory.time_text,
        "location_id": memory.location_id,
        "actors": memory.actors,
        "keywords": memory.keywords,
        "facts": memory.facts,
        "open_threads": memory.open_threads,
        "source_turn_ids": memory.source_turn_ids,
    }
