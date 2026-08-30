import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.app.api.routes as routes_module
from backend.app.main import create_app
from backend.app.db.base import Base
from backend.app.core.config import get_settings
from backend.app.models import (
    GameSession,
    JournalEntry,
    StoryArc,
    StoryArcGenerationJob,
    TurnRecord,
)
from backend.app.services.story_arcs import (
    build_story_arc_context,
    compress_story_arcs,
    ensure_story_arc_job,
    is_story_arc_blocking,
    story_arc_mode,
)
from backend.app.schemas.game import StoryArcResponse
import backend.app.services.story_arcs as story_arc_service


def _database() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _add_turns(db: Session, session_id: str, start: int, end: int) -> None:
    for sequence in range(start, end + 1):
        turn = TurnRecord(
            session_id=session_id,
            sequence=sequence,
            action={"kind": "choice", "choice_id": f"choice-{sequence}"},
            action_type="choice",
            narrative=f"这是第 {sequence} 个节点的剧情正文。",
            llm_response={
                "turn": {
                    "title": f"节点 {sequence}",
                    "scene_type": "dialogue",
                    "current_date": "1991-07-01",
                    "location_id": "home",
                }
            },
            authoritative_changes={},
            state_version_before=sequence - 1,
            state_version_after=sequence,
        )
        db.add(turn)
        db.flush()
        if sequence != 3:
            db.add(
                JournalEntry(
                    session_id=session_id,
                    turn_id=turn.id,
                    entry_type="turn",
                    title=f"节点 {sequence}",
                    summary=f"第 {sequence} 个节点摘要。",
                    data={"sequence": sequence},
                )
            )


@pytest.mark.parametrize(
    "era_id",
    ["dumbledore_era", "parent_generation", "second_generation", "modern"],
)
def test_story_arc_freezes_first_25_nodes_and_keeps_new_fallback_nodes(
    era_id: str,
) -> None:
    db = _database()
    session = GameSession(name="测试", era_id=era_id, state_version=35)
    db.add(session)
    db.flush()
    _add_turns(db, session.id, 1, 35)
    db.commit()

    job = ensure_story_arc_job(db, session.id)
    assert job is not None
    assert job.source_turn_start == 1
    assert job.source_turn_end == 25
    assert len(job.source_turn_ids) == 25

    _add_turns(db, session.id, 36, 37)
    db.commit()
    context = build_story_arc_context(
        db,
        session.id,
        action_text="继续调查",
        location_id="home",
        actor_ids=[],
    )
    assert [item["sequence"] for item in context["pending_turn_summaries"]] == list(range(1, 28))

    job.status = "ready"
    job.completed_at = job.created_at
    db.add(
        StoryArc(
            session_id=session.id,
            scope_key="arc-0001-0025",
            title="第一阶段",
            summary="前二十五个节点的阶段摘要。",
            source_turn_ids=list(job.source_turn_ids),
            covered_turn_start=1,
            covered_turn_end=25,
        )
    )
    db.commit()
    context = build_story_arc_context(
        db,
        session.id,
        action_text="继续调查",
        location_id="home",
        actor_ids=[],
    )
    assert [item["sequence"] for item in context["pending_turn_summaries"]] == [26, 27]
    assert context["story_arcs"][0].covered_turn_start == 1


def test_empty_journal_uses_first_200_characters_without_model_call() -> None:
    db = _database()
    session = GameSession(name="测试", era_id="second_generation", state_version=3)
    db.add(session)
    db.flush()
    _add_turns(db, session.id, 1, 13)
    db.commit()

    context = build_story_arc_context(
        db,
        session.id,
        action_text="回忆",
        location_id="home",
        actor_ids=[],
    )
    summaries = {
        item["sequence"]: item["summary"]
        for item in context["pending_turn_summaries"]
    }
    assert summaries[3] == "这是第 3 个节点的剧情正文。"


def test_provider_without_concurrency_automatically_selects_queue_mode() -> None:
    class Settings:
        class Game:
            allow_story_arc_parallel_with_gameplay = True

        class LLM:
            supports_concurrent_requests = False

        game = Game()
        llm = LLM()

    assert story_arc_mode(Settings()) == "queue"


