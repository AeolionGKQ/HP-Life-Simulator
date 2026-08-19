from fastapi.testclient import TestClient

from backend.app.providers.openai_compatible import OpenAICompatibleProvider
from backend.app.main import create_app


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


def test_setup_materializes_npcs_and_state() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/sessions",
            json={"name": "完整流程测试"},
        ).json()
        session_id = created["id"]
        for step in range(1, 13):
            response = client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": f"answer-{step}"},
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
        assert state.json()["state"]["identity"]["name"] == "answer-2"

        npcs = client.get(f"/api/sessions/{session_id}/npcs")
        relationships = client.get(f"/api/sessions/{session_id}/relationships")
        assert npcs.status_code == 200
        assert relationships.status_code == 200
        assert len(npcs.json()) >= 9
        assert len(relationships.json()) >= 9


def test_action_applies_rules_and_is_idempotent(monkeypatch) -> None:
    async def fake_completion(self, messages):
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
                            "location_id": "home",
                            "time_advance_minutes": 15
                          },
                          "choices": [
                            {
                              "id": "open_letter",
                              "label": "打开信封",
                              "kind": "action",
                              "risk": "low"
                            },
                            {
                              "id": "choice_other",
                              "label": "其他",
                              "kind": "free_text",
                              "risk": "unknown"
                            }
                          ],
                          "state_proposals": {
                            "attribute_deltas": {"courage": 1},
                            "relationship_deltas": [
                              {
                                "npc_id": "hermione_granger",
                                "affinity_delta": 4
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
        for step in range(1, 13):
            client.post(
                f"/api/sessions/{session_id}/setup/answer",
                json={"step": step, "answer": f"answer-{step}"},
            )
        client.post(
            f"/api/sessions/{session_id}/setup/confirm",
            json={"confirmed": True},
        )
        action = {
            "client_action_id": f"fixed-action-id-{session_id}",
            "expected_state_version": 1,
            "kind": "choice",
            "choice_id": "start_story",
        }
        result = client.post(f"/api/sessions/{session_id}/actions", json=action)
        assert result.status_code == 200
        assert result.json()["state_version"] == 2
        assert result.json()["response"]["worldline"]["offset_rate"] == 3.5

        repeated = client.post(f"/api/sessions/{session_id}/actions", json=action)
        assert repeated.status_code == 200
        assert repeated.json()["turn_id"] == result.json()["turn_id"]

        state = client.get(f"/api/sessions/{session_id}/state").json()["state"]
        assert state["attributes"]["courage"] == 1
        assert state["current_context"]["datetime"].endswith("09:15:00+00:00")
