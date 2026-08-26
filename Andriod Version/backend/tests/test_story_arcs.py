from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models import (
    GameSession,
    JournalEntry,
    StoryArc,
    StoryArcGenerationJob,
    TurnRecord,
)
from backend.app.services.story_arcs import (
    build_story_arc_context,
    ensure_story_arc_job,
    is_story_arc_blocking,
    story_arc_mode,
)
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


def test_story_arc_freezes_first_25_nodes_and_keeps_new_fallback_nodes() -> None:
    db = _database()
    session = GameSession(name="测试", era_id="second_generation", state_version=35)
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
