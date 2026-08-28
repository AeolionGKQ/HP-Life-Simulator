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


def test_dumbledore_context_uses_hollow_opening_and_full_cast() -> None:
    context = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1892-07-01",
            grade="not_enrolled",
            location_id="godrics_hollow",
        ),
    )

    assert context["id"] == "dumbledore_era"
    assert context["era_frame"]["opening_date"] == "1892-07-01"
    assert "煤油灯" in context["era_frame"]["era_background"]
    assert context["mainline_phase"]["id"] == "godrics_hollow_summer"
    assert context["forbidden_figures"]
    assert "哈利·波特" in context["forbidden_figures"]
    assert context["available_figures"]
    assert any(item["name"] == "格里塞尔达·马奇班克斯" for item in context["available_figures"])
    assert all(
        item["era_status"] and item["how_to_use"] for item in context["available_figures"]
    )
    assert "礼仪" in context["era_frame"]["era_background"]
    assert "future_timeline" not in context["mainline_phase"]


def test_dumbledore_cast_keeps_1899_canon_red_lines() -> None:
    context = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1899-08-10",
            grade="left_school",
            location_id="godrics_hollow",
        ),
        action={"kind": "free_text", "text": "留在混战现场看着阿利安娜坠落"},
    )

    cast = {item["npc_id"]: item for item in context["cast_index"]}
    ariana_rules = " ".join(cast["ariana_dumbledore"]["must_not"])
    assert "不得确认杀死她的咒语来自谁" in ariana_rules
    grindelwald_rules = " ".join(cast["gellert_grindelwald"]["must_not"])
    assert "歇斯底里的杀人狂" in grindelwald_rules
    assert "纳粹德国" in grindelwald_rules
    albus_rules = " ".join(cast["albus_dumbledore"]["must_not"])
    assert "圣人" in albus_rules
    assert "爱情" in albus_rules
    assert "以血立誓" in cast["gellert_grindelwald"]["background"]

    fall = next(node for node in context["relevant_nodes"] if node["id"] == "ariana_fall")
    assert "施法者必须保持未知" in fall["pressure_summary"]


def test_dumbledore_aftermath_phase_carries_future_timeline() -> None:
    context = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1900-05-01",
            grade="left_school",
            location_id="godrics_hollow",
        ),
    )

    assert context["mainline_phase"]["id"] == "greater_good_aftermath"
    timeline = context["mainline_phase"]["future_timeline"]
    for keyword in (
        "圣徒",
        "纽蒙迦德",
        "血盟",
        "1932",
        "1945",
        "老魔杖",
        "硬锚点",
        "架空历史",
        "麒麟",
        "1926",
        "1927",
        "留白",
    ):
        assert keyword in timeline
    assert "只有当前日期真正到达对应年份" in timeline
    assert "约1932年" in timeline
    assert any(item["npc_id"] == "albus_dumbledore" for item in context["cast_index"])
    albus = next(item for item in context["cast_index"] if item["npc_id"] == "albus_dumbledore")
    assert "校长" in albus["must_not"][0]
    assert albus["background"]
    assert "更弱" in context["freedom_rules"][-5]
    assert any(item["name"] == "纽特·斯卡曼德" for item in context["available_figures"])


def test_dumbledore_grindelwald_node_waits_until_1899() -> None:
    early = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1892-09-02",
            grade="year_1",
            location_id="hogwarts_castle",
        ),
    )
    late = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1899-07-20",
            grade="left_school",
            location_id="godrics_hollow",
        ),
        action={"kind": "free_text", "text": "去找阿不思和那个金发的格林德沃"},
    )

    assert early["mainline_phase"]["id"] == "brilliant_classmate"
    assert all(node["id"] != "grindelwald_summer" for node in early["relevant_nodes"])
    assert late["mainline_phase"]["id"] == "greater_good_summer"
    assert any(node["id"] == "grindelwald_summer" for node in late["relevant_nodes"])


