from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.models import (
    GameSession,
    JournalEntry,
    StoryArcGenerationJob,
    StoryArc,
    TurnRecord,
)
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.schemas.game import StoryArcResponse
from backend.app.db.session import get_session_factory


STORY_ARC_PROTOCOL = """输出必须严格遵守以下 JSON 协议：
1. 只输出一个 JSON 对象，不要输出 Markdown、代码围栏、解释或前后缀。
2. response_type 必须是 "story_arc"，schema_version 必须是 "1.0"。
3. summary 必须是对输入全部剧情节点的连续阶段性总结，不得编造输入之外的事实。
4. causal_chain、open_threads、key_characters、key_locations、keywords、important_turns
   没有内容时返回空数组，不得省略字段。

{
  "response_type": "story_arc",
  "schema_version": "1.0",
  "title": "阶段性故事弧标题",
  "summary": "完整阶段性故事弧摘要",
  "causal_chain": ["关键因果链"],
  "open_threads": ["尚未解决的线索"],
  "key_characters": ["关键人物稳定 ID 或姓名"],
  "key_locations": ["关键地点稳定 ID 或名称"],
  "keywords": ["检索关键词"],
  "important_turns": [1, 2],
  "self_check": {"source_nodes_covered": true}
}"""


_running_tasks: set[asyncio.Task[None]] = set()
_compressing_sessions: set[str] = set()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def story_arc_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return (
        "parallel"
        if (
            settings.game.allow_story_arc_parallel_with_gameplay
            and settings.llm.supports_concurrent_requests
        )
        else "queue"
    )


def is_story_arc_blocking(db: Session, session_id: str) -> bool:
    settings = get_settings()
    if story_arc_mode(settings) != "queue":
        return False
    return (
        db.scalar(
            select(StoryArcGenerationJob.id)
            .where(
                StoryArcGenerationJob.session_id == session_id,
                StoryArcGenerationJob.status.in_(("pending", "generating")),
            )
            .limit(1)
        )
        is not None
    )


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def job_to_dict(job: StoryArcGenerationJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "status": job.status,
        "source_turn_start": job.source_turn_start,
        "source_turn_end": job.source_turn_end,
        "attempt": job.attempt,
        "error": job.error,
        "started_at": _format_datetime(job.started_at),
        "completed_at": _format_datetime(job.completed_at),
        "created_at": job.created_at.isoformat(),
    }


def repair_orphaned_story_arc_jobs() -> None:
    """Restore ready job metadata for imported story arcs from older saves."""
    db = get_session_factory()()
    try:
        arcs = list(db.scalars(select(StoryArc).where(StoryArc.status == "ready")))
        for arc in arcs:
            if arc.covered_turn_start is None or arc.covered_turn_end is None:
                continue
            existing = db.scalar(
                select(StoryArcGenerationJob.id).where(
                    StoryArcGenerationJob.session_id == arc.session_id,
                    StoryArcGenerationJob.source_turn_start == arc.covered_turn_start,
                    StoryArcGenerationJob.source_turn_end == arc.covered_turn_end,
                )
            )
            if existing is not None:
                continue
            session = db.get(GameSession, arc.session_id)
            if session is None:
                continue
            db.add(
                StoryArcGenerationJob(
                    session_id=arc.session_id,
                    status="ready",
                    request_id=f"repair-arc-{uuid4()}",
                    source_turn_start=arc.covered_turn_start,
                    source_turn_end=arc.covered_turn_end,
                    source_turn_ids=list(arc.source_turn_ids or []),
                    source_state_version=session.state_version,
                    attempt=1,
                    completed_at=utc_now(),
                )
            )
        db.commit()
    finally:
        db.close()


def _journal_summary(turn: TurnRecord, journal: JournalEntry | None) -> str:
    if journal and journal.summary and journal.summary.strip():
        return journal.summary.strip()
    return (turn.narrative or "本节点没有可用的剧情正文。")[:200]


