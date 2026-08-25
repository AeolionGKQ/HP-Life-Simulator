from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.content.attributes import (
    DIMENSION_CATALOG,
    DIMENSION_IDS,
    RESOURCE_CATALOG,
    RESOURCE_IDS,
)
from backend.app.models import GameSession, PlayerState
from backend.app.prompts.attributes import (
    ATTRIBUTE_INITIALIZATION_PROTOCOL,
    build_attribute_initialization_messages,
)
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.schemas.game import AttributeInitializationResponse


class AttributeInitializationError(RuntimeError):
    pass


def _extract_content(raw: dict[str, Any]) -> str:
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AttributeInitializationError("模型响应缺少 choices.message.content") from exc
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _parse_initialization(raw: dict[str, Any]) -> AttributeInitializationResponse:
    content = _extract_content(raw).strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        return AttributeInitializationResponse.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AttributeInitializationError("模型返回的初始属性不是合法的新协议 JSON") from exc


def _validate_and_apply(
    state: dict[str, Any],
    response: AttributeInitializationResponse,
) -> dict[str, Any]:
    resources: dict[str, dict[str, float]] = {}
    dimensions: dict[str, dict[str, float]] = {}
    resource_ids = [item.id for item in response.resources]
    dimension_ids = [item.id for item in response.dimensions]
    if set(resource_ids) != RESOURCE_IDS or len(resource_ids) != len(RESOURCE_IDS):
        raise AttributeInitializationError("初始属性必须完整覆盖五项资源且不能重复")
    if set(dimension_ids) != DIMENSION_IDS or len(dimension_ids) != len(DIMENSION_IDS):
        raise AttributeInitializationError("初始属性必须完整覆盖五项长期维度且不能重复")

    for item in response.resources:
        definition = RESOURCE_CATALOG[item.id]
        if item.max < 1 or item.max > definition["absolute_max"]:
            raise AttributeInitializationError(f"资源 {item.id} 的上限超出允许范围")
        if item.value < 0 or item.value > item.max:
            raise AttributeInitializationError(f"资源 {item.id} 的当前值超出允许范围")
        resources[item.id] = {
            "value": item.value,
            "max": item.max,
            "base_max": definition["default_max"],
        }
    for item in response.dimensions:
        definition = DIMENSION_CATALOG[item.id]
        if item.max < 1 or item.max > definition["absolute_max"]:
            raise AttributeInitializationError(f"维度 {item.id} 的上限超出允许范围")
        if item.value < 0 or item.value > item.max:
            raise AttributeInitializationError(f"维度 {item.id} 的当前值超出允许范围")
        dimensions[item.id] = {
            "value": item.value,
            "max": item.max,
            "base_max": definition["default_max"],
        }

    state["resources"] = resources
    state["dimensions"] = dimensions
    state["attribute_initialization"] = {
        "status": "ready",
        "schema_version": "1.2",
        "request_id": state.get("attribute_initialization", {}).get(
            "request_id", f"attribute-init-{uuid4().hex[:12]}"
        ),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source": "llm_initialization",
        "error": None,
        "calibration_summary": response.calibration_summary,
        "initial_values": {
            "resources": [item.model_dump() for item in response.resources],
            "dimensions": [item.model_dump() for item in response.dimensions],
        },
    }
    return state


async def initialize_attributes(
    db: Session,
    game_session: GameSession,
    player_state: PlayerState,
) -> dict[str, Any]:
    state = deepcopy(player_state.state)
    initialization = state.setdefault("attribute_initialization", {})
    if initialization.get("status") == "ready":
        game_session.status = "active"
        db.commit()
        return state
    initialization["status"] = "generating"
    initialization["request_id"] = f"attribute-init-{uuid4().hex[:12]}"
    player_state.state = state
    flag_modified(player_state, "state")
    db.commit()
    from backend.app.core.config import get_settings

    provider = OpenAICompatibleProvider(get_settings().llm)
    try:
        raw = await provider.chat_completion(
            build_attribute_initialization_messages(game_session, player_state)
        )
        response = _parse_initialization(raw)
        state = _validate_and_apply(state, response)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        state["attribute_initialization"] = {
            **initialization,
            "status": "failed",
            "error": "无法连接模型服务或模型服务返回错误",
        }
        player_state.state = state
        db.commit()
        raise AttributeInitializationError(str(exc)) from exc
    except AttributeInitializationError as exc:
        state["attribute_initialization"] = {
            **initialization,
            "status": "failed",
            "error": str(exc),
        }
        player_state.state = state
        db.commit()
        raise
    player_state.state = deepcopy(state)
    flag_modified(player_state, "state")
    game_session.status = "active"
    game_session.state_version += 1
    db.flush()
    db.commit()
    db.refresh(player_state)
    db.refresh(game_session)
    return state


def initialization_protocol() -> str:
    return ATTRIBUTE_INITIALIZATION_PROTOCOL
