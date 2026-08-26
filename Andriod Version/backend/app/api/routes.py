from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import LLMSettings, get_settings, update_llm_config
from backend.app.content.eras import list_eras
from backend.app.db.session import get_db, get_engine
from backend.app.models import GameSession
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.schemas.common import (
    HealthResponse,
    LLMConfigUpdate,
    LLMConfigStatus,
    LLMConnectionResult,
)
from backend.app.schemas.sessions import (
    SessionCreate,
    SessionDetail,
    SessionRead,
    SessionRename,
    SaveExport,
)
from backend.app.schemas.game import (
    ActionRequest,
    AttributeInitializationRequest,
    CourseSelectionRequest,
    CourseView,
    JournalRead,
    MemoryRead,
    NPCRead,
    PlayerStateResponse,
    RelationshipRead,
    SetupAnswer,
    SetupConfirm,
    SetupNavigate,
    SetupView,
    StoryArcJobRead,
    StoryArcRead,
    StoryArcStatus,
    TurnResponse,
)
from backend.app.services.sessions import (
    create_session,
    delete_session,
    export_session,
    get_player_state,
    get_session,
    list_journal,
    list_memories,
    list_npcs,
    list_relationships,
    list_sessions,
    list_turns,
    import_session,
    rename_session,
)
from backend.app.services.setup import (
    confirm_setup,
    get_setup_view,
    navigate_setup_step,
    save_setup_answer,
)
from backend.app.services.turns import TurnGenerationError, generate_turn
from backend.app.services.story_arcs import (
    job_to_dict,
    list_story_arc_reads,
    retry_story_arc_job,
    story_arc_status,
)
from backend.app.services.courses import get_courses_view, select_courses
from backend.app.services.attributes import (
    AttributeInitializationError,
    initialize_attributes,
)

router = APIRouter(prefix="/api")


@router.get("/content/eras")
def get_eras() -> list[dict[str, object]]:
    return list_eras()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "error"
    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        app_name=settings.app.name,
        database=database_status,
        llm_configured=bool(settings.llm.api_key.get_secret_value()),
    )


@router.get("/config/llm", response_model=LLMConfigStatus)
def llm_config_status() -> LLMConfigStatus:
    settings = get_settings()
    return LLMConfigStatus(
        configured=bool(settings.llm.api_key.get_secret_value()),
        base_url=settings.llm.base_url,
        model=settings.llm.model,
        api_key_present=bool(settings.llm.api_key.get_secret_value()),
    )


@router.post("/llm/test", response_model=LLMConnectionResult)
async def test_llm_connection(
    payload: LLMConfigUpdate | None = None,
) -> LLMConnectionResult:
    settings = get_settings()
    llm_settings = settings.llm
    if payload is not None:
        llm_settings = LLMSettings(
            base_url=payload.base_url,
            api_key=payload.api_key,
            model=payload.model,
            timeout_seconds=settings.llm.timeout_seconds,
            temperature=settings.llm.temperature,
            supports_json_schema=settings.llm.supports_json_schema,
            stream=False,
        )
    provider = OpenAICompatibleProvider(llm_settings)
    success, message, latency_ms = await provider.test_connection()
    return LLMConnectionResult(
        success=success,
        model=llm_settings.model,
        message=message,
        latency_ms=latency_ms,
    )


@router.put("/config/llm", response_model=LLMConfigStatus)
def update_llm_config_route(payload: LLMConfigUpdate) -> LLMConfigStatus:
    try:
        settings = update_llm_config(
            base_url=payload.base_url,
            api_key=payload.api_key,
            model=payload.model,
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="无法写入本地配置文件") from exc
    return LLMConfigStatus(
        configured=bool(settings.llm.api_key.get_secret_value()),
        base_url=settings.llm.base_url,
        model=settings.llm.model,
        api_key_present=True,
    )


@router.post(
    "/sessions",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_game_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
) -> SessionRead:
    return create_session(db, payload.name)


@router.get("/sessions", response_model=list[SessionRead])
def get_game_sessions(db: Session = Depends(get_db)) -> list[SessionRead]:
    return list_sessions(db)


