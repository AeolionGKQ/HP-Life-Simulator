import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from backend.app.db.session import get_session_factory
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.main import create_app
from backend.app.content.setup import get_setup_step
from backend.app.models import (
    GameSession,
    JournalEntry,
    LongTermMemory,
    NPCState,
    PlayerState,
    Relationship,
    StorySummary,
    TurnRecord,
)
from backend.app.rules.state import apply_turn_rules
from backend.app.schemas.game import NarrativeResponse
from backend.app.services.setup import _materialize_player_state
from backend.app.services.sessions import _normalize_imported_player_state


def test_journal_is_ordered_by_latest_turn_first() -> None:
    with TestClient(create_app()) as client:
        created = client.post("/api/sessions", json={"name": "纪事排序测试"})
        assert created.status_code == 201
        session_id = created.json()["id"]

        with get_session_factory()() as db:
            for sequence in (1, 2, 3):
                turn = TurnRecord(
                    session_id=session_id,
                    sequence=sequence,
                    action_type="test",
                    action={"sequence": sequence},
                    state_version_before=sequence - 1,
                    state_version_after=sequence,
                )
                db.add(turn)
                db.flush()
                db.add(
                    JournalEntry(
                        session_id=session_id,
                        turn_id=turn.id,
                        entry_type="turn",
                        title=f"第{sequence}回合",
                        summary=f"摘要{sequence}",
                        data={"sequence": sequence},
                        created_at=datetime(
                            2026,
                            1,
                            4 - sequence,
                            tzinfo=timezone.utc,
                        ),
                    )
                )
            db.commit()

        journal = client.get(f"/api/sessions/{session_id}/journal")
        assert journal.status_code == 200
        assert [item["data"]["sequence"] for item in journal.json()] == [3, 2, 1]


def test_unexpected_initialization_failure_does_not_lock_the_save(monkeypatch) -> None:
    async def broken_completion(self, messages):
        # 模拟网关返回非 JSON 正文时 response.json() 抛出的异常。
        raise ValueError("Expecting value: line 1 column 1 (char 0)")

    with TestClient(create_app()) as client:
        session_id = client.post(
            "/api/sessions",
            json={"name": "属性异常兜底测试"},
        ).json()["id"]
        for step in range(1, 18):
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={
                    "step": step,
                    "answer": (
                        "second_generation"
                        if step == 1
                        else "1980-03-12"
                        if step == 4
                        else "before_first_letter"
                        if step == 14
                        else "gryffindor"
                        if step == 15
                        else f"answer-{step}"
                    ),
                },
            )
            assert response.status_code == 200

        monkeypatch.setattr(
            OpenAICompatibleProvider,
            "chat_completion",
            broken_completion,
        )
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 502, confirmed.text

        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["attribute_initialization"]["status"] == "failed"

        retried = client.post(
            f"/api/sessions/{session_id}/attributes/initialize",
            json={"adjustment_instruction": "", "force": False},
        )
        assert retried.status_code == 502, retried.text
        assert "正在生成" not in retried.json()["detail"]


@pytest.fixture(autouse=True)
def mock_attribute_initialization(monkeypatch) -> None:
    async def fake_initialization(self, messages):
        return {
            "choices": [{
                "message": {
                    "content": """{
                      "response_type": "attribute_initialization",
                      "schema_version": "1.2",
                      "resources": [
                        {"id": "health", "value": 100, "max": 100, "reason": "稳定"},
                        {"id": "mana", "value": 100, "max": 100, "reason": "稳定"},
                        {"id": "sanity", "value": 100, "max": 100, "reason": "稳定"},
                        {"id": "energy", "value": 100, "max": 100, "reason": "充足"},
                        {"id": "satiety", "value": 100, "max": 100, "reason": "正常"}
                      ],
                      "dimensions": [
                        {"id": "constitution", "value": 10, "max": 20, "reason": "普通"},
                        {"id": "intelligence", "value": 10, "max": 20, "reason": "普通"},
                        {"id": "willpower", "value": 10, "max": 20, "reason": "普通"},
                        {"id": "charisma", "value": 10, "max": 20, "reason": "普通"},
                        {"id": "magical_power", "value": 10, "max": 20, "reason": "普通"}
                      ],
                      "calibration_summary": "初始属性已生成",
                      "self_check": {}
                    }"""
                }
            }]
        }

    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "chat_completion",
        fake_initialization,
    )


def test_create_and_read_session() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "测试人生"},
        )
        assert created.status_code == 201
        session = created.json()
        assert session["era_id"] == "second_generation"
        assert session["status"] == "setup"

        detail = client.get(f"/api/sessions/{session['id']}")
        assert detail.status_code == 200
        assert detail.json()["player_state"]["setup"]["current_step"] == 1
        assert detail.json()["player_state"]["setup"]["schema_version"] == 2
        assert "resources" in detail.json()["player_state"]
        assert "dimensions" in detail.json()["player_state"]
        assert "attributes" not in detail.json()["player_state"]
        assert "letters" not in detail.json()["player_state"]


def test_export_and_import_session_round_trip() -> None:
    with TestClient(create_app()) as client:
        created = client.post("/api/sessions", json={"name": "可携带的魔法人生"})
        assert created.status_code == 201
        source_id = created.json()["id"]

        with get_session_factory()() as db:
            player_state = db.scalar(
                select(PlayerState).where(PlayerState.session_id == source_id)
            )
            assert player_state is not None
            state = dict(player_state.state)
            state["identity"] = {"name": "艾琳·格雷"}
            player_state.state = state
            turn = TurnRecord(
                session_id=source_id,
                sequence=1,
                client_action_id=f"export-test-action-{uuid4()}",
                action_type="start_story",
                action={"kind": "start_story"},
                response_type="narrative",
                narrative="一封信在窗台上等待。",
                llm_response={"turn": {"title": "来信"}},
                proposed_changes={},
                authoritative_changes={"visible": {"resource_deltas": []}},
                memory_update={"summary": "收到入学来信"},
                worldline={"offset_rate": 0},
                state_version_before=0,
                state_version_after=1,
            )
            db.add(turn)
            db.flush()
            db.add(
                JournalEntry(
                    session_id=source_id,
                    turn_id=turn.id,
                    entry_type="story",
                    title="来信",
                    summary="收到入学来信",
                    data={},
                )
            )
            db.commit()

        exported = client.get(f"/api/sessions/{source_id}/export")
        assert exported.status_code == 200
        export_payload = exported.json()
        assert export_payload["schema_version"] == "1.0"
        assert export_payload["session"]["id"] == source_id
        assert len(export_payload["turns"]) == 1
        assert len(export_payload["journal_entries"]) == 1
        export_payload["story_arcs"] = [{
            "scope_key": "arc-0001-0025",
            "status": "ready",
            "title": "第一阶段",
            "summary": "前二十五个节点的阶段摘要。",
            "causal_chain": ["收到入学来信"],
            "open_threads": ["等待入学通知"],
            "key_characters": [],
            "key_locations": ["家中"],
            "keywords": ["入学"],
            "important_turns": [1],
            "source_turn_ids": [],
            "covered_turn_start": 1,
            "covered_turn_end": 25,
            "version": 1,
            "updated_at": "2026-08-26T00:00:00+00:00",
        }]

        imported = client.post("/api/sessions/import", json=export_payload)
        assert imported.status_code == 201
        imported_session = imported.json()
        assert imported_session["id"] != source_id
        assert imported_session["name"] == "可携带的魔法人生（导入）"

        detail = client.get(f"/api/sessions/{imported_session['id']}")
        assert detail.status_code == 200
        assert detail.json()["player_state"]["identity"]["name"] == "艾琳·格雷"

        turns = client.get(f"/api/sessions/{imported_session['id']}/turns")
        assert turns.status_code == 200
        assert turns.json()[0]["narrative"] == "一封信在窗台上等待。"
        journal = client.get(f"/api/sessions/{imported_session['id']}/journal")
        assert journal.status_code == 200
        assert journal.json()[0]["summary"] == "收到入学来信"
        story_arcs = client.get(
            f"/api/sessions/{imported_session['id']}/story-arcs"
        )
        assert story_arcs.status_code == 200
        assert story_arcs.json()[0]["title"] == "第一阶段"


