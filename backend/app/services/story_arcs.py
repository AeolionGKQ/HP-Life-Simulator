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
            StoryArcGenerationJob.status.in_(("pending", "generating", "ready", "failed")),
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
        return existing if existing.status in {"pending", "generating"} else None
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
                OpenAICompatibleProvider(settings.llm),
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
    except Exception as error:
        db.rollback()
        job = db.get(StoryArcGenerationJob, job_id)
        if job:
            job.status = "failed"
            job.error = str(error)[:2000]
            job.completed_at = utc_now()
            db.commit()
    finally:
        db.close()


def schedule_story_arc_job(job_id: str) -> None:
    task = asyncio.create_task(_run_story_arc_job(job_id))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)


def recover_story_arc_jobs() -> None:
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