def _turn_projection(
    turn: TurnRecord,
    journal: JournalEntry | None,
    *,
    include_narrative: bool = False,
) -> dict[str, Any]:
    response = turn.llm_response if isinstance(turn.llm_response, dict) else {}
    turn_data = response.get("turn", {}) if isinstance(response, dict) else {}
    projection = {
        "sequence": turn.sequence,
        "title": str(turn_data.get("title") or f"第 {turn.sequence} 个节点"),
        "scene_type": str(turn_data.get("scene_type") or ""),
        "action": turn.action,
        "summary": _journal_summary(turn, journal),
        "current_date": turn_data.get("current_date"),
        "location_id": turn_data.get("location_id"),
        "location_name": turn_data.get("location_name"),
        "important_changes": (
            turn.authoritative_changes.get("visible", {})
            if isinstance(turn.authoritative_changes, dict)
            else {}
        ),
    }
    if include_narrative:
        projection["narrative"] = turn.narrative or ""
    return projection


def _story_arc_context(summary: StoryArc, job: StoryArcGenerationJob) -> dict[str, Any]:
    title = f"故事弧：第 {job.source_turn_start}—{job.source_turn_end} 轮"
    return {
        "scope_key": summary.scope_key,
        "title": title,
        "summary": summary.summary,
        "causal_chain": summary.causal_chain,
        "open_threads": summary.open_threads,
        "covered_turn_start": summary.covered_turn_start,
        "covered_turn_end": summary.covered_turn_end,
        "source_turn_ids": list(job.source_turn_ids or []),
    }


def _tokenize(value: str) -> set[str]:
    return {
        token.casefold()
        for token in value.replace("，", " ").replace("。", " ").split()
        if len(token.strip()) >= 2
    }


def recall_story_arcs(
    db: Session,
    session_id: str,
    *,
    action_text: str,
    location_id: str | None,
    actor_ids: list[str],
) -> list[StoryArc]:
    rows = list(
        db.execute(
            select(StoryArc, StoryArcGenerationJob)
            .join(
                StoryArcGenerationJob,
                StoryArcGenerationJob.session_id == StoryArc.session_id,
            )
            .where(
                StoryArc.session_id == session_id,
                StoryArc.status == "ready",
                StoryArcGenerationJob.status == "ready",
                StoryArcGenerationJob.source_turn_start == StoryArc.covered_turn_start,
                StoryArcGenerationJob.source_turn_end == StoryArc.covered_turn_end,
            )
            .order_by(StoryArc.updated_at.desc())
        )
    )
    if len(rows) <= 3:
        return [summary for summary, _ in rows]
    latest, _ = rows[0]
    tokens = _tokenize(action_text)
    actor_tokens = {item.casefold() for item in actor_ids}
    scored: list[tuple[int, StoryArc]] = []
    for summary, _ in rows[1:]:
        text = " ".join(
            [
                summary.summary,
                *[str(item) for item in summary.causal_chain],
                *[str(item) for item in summary.open_threads],
                *[str(item) for item in summary.key_characters],
                *[str(item) for item in summary.key_locations],
                *[str(item) for item in summary.keywords],
            ]
        ).casefold()
        score = sum(2 for token in tokens if token in text)
        if location_id and location_id.casefold() in text:
            score += 5
        score += sum(2 for token in actor_tokens if token in text)
        scored.append((score, summary))
    scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
    return [latest, *(summary for _, summary in scored[:2])]


def build_story_arc_context(
    db: Session,
    session_id: str,
    *,
    action_text: str,
    location_id: str | None,
    actor_ids: list[str],
) -> dict[str, Any]:
    settings = get_settings()
    latest_sequence = (
        db.scalar(
            select(TurnRecord.sequence)
            .where(TurnRecord.session_id == session_id)
            .order_by(TurnRecord.sequence.desc())
            .limit(1)
        )
        or 0
    )
    raw_cutoff = max(0, latest_sequence - settings.game.recent_narrative_turns)
    ready_ids: set[str] = set()
    for ids in db.scalars(
        select(StoryArcGenerationJob.source_turn_ids).where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status == "ready",
        )
    ):
        ready_ids.update(str(item) for item in (ids or []))

    old_turns = list(
        db.scalars(
            select(TurnRecord)
            .where(
                TurnRecord.session_id == session_id,
                TurnRecord.sequence <= raw_cutoff,
            )
            .order_by(TurnRecord.sequence.asc())
        )
    )
    journals = {
        entry.turn_id: entry
        for entry in db.scalars(
            select(JournalEntry).where(JournalEntry.session_id == session_id)
        )
        if entry.turn_id
    }
    pending = [
        _turn_projection(turn, journals.get(turn.id), include_narrative=False)
        for turn in old_turns
        if turn.id not in ready_ids
    ]
    arcs = recall_story_arcs(
        db,
        session_id,
        action_text=action_text,
        location_id=location_id,
        actor_ids=actor_ids,
    )
    return {
        "pending_turn_summaries": pending,
        "story_arcs": arcs,
        "ready_source_turn_ids": ready_ids,
    }