def test_origin_setup_options_have_three_preset_descriptions() -> None:
    step = get_setup_step(6)

    assert [option.value for option in step.options] == [
        "pure_blood",
        "half_blood",
        "muggle_born",
    ]
    assert all(option.description for option in step.options)
    assert "父母双方都是巫师" in step.options[0].description
    assert "同时连接魔法界与麻瓜世界" in step.options[1].description
    assert "父母都是麻瓜" in step.options[2].description


def test_setup_accepts_empty_initial_friend_answer() -> None:
    with TestClient(create_app()) as client:
        session_id = client.post(
            "/api/sessions",
            json={"name": "无预设好友测试"},
        ).json()["id"]
        with get_session_factory()() as db:
            player_state = db.scalar(
                select(PlayerState).where(PlayerState.session_id == session_id)
            )
            assert player_state is not None
            state = dict(player_state.state)
            setup = dict(state["setup"])
            setup["current_step"] = 13
            state["setup"] = setup
            player_state.state = state
            db.commit()

        response = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 13, "answer": ""},
        )

        assert response.status_code == 200
        assert response.json()["current"]["step"] == 14
        assert response.json()["answers"]["13"] == ""


def test_starting_point_accepts_only_predefined_story_nodes() -> None:
    with TestClient(create_app()) as client:
        for starting_point in (
            "before_first_letter",
            "diagon_alley",
            "platform_nine_three_quarters",
            "sorting_ceremony",
        ):
            created = client.post(
                "/api/sessions",
                json={"name": f"预设起点测试-{starting_point}"},
            )
            session_id = created.json()["id"]
            with get_session_factory()() as db:
                player_state = db.scalar(
                    select(PlayerState).where(PlayerState.session_id == session_id)
                )
                assert player_state is not None
                state = dict(player_state.state)
                setup = dict(state["setup"])
                setup["current_step"] = 14
                state["setup"] = setup
                player_state.state = state
                db.commit()

            selected = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": 14, "answer": starting_point},
            )
            assert selected.status_code == 200
            assert selected.json()["answers"]["14"] == starting_point

        legacy_session_id = client.post(
            "/api/sessions",
            json={"name": "旧起点兼容测试"},
        ).json()["id"]
        with get_session_factory()() as db:
            player_state = db.scalar(
                select(PlayerState).where(PlayerState.session_id == legacy_session_id)
            )
            assert player_state is not None
            state = dict(player_state.state)
            setup = dict(state["setup"])
            setup["current_step"] = 14
            state["setup"] = setup
            player_state.state = state
            db.commit()

        custom = client.post(
            f"/api/sessions/{legacy_session_id}/setup/answer",
            json={"step": 14, "answer": "我想从密室开启故事"},
        )
        assert custom.status_code == 409
        assert "预设节点" in custom.json()["detail"]

        legacy = client.post(
            f"/api/sessions/{legacy_session_id}/setup/answer",
            json={"step": 14, "answer": "owl_letter_arrival"},
        )
        assert legacy.status_code == 200
        assert legacy.json()["answers"]["14"] == "owl_letter_arrival"


@pytest.mark.parametrize(
    ("starting_point", "expected_date", "expected_location", "wand_obtained", "term"),
    [
        ("before_first_letter", "1991-07-01", "home", False, "summer"),
        ("diagon_alley", "1991-07-01", "diagon_alley", False, "summer"),
        (
            "platform_nine_three_quarters",
            "1991-09-01",
            "platform_nine_three_quarters",
            True,
            "autumn",
        ),
        ("sorting_ceremony", "1991-09-01", "hogwarts_great_hall", True, "autumn"),
    ],
)
def test_custom_origin_cannot_change_selected_starting_point(
    starting_point: str,
    expected_date: str,
    expected_location: str,
    wand_obtained: bool,
    term: str,
) -> None:
    state: dict = {"school": {}}
    answers = {
        "2": "龙裔",
        "3": "未设定",
        "4": "1980-03-12",
        "6": "火龙化成人",
        "7": ["见过巫师施法"],
        "10": "冬青木，龙心弦",
        "11": "咒语直觉",
        "14": starting_point,
        "15": "gryffindor",
    }

    _materialize_player_state(state, answers, "second_generation")

    assert state["family"]["origin_id"] == "custom"
    assert state["current_context"]["current_date"] == expected_date
    assert state["current_context"]["location_id"] == expected_location
    assert state["current_context"]["activity"] == starting_point
    assert state["wand"]["obtained"] is wand_obtained
    assert state["story_milestones"]["wand_obtained"] is wand_obtained
    assert state["school"]["term"] == term


@pytest.mark.parametrize(
    ("raw_origin", "expected_origin_id"),
    [
        ("pure_blood", "pure_blood"),
        ("纯血家族", "pure_blood"),
        ("half_blood", "half_blood"),
        ("混血家庭", "half_blood"),
        ("muggle_born", "muggle_born"),
        ("麻瓜出身", "muggle_born"),
        ("火龙化成人", "custom"),
    ],
)
def test_origin_values_are_normalized_during_state_materialization(
    raw_origin: str,
    expected_origin_id: str,
) -> None:
    state: dict = {"school": {}}
    answers = {
        "4": "1980-03-12",
        "6": raw_origin,
        "14": "before_first_letter",
        "15": "gryffindor",
    }

    _materialize_player_state(state, answers, "second_generation")

    assert state["family"]["origin_id"] == expected_origin_id
    assert state["family"]["bloodline"] == raw_origin


def test_modern_materialization_uses_fixed_fourth_year_opening() -> None:
    state: dict = {"school": {}}
    answers = {
        "2": "现代测试者",
        "3": "未设定",
        "4": "2006-03-12",
        "6": "half_blood",
        "10": "冬青木，凤凰羽毛",
        "11": "咒语直觉",
        "14": "sorting_ceremony",
        "15": "slytherin",
    }

    _materialize_player_state(state, answers, "modern")

    assert state["identity"]["age"] == 14
    assert state["current_context"] == {
        "datetime": "2020-09-01T10:30:00+00:00",
        "current_date": "2020-09-01",
        "period": "morning",
        "location_id": "platform_nine_three_quarters",
        "activity": "platform_nine_three_quarters",
    }
    assert state["school"]["grade"] == "year_4"
    assert state["school"]["school_year"] == "2020-2021"
    assert state["school"]["enrollment_started"] is True
    assert state["school"]["sorting_completed"] is True
    assert state["school"]["active_courses"] == []
    assert state["school"]["course_history"] == []
    assert state["worldline"]["mode"] == "temporal_disturbance"
    assert state["worldline"]["current_timeline_id"] == "original_2020"
    assert state["modern_arc"]["phase_id"] == "modern_school_arrival"
    assert state["skills"]["expecto_patronum"]["name"] == "呼神护卫"
    assert state["skills"]["expecto_patronum"]["learned"] is True
    assert state["patronus"]["learned"] is True
    assert state["patronus"]["status"] == "已学会【呼神护卫】"


