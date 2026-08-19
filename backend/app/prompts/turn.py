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
只返回符合协议的 JSON，不要使用 Markdown 代码围栏。
每次只能返回 response_type 为 narrative 或 memory_request 的一种结果。
正式 narrative 必须包含 choices，最后一个选项必须是 kind 为 free_text 的“其他”。
世界线偏移率必须返回 0 到 100 之间的数值。
state_proposals 只能使用以下可选字段：vital_deltas、attribute_deltas、skill_deltas、
reputation_deltas、inventory_add、inventory_remove、relationship_deltas。
所有变化都填写相对变化量，不要直接覆盖程序状态。
relationship_deltas 中使用 npc_id、affinity_delta、trust_delta 和可选 stage。
不要绕过年龄限制设置恋爱阶段。
如果现有摘要不足以确认旧事件，先返回 memory_request；每个回合最多请求一次查阅。"""

    context = {
        "session": {
            "id": game_session.id,
            "era_id": game_session.era_id,
            "status": game_session.status,
            "state_version": game_session.state_version,
        },
        "player_state": player_state.state,
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