def _source_turns_for_new_job(
    db: Session,
    session_id: str,
) -> list[TurnRecord]:
    settings = get_settings()
    latest_sequence = (
        db.scalar(
            select(TurnRecord.sequence)
            .where(TurnRecord.session_id == session_id)
            .order_by(TurnRecord.sequence.desc())
            .limit(1)
        )
        or 0
    )
    raw_cutoff = latest_sequence - settings.game.recent_narrative_turns
    if raw_cutoff < settings.game.story_arc_turns:
        return []
    used_ids: set[str] = set()
    for ids in db.scalars(
        select(StoryArcGenerationJob.source_turn_ids).where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status.in_(("pending", "generating", "ready")),
        )
    ):
        used_ids.update(str(item) for item in (ids or []))
    candidates = list(
        db.scalars(
            select(TurnRecord)
            .where(
                TurnRecord.session_id == session_id,
                TurnRecord.sequence <= raw_cutoff,
            )
            .order_by(TurnRecord.sequence.asc())
        )
    )
    return [turn for turn in candidates if turn.id not in used_ids][: settings.game.story_arc_turns]


def ensure_story_arc_job(db: Session, session_id: str) -> StoryArcGenerationJob | None:
    active = db.scalar(
        select(StoryArcGenerationJob)
        .where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status.in_(("pending", "generating")),
        )
        .order_by(StoryArcGenerationJob.created_at.asc())
        .limit(1)
    )
    if active is not None:
        # 一个存档同一时间只追赶一批 25 个节点；当前任务完成后，
        # 下一次新剧情节点再触发下一批，避免后台无界并发占满模型服务。
        return None

    source_turns = _source_turns_for_new_job(db, session_id)
    settings = get_settings()
    if len(source_turns) < settings.game.story_arc_turns:
        return None
    start = source_turns[0].sequence
    end = source_turns[-1].sequence
    existing = db.scalar(
        select(StoryArcGenerationJob).where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.source_turn_start == start,
            StoryArcGenerationJob.source_turn_end == end,
        )
    )
    if existing:
        if existing.status in {"pending", "generating"}:
            return existing
        if existing.status == "failed":
            # 兼容旧版本留下的失败记录：失败来源节点没有被成功归档，
            # 下一次新剧情节点到来时应重新使用同一批节点。
            existing.status = "pending"
            existing.attempt = 0
            existing.error = None
            existing.started_at = None
            existing.completed_at = None
            db.commit()
            db.refresh(existing)
            return existing
        return None
    session = db.get(GameSession, session_id)
    if session is None:
        return None
    job = StoryArcGenerationJob(
        session_id=session_id,
        status="pending",
        request_id=f"arc-{uuid4().hex}",
        source_turn_start=start,
        source_turn_end=end,
        source_turn_ids=[turn.id for turn in source_turns],
        source_state_version=session.state_version,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.scalar(
            select(StoryArcGenerationJob).where(
                StoryArcGenerationJob.session_id == session_id,
                StoryArcGenerationJob.source_turn_start == start,
                StoryArcGenerationJob.source_turn_end == end,
            )
        )
    db.refresh(job)
    return job


def build_story_arc_messages(
    source_turns: list[dict[str, Any]],
    *,
    source_start: int,
    source_end: int,
) -> list[dict[str, str]]:
    context = {
        "protocol": {"name": "hp_simulator_story_arc", "version": "1.0"},
        "source_turn_start": source_start,
        "source_turn_end": source_end,
        "source_turns": source_turns,
    }
    system = (
        "你是《霍格沃兹人生模拟器》的长期记忆整理者。"
        "你只能总结给定的剧情节点，不得修改玩家状态，不得加入输入之外的事实。"
        "请保留关键因果、人物、地点和未解决线索，输出严格 JSON。\n\n"
        f"{STORY_ARC_PROTOCOL}"
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": "请整理以下固定范围剧情节点：\n"
            + json.dumps(context, ensure_ascii=False, default=str),
        },
    ]