def test_queue_mode_blocks_gameplay_while_job_is_pending(monkeypatch) -> None:
    class Settings:
        class Game:
            allow_story_arc_parallel_with_gameplay = True

        class LLM:
            supports_concurrent_requests = False

        game = Game()
        llm = LLM()

    monkeypatch.setattr(story_arc_service, "get_settings", lambda: Settings())
    db = _database()
    session = GameSession(name="测试", era_id="second_generation", state_version=1)
    db.add(session)
    db.flush()
    db.add(
        StoryArcGenerationJob(
            session_id=session.id,
            status="pending",
            request_id="test-job",
            source_turn_start=1,
            source_turn_end=25,
            source_turn_ids=[],
            source_state_version=1,
        )
    )
    db.commit()
    assert is_story_arc_blocking(db, session.id)


def test_manual_compression_merges_arcs_and_preserves_covered_turn_range(monkeypatch) -> None:
    db = _database()
    session = GameSession(name="测试", era_id="second_generation", state_version=75)
    db.add(session)
    db.flush()
    _add_turns(db, session.id, 1, 75)
    turns = list(
        db.query(TurnRecord)
        .filter(TurnRecord.session_id == session.id)
        .order_by(TurnRecord.sequence.asc())
    )
    for index, (start, end) in enumerate(((1, 25), (26, 50), (51, 75))):
        source_ids = [turn.id for turn in turns[start - 1:end]]
        db.add(
            StoryArcGenerationJob(
                session_id=session.id,
                status="ready",
                request_id=f"ready-{index}",
                source_turn_start=start,
                source_turn_end=end,
                source_turn_ids=source_ids,
                source_state_version=75,
                attempt=1,
                completed_at=session.created_at,
            )
        )
        db.add(
            StoryArc(
                session_id=session.id,
                scope_key=f"arc-{start:04d}-{end:04d}",
                status="ready",
                title=f"阶段 {index + 1}",
                summary=f"阶段 {index + 1} 的摘要",
                open_threads=["调查已解决的旧线索", "继续追查黑巫师", "继续追查黑巫师"],
                source_turn_ids=source_ids,
                covered_turn_start=start,
                covered_turn_end=end,
            )
        )
    db.commit()

    async def fake_request(_provider, _messages):
        return StoryArcResponse(
            response_type="story_arc",
            title="压缩后的完整故事",
            summary="保留三段剧情的关键因果和后续影响。",
            causal_chain=["关键因果"],
            open_threads=["继续追查黑巫师", "已完成的旧事项"],
            key_characters=["player"],
            key_locations=["home"],
            keywords=["主线"],
            important_turns=[5, 50, 75],
        )

    monkeypatch.setattr(story_arc_service, "_request_story_arc", fake_request)
    merged = asyncio.run(compress_story_arcs(db, session.id))

    assert merged.covered_turn_start == 1
    assert merged.covered_turn_end == 75
    assert merged.source_turn_ids == [turn.id for turn in turns]
    assert merged.open_threads == ["继续追查黑巫师"]
    assert db.query(StoryArc).filter(StoryArc.status == "merged").count() == 3
    visible = story_arc_service.list_story_arc_reads(db, session.id)
    assert len(visible) == 1
    assert visible[0]["scope_key"] == "arc-compressed-0001-0075"
    _add_turns(db, session.id, 76, 100)
    turns = list(
        db.query(TurnRecord)
        .filter(TurnRecord.session_id == session.id)
        .order_by(TurnRecord.sequence.asc())
    )
    db.add(
        StoryArcGenerationJob(
            session_id=session.id,
            status="ready",
            request_id="ready-76-100",
            source_turn_start=76,
            source_turn_end=100,
            source_turn_ids=[turn.id for turn in turns[75:]],
            source_state_version=100,
            attempt=1,
            completed_at=session.created_at,
        )
    )
    db.add(
        StoryArc(
            session_id=session.id,
            scope_key="arc-0076-0100",
            status="ready",
            title="第四阶段",
            summary="第四阶段的摘要",
            open_threads=["调查新线索"],
            source_turn_ids=[turn.id for turn in turns[75:]],
            covered_turn_start=76,
            covered_turn_end=100,
        )
    )
    db.commit()

    merged_again = asyncio.run(compress_story_arcs(db, session.id))
    assert merged_again.covered_turn_start == 1
    assert merged_again.covered_turn_end == 100
    assert merged_again.source_turn_ids == [turn.id for turn in turns]
    visible = story_arc_service.list_story_arc_reads(db, session.id)
    assert len(visible) == 1
    assert visible[0]["scope_key"] == "arc-compressed-0001-0100"