def test_modern_setup_exposes_fixed_start_and_seeds_modern_cast() -> None:
    answers = {
        1: "modern",
        2: "现代好友测试",
        3: "女",
        4: "2006-03-12",
        5: "乌黑短发，深褐色眼睛",
        6: "混血家庭",
        7: "在麻瓜学校隐藏反常能力",
        8: "冷静谨慎，好奇求知",
        9: "血统平等",
        10: "冬青木，凤凰羽毛",
        11: "咒语直觉",
        12: "猫头鹰",
        13: "阿不思·西弗勒斯·波特",
        14: "platform_nine_three_quarters",
        15: "ravenclaw",
        16: "猫",
        17: "",
    }
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "现代线固定开局测试"},
        ).json()
        session_id = created["id"]
        for step, answer in answers.items():
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": answer},
            )
            assert response.status_code == 200, response.text
            if step == 3:
                assert "推荐出生年份为2009年" in response.json()["current"]["description"]
            if step == 12:
                assert any(
                    option["value"] == "阿不思·西弗勒斯·波特"
                    for option in response.json()["current"]["options"]
                )
            if step == 13:
                assert response.json()["current"]["title"] == "固定剧情起点"
                assert "第一版" not in response.json()["current"]["description"]
                assert "唯一的剧情起点" in response.json()["current"]["description"]
                assert len(response.json()["current"]["options"]) == 1
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200, confirmed.text
        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["school"]["grade"] == "year_4"
        assert state["current_context"]["current_date"] == "2020-09-01"
        npcs = client.get(f"/api/sessions/{session_id}/npcs").json()
        npc_by_id = {npc["npc_id"]: npc for npc in npcs}
        assert npc_by_id["albus_potter"]["state"]["age"] == 14
        assert npc_by_id["albus_potter"]["state"]["age_reference_date"] == "2020-09-01"
        relationships = client.get(
            f"/api/sessions/{session_id}/relationships"
        ).json()
        assert any(
            item["target_id"] == "albus_potter"
            and item["state"]["stage"] == "friend"
            for item in relationships
        )


def test_dumbledore_materialization_uses_summer_hollow_opening() -> None:
    state: dict = {"school": {}}
    answers = {
        "2": "山谷测试者",
        "3": "未设定",
        "4": "1881-03-12",
        "6": "half_blood",
        "10": "冬青木，凤凰羽毛",
        "11": "咒语直觉",
        "14": "platform_nine_three_quarters",
        "15": "gryffindor",
    }

    _materialize_player_state(state, answers, "dumbledore_era")

    assert state["identity"]["age"] == 11
    assert state["current_context"] == {
        "datetime": "1892-07-01T09:00:00+00:00",
        "current_date": "1892-07-01",
        "period": "morning",
        "location_id": "godrics_hollow",
        "activity": "godrics_hollow",
    }
    assert state["school"]["grade"] == "not_enrolled"
    assert state["school"]["enrollment_started"] is False
    assert state["school"]["sorting_completed"] is False
    assert state["school"]["school_year"] == "1892-1893"
    assert state["school"]["active_courses"] == []
    assert state["story_milestones"]["wand_obtained"] is True
    assert state["story_milestones"]["sorting_completed"] is False
    assert state["wand"]["obtained"] is True
    assert state["wand"]["status"] == "obtained"
    assert state["worldline"] == {
        "offset_rate": 0.0,
        "last_delta": 0.0,
        "reason": "邓布利多时代刚从1892年夏的戈德里克山谷开始",
        "affected_nodes": [],
    }
    assert "modern_arc" not in state
    assert "temporal_disturbance" not in state["worldline"]


def test_parent_materialization_waits_for_sorting_before_first_year() -> None:
    state: dict = {"school": {}, "skills": {}}
    answers = {
        "2": "掠夺者测试者",
        "3": "未设定",
        "4": "1960-03-12",
        "6": "muggle_born",
        "10": "冬青木，凤凰羽毛",
        "11": "咒语直觉",
        "14": "sorting_ceremony",
        "15": "gryffindor",
    }

    _materialize_player_state(state, answers, "parent_generation")

    assert state["identity"]["age"] == 11
    assert state["current_context"]["current_date"] == "1971-09-01"
    assert state["current_context"]["location_id"] == "platform_nine_three_quarters"
    assert state["school"]["grade"] == "not_enrolled"
    assert state["school"]["enrollment_started"] is False
    assert state["school"]["sorting_completed"] is False
    assert state["school"]["grade_started_year"] is None
    assert state["school"]["active_courses"] == []

    enrolled, changes = apply_turn_rules(
        state,
        [],
        NarrativeResponse(
            response_type="narrative",
            turn={
                "title": "分院仪式",
                "narrative": "分院帽宣布了学院归属。",
                "current_date": "1971-09-01",
                "location_id": "hogwarts",
                "grade": "year_1",
                "school_transition": {
                    "type": "enrollment",
                    "from_grade": "not_enrolled",
                    "to_grade": "year_1",
                    "reason": "sorting_completed",
                    "evidence": "分院帽完成分院并宣布学院归属。",
                },
            },
            choices=[],
            worldline={},
            events=[{
                "type": "sorting_completed",
                "evidence": "分院帽完成分院并宣布学院归属。",
            }],
        ),
    )
    assert enrolled["school"]["grade"] == "year_1"
    assert enrolled["school"]["enrollment_started"] is True
    assert enrolled["school"]["sorting_completed"] is True
    assert enrolled["school"]["grade_started_year"] == 1971
    assert "charms" in enrolled["school"]["active_courses"]
    assert "flying" in enrolled["school"]["active_courses"]
    assert enrolled["skills"]["charms"]["course_skill"] is True
    assert changes["school_grade"]["type"] == "enrollment"
    assert state["worldline"]["offset_rate"] == 0.0
    assert "modern_arc" not in state


def test_dumbledore_setup_exposes_fixed_start_and_seeds_young_dumbledore() -> None:
    answers = {
        1: "dumbledore_era",
        2: "山谷好友测试",
        3: "女",
        4: "1881-03-12",
        5: "乌黑短发，深褐色眼睛",
        6: "混血家庭",
        7: "在山谷里听过不愿被提起的传闻",
        8: "冷静谨慎，好奇求知",
        9: "保护家人",
        10: "冬青木，凤凰羽毛",
        11: "咒语直觉",
        12: "猫头鹰",
        13: "阿不思·邓布利多",
        14: "godrics_hollow",
        15: "ravenclaw",
        16: "猫",
        17: "",
    }
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "邓布利多时代固定开局测试"},
        ).json()
        session_id = created["id"]
        for step, answer in answers.items():
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": answer},
            )
            assert response.status_code == 200, response.text
            if step == 3:
                assert "推荐出生年份为1881年" in response.json()["current"]["description"]
            if step == 12:
                option_values = [option["value"] for option in response.json()["current"]["options"]]
                assert "阿不思·邓布利多" in option_values
                assert "阿利安娜·邓布利多" in option_values
                assert "盖勒特·格林德沃" in option_values
                assert "哈利·波特" not in option_values
            if step == 13:
                current = response.json()["current"]
                assert current["title"] == "剧情起点"
                assert "第一版" not in current["description"]
                assert "已经毕业的成年巫师" in current["description"]
                options = current["options"]
                assert len(options) == 3
                assert options[0]["value"] == "godrics_hollow"
                assert options[0]["category"] == "常规开局"
                endgame = [item for item in options if item["category"] == "直入终局"]
                assert [item["value"] for item in endgame] == [
                    "godrics_hollow_1899_summer",
                    "godrics_hollow_1899_fall",
                ]
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200, confirmed.text
        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["school"]["grade"] == "not_enrolled"
        assert state["current_context"]["current_date"] == "1892-07-01"
        npcs = client.get(f"/api/sessions/{session_id}/npcs").json()
        npc_by_id = {npc["npc_id"]: npc for npc in npcs}
        assert "harry_potter" not in npc_by_id
        assert npc_by_id["albus_dumbledore"]["state"]["age"] == 11
        assert "少年" in npc_by_id["albus_dumbledore"]["state"]["role"]
        assert npc_by_id["gellert_grindelwald"]["state"]["age_reference_date"] == "1899-07-01"