def test_dumbledore_endgame_dates_land_on_expected_phases() -> None:
    at_fall = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1899-08-31",
            grade="left_school",
            location_id="godrics_hollow",
        ),
        action={"kind": "start_story", "text": "阿不思抱着阿利安娜，格林德沃夺门而逃"},
    )
    next_day = build_generation_context(
        era_id="dumbledore_era",
        player_state=_state(
            current_date="1899-09-01",
            grade="left_school",
            location_id="godrics_hollow",
        ),
    )

    assert at_fall["mainline_phase"]["id"] == "greater_good_summer"
    fall_node = next(
        node for node in at_fall["relevant_nodes"] if node["id"] == "ariana_fall"
    )
    assert fall_node["status"] == "active"
    assert "future_timeline" not in at_fall["mainline_phase"]

    assert next_day["mainline_phase"]["id"] == "greater_good_aftermath"
    assert "future_timeline" in next_day["mainline_phase"]


def test_parent_context_uses_1971_platform_and_student_snape() -> None:
    context = build_generation_context(
        era_id="parent_generation",
        player_state=_state(
            current_date="1971-09-01",
            grade="year_1",
            location_id="platform_nine_three_quarters",
        ),
    )

    assert context["id"] == "parent_generation"
    assert context["era_frame"]["opening_date"] == "1971-09-01"
    assert context["years"] == "1971–1981+"
    assert "摇滚乐" in context["era_frame"]["era_background"]
    assert "成年与战争时代" in context["adult_timeline"]
    assert context["mainline_phase"]["id"] == "platform_1971"
    assert any(item["npc_id"] == "severus_snape" for item in context["cast_index"])
    assert len(context["available_figures"]) >= 10
    assert any(item["name"] == "凤凰社" for item in context["available_figures"])
    snape = next(item for item in context["cast_index"] if item["npc_id"] == "severus_snape")
    assert "教授" in snape["must_not"][0]
    assert "哈利·波特作为学生或少年" in context["forbidden_figures"]


def test_parent_cast_hides_future_facts_until_date_or_evidence() -> None:
    early = build_generation_context(
        era_id="parent_generation",
        player_state=_state(
            current_date="1971-09-01",
            grade="year_1",
            location_id="platform_nine_three_quarters",
        ),
    )
    early_james = next(
        item for item in early["cast_index"] if item["npc_id"] == "james_potter"
    )
    early_snape = next(
        item for item in early["cast_index"] if item["npc_id"] == "severus_snape"
    )
    assert "阿尼马格斯" not in early_james["background"]
    assert "食死徒" not in early_snape["background"]
    assert "1981" not in early_james["background"]

    late = build_generation_context(
        era_id="parent_generation",
        player_state=_state(
            current_date="1978-07-01",
            grade="left_school",
            location_id="london",
        ),
    )
    late_snape = next(
        item for item in late["cast_index"] if item["npc_id"] == "severus_snape"
    )
    assert "食死徒" in late_snape["background"]


def test_parent_context_continues_after_1981() -> None:
    context = build_generation_context(
        era_id="parent_generation",
        player_state=_state(
            current_date="1982-01-01",
            grade="left_school",
            location_id="london",
        ),
    )

    assert context["years"] == "1971–1981+"
    assert context["mainline_phase"]["id"] == "halloween_1981"
    assert context["timeline_phase"]["calendar_year"] == 1982


def test_parent_mudblood_node_waits_until_1976() -> None:
    early = build_generation_context(
        era_id="parent_generation",
        player_state=_state(
            current_date="1972-03-01",
            grade="year_1",
            location_id="hogwarts_castle",
        ),
    )
    late = build_generation_context(
        era_id="parent_generation",
        player_state=_state(
            current_date="1976-05-01",
            grade="year_5",
            location_id="hogwarts_courtyard",
        ),
        action={"kind": "free_text", "text": "去看詹姆当众羞辱斯内普"},
    )

    assert early["mainline_phase"]["id"] == "marauders_forming"
    assert all(node["id"] != "snape_worst_memory" for node in early["relevant_nodes"])
    assert late["mainline_phase"]["id"] == "mudblood_year"
    assert any(node["id"] == "snape_worst_memory" for node in late["relevant_nodes"])