@router.get("/sessions/{session_id}/export", response_model=SaveExport)
def export_game_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SaveExport:
    game_session = _require_session(db, session_id)
    try:
        return export_session(db, game_session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/import", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def import_game_session(
    payload: SaveExport,
    db: Session = Depends(get_db),
) -> SessionRead:
    try:
        return import_session(db, payload)
    except (KeyError, TypeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"存档文件格式无效：{exc}") from exc


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_game_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionDetail:
    game_session = get_session(db, session_id)
    if game_session is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    player_state = get_player_state(db, session_id)
    return SessionDetail(
        **SessionRead.model_validate(game_session).model_dump(),
        player_state=player_state.state if player_state else {},
    )


def _require_session(
    db: Session,
    session_id: str,
) -> GameSession:
    game_session = get_session(db, session_id)
    if game_session is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return game_session


@router.get("/sessions/{session_id}/state", response_model=PlayerStateResponse)
def get_game_state(
    session_id: str,
    db: Session = Depends(get_db),
) -> PlayerStateResponse:
    game_session = _require_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if player_state is None:
        raise HTTPException(status_code=404, detail="角色状态不存在")
    return PlayerStateResponse(
        session_id=session_id,
        state_version=game_session.state_version,
        state=player_state.state,
    )


@router.post(
    "/sessions/{session_id}/departure-notice/acknowledge",
    response_model=PlayerStateResponse,
)
def acknowledge_departure_notice(
    session_id: str,
    db: Session = Depends(get_db),
) -> PlayerStateResponse:
    game_session = _require_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if player_state is None:
        raise HTTPException(status_code=404, detail="角色状态不存在")
    state = dict(player_state.state)
    school = dict(state.get("school", {}))
    notice = dict(school.get("departure_notice", {}))
    if notice.get("status") == "pending":
        notice["status"] = "acknowledged"
        school["departure_notice"] = notice
        state["school"] = school
        player_state.state = state
        game_session.state_version += 1
        db.commit()
    return PlayerStateResponse(
        session_id=session_id,
        state_version=game_session.state_version,
        state=player_state.state,
    )


@router.get("/sessions/{session_id}/courses", response_model=CourseView)
def get_game_courses(
    session_id: str,
    db: Session = Depends(get_db),
) -> CourseView:
    game_session = _require_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if player_state is None:
        raise HTTPException(status_code=404, detail="角色状态不存在")
    return get_courses_view(game_session, player_state)


