"""回归测试：WebSocket 按 game_id 分桶（#49）与 prompt 会话隔离 / frame 语义（#50）。

- ConnectionManager 必须按 game_id 隔离广播，坏连接要被剔除；
- prompt 必须拷贝进会话，换局后不得读到上一局遗留的 prompt；
- record_agent_prompt 不再写入永不落地的 god_* 字段。
"""

import asyncio

import pytest


class _FakeWS:
    def __init__(self):
        self.accepted = False
        self.sent = []
        self.closed = None

    async def accept(self):
        self.accepted = True

    async def send_text(self, message: str):
        self.sent.append(message)

    async def close(self, code: int = 1000):
        self.closed = code


class _BrokenWS(_FakeWS):
    async def send_text(self, message: str):
        raise RuntimeError("connection lost")


# --------------------------------------------------------------------------
# #49 — WebSocket 分桶
# --------------------------------------------------------------------------

def test_broadcast_isolated_by_game_id():
    from core.server import ConnectionManager

    async def run():
        mgr = ConnectionManager()
        ws_a = _FakeWS()
        ws_b = _FakeWS()
        await mgr.connect(ws_a, "game-a")
        await mgr.connect(ws_b, "game-b")

        await mgr.broadcast("game-a", "hello-a")
        assert ws_a.sent == ["hello-a"]
        assert ws_b.sent == [], "B 局的连接不应收到 A 局的帧"

        await mgr.broadcast("game-b", "hello-b")
        assert ws_b.sent == ["hello-b"]

    asyncio.run(run())


def test_broadcast_prunes_broken_connection():
    from core.server import ConnectionManager

    async def run():
        mgr = ConnectionManager()
        good = _FakeWS()
        bad = _BrokenWS()
        await mgr.connect(good, "game")
        await mgr.connect(bad, "game")

        await mgr.broadcast("game", "first")
        assert good.sent == ["first"], "坏连接不应阻塞好连接收帧"
        await mgr.broadcast("game", "second")
        assert good.sent == ["first", "second"], "坏连接应在首次失败后被剔除"

    asyncio.run(run())


# --------------------------------------------------------------------------
# #50 — prompt 会话隔离 / frame 语义
# --------------------------------------------------------------------------

def test_record_agent_prompt_omits_god_fields():
    from core.gateway import reset_gateway

    gw = reset_gateway()
    gw.record_agent_prompt("Alice", "sys", "user", "raw", "char")
    entry = gw.agent_prompts["Alice"]
    assert entry["system"] == "sys"
    assert entry["character_response"] == "char"
    for field in ("god_kind", "god_reason", "god_raw", "god_tool"):
        assert field not in entry, f"应移除永不落地的 {field} 字段"


def test_capture_prompts_scopes_to_session_agents():
    from core import game_session as gs
    from core.gateway import reset_gateway, get_gateway

    gw = reset_gateway()
    # 上一局遗留的 prompt（同名单例残留）
    gw.agent_prompts["Isabella"] = {
        "system": "stale", "user": "u", "raw_response": "r", "character_response": "c",
    }
    gw.agent_prompts["Bob"] = {
        "system": "fresh", "user": "u", "raw_response": "r", "character_response": "c",
    }

    class FakeSim:
        world_agents = {"Bob": object()}
        tick_count = 7

    session = gs.GameSession(FakeSim(), "game-b")
    session.capture_prompts(frame=7)

    assert "Bob" in session.prompts
    assert "Isabella" not in session.prompts, "上一局的 prompt 不应串进本局"

    mgr = gs.SessionManager()
    mgr.current = session
    data = mgr.agent_prompts("game-b", agent_id="Bob")
    assert data["frame"] == 7, "frame 应为 prompt 被捕获的 tick，而非当前 tick"
    assert data["prompts"]["Bob"]["system"] == "fresh"


# --------------------------------------------------------------------------
# 端到端：换局后 prompt 隔离
# --------------------------------------------------------------------------

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

    async def mock_determine_next_action(state, **kwargs):
        from core.gateway import get_gateway
        get_gateway().record_agent_prompt(
            agent_id=state.name,
            system="sys",
            user="user",
            raw_response="raw",
            character_response="char",
        )
        return dict(FAKE_ACTION)

    monkeypatch.setattr("core.dag_simulation.determine_next_action", mock_determine_next_action)

    from core.game_session import reset_manager
    reset_manager()

    from core.server import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    reset_manager()


def test_prompts_do_not_leak_between_games(client):
    template = client.get("/api/templates/initial").json()
    body = {
        "map_config": template["map"],
        "agent_configs": template["agents"],
        "object_configs": template["objects"],
    }

    resp_a = client.post("/api/games", json={**body, "start_time": "08:00"})
    assert resp_a.status_code == 200, resp_a.text
    game_a = resp_a.json()["game_id"]
    agent_a = resp_a.json()["state"]["agents"][0]["id"]
    assert client.post(f"/api/games/{game_a}/step", json={"steps": 1}).status_code == 200

    pa = client.get(f"/api/games/{game_a}/prompts", params={"agent_id": agent_a}).json()
    assert pa["prompts"].get(agent_a, {}).get("system") == "sys"
    assert pa["frame"] is not None, "step 后 prompt 应带真实捕获帧"

    # 换新局（未 step），不得读到 A 局遗留的 prompt
    client.post("/api/games/abandon")
    resp_b = client.post("/api/games", json={**body, "start_time": "09:00"})
    assert resp_b.status_code == 200, resp_b.text
    game_b = resp_b.json()["game_id"]
    agent_b = resp_b.json()["state"]["agents"][0]["id"]

    pb = client.get(f"/api/games/{game_b}/prompts", params={"agent_id": agent_b}).json()
    assert pb["prompts"] == {}, "新局未 step 不应读到上一局 prompt"
    assert pb["frame"] is None
