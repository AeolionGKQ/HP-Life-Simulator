from __future__ import annotations

from datetime import date
from typing import Any, Iterable


AFFINITY_MIN = 0
AFFINITY_MAX = 100
TRUST_MIN = 0
TRUST_MAX = 100
RELATIONSHIP_TURN_LIMIT = 10

SOCIAL_STAGE_IDS: tuple[str, ...] = (
    "stranger",
    "acquaintance",
    "friend",
    "close_friend",
    "estranged",
    "hostile",
)
ROMANCE_STAGE_IDS: tuple[str, ...] = (
    "locked",
    "none",
    "dating",
    "committed",
    "adult_stage",
    "marriage",
)
ROMANTIC_STAGE_IDS = frozenset({"dating", "committed", "adult_stage", "marriage"})
BOND_TYPE_IDS: tuple[str, ...] = (
    "potential",
    "friendship",
    "rivalry",
    "mentor",
    "family",
    "professional",
    "romance",
    "other",
)

SOCIAL_STAGE_ORDER = {
    "stranger": 0,
    "acquaintance": 1,
    "friend": 2,
    "close_friend": 3,
}
SOCIAL_STAGE_THRESHOLDS = {
    "acquaintance": (5, 5),
    "friend": (20, 10),
    "close_friend": (45, 35),
}


def safe_bounded_int(
    value: Any,
    *,
    default: int = 0,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(maximum, parsed))


def safe_delta(value: Any, *, limit: int = RELATIONSHIP_TURN_LIMIT) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return max(-limit, min(limit, parsed))


def age_band(age: Any) -> str:
    if age is None:
        return "unknown"
    try:
        parsed = int(age)
    except (TypeError, ValueError, OverflowError):
        return "unknown"
    if parsed < 12:
        return "child"
    if parsed < 18:
        return "minor"
    return "adult"


def normalize_relationship_state(
    value: Any,
    *,
    current_date: str | None = None,
    player_age: int | None = None,
) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    state = dict(raw)

    legacy_stage = str(state.get("stage") or "stranger")
    legacy_romance = str(state.get("romance_state") or "")
    romance_stage = str(state.get("romance_stage") or "")

    if legacy_stage in ROMANTIC_STAGE_IDS:
        if not romance_stage or romance_stage not in ROMANCE_STAGE_IDS:
            romance_stage = legacy_stage
        legacy_stage = "close_friend"
    if legacy_romance in ROMANTIC_STAGE_IDS and (
        not romance_stage or romance_stage not in ROMANCE_STAGE_IDS
    ):
        romance_stage = legacy_romance
    if romance_stage not in ROMANCE_STAGE_IDS:
        romance_stage = "none"
    if player_age is not None and player_age < 12 and romance_stage == "none":
        romance_stage = "locked"

    social_stage = legacy_stage if legacy_stage in SOCIAL_STAGE_IDS else "stranger"
    bond_type = str(state.get("bond_type") or "potential")
    if bond_type not in BOND_TYPE_IDS:
        bond_type = "other"

    pending = state.get("pending_unlocks", state.get("pending_stage_unlocks", []))
    normalized_pending: list[dict[str, Any]] = []
    if isinstance(pending, list):
        seen: set[str] = set()
        for item in pending:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("romance_stage") or item.get("stage") or "")
            if stage not in ROMANTIC_STAGE_IDS or stage in seen:
                continue
            seen.add(stage)
            normalized_pending.append(
                {
                    "romance_stage": stage,
                    "required_age": safe_bounded_int(
                        item.get("required_age"),
                        default=18 if stage != "dating" else 12,
                        minimum=0,
                        maximum=150,
                    ),
                    "reason": str(item.get("reason") or ""),
                }
            )
    if player_age is not None:
        required_age = 12 if romance_stage == "dating" else 18
        if romance_stage in ROMANTIC_STAGE_IDS and player_age < required_age:
            if not any(
                item["romance_stage"] == romance_stage
                for item in normalized_pending
            ):
                normalized_pending.append(
                    {
                        "romance_stage": romance_stage,
                        "required_age": required_age,
                        "reason": "旧存档恋爱阶段等待年龄条件复核",
                    }
                )
            romance_stage = "locked"
        elif romance_stage == "locked" and not normalized_pending:
            romance_stage = "none"

    normalized: dict[str, Any] = {
        "affinity": safe_bounded_int(
            state.get("affinity"),
            minimum=AFFINITY_MIN,
            maximum=AFFINITY_MAX,
        ),
        "trust": safe_bounded_int(
            state.get("trust"),
            minimum=TRUST_MIN,
            maximum=TRUST_MAX,
        ),
        "stage": social_stage,
        "bond_type": bond_type,
        "romance_stage": romance_stage,
        "known_secrets": state.get("known_secrets", [])
        if isinstance(state.get("known_secrets", []), list)
        else [],
        "recent_interaction_ids": state.get("recent_interaction_ids", [])
        if isinstance(state.get("recent_interaction_ids", []), list)
        else [],
        "pending_unlocks": normalized_pending,
        "known_since": state.get("known_since"),
        "last_interaction_date": state.get("last_interaction_date"),
        "last_change": state.get("last_change")
        if isinstance(state.get("last_change"), dict)
        else {"affinity_delta": 0, "trust_delta": 0, "reason": ""},
        "origin": state.get("origin", "preset"),
    }
    if current_date and not normalized["known_since"]:
        normalized["known_since"] = current_date
    return normalized


def romance_summary(
    relationships: Iterable[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    active: list[tuple[str, str]] = []
    pending: list[dict[str, Any]] = []
    for relation_id, raw_state in relationships:
        state = normalize_relationship_state(raw_state)
        romance_stage = state["romance_stage"]
        if romance_stage in ROMANTIC_STAGE_IDS:
            active.append((relation_id, romance_stage))
        for item in state["pending_unlocks"]:
            pending.append({"relationship_id": relation_id, **item})

    if any(stage == "marriage" for _, stage in active):
        status = "married"
    elif len(active) > 1:
        status = "multiple_bonds"
    elif any(stage in {"committed", "adult_stage"} for _, stage in active):
        status = "committed"
    elif active:
        status = "dating"
    else:
        status = "single"

    primary = next(
        (relation_id for relation_id, stage in active if stage == "marriage"),
        active[0][0] if active else None,
    )
    return {
        "status": status,
        "active_relationship_ids": [relation_id for relation_id, _ in active],
        "primary_relationship_id": primary,
        "pending_stage_unlocks": pending,
    }


def current_age_for_npc(state: dict[str, Any], current_date: date) -> int | None:
    birthday = state.get("birthday")
    if isinstance(birthday, str):
        try:
            birth_date = date.fromisoformat(birthday[:10])
        except ValueError:
            birth_date = None
        if birth_date:
            age = current_date.year - birth_date.year
            if (current_date.month, current_date.day) < (
                birth_date.month,
                birth_date.day,
            ):
                age -= 1
            return max(0, age)

    raw_age = state.get("age")
    reference = state.get("age_reference_date")
    try:
        age = int(raw_age)
    except (TypeError, ValueError, OverflowError):
        return None
    if isinstance(reference, str):
        try:
            reference_date = date.fromisoformat(reference[:10])
            age += max(0, current_date.year - reference_date.year)
        except ValueError:
            pass
    return max(0, age)
