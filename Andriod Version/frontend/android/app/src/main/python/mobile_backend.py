from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import types
from datetime import date, datetime
from pathlib import Path
from typing import Any


_RUNTIME: dict[str, Any] | None = None
_RUNTIME_LOCK = threading.RLock()


def reset_runtime() -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is not None:
            try:
                _RUNTIME["db"].get_engine().dispose()
            except Exception:
                pass
            _RUNTIME["db"].get_engine.cache_clear()
            _RUNTIME["db"].get_session_factory.cache_clear()
        _RUNTIME = None


def _patch_pydantic() -> None:
    import pydantic

    if not hasattr(pydantic, "ConfigDict"):
        pydantic.ConfigDict = lambda **kwargs: kwargs
    if not hasattr(pydantic, "field_validator"):
        pydantic.field_validator = lambda *args, **kwargs: (
            lambda function: function
        )
    if not hasattr(pydantic, "model_validator"):
        pydantic.model_validator = lambda *args, **kwargs: (
            lambda function: function
        )

    base_model = pydantic.BaseModel
    if not hasattr(base_model, "model_validate"):
        base_model.model_validate = classmethod(
            lambda cls, value: cls.parse_obj(value)
        )
    if not hasattr(base_model, "model_dump"):
        def model_dump(self: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
            if kwargs.get("mode") == "json":
                return json.loads(self.json())
            return self.dict()

        base_model.model_dump = model_dump
    if not hasattr(base_model, "model_copy"):
        base_model.model_copy = lambda self, *, update=None, deep=False: self.copy(
            update=update or {},
            deep=deep,
        )


def _alias_backend_package() -> None:
    if "backend.app" in sys.modules:
        return
    import importlib

    app_module = importlib.import_module("app")
    backend_module = types.ModuleType("backend")
    backend_module.__path__ = []
    backend_module.app = app_module
    sys.modules["backend"] = backend_module
    sys.modules["backend.app"] = app_module


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _prepare_config(files_dir: str) -> Path:
    data_dir = Path(files_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "settings.local.toml"
    existing: dict[str, Any] = {}
    if config_path.exists():
        import tomllib

        with config_path.open("rb") as config_file:
            existing = tomllib.load(config_file)
    llm = existing.get("llm", {})
    database_path = (data_dir / "game.db").resolve().as_posix()
    config_path.write_text(
        "[app]\n"
        f"name = {_toml_string(str(existing.get('app', {}).get('name', '霍格沃兹人生模拟器')))}\n"
        f"data_dir = {_toml_string(data_dir.resolve().as_posix())}\n"
        f"frontend_dist_dir = {_toml_string(data_dir.resolve().as_posix())}\n\n"
        "[database]\n"
        f"url = {_toml_string(f'sqlite:///{database_path}')}\n"
        "echo = false\n\n"
        "[llm]\n"
        f"base_url = {_toml_string(str(llm.get('base_url', '')))}\n"
        f"api_key = {_toml_string(str(llm.get('api_key', '')))}\n"
        f"model = {_toml_string(str(llm.get('model', '')))}\n"
        f"timeout_seconds = {float(llm.get('timeout_seconds', 300))}\n"
        f"temperature = {float(llm.get('temperature', 0.8))}\n"
        # Match the PC default. Some OpenAI-compatible services reject
        # response_format on the simple connectivity probe.
        "supports_json_schema = false\n"
        "supports_concurrent_requests = true\n"
        f"stream = false\n\n"
        "[game]\n"
        "era_id = \"second_generation\"\n"
        "recent_narrative_turns = 10\n"
        "recent_turn_token_limit = 12000\n"
        "automatic_memory_recall_limit = 6\n"
        "memory_request_limit = 5\n"
        "allow_story_arc_parallel_with_gameplay = true\n"
        "story_arc_turns = 25\n"
        "story_arc_job_timeout_seconds = 900\n"
        "worldline_min = 0.0\n"
        "worldline_max = 100.0\n",
        encoding="utf-8",
    )
    os.environ["HP_SIMULATOR_CONFIG"] = str(config_path)
    os.environ["HP_SIMULATOR_ANDROID"] = "1"
    return config_path


def _load_runtime_unlocked(files_dir: str) -> dict[str, Any]:
    global _RUNTIME
    config_path = _prepare_config(files_dir)
    if _RUNTIME is not None and _RUNTIME["config_path"] == config_path:
        return _RUNTIME

    _alias_backend_package()
    _patch_pydantic()
    from backend.app.core import config as backend_config
    from backend.app.db import session as backend_db

    backend_config.get_settings.cache_clear()
    backend_db.get_engine.cache_clear()
    backend_db.get_session_factory.cache_clear()
    backend_db.initialize_database()

    from backend.app.content.eras import list_eras
    from backend.app.providers.openai_compatible import OpenAICompatibleProvider
    from backend.app.services.attributes import (
        AttributeInitializationError,
        initialize_attributes,
    )
    from backend.app.services.courses import get_courses_view, select_courses
    from backend.app.services.sessions import (
        create_session,
        delete_session,
        export_session,
        get_player_state,
        get_session,
        import_session,
        list_journal,
        list_memories,
        list_npcs,
        list_relationships,
        list_sessions,
        list_turns,
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
        compress_story_arcs,
        job_to_dict,
        list_story_arc_reads,
        repair_orphaned_story_arc_jobs,
        retry_story_arc_job,
        story_arc_status,
    )
    from backend.app.schemas.common import LLMConfigUpdate
    from backend.app.schemas.game import (
        ActionRequest,
        AttributeInitializationRequest,
        CourseSelectionRequest,
        SetupAnswer,
        SetupConfirm,
        SetupNavigate,
    )
    from backend.app.schemas.sessions import SaveExport, SessionCreate, SessionRename

    repair_orphaned_story_arc_jobs()

    _RUNTIME = {
        "config_path": config_path,
        "config": backend_config,
        "db": backend_db,
        "list_eras": list_eras,
        "provider": OpenAICompatibleProvider,
        "AttributeInitializationError": AttributeInitializationError,
        "initialize_attributes": initialize_attributes,
        "get_courses_view": get_courses_view,
        "select_courses": select_courses,
        "list_memories": list_memories,
        "create_session": create_session,
        "delete_session": delete_session,
        "export_session": export_session,
        "get_player_state": get_player_state,
        "get_session": get_session,
        "import_session": import_session,
        "list_journal": list_journal,
        "list_npcs": list_npcs,
        "list_relationships": list_relationships,
        "list_sessions": list_sessions,
        "list_turns": list_turns,
        "rename_session": rename_session,
        "confirm_setup": confirm_setup,
        "get_setup_view": get_setup_view,
        "navigate_setup_step": navigate_setup_step,
        "save_setup_answer": save_setup_answer,
        "TurnGenerationError": TurnGenerationError,
        "generate_turn": generate_turn,
        "compress_story_arcs": compress_story_arcs,
        "job_to_dict": job_to_dict,
        "list_story_arc_reads": list_story_arc_reads,
        "retry_story_arc_job": retry_story_arc_job,
        "story_arc_status": story_arc_status,
        "LLMConfigUpdate": LLMConfigUpdate,
        "ActionRequest": ActionRequest,
        "AttributeInitializationRequest": AttributeInitializationRequest,
        "CourseSelectionRequest": CourseSelectionRequest,
        "SetupAnswer": SetupAnswer,
        "SetupConfirm": SetupConfirm,
        "SetupNavigate": SetupNavigate,
        "SessionCreate": SessionCreate,
        "SessionRename": SessionRename,
        "SaveExport": SaveExport,
    }
    return _RUNTIME


def _load_runtime(files_dir: str) -> dict[str, Any]:
    with _RUNTIME_LOCK:
        return _load_runtime_unlocked(files_dir)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "dict") and not isinstance(value, dict):
        return _jsonable(value.dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _dump(value: Any) -> str:
    return json.dumps(_jsonable(value), ensure_ascii=False, separators=(",", ":"))


def _session_dict(session: Any) -> dict[str, Any]:
    return {
        "id": session.id,
        "name": session.name,
        "era_id": session.era_id,
        "status": session.status,
        "state_version": session.state_version,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def _get_session_or_raise(runtime: dict[str, Any], db: Any, session_id: str) -> Any:
    session = runtime["get_session"](db, session_id)
    if session is None:
        raise ValueError("存档不存在")
    return session


def _run_async(function: Any, *args: Any, **kwargs: Any) -> Any:
    return asyncio.run(function(*args, **kwargs))


def request(path: str, method: str, body: str, files_dir: str) -> str:
    runtime = _load_runtime(files_dir)
    payload = json.loads(body) if body else {}
    backend_config = runtime["config"]
    backend_db = runtime["db"]
    settings = backend_config.get_settings()

    if path == "/api/health":
        connection = backend_db.get_engine().connect()
        try:
            connection.exec_driver_sql("SELECT 1")
        finally:
            connection.close()
        return _dump(
            {
                "status": "ok",
                "app_name": settings.app.name,
                "database": "ok",
                "llm_configured": bool(settings.llm.api_key.get_secret_value()),
            }
        )
    if path == "/api/content/eras":
        return _dump(runtime["list_eras"]())
    if path == "/api/config/llm":
        if method == "PUT":
            update = runtime["LLMConfigUpdate"].model_validate(payload)
            next_settings = backend_config.update_llm_config(
                base_url=update.base_url.rstrip("/"),
                api_key=update.api_key,
                model=update.model,
            )
            return _dump(
                {
                    "configured": bool(next_settings.llm.api_key.get_secret_value()),
                    "base_url": next_settings.llm.base_url,
                    "model": next_settings.llm.model,
                    "api_key_present": True,
                }
            )
        return _dump(
            {
                "configured": bool(settings.llm.api_key.get_secret_value()),
                "base_url": settings.llm.base_url,
                "model": settings.llm.model,
                "api_key_present": bool(settings.llm.api_key.get_secret_value()),
            }
        )
    if path == "/api/llm/test":
        llm_settings = settings.llm
        if payload:
            update = runtime["LLMConfigUpdate"].model_validate(payload)
            llm_settings = type(settings.llm)(
                base_url=update.base_url.rstrip("/"),
                api_key=update.api_key,
                model=update.model,
                timeout_seconds=settings.llm.timeout_seconds,
                temperature=settings.llm.temperature,
                supports_json_schema=settings.llm.supports_json_schema,
                supports_concurrent_requests=settings.llm.supports_concurrent_requests,
                stream=False,
            )
        result = _run_async(runtime["provider"](llm_settings).test_connection)
        success, message, latency_ms = result
        return _dump(
            {
                "success": success,
                "model": llm_settings.model,
                "message": message,
                "latency_ms": latency_ms,
            }
        )
    if path == "/api/sessions":
        db = backend_db.get_session_factory()()
        try:
            if method == "POST":
                session = runtime["create_session"](
                    db,
                    runtime["SessionCreate"].model_validate(payload).name,
                )
                return _dump(_session_dict(session))
            return _dump([_session_dict(item) for item in runtime["list_sessions"](db)])
        finally:
            db.close()

    if path == "/api/sessions/import" and method == "POST":
        db = backend_db.get_session_factory()()
        try:
            imported = runtime["import_session"](
                db,
                runtime["SaveExport"].model_validate(payload),
            )
            return _dump(_session_dict(imported))
        except (KeyError, TypeError, ValueError) as exc:
            db.rollback()
            raise ValueError(f"存档文件格式无效：{exc}") from exc
        finally:
            db.close()

    if not path.startswith("/api/sessions/"):
        raise ValueError(f"移动端暂不支持 {method} {path}")
    session_id, _, suffix = path.removeprefix("/api/sessions/").partition("/")
    db = backend_db.get_session_factory()()
    try:
        session = _get_session_or_raise(runtime, db, session_id)
        player_state = runtime["get_player_state"](db, session_id)
        if player_state is None:
            raise ValueError("角色状态不存在")

        if not suffix:
            if method == "GET":
                return _dump(
                    {
                        **_session_dict(session),
                        "player_state": player_state.state,
                    }
                )
            if method == "PATCH":
                renamed = runtime["rename_session"](
                    db,
                    session,
                    runtime["SessionRename"].model_validate(payload).name,
                )
                return _dump(_session_dict(renamed))
            if method == "DELETE":
                runtime["delete_session"](db, session)
                return "null"

        if suffix == "export" and method == "GET":
            return _dump(runtime["export_session"](db, session))

        if suffix == "state" and method == "GET":
            return _dump(
                {
                    "session_id": session_id,
                    "state_version": session.state_version,
                    "state": player_state.state,
                }
            )
        if suffix == "departure-notice/acknowledge" and method == "POST":
            state = dict(player_state.state)
            school = dict(state.get("school", {}))
            notice = dict(school.get("departure_notice", {}))
            if notice.get("status") == "pending":
                notice["status"] = "acknowledged"
                school["departure_notice"] = notice
                state["school"] = school
                player_state.state = state
                session.state_version += 1
                db.commit()
            return _dump(
                {
                    "session_id": session_id,
                    "state_version": session.state_version,
                    "state": player_state.state,
                }
            )
        if suffix == "courses":
            if session.era_id == "modern":
                raise ValueError("现代世代不启用课程系统")
            if method == "GET":
                return _dump(runtime["get_courses_view"](session, player_state))
            if method == "PUT":
                selection = runtime["CourseSelectionRequest"].model_validate(payload)
                return _dump(runtime["select_courses"](db, session, player_state, selection))
        if suffix == "journal" and method == "GET":
            return _dump(
                [
                    {
                        "id": item.id,
                        "turn_id": item.turn_id,
                        "entry_type": item.entry_type,
                        "title": item.title,
                        "summary": item.summary,
                        "data": item.data,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in runtime["list_journal"](db, session_id)
                ]
            )
        if suffix == "memories" and method == "GET":
            return _dump(
                [
                    {
                        "memory_id": item.memory_id,
                        "title": item.title,
                        "summary": item.summary,
                        "event_type": item.event_type,
                        "status": item.status,
                        "importance": item.importance,
                        "time": item.time_text,
                        "location_id": item.location_id,
                        "actors": item.actors,
                        "keywords": item.keywords,
                        "facts": item.facts,
                        "open_threads": item.open_threads,
                    }
                    for item in runtime["list_memories"](db, session_id)
                ]
            )
        if suffix == "story-arcs" and method == "GET":
            return _dump(runtime["list_story_arc_reads"](db, session_id))
        if suffix == "story-arcs/status" and method == "GET":
            return _dump(runtime["story_arc_status"](db, session_id))
        if suffix == "story-arcs/retry" and method == "POST":
            return _dump(
                runtime["job_to_dict"](
                    runtime["retry_story_arc_job"](db, session_id)
                )
            )
        if suffix == "story-arcs/compress" and method == "POST":
            merged = _run_async(
                runtime["compress_story_arcs"],
                db,
                session_id,
            )
            merged_read = next(
                item
                for item in runtime["list_story_arc_reads"](db, session_id)
                if item["scope_key"] == merged.scope_key
            )
            return _dump(merged_read)
        if suffix == "relationships" and method == "GET":
            return _dump(
                [
                    {
                        "source_id": item.source_id,
                        "target_id": item.target_id,
                        "state": item.state,
                    }
                    for item in runtime["list_relationships"](db, session_id)
                ]
            )
        if suffix == "npcs" and method == "GET":
            return _dump(
                [
                    {
                        "npc_id": item.npc_id,
                        "is_original_character": item.is_original_character,
                        "state": item.state,
                    }
                    for item in runtime["list_npcs"](db, session_id)
                ]
            )
        if suffix == "turns" and method == "GET":
            return _dump(
                [
                    {
                        "id": item.id,
                        "sequence": item.sequence,
                        "action": item.action,
                        "narrative": item.narrative,
                        "response": item.llm_response,
                        "state_version_after": item.state_version_after,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in runtime["list_turns"](db, session_id)
                ]
            )
        if suffix == "setup" and method == "GET":
            return _dump(runtime["get_setup_view"](session, player_state))
        if suffix == "setup/navigate" and method == "POST":
            navigate = runtime["SetupNavigate"].model_validate(payload)
            return _dump(
                runtime["navigate_setup_step"](
                    db,
                    session,
                    player_state,
                    navigate,
                )
            )
        if suffix == "setup/answer" and method == "POST":
            answer = runtime["SetupAnswer"].model_validate(payload)
            return _dump(runtime["save_setup_answer"](db, session, player_state, answer))
        if suffix == "setup/confirm" and method == "POST":
            runtime["SetupConfirm"].model_validate(payload)
            setup_view = runtime["confirm_setup"](db, session, player_state)
            initialized_state = _run_async(
                runtime["initialize_attributes"],
                db,
                session,
                player_state,
            )
            return _dump(
                setup_view.model_copy(
                    update={
                        "attribute_initialization": initialized_state[
                            "attribute_initialization"
                        ]
                    }
                )
            )
        if suffix == "attributes/initialize" and method == "POST":
            if not player_state.state.get("setup", {}).get("completed"):
                raise ValueError("角色创建尚未完成")
            request = runtime["AttributeInitializationRequest"].model_validate(payload)
            _run_async(
                runtime["initialize_attributes"],
                db,
                session,
                player_state,
                adjustment_instruction=request.adjustment_instruction,
                force=request.force,
            )
            return _dump(runtime["get_setup_view"](session, player_state))
        if suffix == "actions" and method == "POST":
            action = runtime["ActionRequest"].model_validate(payload)
            return _dump(
                _run_async(runtime["generate_turn"], db, session, player_state, action)
            )
    finally:
        db.close()
    raise ValueError(f"移动端暂不支持 {method} {path}")
