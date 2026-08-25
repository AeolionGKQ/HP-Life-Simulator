from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models import LongTermMemory


def recall_memories(
    db: Session,
    session_id: str,
    *,
    action_text: str,
    location_id: str | None,
    actor_ids: Iterable[str] = (),
) -> list[LongTermMemory]:
    settings = get_settings()
    memories = list(
        db.scalars(
            select(LongTermMemory)
            .where(LongTermMemory.session_id == session_id)
            .order_by(LongTermMemory.importance.desc(), LongTermMemory.updated_at.desc())
        )
    )
    tokens = {
        token.lower()
        for token in re.findall(r"[\w\u4e00-\u9fff]+", action_text)
        if len(token) >= 2
    }
    actor_set = set(actor_ids)
    scored: list[tuple[int, LongTermMemory]] = []
    for memory in memories:
        score = memory.importance
        if memory.status == "open":
            score += 4
        if location_id and memory.location_id == location_id:
            score += 5
        if actor_set.intersection(set(memory.actors)):
            score += 5
        searchable = set(memory.keywords)
        searchable.update(memory.actors)
        searchable.update(re.findall(r"[\w\u4e00-\u9fff]+", memory.summary))
        score += 2 * len(tokens.intersection({str(item).lower() for item in searchable}))
        if score > memory.importance:
            scored.append((score, memory))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        memory
        for _, memory in scored[: settings.game.automatic_memory_recall_limit]
    ]


def get_memories_by_ids(
    db: Session,
    session_id: str,
    memory_ids: list[str],
) -> list[LongTermMemory]:
    if not memory_ids:
        return []
    memories = list(
        db.scalars(
            select(LongTermMemory).where(
                LongTermMemory.session_id == session_id,
                LongTermMemory.memory_id.in_(memory_ids),
            )
        )
    )
    order = {memory_id: index for index, memory_id in enumerate(memory_ids)}
    return sorted(memories, key=lambda item: order.get(item.memory_id, 999))