def _compact_text_list(
    values: list[Any] | None,
    *,
    limit: int,
    discard_obsolete: bool = False,
) -> list[str]:
    obsolete_markers = (
        "已解决",
        "已完成",
        "不再需要",
        "已经结束",
        "过期",
        "失效",
        "放弃",
        "取消",
    )
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = str(value).strip()
        if not text:
            continue
        if discard_obsolete and any(marker in text for marker in obsolete_markers):
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text[:500])
        if len(result) >= limit:
            break
    return result


def build_story_arc_compression_messages(
    arcs: list[StoryArc],
    *,
    source_start: int,
    source_end: int,
) -> list[dict[str, str]]:
    compact_arcs = [
        {
            "covered_turn_start": arc.covered_turn_start,
            "covered_turn_end": arc.covered_turn_end,
            "title": str(arc.title or "")[:300],
            "summary": str(arc.summary or "")[:1800],
            "causal_chain": _compact_text_list(arc.causal_chain, limit=8),
            "open_threads": _compact_text_list(
                arc.open_threads,
                limit=8,
                discard_obsolete=True,
            ),
            "key_characters": _compact_text_list(arc.key_characters, limit=12),
            "key_locations": _compact_text_list(arc.key_locations, limit=12),
            "keywords": _compact_text_list(arc.keywords, limit=12),
            "important_turns": list(arc.important_turns or [])[:12],
        }
        for arc in arcs
    ]
    context = {
        "protocol": {"name": "hp_simulator_story_arc_compression", "version": "1.0"},
        "source_turn_start": source_start,
        "source_turn_end": source_end,
        "story_arcs": compact_arcs,
    }
    system = (
        "你是《霍格沃兹人生模拟器》的长期记忆压缩整理者。"
        "请把输入的多个连续故事弧压缩成一个可供后续剧情召回的长期记忆。"
        "只能使用输入中的事实，不得补写或推测剧情。"
        "摘要应优先保留会影响后续选择的因果链、重大人物关系、关键地点和仍可行动的未完事项。"
        "删除重复、琐碎、已经解决、已经失效或对后续剧情没有作用的内容。"
        "open_threads 只保留当前仍未解决且值得后续剧情处理的线索；无法确认仍有效的线索直接删除。"
        "输出必须严格 JSON。\n\n"
        f"{STORY_ARC_PROTOCOL}"
    )
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                "请将以下故事弧压缩成一个故事弧。覆盖范围固定为"
                f"第 {source_start}—{source_end} 轮：\n"
                + json.dumps(context, ensure_ascii=False, default=str)
            ),
        },
    ]


def _response_content(raw_response: dict[str, Any]) -> Any:
    content = (
        raw_response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)
    return content


def _story_arc_provider(settings: Settings) -> OpenAICompatibleProvider:
    """故事弧总结与压缩始终保留模型思考，不受顶部的模型思考开关影响。

    这两类任务要在几十个回合里做长程因果归纳，关掉思考会明显降低质量，
    而它们都在后台异步执行，玩家不会因为多花的耗时而等待。
    """
    return OpenAICompatibleProvider(
        settings.llm.model_copy(
            update={"enable_thinking": True, "thinking_disable_fields": None}
        )
    )


