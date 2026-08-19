from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.models import Relationship
from backend.app.schemas.game import NarrativeResponse


def apply_turn_rules(
    state: dict[str, Any],
    relationships: list[Relationship],
    response: NarrativeResponse,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """应用模型提出的可验证变化，返回新状态和审计差异。"""
    next_state = deepcopy(state)
    proposals = response.player_changes.model_dump()
    if not any(proposals.values()) and response.state_proposals:
        proposals = deepcopy(response.state_proposals)
    changes: dict[str, Any] = {}

    context = next_state.setdefault("current_context", {})
    old_datetime = _parse_datetime(context.get("datetime"))
    advance_minutes = response.turn.time_advance_minutes
    if advance_minutes:
        new_datetime = old_datetime + timedelta(minutes=advance_minutes)
        context["datetime"] = new_datetime.isoformat()
        context["period"] = _period(new_datetime.hour)
        changes["time_advance_minutes"] = advance_minutes
    if response.turn.location_id:
        context["location_id"] = response.turn.location_id
        changes["location_id"] = response.turn.location_id
    _update_age(next_state, old_datetime, changes)

    _apply_numeric_deltas(next_state, "vitals", proposals.get("vital_deltas"), changes)
    _apply_numeric_deltas(
        next_state, "attributes", proposals.get("attribute_deltas"), changes
    )
    _apply_skills(next_state, proposals.get("skill_deltas"), changes)
    _apply_skill_entries(next_state, proposals, changes)
    _apply_statuses(next_state, proposals, changes)
    _apply_traits(next_state, proposals, changes)
    _apply_reputation(next_state, proposals.get("reputation_deltas"), changes)
    _apply_inventory(next_state, proposals, changes)
    _apply_relationships(next_state, relationships, proposals, changes)
    _apply_lifecycle(next_state, changes)
    return next_state, changes


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime(1991, 7, 1, 9, tzinfo=timezone.utc)


def _period(hour: int) -> str:
    if hour < 6:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    if hour < 22:
        return "evening"
    return "night"


def _apply_numeric_deltas(
    state: dict[str, Any],
    section: str,
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, dict):
        return
    target = state.setdefault(section, {})
    applied: dict[str, float] = {}
    for key, raw_delta in deltas.items():
        if key not in target or not isinstance(raw_delta, (int, float)):
            continue
        before = target[key]
        maximum = target.get(f"max_{key}", 100)
        target[key] = max(0, min(maximum, before + raw_delta))
        applied[key] = target[key] - before
    if applied:
        changes[section] = applied


def _apply_skills(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, dict):
        return
    skills = state.setdefault("skills", {})
    applied: dict[str, int] = {}
    for skill_id, raw_delta in deltas.items():
        if not isinstance(raw_delta, (int, float)):
            continue
        skill = skills.setdefault(skill_id, {"level": 0, "experience": 0})
        before = int(skill.get("level", 0))
        skill["level"] = max(0, min(100, before + int(raw_delta)))
        applied[skill_id] = skill["level"] - before
    if applied:
        changes["skills"] = applied


def _apply_skill_entries(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    skills = state.setdefault("skills", {})
    added: list[str] = []
    for item in proposals.get("skill_add", []) or []:
        if not isinstance(item, dict):
            continue
        skill_id = _stable_id(item.get("id") or item.get("skill_id") or item.get("name"))
        if not skill_id:
            continue
        current = skills.setdefault(
            skill_id,
            {
                "name": item.get("name") or skill_id,
                "level": 0,
                "experience": 0,
                "description": item.get("description", ""),
            },
        )
        current["name"] = item.get("name") or current.get("name") or skill_id
        current["description"] = item.get("description") or current.get(
            "description", ""
        )
        current["level"] = max(
            int(current.get("level", 0)),
            int(item.get("level", 1)),
        )
        added.append(skill_id)
    removed: list[str] = []
    for raw_id in proposals.get("skill_remove", []) or []:
        skill_id = _stable_id(raw_id)
        if skill_id in skills:
            del skills[skill_id]
            removed.append(skill_id)
    if added or removed:
        changes["skills_entries"] = {"added": added, "removed": removed}


def _apply_statuses(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    statuses = state.setdefault("statuses", [])
    by_id = {
        str(item.get("id")): item
        for item in statuses
        if isinstance(item, dict) and item.get("id")
    }
    added: list[dict[str, Any]] = []
    for item in proposals.get("status_add", []) or []:
        if not isinstance(item, dict):
            continue
        status_id = _stable_id(item.get("id") or item.get("name"))
        if not status_id:
            continue
        value = {
            "id": status_id,
            "name": item.get("name") or status_id,
            "description": item.get("description") or item.get("effect", ""),
            "severity": item.get("severity", "normal"),
            "duration_minutes": item.get("duration_minutes"),
        }
        by_id[status_id] = value
        added.append(value)
    removed: list[str] = []
    for raw_id in proposals.get("status_remove", []) or []:
        status_id = _stable_id(raw_id)
        if status_id in by_id:
            del by_id[status_id]
            removed.append(status_id)
    state["statuses"] = list(by_id.values())
    if added or removed:
        changes["statuses"] = {"added": added, "removed": removed}


def _apply_traits(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    traits = state.setdefault("traits", [])
    by_id = {
        str(item.get("id")): item
        for item in traits
        if isinstance(item, dict) and item.get("id")
    }
    added: list[dict[str, Any]] = []
    for item in (proposals.get("trait_add", []) or [])[:2]:
        if not isinstance(item, dict):
            continue
        trait_id = _stable_id(item.get("id") or item.get("name"))
        name = str(item.get("name") or "")
        description = str(item.get("description") or "")
        if not trait_id or not name or not description:
            continue
        trait = {
            "id": trait_id,
            "name": name,
            "description": description,
            "polarity": (
                "negative" if item.get("polarity") == "negative" else "positive"
            ),
            "source": item.get("source", ""),
            "reason": item.get("reason", ""),
        }
        by_id[trait_id] = trait
        added.append(trait)
    removed: list[str] = []
    for raw_id in proposals.get("trait_remove", []) or []:
        trait_id = _stable_id(raw_id)
        if trait_id in by_id:
            del by_id[trait_id]
            removed.append(trait_id)
    state["traits"] = list(by_id.values())
    if added or removed:
        changes["traits"] = {"added": added, "removed": removed}


def _stable_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def _apply_reputation(
    state: dict[str, Any],
    deltas: Any,
    changes: dict[str, Any],
) -> None:
    if not isinstance(deltas, dict):
        return
    reputation = state.setdefault("reputation", {})
    applied: dict[str, int] = {}
    for key, raw_delta in deltas.items():
        if not isinstance(raw_delta, (int, float)):
            continue
        before = int(reputation.get(key, 0))
        reputation[key] = max(-100, min(100, before + int(raw_delta)))
        applied[key] = reputation[key] - before
    if applied:
        changes["reputation"] = applied


def _apply_inventory(
    state: dict[str, Any],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    inventory = state.setdefault("inventory", [])
    added = proposals.get("inventory_add", [])
    removed = proposals.get("inventory_remove", [])
    added_items = []
    if isinstance(added, list):
        for item in added:
            if not isinstance(item, dict):
                continue
            item_id = _stable_id(item.get("item_id") or item.get("id") or item.get("name"))
            if not item_id:
                continue
            normalized_item = {
                **item,
                "item_id": item_id,
                "name": item.get("name") or item_id,
                "description": item.get("description") or item.get("effect", ""),
                "quantity": max(1, int(item.get("quantity", 1))),
            }
            existing = next(
                (
                    current
                    for current in inventory
                    if isinstance(current, dict)
                    and current.get("item_id") == item_id
                ),
                None,
            )
            if existing is not None:
                existing["quantity"] = int(existing.get("quantity", 1)) + normalized_item["quantity"]
            else:
                inventory.append(normalized_item)
            added_items.append(normalized_item)
    removed_ids = {
        _stable_id(item.get("item_id") or item.get("id") or item.get("name"))
        if isinstance(item, dict)
        else _stable_id(item)
        for item in removed
        if (isinstance(item, (dict, str)) and item)
    } if isinstance(removed, list) else set()
    if removed_ids:
        state["inventory"] = [
            item
            for item in inventory
            if str(item.get("item_id")) not in removed_ids
        ]
    if added_items or removed_ids:
        changes["inventory"] = {
            "added": added_items,
            "removed_ids": sorted(removed_ids),
        }


def _apply_relationships(
    state: dict[str, Any],
    relationships: list[Relationship],
    proposals: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    deltas = proposals.get("relationship_deltas")
    if not isinstance(deltas, list):
        return
    player_age = int(state.get("identity", {}).get("age", 10))
    by_npc = {relationship.target_id: relationship for relationship in relationships}
    applied: list[dict[str, Any]] = []
    for item in deltas:
        if not isinstance(item, dict):
            continue
        npc_id = str(item.get("npc_id", ""))
        relationship = by_npc.get(npc_id)
        if relationship is None:
            continue
        relation_state = deepcopy(relationship.state)
        before = {
            "affinity": int(relation_state.get("affinity", 0)),
            "trust": int(relation_state.get("trust", 0)),
            "stage": relation_state.get("stage", "stranger"),
        }
        relation_state["affinity"] = max(
            0,
            min(100, before["affinity"] + int(item.get("affinity_delta", 0))),
        )
        relation_state["trust"] = max(
            0,
            min(100, before["trust"] + int(item.get("trust_delta", 0))),
        )
        requested_stage = item.get("stage")
        if requested_stage:
            requested_stage = str(requested_stage)
            if _stage_allowed(requested_stage, player_age):
                relation_state["stage"] = requested_stage
            else:
                pending = relation_state.setdefault("pending_stage_unlocks", [])
                requirement = 12 if requested_stage in {"dating", "romance"} else 18
                if not any(
                    item.get("stage") == requested_stage
                    for item in pending
                    if isinstance(item, dict)
                ):
                    pending.append(
                        {"stage": requested_stage, "required_age": requirement}
                    )
        _release_pending_stage(relation_state, player_age)
        relationship.state = relation_state
        applied.append(
            {
                "npc_id": npc_id,
                "before": before,
                "after": {
                    "affinity": relation_state["affinity"],
                    "trust": relation_state["trust"],
                    "stage": relation_state["stage"],
                },
            }
        )
    if applied:
        changes["relationships"] = applied


def _stage_allowed(stage: str, player_age: int) -> bool:
    if stage in {"dating", "romance"}:
        return player_age >= 12
    if stage in {"committed", "adult_stage", "marriage"}:
        return player_age >= 18
    return True


def _release_pending_stage(relation_state: dict[str, Any], player_age: int) -> None:
    pending = relation_state.get("pending_stage_unlocks", [])
    if not isinstance(pending, list):
        return
    remaining = []
    for item in pending:
        if not isinstance(item, dict):
            continue
        required_age = int(item.get("required_age", 99))
        if player_age >= required_age:
            relation_state["stage"] = str(item.get("stage", relation_state.get("stage")))
        else:
            remaining.append(item)
    relation_state["pending_stage_unlocks"] = remaining


def _update_age(
    state: dict[str, Any],
    current_datetime: datetime,
    changes: dict[str, Any],
) -> None:
    identity = state.setdefault("identity", {})
    birthday = identity.get("birthday")
    if not isinstance(birthday, str):
        return
    try:
        birth_date = datetime.fromisoformat(birthday).date()
    except ValueError:
        return
    new_age = current_datetime.date().year - birth_date.year
    if (current_datetime.month, current_datetime.day) < (
        birth_date.month,
        birth_date.day,
    ):
        new_age -= 1
    old_age = identity.get("age")
    identity["age"] = max(0, new_age)
    if old_age != identity["age"]:
        changes["age"] = {"before": old_age, "after": identity["age"]}


def _apply_lifecycle(state: dict[str, Any], changes: dict[str, Any]) -> None:
    hp = state.get("vitals", {}).get("hp")
    if isinstance(hp, (int, float)) and hp <= 0:
        state.setdefault("lifecycle", {})["status"] = "critical"
        changes["lifecycle"] = "critical"
