from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


RESOURCE_CATALOG: dict[str, dict[str, int]] = {
    "health": {"default_max": 100, "absolute_max": 200},
    "mana": {"default_max": 100, "absolute_max": 200},
    "sanity": {"default_max": 100, "absolute_max": 150},
    "energy": {"default_max": 100, "absolute_max": 100},
    "satiety": {"default_max": 100, "absolute_max": 100},
}

DIMENSION_CATALOG: dict[str, dict[str, int]] = {
    "constitution": {"default_max": 20, "absolute_max": 30},
    "intelligence": {"default_max": 20, "absolute_max": 30},
    "willpower": {"default_max": 20, "absolute_max": 30},
    "charisma": {"default_max": 20, "absolute_max": 30},
    "magical_power": {"default_max": 20, "absolute_max": 30},
}


def initial_resources() -> dict[str, dict[str, int]]:
    return {
        key: {
            "value": definition["default_max"],
            "max": definition["default_max"],
            "base_max": definition["default_max"],
        }
        for key, definition in RESOURCE_CATALOG.items()
    }


def initial_dimensions() -> dict[str, dict[str, int]]:
    return {
        key: {"value": 0, "max": definition["default_max"], "base_max": definition["default_max"]}
        for key, definition in DIMENSION_CATALOG.items()
    }


def _prompt(state: dict[str, Any], era: dict[str, Any]) -> list[dict[str, str]]:
    protocol = """只输出一个 JSON 对象，不要输出 Markdown 或解释文字。
response_type 必须为 "attribute_initialization"，schema_version 必须为 "1.2"。
resources 必须完整包含 health、mana、sanity、energy、satiety 五项；
dimensions 必须完整包含 constitution、intelligence、willpower、charisma、magical_power 五项。
每项只需包含 id、value、max、reason。value 和 max 必须是数字，且 value 必须在 0 到 max 之间。
资源 max 不得超过对应目录上限，维度 max 不得超过对应目录上限。
只能根据角色创建设定校准属性，不要生成剧情、选项、关系变化或物品。"""
    context = {
        "generation": {
            "id": era["id"],
            "name": era["name"],
            "years": era["years"],
        },
        "character_setup": {
            key: state.get(key)
            for key in (
                "identity",
                "appearance",
                "family",
                "background",
                "personality",
                "values",
                "wand",
                "magic_talents",
                "pet",
                "patronus",
                "character_notes",
                "school",
                "current_context",
            )
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "你是《霍格沃兹人生模拟器》的角色属性校准器。"
                "请给出克制、合理、能从角色设定中找到依据的初始属性。"
                f"\n\n{protocol}"
            ),
        },
        {
            "role": "user",
            "content": "以下是角色创建完成后的权威设定：\n"
            + json.dumps(context, ensure_ascii=False, default=str),
        },
    ]


def _extract_json(response: dict[str, Any]) -> dict[str, Any]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("模型响应缺少初始属性内容") from exc
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)
    content = content.strip()
    if content.startswith("```"):
        content = content.removeprefix("```json").removeprefix("```").strip()
        if content.endswith("```"):
            content = content[:-3].strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("模型返回的初始属性不是合法 JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("模型返回的初始属性格式无效")
    return result


def _validate_items(
    items: Any,
    catalog: dict[str, dict[str, int]],
    kind: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError(f"模型返回的{kind}属性不是数组")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"模型返回的{kind}属性格式无效")
        item_id = item.get("id")
        if item_id not in catalog or item_id in result:
            raise ValueError(f"模型返回的{kind}属性 ID 无效或重复")
        value = item.get("value")
        maximum = item.get("max")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{kind}属性当前值必须是数字")
        if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
            raise ValueError(f"{kind}属性上限必须是数字")
        if maximum < 1 or maximum > catalog[item_id]["absolute_max"]:
            raise ValueError(f"{kind}属性上限超出允许范围")
        if value < 0 or value > maximum:
            raise ValueError(f"{kind}属性当前值超出允许范围")
        result[item_id] = {
            "value": value,
            "max": maximum,
            "base_max": catalog[item_id]["default_max"],
        }
    if set(result) != set(catalog):
        raise ValueError(f"模型返回的{kind}属性不完整")
    return result


def generate_initial_attributes(
    config: dict[str, Any],
    state: dict[str, Any],
    era: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    llm = config.get("llm", {})
    base_url = str(llm.get("base_url", "")).strip().rstrip("/")
    api_key = str(llm.get("api_key", "")).strip()
    model = str(llm.get("model", "")).strip()
    if not base_url or not api_key or not model:
        raise ValueError("请先配置模型服务，再生成初始属性")

    payload = {
        "model": model,
        "messages": _prompt(state, era),
        "stream": False,
    }
    request = Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError("无法连接模型服务或模型服务返回错误") from exc

    result = _extract_json(raw)
    resources = _validate_items(result.get("resources"), RESOURCE_CATALOG, "资源")
    dimensions = _validate_items(result.get("dimensions"), DIMENSION_CATALOG, "长期维度")
    metadata = {
        "status": "ready",
        "schema_version": "1.2",
        "request_id": f"attribute-init-{uuid4().hex[:12]}",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source": "llm_initialization",
        "error": None,
        "calibration_summary": str(result.get("calibration_summary", "")),
        "initial_values": {
            "resources": [
                {"id": key, **value} for key, value in resources.items()
            ],
            "dimensions": [
                {"id": key, **value} for key, value in dimensions.items()
            ],
        },
    }
    return resources, dimensions, metadata


def test_connection(config: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    llm = dict(config.get("llm", {}))
    if payload:
        llm.update(payload)
    base_url = str(llm.get("base_url", "")).strip().rstrip("/")
    api_key = str(llm.get("api_key", "")).strip()
    model = str(llm.get("model", "")).strip()
    if not base_url or not api_key or not model:
        raise ValueError("请完整填写 Base URL、API Key 和模型名")
    request = Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": "只回复 OK，不要回复其他内容。"},
                    {"role": "user", "content": "连接测试"},
                ],
                "temperature": 0,
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=120) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        message = "模型服务连接成功" if content else "模型服务已成功返回响应"
        return {
            "success": True,
            "model": model,
            "message": message,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
    except HTTPError as exc:
        return {
            "success": False,
            "model": model,
            "message": f"模型服务返回 HTTP {exc.code}",
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
    except (URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        return {
            "success": False,
            "model": model,
            "message": "无法连接模型服务或响应格式无效",
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