async def _request_story_arc(
    provider: OpenAICompatibleProvider,
    messages: list[dict[str, str]],
) -> StoryArcResponse:
    try:
        raw = await provider.chat_completion(messages, temperature=0.2)
        return StoryArcResponse.model_validate(_response_content(raw))
    except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as first_error:
        repair_messages = [
            *messages,
            {
                "role": "user",
                "content": (
                    "上一次故事弧响应未通过校验，请只根据同一批固定节点重新输出。\n"
                    f"校验原因：{first_error}\n{STORY_ARC_PROTOCOL}"
                ),
            },
        ]
        try:
            raw = await provider.chat_completion(repair_messages, temperature=0)
            return StoryArcResponse.model_validate(_response_content(raw))
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise RuntimeError(f"故事弧连续两次生成失败：{error}") from first_error


async def compress_story_arcs(db: Session, session_id: str) -> StoryArc:
    if session_id in _compressing_sessions:
        raise ValueError("当前故事弧正在压缩，请稍候")
    active_job = db.scalar(
        select(StoryArcGenerationJob.id).where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status.in_(("pending", "generating")),
        )
    )
    if active_job is not None:
        raise ValueError("当前有故事弧整理任务正在运行，请稍候再压缩")

    arcs = list(
        db.scalars(
            select(StoryArc)
            .where(
                StoryArc.session_id == session_id,
                StoryArc.status == "ready",
                StoryArc.covered_turn_start.is_not(None),
                StoryArc.covered_turn_end.is_not(None),
            )
            .order_by(
                StoryArc.covered_turn_start.asc(),
                StoryArc.covered_turn_end.asc(),
            )
        )
    )
    if len(arcs) < 2:
        raise ValueError("至少需要两条已完成的故事弧才能压缩")
    source_start = min(int(arc.covered_turn_start) for arc in arcs)
    source_end = max(int(arc.covered_turn_end) for arc in arcs)
    game_session = db.get(GameSession, session_id)
    if game_session is None:
        raise ValueError("存档不存在")

    _compressing_sessions.add(session_id)
    try:
        settings = get_settings()
        response = await asyncio.wait_for(
            _request_story_arc(
                _story_arc_provider(settings),
                build_story_arc_compression_messages(
                    arcs,
                    source_start=source_start,
                    source_end=source_end,
                ),
            ),
            timeout=settings.game.story_arc_job_timeout_seconds,
        )
        if any(turn < source_start or turn > source_end for turn in response.important_turns):
            raise RuntimeError("故事弧 important_turns 超出了压缩范围")

        source_turns = list(
            db.scalars(
                select(TurnRecord)
                .where(
                    TurnRecord.session_id == session_id,
                    TurnRecord.sequence >= source_start,
                    TurnRecord.sequence <= source_end,
                )
                .order_by(TurnRecord.sequence.asc())
            )
        )
        source_turn_ids = [turn.id for turn in source_turns]
        scope_key = f"arc-compressed-{source_start:04d}-{source_end:04d}"
        summary = db.scalar(
            select(StoryArc).where(
                StoryArc.session_id == session_id,
                StoryArc.scope_key == scope_key,
            )
        )
        if summary is None:
            summary = StoryArc(
                session_id=session_id,
                scope_key=scope_key,
                status="ready",
                title=response.title,
                summary=str(response.summary).strip()[:4000],
                causal_chain=_compact_text_list(response.causal_chain, limit=8),
                open_threads=_compact_text_list(
                    response.open_threads,
                    limit=8,
                    discard_obsolete=True,
                ),
                key_characters=_compact_text_list(response.key_characters, limit=15),
                key_locations=_compact_text_list(response.key_locations, limit=15),
                keywords=_compact_text_list(response.keywords, limit=15),
                important_turns=response.important_turns,
                source_turn_ids=source_turn_ids,
                covered_turn_start=source_start,
                covered_turn_end=source_end,
            )
            db.add(summary)
        else:
            summary.status = "ready"
            summary.title = response.title
            summary.summary = str(response.summary).strip()[:4000]
            summary.causal_chain = _compact_text_list(response.causal_chain, limit=8)
            summary.open_threads = _compact_text_list(
                response.open_threads,
                limit=8,
                discard_obsolete=True,
            )
            summary.key_characters = _compact_text_list(response.key_characters, limit=15)
            summary.key_locations = _compact_text_list(response.key_locations, limit=15)
            summary.keywords = _compact_text_list(response.keywords, limit=15)
            summary.important_turns = response.important_turns
            summary.source_turn_ids = source_turn_ids
            summary.covered_turn_start = source_start
            summary.covered_turn_end = source_end
            summary.version = (summary.version or 0) + 1

        existing_job = db.scalar(
            select(StoryArcGenerationJob).where(
                StoryArcGenerationJob.session_id == session_id,
                StoryArcGenerationJob.source_turn_start == source_start,
                StoryArcGenerationJob.source_turn_end == source_end,
            )
        )
        if existing_job is None:
            existing_job = StoryArcGenerationJob(
                session_id=session_id,
                status="ready",
                request_id=f"arc-compress-{uuid4().hex}",
                source_turn_start=source_start,
                source_turn_end=source_end,
                source_turn_ids=source_turn_ids,
                source_state_version=game_session.state_version,
                attempt=1,
                completed_at=utc_now(),
            )
            db.add(existing_job)
        else:
            existing_job.status = "ready"
            existing_job.source_turn_ids = source_turn_ids
            existing_job.error = None
            existing_job.completed_at = utc_now()

        for arc in arcs:
            arc.status = "merged"
        db.commit()
        db.refresh(summary)
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        _compressing_sessions.discard(session_id)