def _dumbledore_endgame_answers(starting_point: str, name: str) -> dict[int, str]:
    return {
        1: "dumbledore_era",
        2: name,
        3: "女",
        4: "1881-03-12",
        5: "赤褐长发，浅灰色眼睛",
        6: "混血家庭",
        7: "曾和家中画像偷偷交谈",
        8: "冷静谨慎，重情忠诚",
        9: "家人与同伴优先",
        10: "白蜡木，凤凰羽毛",
        11: "咒语直觉",
        12: "猫头鹰",
        13: starting_point,
        14: "ravenclaw",
        15: "牝鹿",
        16: "",
    }


def _run_dumbledore_endgame_setup(client: TestClient, starting_point: str, name: str) -> str:
    created = client.post("/api/sessions", json={"name": name}).json()
    session_id = created["id"]
    answers = _dumbledore_endgame_answers(starting_point, name)
    step_to_answer = {
        1: answers[1],
        2: answers[2],
        3: answers[3],
        4: answers[4],
        5: answers[5],
        6: answers[6],
        7: answers[7],
        8: answers[8],
        9: answers[9],
        10: answers[10],
        11: answers[11],
        12: answers[12],
        13: "",
        14: answers[13],
        15: answers[14],
        16: answers[15],
        17: answers[16],
    }
    for step in range(1, 18):
        response = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": step, "answer": step_to_answer[step]},
        )
        assert response.status_code == 200, response.text
    confirmed = client.post(
        f"/api/sessions/{session_id}/setup/confirm",
        json={"confirmed": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    return session_id


def test_dumbledore_endgame_before_fall_starts_as_adult_graduate() -> None:
    with TestClient(create_app()) as client:
        session_id = _run_dumbledore_endgame_setup(
            client,
            "godrics_hollow_1899_summer",
            "直入终局·死亡之前",
        )
        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]

        assert state["current_context"]["current_date"] == "1899-07-10"
        assert state["current_context"]["activity"] == "godrics_hollow_1899_summer"
        assert state["current_context"]["location_id"] == "godrics_hollow"
        assert state["identity"]["age"] == 18
        assert state["identity"]["age_band"] == "adult"
        assert state["school"]["grade"] == "left_school"
        assert state["school"]["departure_reason"] == "graduated_after_newts"
        assert state["school"]["sorting_completed"] is True
        assert state["story_milestones"]["sorting_completed"] is True
        assert state["story_milestones"]["wand_obtained"] is True
        assert state["skills"]["expecto_patronum"]["learned"] is True
        assert state["patronus"]["learned"] is True
        assert state["patronus"]["status"] == "已学会【呼神护卫】"
        assert state["skills"]["charms"]["course_skill"] is True
        assert state["skills"]["charms"]["level"] == 5
        assert state["endgame_entry"]["ariana_alive"] is True
        assert state["endgame_entry"]["grindelwald_present"] is True
        assert "挚友" in state["endgame_entry"]["premise"]

        npc_by_id = {
            npc["npc_id"]: npc
            for npc in client.get(f"/api/sessions/{session_id}/npcs").json()
        }
        assert npc_by_id["albus_dumbledore"]["state"]["age"] == 18
        assert "毕业" in npc_by_id["albus_dumbledore"]["state"]["role"]
        assert npc_by_id["gellert_grindelwald"]["state"]["location_id"] == "godrics_hollow"
        assert "life_status" not in npc_by_id["ariana_dumbledore"]["state"]
        assert npc_by_id["kendra_dumbledore"]["state"]["life_status"] == "deceased"

        relationships = client.get(f"/api/sessions/{session_id}/relationships").json()
        relation_by_id = {item["target_id"]: item for item in relationships}
        assert relation_by_id["albus_dumbledore"]["state"]["stage"] == "close_friend"
        assert relation_by_id["albus_dumbledore"]["state"]["affinity"] >= 70
        assert relation_by_id["gellert_grindelwald"]["state"]["stage"] == "acquaintance"

        memories = client.get(f"/api/sessions/{session_id}/memories").json()
        titles = " ".join(str(item.get("title", "")) for item in memories)
        assert "七年" in titles
        assert "混战" not in titles


def test_dumbledore_endgame_at_fall_marks_ariana_dead_and_grindelwald_fled() -> None:
    with TestClient(create_app()) as client:
        session_id = _run_dumbledore_endgame_setup(
            client,
            "godrics_hollow_1899_fall",
            "直入终局·死亡之时",
        )
        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]

        assert state["current_context"]["current_date"] == "1899-08-31"
        assert state["current_context"]["activity"] == "godrics_hollow_1899_fall"
        assert state["school"]["grade"] == "left_school"
        assert state["endgame_entry"]["ariana_alive"] is False
        assert state["endgame_entry"]["grindelwald_present"] is False
        assert state["skills"]["expecto_patronum"]["learned"] is True
        assert state["patronus"]["learned"] is True

        npc_by_id = {
            npc["npc_id"]: npc
            for npc in client.get(f"/api/sessions/{session_id}/npcs").json()
        }
        assert npc_by_id["ariana_dumbledore"]["state"]["life_status"] == "deceased"
        assert npc_by_id["kendra_dumbledore"]["state"]["life_status"] == "deceased"
        assert npc_by_id["gellert_grindelwald"]["state"]["presence"] == "fled_abroad"
        assert npc_by_id["gellert_grindelwald"]["state"]["location_id"] == "unknown"

        relationships = client.get(f"/api/sessions/{session_id}/relationships").json()
        relation_by_id = {item["target_id"]: item for item in relationships}
        assert relation_by_id["albus_dumbledore"]["state"]["stage"] == "close_friend"
        assert relation_by_id["ariana_dumbledore"]["state"]["stage"] == "stranger"

        memories = client.get(f"/api/sessions/{session_id}/memories").json()
        summaries = " ".join(str(item.get("summary", "")) for item in memories)
        assert "混战" in summaries
        assert "没有任何人能确定那道致命咒语来自谁" in summaries


def test_dumbledore_endgame_start_is_rejected_for_other_eras() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "跨世代起点校验"},
        ).json()
        session_id = created["id"]
        for step, answer in {
            1: "second_generation",
            2: "越界测试",
            3: "女",
            4: "1980-03-12",
            5: "乌黑短发",
            6: "混血家庭",
            7: "曾和家中画像偷偷交谈",
            8: "冷静谨慎",
            9: "血统平等",
            10: "冬青木",
            11: "咒语直觉",
            12: "猫头鹰",
            13: "",
        }.items():
            assert (
                client.post(
                    f"/api/sessions/{session_id}/setup/answer",
                    json={"step": step, "answer": answer},
                ).status_code
                == 200
            )
        rejected = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 14, "answer": "godrics_hollow_1899_fall"},
        )
        assert rejected.status_code == 409
        assert "直入终局" in rejected.json()["detail"]


