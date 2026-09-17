"""
HTTP contract tests for the dashboard API.
Mocks LLM calls so the DAG tick path does not hit the network.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

import pytest

FAKE_ACTION = {
    "internal_thought": "mock thought",
    "observable_action": "站在原地观察小镇",
    "duration_minutes": 15,
    "action_type": "idle",
    "move_to": None,
    "eat_item": None,
    "attack_target": None,
    "craft": None,
    "take_item_tag": None,
    "give_item": None,
    "drop_item_tag": None,
    "produce_item_tag": None,
    "propose_blueprint": None,
    "vote_on_blueprint": None,
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SINA_DATA_DIR", str(tmp_path))

    async def mock_determine_next_action(**kwargs):
        return dict(FAKE_ACTION)

    monkeypatch.setattr("core.dag_simulation.determine_next_action", mock_determine_next_action)

    from core.game_session import reset_manager
    reset_manager()

    from core.server import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    reset_manager()


def test_current_game_starts_empty(client):
    resp = client.get("/api/games/current")
    assert resp.status_code == 200
    body = resp.json()
    assert body["game_id"] is None
    assert body["state"] is None


def test_template_is_populated(client):
    resp = client.get("/api/templates/initial")
    assert resp.status_code == 200
    body = resp.json()
    assert body["map"]["locations"]
    assert body["map"]["edges"]
    assert len(body["agents"]) >= 1
    names = {a["name"] for a in body["agents"]}
    assert "Isabella" in names


def _create(client):
    template = client.get("/api/templates/initial").json()
    resp = client.post("/api/games", json={
        "map_config": template["map"],
        "agent_configs": template["agents"],
        "object_configs": template["objects"],
        "start_time": "08:00",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_create_step_and_get_state(client):
    created = _create(client)
    game_id = created["game_id"]
    state = created["state"]
    assert state["agents"]
    assert state["map"]["locations"]
    assert state["map"]["edges"]
    assert state["game_time"] == "08:00"
    frame0 = state["frame"]

    current = client.get("/api/games/current").json()
    assert current["game_id"] == game_id

    got = client.get(f"/api/games/{game_id}")
    assert got.status_code == 200
    assert got.json()["game_id"] == game_id

    stepped = client.post(f"/api/games/{game_id}/step", json={"steps": 1})
    assert stepped.status_code == 200, stepped.text
    body = stepped.json()
    assert body["frames_executed"] == 1
    assert body["results"]

    after = client.get(f"/api/games/{game_id}").json()
    assert after["frame"] > frame0
    assert after["agents"]
    assert after["map"]["locations"]


def test_saves_continue_delete_download_clear(client):
    created = _create(client)
    game_id = created["game_id"]
    client.post(f"/api/games/{game_id}/step", json={"steps": 1})

    listed = client.get("/api/saves").json()
    assert "saves" in listed
    ids = {s["game_id"] for s in listed["saves"]}
    assert game_id in ids

    downloaded = client.get(f"/api/saves/{game_id}/download")
    assert downloaded.status_code == 200
    payload = downloaded.json()
    assert payload["game_id"] == game_id
    assert "world" in payload
    assert payload.get("state", {}).get("frame", 0) >= 1

    client.post("/api/games/abandon")
    assert client.get("/api/games/current").json()["game_id"] is None

    continued = client.post(f"/api/saves/{game_id}/continue")
    assert continued.status_code == 200, continued.text
    assert continued.json()["game_id"] == game_id
    assert continued.json()["state"]["agents"]

    imported = client.post("/api/saves/import", json=payload)
    assert imported.status_code == 200, imported.text
    imported_id = imported.json()["game_id"]

    deleted = client.delete(f"/api/saves/{imported_id}")
    assert deleted.status_code == 200
    assert client.delete(f"/api/saves/{imported_id}").status_code == 404

    cleared = client.post("/api/saves/clear")
    assert cleared.status_code == 200
    assert client.get("/api/saves").json()["saves"] == []


def test_llm_config_roundtrip_masks_key(client):
    posted = client.post("/api/config/llm", json={
        "base_url": "https://example.invalid/v1",
        "api_key": "sk-test-secret-key-1234",
        "model": "unit-test-model",
        "embedding_model": "unit-embed",
        "embedding_provider": "openai",
        "thinking_enabled": False,
    })
    assert posted.status_code == 200, posted.text
    cfg = posted.json()["config"]
    assert cfg["model"] == "unit-test-model"
    assert cfg["base_url"] == "https://example.invalid/v1"
    assert "sk-test-secret-key-1234" not in posted.text

    fetched = client.get("/api/config/llm")
    assert fetched.status_code == 200
    got = fetched.json()["config"]
    assert got["model"] == "unit-test-model"
    assert got["base_url"] == "https://example.invalid/v1"
    assert "sk-test-secret-key-1234" not in fetched.text
    assert got.get("has_api_key") is True


def test_memories_and_prompts_after_step(client):
    created = _create(client)
    game_id = created["game_id"]
    agent_id = created["state"]["agents"][0]["id"]
    client.post(f"/api/games/{game_id}/step", json={"steps": 1})

    mem = client.get(f"/api/agents/{agent_id}/memories")
    assert mem.status_code == 200
    body = mem.json()
    assert body["agent_id"] == agent_id
    assert "short_term" in body
    assert "long_term" in body

    prompts = client.get(f"/api/games/{game_id}/prompts", params={"agent_id": agent_id})
    assert prompts.status_code == 200
    pdata = prompts.json()
    assert "prompts" in pdata
    assert isinstance(pdata["prompts"], dict)


def test_missing_routes_are_not_404_for_known_ids(client):
    created = _create(client)
    game_id = created["game_id"]
    assert client.get(f"/api/saves/{game_id}/download").status_code == 200
    assert client.delete("/api/saves/does-not-exist").status_code == 404
    assert client.get("/api/games/does-not-exist").status_code == 404