@router.put("/sessions/{session_id}/courses", response_model=CourseView)
def update_game_courses(
    session_id: str,
    payload: CourseSelectionRequest,
    db: Session = Depends(get_db),
) -> CourseView:
    game_session = _require_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if player_state is None:
        raise HTTPException(status_code=404, detail="角色状态不存在")
    try:
        return select_courses(db, game_session, player_state, payload)
    except ValueError as exc:
        db.rollback()
        detail = str(exc)
        status_code = 409 if "版本" in detail or "变化" in detail else 422
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/sessions/{session_id}/journal", response_model=list[JournalRead])
def get_game_journal(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[JournalRead]:
    _require_session(db, session_id)
    return [
        JournalRead(
            id=entry.id,
            turn_id=entry.turn_id,
            entry_type=entry.entry_type,
            title=entry.title,
            summary=entry.summary,
            data=entry.data,
            created_at=entry.created_at.isoformat(),
        )
        for entry in list_journal(db, session_id)
    ]


@router.get(
    "/sessions/{session_id}/relationships",
    response_model=list[RelationshipRead],
)
def get_game_relationships(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[RelationshipRead]:
    _require_session(db, session_id)
    return [
        RelationshipRead(
            source_id=item.source_id,
            target_id=item.target_id,
            state=item.state,
        )
        for item in list_relationships(db, session_id)
    ]


@router.get("/sessions/{session_id}/npcs", response_model=list[NPCRead])
def get_game_npcs(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[NPCRead]:
    _require_session(db, session_id)
    return [
        NPCRead(
            npc_id=item.npc_id,
            is_original_character=item.is_original_character,
            state=item.state,
        )
        for item in list_npcs(db, session_id)
    ]


@router.get(
    "/sessions/{session_id}/memories",
    response_model=list[MemoryRead],
)
def get_game_memories(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[MemoryRead]:
    _require_session(db, session_id)
    return [
        MemoryRead(
            memory_id=item.memory_id,
            title=item.title,
            summary=item.summary,
            event_type=item.event_type,
            status=item.status,
            importance=item.importance,
            time=item.time_text,
            location_id=item.location_id,
            actors=item.actors,
            keywords=item.keywords,
            facts=item.facts,
            open_threads=item.open_threads,
        )
        for item in list_memories(db, session_id)
    ]


@router.get("/sessions/{session_id}/turns")
def get_game_turns(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _require_session(db, session_id)
    return [
        {
            "id": item.id,
            "sequence": item.sequence,
            "action": item.action,
            "narrative": item.narrative,
            "response": item.llm_response,
            "state_version_after": item.state_version_after,
            "created_at": item.created_at.isoformat(),
        }
        for item in list_turns(db, session_id)
    ]


@router.patch("/sessions/{session_id}", response_model=SessionRead)
def rename_game_session(
    session_id: str,
    payload: SessionRename,
    db: Session = Depends(get_db),
) -> SessionRead:
    game_session = get_session(db, session_id)
    if game_session is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return rename_session(db, game_session, payload.name)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game_session(session_id: str, db: Session = Depends(get_db)) -> Response:
    game_session = get_session(db, session_id)
    if game_session is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    delete_session(db, game_session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/sessions/{session_id}/story-arcs",
    response_model=list[StoryArcRead],
)
def get_story_arcs(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[StoryArcRead]:
    _require_session(db, session_id)
    return [StoryArcRead.model_validate(item) for item in list_story_arc_reads(db, session_id)]


@router.get(
    "/sessions/{session_id}/story-arcs/status",
    response_model=StoryArcStatus,
)
def get_story_arc_status(
    session_id: str,
    db: Session = Depends(get_db),
) -> StoryArcStatus:
    _require_session(db, session_id)
    return StoryArcStatus.model_validate(story_arc_status(db, session_id))


@router.post(
    "/sessions/{session_id}/story-arcs/retry",
    response_model=StoryArcJobRead,
)
async def retry_story_arc(
    session_id: str,
    db: Session = Depends(get_db),
) -> StoryArcJobRead:
    _require_session(db, session_id)
    try:
        return StoryArcJobRead.model_validate(
            job_to_dict(retry_story_arc_job(db, session_id))
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/setup", response_model=SetupView)
def get_game_setup(
    session_id: str,
    db: Session = Depends(get_db),
) -> SetupView:
    game_session = get_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if game_session is None or player_state is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    return get_setup_view(game_session, player_state)


@router.post("/sessions/{session_id}/setup/answer", response_model=SetupView)
def answer_game_setup(
    session_id: str,
    payload: SetupAnswer,
    db: Session = Depends(get_db),
) -> SetupView:
    game_session = get_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if game_session is None or player_state is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    try:
        return save_setup_answer(db, game_session, player_state, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/setup/navigate", response_model=SetupView)
def navigate_game_setup(
    session_id: str,
    payload: SetupNavigate,
    db: Session = Depends(get_db),
) -> SetupView:
    game_session = get_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if game_session is None or player_state is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    try:
        return navigate_setup_step(db, game_session, player_state, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/setup/confirm", response_model=SetupView)
async def confirm_game_setup(
    session_id: str,
    _: SetupConfirm,
    db: Session = Depends(get_db),
) -> SetupView:
    game_session = get_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if game_session is None or player_state is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    try:
        setup_view = confirm_setup(db, game_session, player_state)
        initialized_state = await initialize_attributes(db, game_session, player_state)
        return setup_view.model_copy(
            update={
                "attribute_initialization": initialized_state["attribute_initialization"]
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AttributeInitializationError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/attributes/initialize",
    response_model=SetupView,
)
async def initialize_game_attributes(
    session_id: str,
    payload: AttributeInitializationRequest | None = None,
    db: Session = Depends(get_db),
) -> SetupView:
    game_session = get_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if game_session is None or player_state is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    if not player_state.state.get("setup", {}).get("completed"):
        raise HTTPException(status_code=409, detail="角色创建尚未完成")
    try:
        request = payload or AttributeInitializationRequest()
        await initialize_attributes(
            db,
            game_session,
            player_state,
            adjustment_instruction=request.adjustment_instruction,
            force=request.force,
        )
        return get_setup_view(game_session, player_state)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AttributeInitializationError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/actions", response_model=TurnResponse)
async def submit_game_action(
    session_id: str,
    payload: ActionRequest,
    db: Session = Depends(get_db),
) -> TurnResponse:
    game_session = get_session(db, session_id)
    player_state = get_player_state(db, session_id)
    if game_session is None or player_state is None:
        raise HTTPException(status_code=404, detail="存档不存在")
    try:
        return await generate_turn(db, game_session, player_state, payload)
    except TurnGenerationError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