def test_parent_setup_exposes_fixed_start_and_seeds_student_snape() -> None:
    answers = {
        1: "parent_generation",
        2: "亲世代好友测试",
        3: "男",
        4: "1960-03-12",
        5: "乌黑短发，深褐色眼睛",
        6: "麻瓜出身",
        7: "在麻瓜学校隐藏反常能力",
        8: "冷静谨慎，好奇求知",
        9: "血统平等",
        10: "冬青木，凤凰羽毛",
        11: "咒语直觉",
        12: "猫头鹰",
        13: "莉莉·伊万斯",
        14: "platform_nine_three_quarters",
        15: "gryffindor",
        16: "猫",
        17: "",
    }
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "亲世代固定开局测试"},
        ).json()
        session_id = created["id"]
        for step, answer in answers.items():
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": answer},
            )
            assert response.status_code == 200, response.text
            if step == 3:
                assert "推荐出生年份为1960年" in response.json()["current"]["description"]
            if step == 12:
                assert any(
                    option["value"] == "莉莉·伊万斯"
                    for option in response.json()["current"]["options"]
                )
                assert all(
                    option["value"] != "哈利·波特"
                    for option in response.json()["current"]["options"]
                )
            if step == 13:
                assert response.json()["current"]["title"] == "固定剧情起点"
                assert "第一版" not in response.json()["current"]["description"]
                assert "未来的朋友与对手" in response.json()["current"]["description"]
                assert response.json()["current"]["options"][0]["label"] == "1971年9月1日·九又四分之三站台"
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200, confirmed.text
        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["school"]["grade"] == "not_enrolled"
        assert state["school"]["enrollment_started"] is False
        assert state["school"]["sorting_completed"] is False
        assert state["school"]["active_courses"] == []
        npcs = client.get(f"/api/sessions/{session_id}/npcs").json()
        npc_by_id = {npc["npc_id"]: npc for npc in npcs}
        assert "harry_potter" not in npc_by_id
        assert "学生" in npc_by_id["severus_snape"]["state"]["role"]
        assert npc_by_id["james_potter"]["state"]["age"] == 11
        relationships = client.get(
            f"/api/sessions/{session_id}/relationships"
        ).json()
        assert any(
            item["target_id"] == "lily_evans" and item["state"]["stage"] == "friend"
            for item in relationships
        )


def test_import_normalizes_unknown_era_without_leaking_modern_fields() -> None:
    state = {
        "worldline": {
            "mode": "temporal_disturbance",
            "offset_rate": 12,
            "temporal_disturbance": 60,
            "temporal_stability": 40,
            "current_timeline_id": "altered_2020",
        },
        "modern_arc": {"phase_id": "modern_aftershock"},
    }

    normalized = _normalize_imported_player_state(state, "second_generation")

    assert normalized["worldline"] == {"offset_rate": 12}
    assert "modern_arc" not in normalized
    assert state["worldline"]["temporal_disturbance"] == 60


def test_acknowledge_departure_notice_persists_and_increments_state_version() -> None:
    with TestClient(create_app()) as client:
        created = client.post("/api/sessions", json={"name": "开除通知测试"})
        session_id = created.json()["id"]
        before_version = created.json()["state_version"]

        with get_session_factory()() as db:
            player_state = db.scalar(
                select(PlayerState).where(PlayerState.session_id == session_id)
            )
            assert player_state is not None
            state = dict(player_state.state)
            school = dict(state.get("school", {}))
            school["grade"] = "left_school"
            school["departure_reason"] = "expelled"
            school["departure_notice"] = {
                "status": "pending",
                "notice_id": "expulsion:year_1:-61",
                "reason": "expelled",
                "title": "霍格沃兹开除通知",
                "message": "声望过低，已被开除。",
            }
            state["school"] = school
            player_state.state = state
            db.commit()

        response = client.post(
            f"/api/sessions/{session_id}/departure-notice/acknowledge"
        )

        assert response.status_code == 200
        assert response.json()["state_version"] == before_version + 1
        assert (
            response.json()["state"]["school"]["departure_notice"]["status"]
            == "acknowledged"
        )


def test_setup_requires_current_step() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "测试创建流程"},
        )
        session_id = created.json()["id"]
        setup = client.get(f"/api/sessions/{session_id}/setup")
        assert setup.status_code == 200
        assert setup.json()["current"]["title"] == "选择世代"
        response = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 2, "answer": {"name": "测试者"}},
        )
        assert response.status_code == 409

        era_response = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 1, "answer": "second_generation"},
        )
        assert era_response.status_code == 200
        assert era_response.json()["steps_total"] == 18
        assert era_response.json()["current"]["title"] == "姓名"
        gender_response = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 2, "answer": "艾琳"},
        )
        assert gender_response.status_code == 200
        assert [option["label"] for option in gender_response.json()["current"]["options"]] == [
            "女",
            "男",
        ]

        client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 3, "answer": "女"},
        )
        birthday_view = client.get(f"/api/sessions/{session_id}/setup")
        assert birthday_view.status_code == 200
        assert "推荐出生年份为1980年" in birthday_view.json()["current"]["description"]
        for invalid_value in (
            "三月十二日",
            "19800312",
            "1980/03/12",
            "1980-02-30",
        ):
            invalid_birthday = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": 4, "answer": invalid_value},
            )
            assert invalid_birthday.status_code == 409
            assert invalid_birthday.json()["detail"] == "请选择有效的生日日期"


def test_setup_can_navigate_back_and_edit_a_completed_step() -> None:
    with TestClient(create_app()) as client:
        session_id = client.post(
            "/api/sessions",
            json={"name": "角色创建翻页测试"},
        ).json()["id"]
        answers = {
            1: "second_generation",
            2: "旧名字",
            3: "女",
        }
        for step, answer in answers.items():
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": answer},
            )
            assert response.status_code == 200

        navigated = client.post(
            f"/api/sessions/{session_id}/setup/navigate",
            json={"step": 2},
        )
        assert navigated.status_code == 200
        assert navigated.json()["current_step"] == 2
        assert navigated.json()["answers"]["2"] == "旧名字"

        edited = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 2, "answer": "新名字"},
        )
        assert edited.status_code == 200
        assert edited.json()["current_step"] == 3
        assert edited.json()["answers"]["2"] == "新名字"
        assert edited.json()["answers"]["3"] == "女"

        cannot_go_forward = client.post(
            f"/api/sessions/{session_id}/setup/navigate",
            json={"step": 3},
        )
        assert cannot_go_forward.status_code == 409

        first_step = client.post(
            f"/api/sessions/{session_id}/setup/navigate",
            json={"step": 1},
        )
        assert first_step.status_code == 200
        assert first_step.json()["current_step"] == 1


def test_setup_academy_only_accepts_four_choices() -> None:
    with TestClient(create_app()) as client:
        session_id = client.post(
            "/api/sessions",
            json={"name": "学院选择测试"},
        ).json()["id"]
        for step in range(1, 15):
            answer = (
                    "second_generation"
                    if step == 1
                    else "1980-03-12"
                    if step == 4
                    else "before_first_letter"
                    if step == 14
                    else f"answer-{step}"
            )
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": answer},
            )
            assert response.status_code == 200

        assert [option["value"] for option in response.json()["current"]["options"]] == [
            "gryffindor",
            "hufflepuff",
            "ravenclaw",
            "slytherin",
        ]
        invalid = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 15, "answer": "自定义学院"},
        )
        assert invalid.status_code == 409
        assert "四个学院" in invalid.json()["detail"]

        valid = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 15, "answer": "ravenclaw"},
        )
        assert valid.status_code == 200
        assert valid.json()["current"]["step"] == 16
        patronus = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 16, "answer": "银色猫头鹰"},
        )
        assert patronus.status_code == 200
        assert patronus.json()["current"]["step"] == 17


