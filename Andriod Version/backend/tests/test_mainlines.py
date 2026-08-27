from __future__ import annotations

from backend.app.content.mainlines import build_generation_context


def _state(
    *,
    current_date: str,
    grade: str = "year_1",
    location_id: str = "hogwarts_castle",
    worldline: dict | None = None,
) -> dict:
    return {
        "school": {
            "grade": grade,
            "school_year": "1991–1992",
            "term": "autumn",
            "course_selection": None,
        },
        "current_context": {
            "current_date": current_date,
            "location_id": location_id,
        },
        "worldline": worldline or {},
    }


def test_generation_context_contains_stable_frame_and_current_phase() -> None:
    context = build_generation_context(
        era_id="second_generation",
        player_state=_state(
            current_date="1991-08-01",
            grade="not_enrolled",
            location_id="home",
        ),
        action={"kind": "choice", "choice_id": "wait_for_letter"},
    )

    assert context["id"] == "second_generation"
    assert context["era_frame"]["historical_mood"]
    assert "南瓜汁的甜腻" in context["era_frame"]["core_atmosphere"]
    assert context["mainline_phase"]["id"] == "letter_and_enrollment"
    assert context["timeline_phase"]["phase_id"] == "pre_enrollment_summer"
    assert context["timeline_phase"]["grade"] == "not_enrolled"
    assert context["freedom_rules"]
    assert "强制任务列表" in context["freedom_rules"][0]


def test_generation_context_selects_year_and_relevant_mainline_node() -> None:
    context = build_generation_context(
        era_id="second_generation",
        player_state=_state(
            current_date="1992-11-02",
            grade="year_2",
            location_id="hogwarts_bathroom",
            worldline={"offset_rate": 4.5, "delta": 1.5},
        ),
        action={
            "kind": "free_text",
            "text": "调查盥洗室里的石化袭击和密室传闻",
        },
    )

    assert context["mainline_phase"]["id"] == "chamber_and_fear"
    assert context["timeline_phase"]["calendar_year"] == 1992
    assert context["timeline_phase"]["grade"] == "year_2"
    assert context["timeline_phase"]["phase_id"] == "year_2_school_year"
    assert context["worldline_pressure"]["offset_rate"] == 4.5
    assert context["worldline_pressure"]["offset_band"] == "low"
    assert any(node["id"] == "chamber_of_secrets" for node in context["relevant_nodes"])


def test_changed_node_is_preserved_as_altered_pressure() -> None:
    context = build_generation_context(
        era_id="second_generation",
        player_state=_state(
            current_date="1998-04-20",
            grade="left_school",
            location_id="hogwarts_castle",
            worldline={
                "offset_rate": 62,
                "last_delta": 3,
                "reason": "玩家提前向盟友传递了战争情报",
                "affected_nodes": ["battle_of_hogwarts"],
            },
        ),
        action={"kind": "choice", "choice_id": "send_warning"},
    )

    assert context["mainline_phase"]["id"] == "resistance_and_battle"
    assert context["timeline_phase"]["phase_id"] == "resistance_and_battle_after_departure"
    assert context["worldline_pressure"]["last_delta"] == 3
    assert context["worldline_pressure"]["offset_band"] == "high"
    changed = context["worldline_pressure"]["changed_nodes"]
    assert changed[0]["id"] == "battle_of_hogwarts"
    assert changed[0]["status"] == "altered"
    assert "因果" in changed[0]["freedom_note"]


def test_modern_context_uses_temporal_disturbance_and_modern_cast() -> None:
    context = build_generation_context(
        era_id="modern",
        player_state={
            **_state(current_date="2020-09-01", grade="year_4"),
            "modern_arc": {"phase_id": "modern_school_arrival"},
            "worldline": {
                "mode": "temporal_disturbance",
                "temporal_disturbance": 12,
                "temporal_stability": 88,
                "current_timeline_id": "original_2020",
                "triggered_thresholds": [],
            },
        },
    )

    assert context["id"] == "modern"
    assert context["mainline_phase"]["id"] == "modern_school_arrival"
    assert context["mainline_phase"]["summary"]
    assert context["era_frame"]["core_atmosphere"]
    assert context["timeline_phase"]["phase_id"] == "modern_school_arrival"
    assert context["timeline_phase"]["grade"] == "year_4"
    assert context["worldline_pressure"]["mode"] == "temporal_disturbance"
    assert context["worldline_pressure"]["band"] == "local_echo"
    assert context["worldline_pressure"]["temporal_stability"] == 88
    assert any(item["npc_id"] == "albus_potter" for item in context["cast_index"])


def test_story_after_battle_uses_postwar_phase() -> None:
    context = build_generation_context(
        era_id="second_generation",
        player_state=_state(
            current_date="1999-01-01",
            grade="left_school",
            location_id="london",
        ),
    )

    assert context["mainline_phase"]["id"] == "postwar_aftermath"
    assert context["mainline_phase"]["title"] == "战后的余波"
    assert "重新写成正在发生" in context["mainline_phase"]["freedom_note"]
    assert context["timeline_phase"]["phase_id"] == "postwar_aftermath_after_departure"