async def _run_story_arc_job(job_id: str) -> None:
    db = get_session_factory()()
    try:
        settings = get_settings()
        claim = db.execute(
            update(StoryArcGenerationJob)
            .where(
                StoryArcGenerationJob.id == job_id,
                StoryArcGenerationJob.status == "pending",
            )
            .values(
                status="generating",
                attempt=StoryArcGenerationJob.attempt + 1,
                started_at=utc_now(),
                error=None,
            )
        )
        if claim.rowcount != 1:
            db.rollback()
            return
        db.commit()
        job = db.get(StoryArcGenerationJob, job_id)
        if job is None:
            return
        turns = list(
            db.scalars(
                select(TurnRecord)
                .where(TurnRecord.id.in_(list(job.source_turn_ids or [])))
                .order_by(TurnRecord.sequence.asc())
            )
        )
        journals = {
            entry.turn_id: entry
            for entry in db.scalars(
                select(JournalEntry).where(JournalEntry.session_id == job.session_id)
            )
            if entry.turn_id
        }
        source = [
            _turn_projection(turn, journals.get(turn.id), include_narrative=False)
            for turn in turns
        ]
        response = await asyncio.wait_for(
            _request_story_arc(
                _story_arc_provider(settings),
                build_story_arc_messages(
                    source,
                    source_start=job.source_turn_start,
                    source_end=job.source_turn_end,
                ),
            ),
            timeout=settings.game.story_arc_job_timeout_seconds,
        )
        if any(
            turn < job.source_turn_start or turn > job.source_turn_end
            for turn in response.important_turns
        ):
            raise RuntimeError("故事弧 important_turns 超出了冻结任务范围")
        scope_key = f"arc-{job.source_turn_start:04d}-{job.source_turn_end:04d}"
        summary = db.scalar(
            select(StoryArc).where(
                StoryArc.session_id == job.session_id,
                StoryArc.scope_key == scope_key,
            )
        )
        if summary is None:
            summary = StoryArc(
                session_id=job.session_id,
                scope_key=scope_key,
                status="ready",
                title=response.title,
                summary=response.summary,
                causal_chain=response.causal_chain,
                open_threads=response.open_threads,
                key_characters=response.key_characters,
                key_locations=response.key_locations,
                keywords=response.keywords,
                important_turns=response.important_turns,
                source_turn_ids=list(job.source_turn_ids or []),
                covered_turn_start=job.source_turn_start,
                covered_turn_end=job.source_turn_end,
            )
            db.add(summary)
        else:
            summary.status = "ready"
            summary.title = response.title
            summary.summary = response.summary
            summary.causal_chain = response.causal_chain
            summary.open_threads = response.open_threads
            summary.key_characters = response.key_characters
            summary.key_locations = response.key_locations
            summary.keywords = response.keywords
            summary.important_turns = response.important_turns
            summary.source_turn_ids = list(job.source_turn_ids or [])
        summary.causal_chain = response.causal_chain
        summary.open_threads = response.open_threads
        summary.covered_turn_start = job.source_turn_start
        summary.covered_turn_end = job.source_turn_end
        summary.version = (summary.version or 0) + 1
        job.status = "ready"
        job.completed_at = utc_now()
        job.error = None
        db.commit()
    except Exception:
        db.rollback()
        job = db.get(StoryArcGenerationJob, job_id)
        if job:
            # 失败不代表这些节点已经被归档。删除任务记录后，来源节点
            # 会重新回到累积区，并在下一次新剧情节点生成后再次尝试。
            db.delete(job)
            db.commit()
    finally:
        db.close()