def test_manual_compression_rejects_fewer_than_two_arcs() -> None:
    db = _database()
    session = GameSession(name="测试", era_id="second_generation", state_version=25)
    db.add(session)
    db.flush()
    db.add(
        StoryArc(
            session_id=session.id,
            scope_key="arc-0001-0025",
            title="唯一阶段",
            summary="唯一阶段摘要",
            covered_turn_start=1,
            covered_turn_end=25,
        )
    )
    db.commit()

    with pytest.raises(ValueError, match="至少需要两条"):
        asyncio.run(compress_story_arcs(db, session.id))


def test_story_arc_requests_keep_thinking_when_switch_is_off(monkeypatch) -> None:
    db = _database()
    session = GameSession(name="测试", era_id="second_generation", state_version=4)
    db.add(session)
    db.flush()
    _add_turns(db, session.id, 1, 4)
    turns = list(
        db.query(TurnRecord)
        .filter(TurnRecord.session_id == session.id)
        .order_by(TurnRecord.sequence.asc())
    )
    for index, (start, end) in enumerate(((1, 2), (3, 4))):
        db.add(
            StoryArc(
                session_id=session.id,
                scope_key=f"arc-{start:04d}-{end:04d}",
                status="ready",
                title=f"阶段 {index + 1}",
                summary=f"阶段 {index + 1} 的摘要",
                source_turn_ids=[turn.id for turn in turns[start - 1:end]],
                covered_turn_start=start,
                covered_turn_end=end,
            )
        )
    db.commit()
    base = get_settings()
    disabled = base.model_copy(
        update={
            "llm": base.llm.model_copy(
                update={
                    "enable_thinking": False,
                    "thinking_disable_fields": ["thinking"],
                }
            )
        }
    )
    monkeypatch.setattr(story_arc_service, "get_settings", lambda: disabled)

    seen: list[object] = []

    async def fake_request(provider, _messages):
        seen.append(provider.settings)
        return StoryArcResponse(
            response_type="story_arc",
            title="压缩后的故事",
            summary="保留两段剧情的关键因果。",
            causal_chain=["关键因果"],
            open_threads=[],
            key_characters=["player"],
            key_locations=["home"],
            keywords=["主线"],
            important_turns=[2, 4],
        )

    monkeypatch.setattr(story_arc_service, "_request_story_arc", fake_request)
    asyncio.run(compress_story_arcs(db, session.id))

    assert len(seen) == 1
    # 玩家关掉了模型思考，故事弧压缩仍然按开启思考请求。
    assert seen[0].enable_thinking is True
    assert seen[0].thinking_disable_fields is None


def _compress_response(monkeypatch, error: BaseException):
    async def failing_compress(_db, _session_id):
        raise error

    monkeypatch.setattr(routes_module, "_require_session", lambda db, session_id: None)
    monkeypatch.setattr(routes_module, "compress_story_arcs", failing_compress)
    with TestClient(create_app()) as client:
        return client.post("/api/sessions/any-session/story-arcs/compress")


def test_compress_route_reports_timeout_with_retry_hint(monkeypatch) -> None:
    response = _compress_response(monkeypatch, asyncio.TimeoutError())
    assert response.status_code == 504
    detail = response.json()["detail"]
    # TimeoutError 的 str() 是空的，提示不能只剩一个冒号。
    assert "超时" in detail
    assert "请稍后重试" in detail


def test_compress_route_reports_generation_failure_with_retry_hint(monkeypatch) -> None:
    response = _compress_response(
        monkeypatch,
        RuntimeError("故事弧连续两次生成失败：模型服务返回 HTTP 500"),
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "请稍后重试" in detail
    assert "模型服务返回 HTTP 500" in detail


def test_compress_route_keeps_precondition_message_without_retry_hint(monkeypatch) -> None:
    response = _compress_response(
        monkeypatch,
        ValueError("至少需要两条已完成的故事弧才能压缩"),
    )
    assert response.status_code == 409
    # 前置条件不满足时重试没有意义，不应该混入"请稍后重试"。
    assert response.json()["detail"] == "至少需要两条已完成的故事弧才能压缩"