def test_rename_and_delete_save_clears_related_data() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "待整理卷宗"},
        ).json()
        session_id = created["id"]
        renamed = client.patch(
            f"/api/sessions/{session_id}",
            json={"name": "月光下的第一卷"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "月光下的第一卷"

        for step in range(1, 18):
            client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={
                    "step": step,
                    "answer": (
                            "second_generation"
                            if step == 1
                            else "1980-03-12"
                            if step == 4
                            else "before_first_letter"
                            if step == 14
                            else "gryffindor"
                        if step == 15
                        else f"answer-{step}"
                    ),
                },
            )
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["attribute_initialization"]["status"] == "ready", confirmed.text
        assert client.get(f"/api/sessions/{session_id}/state").json()["state"][
            "attribute_initialization"
        ]["status"] == "ready"
        deleted = client.delete(f"/api/sessions/{session_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/sessions/{session_id}").status_code == 404

    with get_session_factory()() as db:
        for model in (
            GameSession,
            PlayerState,
            NPCState,
            Relationship,
            TurnRecord,
            JournalEntry,
            LongTermMemory,
            StorySummary,
        ):
            remaining = db.scalar(
                select(func.count())
                .select_from(model)
                .where(model.session_id == session_id)
            ) if model is not GameSession else db.scalar(
                select(func.count())
                .select_from(GameSession)
                .where(GameSession.id == session_id)
            )
            assert remaining == 0


def test_setup_materializes_npcs_and_state() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "完整流程测试"},
        ).json()
        session_id = created["id"]
        for step in range(1, 18):
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={
                    "step": step,
                    "answer": (
                        "second_generation"
                        if step == 1
                        else "1980-03-12"
                        if step == 4
                        else "before_first_letter"
                        if step == 14
                        else "gryffindor"
                        if step == 15
                        else f"answer-{step}"
                    ),
                },
            )
            assert response.status_code == 200
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["completed"] is True

        state = client.get(f"/api/sessions/{session_id}/state")
        assert state.status_code == 200
        assert state.json()["state"]["identity"] == {
            "name": "answer-2",
            "gender": "answer-3",
            "birthday": "1980-03-12",
            "age": 11,
        }

        npcs = client.get(f"/api/sessions/{session_id}/npcs")
        relationships = client.get(f"/api/sessions/{session_id}/relationships")
        assert npcs.status_code == 200
        assert relationships.status_code == 200
        assert len(npcs.json()) >= 9
        assert len(relationships.json()) >= 9


def test_ready_attributes_can_be_regenerated_before_story_and_not_after(
    monkeypatch,
) -> None:
    calls: list[list[dict[str, str]]] = []

    async def fake_regeneration(self, messages):
        calls.append(messages)
        return {
            "choices": [{
                "message": {
                    "content": """{
                      "response_type": "attribute_initialization",
                      "schema_version": "1.2",
                      "resources": [
                        {"id": "health", "value": 90, "max": 100, "reason": "重生成"},
                        {"id": "mana", "value": 90, "max": 100, "reason": "重生成"},
                        {"id": "sanity", "value": 90, "max": 100, "reason": "重生成"},
                        {"id": "energy", "value": 90, "max": 100, "reason": "重生成"},
                        {"id": "satiety", "value": 90, "max": 100, "reason": "重生成"}
                      ],
                      "dimensions": [
                        {"id": "constitution", "value": 14, "max": 20, "reason": "重生成"},
                        {"id": "intelligence", "value": 10, "max": 20, "reason": "重生成"},
                        {"id": "willpower", "value": 13, "max": 20, "reason": "重生成"},
                        {"id": "charisma", "value": 10, "max": 20, "reason": "重生成"},
                        {"id": "magical_power", "value": 10, "max": 20, "reason": "重生成"}
                      ],
                      "calibration_summary": "按偏好重新生成",
                      "self_check": {}
                    }"""
                }
            }]
        }

    monkeypatch.setattr(
        OpenAICompatibleProvider,
        "chat_completion",
        fake_regeneration,
    )

    with TestClient(create_app()) as client:
        session_id = client.post(
            "/api/sessions",
            json={"name": "初始属性重生成测试"},
        ).json()["id"]
        for step in range(1, 18):
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={
                    "step": step,
                    "answer": (
                        "second_generation"
                        if step == 1
                        else "1980-03-12"
                        if step == 4
                        else "before_first_letter"
                        if step == 14
                        else "gryffindor"
                        if step == 15
                        else f"answer-{step}"
                    ),
                },
            )
            assert response.status_code == 200

        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200
        assert len(calls) == 1

        before = client.get(f"/api/sessions/{session_id}").json()
        regenerated = client.post(
            f"/api/sessions/{session_id}/attributes/initialize",
            json={
                "adjustment_instruction": "体质和意志稍高，魔力保持普通",
                "force": True,
            },
        )
        assert regenerated.status_code == 200, regenerated.text
        assert len(calls) == 2
        assert "体质和意志稍高" in calls[-1][1]["content"]
        assert regenerated.json()["attribute_initialization"]["adjustment_instruction"] == (
            "体质和意志稍高，魔力保持普通"
        )
        state = client.get(f"/api/sessions/{session_id}/state").json()
        assert state["state"]["dimensions"]["constitution"]["value"] == 14
        assert state["state"]["attribute_initialization"]["status"] == "ready"
        assert client.get(f"/api/sessions/{session_id}").json()["state_version"] == (
            before["state_version"] + 1
        )

        cannot_navigate = client.post(
            f"/api/sessions/{session_id}/setup/navigate",
            json={"step": 1},
        )
        assert cannot_navigate.status_code == 409

        with get_session_factory()() as db:
            db.add(
                JournalEntry(
                    session_id=session_id,
                    entry_type="story",
                    title="已经开始的故事",
                    summary="属性重生成不应覆盖已经开始的剧情。",
                )
            )
            db.commit()

        blocked = client.post(
            f"/api/sessions/{session_id}/attributes/initialize",
            json={"adjustment_instruction": "继续提高体质", "force": True},
        )
        assert blocked.status_code == 409
        assert "已经开始剧情" in blocked.json()["detail"]
        assert len(calls) == 2


def test_setup_initial_friends_and_sorting_start() -> None:
    answers = {
        1: "second_generation",
        2: "艾琳",
        3: "女",
        4: "1980-03-12",
        5: "赤褐长发，浅灰色眼睛，身形纤细",
        6: "混血家庭",
        7: "照料过一只受伤的猫头鹰，曾和家中画像偷偷交谈",
        8: "好奇求知，原则坚定",
        9: "血统平等，知识不应被禁止",
        10: "冬青木，独角兽毛，十一又四分之一英寸，柔韧",
        11: "咒语直觉，神奇生物亲和",
        12: "猫狸子混血猫",
        13: "哈利·波特，赫敏·格兰杰，艾薇·摩尔",
        14: "分院时",
        15: "gryffindor",
        16: "猫头鹰",
        17: "我愿意让这段补充设定参与后续故事。",
    }
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "好友与分院起点测试"},
        ).json()
        session_id = created["id"]
        for step, answer in answers.items():
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": answer},
            )
            assert response.status_code == 200
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200

        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["identity"]["name"] == "艾琳"
        assert state["identity"]["gender"] == "女"
        assert state["identity"]["birthday"] == "1980-03-12"
        assert state["school"]["house"] == "gryffindor"
        assert state["personality"]["traits"] == ["好奇求知", "原则坚定"]
        assert [item["name"] for item in state["magic_talents"]] == [
            "咒语直觉",
            "神奇生物亲和",
        ]
        assert state["current_context"]["current_date"] == "1991-09-01"
        assert state["current_context"]["location_id"] == "hogwarts_great_hall"
        assert state["current_context"]["activity"] == "sorting_ceremony"

        npcs = client.get(f"/api/sessions/{session_id}/npcs").json()
        custom_friend = next(
            npc for npc in npcs if npc["state"]["name"] == "艾薇·摩尔"
        )
        assert custom_friend["is_original_character"] is False

        relationships = client.get(
            f"/api/sessions/{session_id}/relationships"
        ).json()
        friends = {
            relationship["target_id"]: relationship
            for relationship in relationships
            if relationship["state"]["stage"] == "friend"
        }
        assert friends["harry_potter"]["state"]["affinity"] == 20
        assert friends["hermione_granger"]["state"]["trust"] == 10
        assert friends[custom_friend["npc_id"]]["state"]["affinity"] == 20