def schedule_story_arc_job(job_id: str) -> None:
    task = asyncio.create_task(_run_story_arc_job(job_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def recover_story_arc_jobs() -> None:
    repair_orphaned_story_arc_jobs()
    db = get_session_factory()()
    try:
        jobs = list(
            db.scalars(
                select(StoryArcGenerationJob).where(
                    StoryArcGenerationJob.status.in_(("pending", "generating"))
                )
            )
        )
        for job in jobs:
            if job.status == "generating":
                job.status = "pending"
                job.started_at = None
        db.commit()
        for job in jobs:
            schedule_story_arc_job(job.id)
    finally:
        db.close()


def list_story_arc_reads(db: Session, session_id: str) -> list[dict[str, Any]]:
    rows = list(
        db.execute(
            select(StoryArc, StoryArcGenerationJob)
            .join(
                StoryArcGenerationJob,
                StoryArcGenerationJob.session_id == StoryArc.session_id,
            )
            .where(
                StoryArc.session_id == session_id,
                StoryArc.status == "ready",
                StoryArcGenerationJob.status == "ready",
                StoryArcGenerationJob.source_turn_start == StoryArc.covered_turn_start,
                StoryArcGenerationJob.source_turn_end == StoryArc.covered_turn_end,
            )
            .order_by(StoryArc.updated_at.desc())
        )
    )
    result = []
    for summary, job in rows:
        result.append(
            {
                "scope_key": summary.scope_key,
                "status": "ready",
                "title": summary.title,
                "summary": summary.summary,
                "causal_chain": summary.causal_chain,
                "open_threads": summary.open_threads,
                "covered_turn_start": summary.covered_turn_start,
                "covered_turn_end": summary.covered_turn_end,
                "source_turn_ids": list(summary.source_turn_ids or []),
                "key_characters": list(summary.key_characters or []),
                "key_locations": list(summary.key_locations or []),
                "keywords": list(summary.keywords or []),
                "important_turns": list(summary.important_turns or []),
                "version": summary.version,
                "updated_at": summary.updated_at.isoformat(),
            }
        )
    return result


def story_arc_status(db: Session, session_id: str) -> dict[str, Any]:
    active = db.scalar(
        select(StoryArcGenerationJob)
        .where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status.in_(("pending", "generating")),
        )
        .order_by(StoryArcGenerationJob.created_at.asc())
        .limit(1)
    )
    failed = db.scalar(
        select(StoryArcGenerationJob)
        .where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status == "failed",
        )
        .order_by(StoryArcGenerationJob.completed_at.desc())
        .limit(1)
    )
    return {
        "mode": story_arc_mode(),
        "blocked": active is not None and story_arc_mode() == "queue",
        "active_job": job_to_dict(active) if active else None,
        "latest_failed_job": job_to_dict(failed) if failed else None,
    }


def retry_story_arc_job(db: Session, session_id: str) -> StoryArcGenerationJob:
    job = db.scalar(
        select(StoryArcGenerationJob)
        .where(
            StoryArcGenerationJob.session_id == session_id,
            StoryArcGenerationJob.status == "failed",
        )
        .order_by(StoryArcGenerationJob.completed_at.desc())
        .limit(1)
    )
    if job is None:
        raise ValueError("当前没有可重试的故事弧任务")
    job.status = "pending"
    job.attempt = 0
    job.error = None
    job.started_at = None
    job.completed_at = None
    db.commit()
    db.refresh(job)
    schedule_story_arc_job(job.id)
    return job
