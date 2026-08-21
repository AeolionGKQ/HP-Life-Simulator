from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from backend.app.db.session import get_session_factory
from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.main import create_app
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


def test_starting_point_accepts_only_predefined_story_nodes() -> None:
    with TestClient(create_app()) as client:
        created = client.post("/api/sessions", json={"name": "预设起点测试"})
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

        custom = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 14, "answer": "我想从密室开启故事"},
        )
        assert custom.status_code == 409
        assert "预设节点" in custom.json()["detail"]

        selected = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 14, "answer": "sorting_ceremony"},
        )
        assert selected.status_code == 200
        assert selected.json()["answers"]["14"] == "sorting_ceremony"


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
        invalid_birthday = client.post(
            f"/api/sessions/{session_id}/setup/answer",
            json={"step": 4, "answer": "三月十二日"},
        )
        assert invalid_birthday.status_code == 409
        assert invalid_birthday.json()["detail"] == "请选择有效的生日日期"


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
                            "current_date": "1991-07-01",
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
                            ]
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
                            ]
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
        current_detail = client.get(f"/api/sessions/{session_id}").json()
        assert current_detail["status"] == "active", current_detail
        assert current_detail["player_state"]["attribute_initialization"]["status"] == "ready", current_detail
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

        fate_action = {
            "client_action_id": f"fate-action-id-{session_id}",
            "expected_state_version": 2,
            "kind": "fate_intervention",
            "fate_instruction": "下一幕让无名书出现在禁书区，并让赫敏发现它。",
        }
        fate_result = client.post(
            f"/api/sessions/{session_id}/actions",
            json=fate_action,
        )
        assert fate_result.status_code == 200, fate_result.text
        assert fate_result.json()["state_version"] == 3
        fate_prompt_context = captured_messages[-1]["content"]
        assert '"kind": "fate_intervention"' in fate_prompt_context
        assert "无名书出现在禁书区" in fate_prompt_context
        recorded_turns = client.get(f"/api/sessions/{session_id}/turns")
        assert recorded_turns.status_code == 200
        assert recorded_turns.json()[-1]["action"]["kind"] == "fate_intervention"

        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["dimensions"]["willpower"]["value"] == 12
        assert state["resources"]["mana"]["value"] == 84
        assert state["current_context"]["current_date"] == "1991-07-01"
        assert state["current_context"]["datetime"].startswith("1991-07-01T09:00:00")
        assert state["inventory"][0]["item_id"] == "hogwarts_letter"
        assert state["statuses"][0]["id"] == "excited"
        assert state["skills"]["spellcasting"]["name"] == "魔咒"
        assert state["traits"][0]["description"] == "你在魔咒练习中表现出稳定的专注力。"