def test_action_applies_rules_and_is_idempotent(monkeypatch) -> None:
    captured_messages = []

    async def fake_completion(self, messages):
        captured_messages.extend(messages)
        if "attribute_initialization" in messages[0]["content"]:
            return {
                "choices": [{
                    "message": {
                        "content": """{
                          "response_type": "attribute_initialization",
                          "schema_version": "1.2",
                          "resources": [
                            {"id": "health", "value": 100, "max": 100, "reason": "稳定"},
                            {"id": "mana", "value": 100, "max": 100, "reason": "稳定"},
                            {"id": "sanity", "value": 100, "max": 100, "reason": "稳定"},
                            {"id": "energy", "value": 100, "max": 100, "reason": "充足"},
                            {"id": "satiety", "value": 100, "max": 100, "reason": "正常"}
                          ],
                          "dimensions": [
                            {"id": "constitution", "value": 10, "max": 20, "reason": "普通"},
                            {"id": "intelligence", "value": 10, "max": 20, "reason": "普通"},
                            {"id": "willpower", "value": 10, "max": 20, "reason": "普通"},
                            {"id": "charisma", "value": 10, "max": 20, "reason": "普通"},
                            {"id": "magical_power", "value": 10, "max": 20, "reason": "普通"}
                          ],
                          "calibration_summary": "初始属性已生成",
                          "self_check": {}
                        }"""
                    }
                }]
            }
        prompt_context = json.loads(messages[1]["content"].split("\n", 1)[1])
        if prompt_context["player_action"]["kind"] == "reshape_fate":
            return {
                "choices": [{
                    "message": {
                        "content": """{
                          "response_type": "narrative",
                          "turn": {
                            "title": "重塑后的迟到来信",
                            "scene_type": "encounter",
                            "narrative": "这一次，羽毛笔让窗外的翅膀声停在了更远的雾里。",
                            "current_date": "1991-06-30",
                            "location_id": "home"
                          },
                          "choices": [
                            {
                              "id": "listen",
                              "label": "屏息听向窗外",
                              "kind": "action",
                              "risk": "low"
                            },
                            {
                              "id": "choice_other",
                              "label": "其他",
                              "kind": "free_text",
                              "risk": "low"
                            }
                          ],
                          "player_changes": {
                            "inventory_add": [
                              {
                                "item_id": "rewritten_note",
                                "name": "重写后的便笺",
                                "description": "只在重塑版本中成立的物品",
                                "quantity": 1
                              }
                            ],
                            "resource_deltas": [
                              {
                                "id": "mana",
                                "delta": -4,
                                "reason_code": "spell_cost",
                                "reason": "重塑版本中的微弱魔法回响"
                              }
                            ]
                          },
                          "state_proposals": {},
                          "worldline": {
                            "offset_rate": 0,
                            "delta": 0,
                            "reason": "重塑后的节点保持原有世界线",
                            "affected_nodes": []
                          },
                          "memory_update": {
                            "summary": "",
                            "create_long_term_memory": false,
                            "resolved_memory_ids": []
                          }
                        }"""
                    }
                }]
            }
        return {
            "choices": [
                {
                    "message": {
                        "content": """{
                          "response_type": "narrative",
                          "turn": {
                            "title": "一封迟到的信",
                            "scene_type": "encounter",
                            "narrative": "窗外传来翅膀拍打玻璃的声音。",
                            "current_date": "1991-06-30",
                            "location_id": "home"
                          },
                          "choices": [
                            {
                              "id": "open_letter",
                              "label": "打开信封",
                              "kind": "action",
                              "risk": "low",
                              "effects": {
                                "gains": [
                                  {
                                    "id": "hogwarts_letter",
                                    "name": "霍格沃兹来信",
                                    "type": "item",
                                    "direction": "gain",
                                    "description": "一封改变人生的来信"
                                  },
                                  {
                                    "id": "spell_practice",
                                    "name": "魔咒熟练",
                                    "type": "trait",
                                    "direction": "gain",
                                    "description": "魔咒练习带来的正面词条"
                                  }
                                ],
                                "losses": []
                              }
                            },
                            {
                              "id": "choice_other",
                              "label": "其他",
                              "kind": "free_text",
                              "risk": "low"
                            }
                          ],
                          "state_proposals": {
                            "dimension_deltas": [
                              {
                                "id": "willpower",
                                "delta": 1,
                                "reason_code": "overcome_fear",
                                "reason": "在恐惧中保持清醒"
                              }
                            ],
                                "relationship_deltas": [
                              {
                                "npc_id": "hermione_granger",
                                "affinity_delta": 4,
                                "reason": "玩家在危机中保护了赫敏",
                                "evidence": "本轮叙事记录了两人的明确互动"
                                  }
                                ],
                                "reputation_deltas": {
                                  "score": 4
                                }
                          },
                          "player_changes": {
                            "inventory_add": [
                              {
                                "item_id": "hogwarts_letter",
                                "name": "霍格沃兹来信",
                                "description": "一封改变人生的来信",
                                "quantity": 1
                              }
                            ],
                            "status_add": [
                              {
                                "id": "excited",
                                "name": "期待",
                                "description": "对即将到来的魔法生活充满期待",
                                "severity": "normal"
                              }
                            ],
                            "skill_add": [
                              {
                                "id": "spellcasting",
                                "name": "魔咒",
                                "description": "使用基础魔咒的能力",
                                "level": 1
                              }
                            ],
                            "trait_add": [
                              {
                                "id": "spell_practice",
                                "name": "魔咒熟练",
                                "description": "你在魔咒练习中表现出稳定的专注力。",
                                "polarity": "positive",
                                "reason": "持续练习魔咒"
                              }
                            ],
                            "resource_deltas": [
                              {
                                "id": "mana",
                                "delta": -8,
                                "reason_code": "spell_cost",
                                "reason": "维持护盾"
                              }
                            ],
                            "dimension_deltas": [
                              {
                                "id": "willpower",
                                "delta": 1,
                                "reason_code": "overcome_fear",
                                "reason": "在恐惧中保持清醒"
                              }
                            ],
                            "relationship_deltas": [
                              {
                                "npc_id": "hermione_granger",
                                "affinity_delta": 4,
                                "reason": "玩家在危机中保护了赫敏",
                                "evidence": "本轮叙事记录了两人的明确互动"
                              }
                            ],
                            "reputation_deltas": {
                              "score": 4
                            }
                          },
                          "worldline": {
                            "offset_rate": 3.5,
                            "delta": 3.5,
                            "reason": "玩家开始介入故事",
                            "affected_nodes": []
                          },
                          "memory_update": {
                            "summary": "玩家收到了一封神秘来信。",
                            "create_long_term_memory": false,
                            "resolved_memory_ids": []
                          }
                        }""",
                    }
                }
            ]
        }

    monkeypatch.setattr(OpenAICompatibleProvider, "chat_completion", fake_completion)
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "回合规则测试"},
        ).json()
        session_id = created["id"]
        for step in range(1, 18):
            client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={
                    "step": step,
                    "answer": (
                            "second_generation"
                            if step == 1
                            else "1980-03-12"
                            if step == 4
                            else "before_first_letter"
                            if step == 14
                            else "gryffindor"
                        if step == 15
                        else f"answer-{step}"
                    ),
                },
            )
        confirmed = client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["attribute_initialization"]["status"] == "ready"
        with get_session_factory()() as db:
            player_state = db.scalar(
                select(PlayerState).where(PlayerState.session_id == session_id)
            )
            assert player_state is not None
            state = json.loads(json.dumps(player_state.state, ensure_ascii=False))
            state["current_context"] = {
                **state.get("current_context", {}),
                "current_date": "1991-05-31",
                "datetime": "1991-05-31T09:00:00+00:00",
                "location_id": "home",
            }
            state["school"] = {
                **state.get("school", {}),
                "grade": "year_1",
                "active_courses": ["charms"],
                "school_year": "1991-1992",
                "term": "spring",
                "course_history": [],
            }
            state["skills"] = {
                "charms": {
                    "id": "charms",
                    "name": "咒语",
                    "description": "学习施放、控制和组合各种实用咒语。",
                    "level": 2,
                    "experience": 0,
                    "source": "course",
                    "course_id": "charms",
                    "course_skill": True,
                }
            }
            player_state.state = state
            db.commit()
        current_detail = client.get(f"/api/sessions/{session_id}").json()
        assert current_detail["status"] == "active", current_detail
        assert current_detail["player_state"]["attribute_initialization"]["status"] == "ready", current_detail
        baseline_state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        baseline_relationships = {
            item["target_id"]: item["state"]
            for item in client.get(
                f"/api/sessions/{session_id}/relationships"
            ).json()
        }
        action = {
            "client_action_id": f"fixed-action-id-{session_id}",
            "expected_state_version": 1,
            "kind": "choice",
            "choice_id": "start_story",
        }
        result = client.post(f"/api/sessions/{session_id}/actions", json=action)
        assert result.status_code == 200, result.text
        assert result.json()["state_version"] == 2
        assert result.json()["response"]["worldline"]["offset_rate"] == 3.5
        assert result.json()["response"]["applied_changes"]["trait_add"][0]["name"] == "魔咒熟练"
        assert result.json()["response"]["applied_changes"]["resource_deltas"][0]["id"] == "mana"
        assert result.json()["response"]["applied_changes"]["dimension_deltas"][0]["id"] == "willpower"
        assert result.json()["response"]["choices"][0]["effects"]["gains"][0]["name"] == "霍格沃兹来信"
        prompt_context = captured_messages[-1]["content"]
        assert '"generation_mainline"' in prompt_context
        assert "霍格沃茨之战" in prompt_context

        repeated = client.post(f"/api/sessions/{session_id}/actions", json=action)
        assert repeated.status_code == 200
        assert repeated.json()["turn_id"] == result.json()["turn_id"]

        reshape = {
            "client_action_id": f"reshape-action-id-{session_id}",
            "expected_state_version": 2,
            "kind": "reshape_fate",
            "reshape_instruction": "让这封信的到来更有悬念，不要重复原节点的状态变化。",
        }
        reshaped = client.post(
            f"/api/sessions/{session_id}/actions",
            json=reshape,
        )
        assert reshaped.status_code == 200, reshaped.text
        assert reshaped.json()["state_version"] == 3
        assert reshaped.json()["response"]["turn"]["title"] == "重塑后的迟到来信"
        assert reshaped.json()["response"]["applied_changes"]["inventory_add"][0]["item_id"] == "rewritten_note"
        assert reshaped.json()["response"]["applied_changes"]["resource_deltas"][0]["delta"] == -4
        assert reshaped.json()["response"]["applied_changes"]["skill_add"] == []
        assert reshaped.json()["response"]["applied_changes"]["course_skill_deltas"]["charms"] == 1
        assert reshaped.json()["response"]["applied_changes"]["relationship_deltas"] == []
        reshaped_state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        for key in ("dimensions", "statuses", "traits", "reputation"):
            assert reshaped_state[key] == baseline_state[key], key
        assert reshaped_state["resources"]["mana"]["value"] == baseline_state["resources"]["mana"]["value"] - 4
        assert [item["item_id"] for item in reshaped_state["inventory"]] == ["rewritten_note"]
        assert reshaped_state["skills"]["charms"]["level"] == baseline_state["skills"]["charms"]["level"] + 1
        assert "spellcasting" not in reshaped_state["skills"]
        assert reshaped_state["school"]["last_course_progression_year"] == 1991
        assert len(reshaped_state["school"]["course_history"]) == 1
        assert reshaped_state["worldline"]["offset_rate"] == baseline_state["worldline"]["offset_rate"]
        reshaped_relationships = {
            item["target_id"]: item["state"]
            for item in client.get(
                f"/api/sessions/{session_id}/relationships"
            ).json()
        }
        for target_id, baseline_relationship in baseline_relationships.items():
            for key in ("affinity", "trust", "stage", "romance_stage"):
                assert reshaped_relationships[target_id][key] == baseline_relationship[key], (
                    target_id,
                    key,
                )
        turns = client.get(f"/api/sessions/{session_id}/turns").json()
        assert len(turns) == 1
        assert turns[0]["id"] == result.json()["turn_id"]
        assert turns[0]["sequence"] == 1
        assert turns[0]["response"]["turn"]["title"] == "重塑后的迟到来信"
        journal = client.get(f"/api/sessions/{session_id}/journal").json()
        assert len(journal) == 1
        assert journal[0]["title"] == "重塑后的迟到来信"
        reshape_prompt_context = captured_messages[-1]["content"]
        assert '"kind": "reshape_fate"' in reshape_prompt_context
        assert "不要重复原节点的状态变化" in reshape_prompt_context

        reshaped_retry = client.post(
            f"/api/sessions/{session_id}/actions",
            json=reshape,
        )
        assert reshaped_retry.status_code == 200
        assert reshaped_retry.json()["turn_id"] == reshaped.json()["turn_id"]
        assert reshaped_retry.json()["state_version"] == 3
        retry_state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert retry_state["resources"]["mana"]["value"] == baseline_state["resources"]["mana"]["value"] - 4
        assert [item["item_id"] for item in retry_state["inventory"]] == ["rewritten_note"]
        assert retry_state["skills"]["charms"]["level"] == baseline_state["skills"]["charms"]["level"] + 1
        assert len(retry_state["school"]["course_history"]) == 1

        fate_action = {
            "client_action_id": f"fate-action-id-{session_id}",
            "expected_state_version": 3,
            "kind": "fate_intervention",
            "fate_instruction": "下一幕让无名书出现在禁书区，并让赫敏发现它。",
        }
        fate_result = client.post(
            f"/api/sessions/{session_id}/actions",
            json=fate_action,
        )
        assert fate_result.status_code == 200, fate_result.text
        assert fate_result.json()["state_version"] == 4
        fate_prompt_context = captured_messages[-1]["content"]
        assert '"kind": "fate_intervention"' in fate_prompt_context
        assert "无名书出现在禁书区" in fate_prompt_context
        recorded_turns = client.get(f"/api/sessions/{session_id}/turns")
        assert recorded_turns.status_code == 200
        assert recorded_turns.json()[-1]["action"]["kind"] == "fate_intervention"

        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["dimensions"]["willpower"]["value"] == 11
        assert state["resources"]["mana"]["value"] == 88
        assert state["current_context"]["current_date"] == "1991-06-30"
        assert state["current_context"]["datetime"].startswith("1991-06-30T09:00:00")
        assert {item["item_id"] for item in state["inventory"]} == {
            "rewritten_note",
            "hogwarts_letter",
        }
        assert state["statuses"][0]["id"] == "excited"
        assert state["skills"]["spellcasting"]["name"] == "魔咒"
        assert state["skills"]["charms"]["level"] == 3
        assert len(state["school"]["course_history"]) == 1
        assert state["traits"][0]["description"] == "你在魔咒练习中表现出稳定的专注力。"
