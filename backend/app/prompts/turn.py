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
    "location_id": null,
    "time_advance_minutes": 0
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
      "risk": "unknown",
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
    "trait_add": [],
    "trait_remove": [],
    "vital_deltas": {},
    "attribute_deltas": {},
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
    system = """你是《霍格沃兹人生模拟器》的剧情主持人。
你只负责原创叙事、扮演 NPC、提出选项和提取长期事件记忆。
必须尊重用户行动，不得替玩家选择。
当前结构化状态是权威事实，不得凭空修改。
上下文中的 generation.generation_mainline 是当前世代的长期剧情锚点。每轮推进都要与该主线保持时代和因果关联；
可以因玩家选择改变具体结局，但不得无故跳离该世代、遗忘核心冲突或引入其他世代的主线人物与事件。
只返回符合协议的 JSON，不要使用 Markdown 代码围栏。
每次只能返回 response_type 为 narrative 或 memory_request 的一种结果。
正式 narrative 必须包含 choices，最后一个选项必须是 kind 为 free_text 的“其他”。
如果某个选项会获得或失去物品、状态、技能或词条，必须在该选项的 effects.gains 或 effects.losses 中明确写出名称和说明；不要隐藏这些后果。
世界线偏移率必须返回 0 到 100 之间的数值。
player_changes 只能使用以下字段：inventory_add、inventory_remove、status_add、
status_remove、skill_add、skill_remove、skill_deltas、trait_add、trait_remove、
vital_deltas、attribute_deltas、reputation_deltas、relationship_deltas。
所有变化都填写相对变化量或明确的新增/移除对象，不要直接覆盖程序状态。
新增物品必须包含 item_id、name、description；新增状态必须包含 id、name、description；
新增技能必须包含 id、name、description；新增词条必须包含 id、name、description、
polarity（positive 或 negative）以及获得原因 reason。
词条是稀有的长期状态，只有在训练成果、重大奇遇、关键选择或剧情必要时才增减；
普通对话和普通移动不要频繁生成词条。每回合最多新增两个词条。
relationship_deltas 中使用 npc_id、affinity_delta、trust_delta 和可选 stage。
不要绕过年龄限制设置恋爱阶段。
如果现有摘要不足以确认旧事件，先返回 memory_request；每个回合最多请求一次查阅。"""
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
        "current_traits": player_state.state.get("traits", []),
        "current_statuses": player_state.state.get("statuses", []),
        "current_skills": player_state.state.get("skills", {}),
        "current_inventory": player_state.state.get("inventory", []),
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
