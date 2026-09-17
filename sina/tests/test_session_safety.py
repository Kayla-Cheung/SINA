"""
SessionManager 安全性与并发回归测试。

覆盖:
- #34 game_id 路径穿越（任意 .json 读取 / 删除）。
- #33 step 循环内反复解引用 self.current，与 create_game/abandon 的会话替换竞态。
"""

import asyncio
from datetime import datetime

import pytest

from core.game_session import GameSession, SessionManager, _save_path, saves_dir


# --------------------------------------------------------------------------
# #34 — 路径穿越
# --------------------------------------------------------------------------

@pytest.fixture
def isolated_data_dir(monkeypatch, tmp_path):
    """把 SINA_DATA_DIR 指向临时目录，避免污染仓库 data/saves。"""
    monkeypatch.setenv("SINA_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("bad_id", [
    "../secret",              # 正向穿越
    "..\\secret",             # Windows 反斜杠穿越
    "../../etc/passwd",
    "a/b",
    "/etc/passwd",
    "..",
    "",
    "x.json",                 # 点号不在白名单内
    "a" * 65,                 # 超长
    "has space",
])
def test_save_path_rejects_unsafe_ids(isolated_data_dir, bad_id):
    with pytest.raises(ValueError):
        _save_path(bad_id)
    with pytest.raises(ValueError):
        _save_path(bad_id, ".memories.db")


def test_save_path_accepts_generated_ids(isolated_data_dir):
    path = _save_path("smallville-ab12cd34")

    assert path.parent == saves_dir().resolve()
    assert path.name == "smallville-ab12cd34.json"


def test_download_save_cannot_escape_saves_dir(isolated_data_dir):
    secret = isolated_data_dir / "secret.json"
    secret.write_text('{"game_id": "secret", "state": {"frame": 999}}', encoding="utf-8")

    mgr = SessionManager()

    with pytest.raises(ValueError):
        mgr.download_save("../secret")
    with pytest.raises(ValueError):
        mgr.download_save("..\\secret")
    assert secret.exists(), "秘密文件不应被读取/删除"


def test_delete_save_cannot_delete_outside_saves_dir(isolated_data_dir):
    victim = isolated_data_dir / "victim.json"
    victim.write_text("{}", encoding="utf-8")

    mgr = SessionManager()

    with pytest.raises(ValueError):
        asyncio.run(mgr.delete_save("../victim"))
    assert victim.exists(), "保存目录之外的文件必须原封不动"


# --------------------------------------------------------------------------
# #33 — 会话替换竞态
# --------------------------------------------------------------------------

class _FakeSim:
    """只实现 run_dag_loop / append_frame_log 所需字段的最小 sim。"""

    def __init__(self):
        self.tick_count = 0
        self.current_logs = []
        self.clock = datetime(2026, 1, 1, 6, 0)

    async def run_dag_loop(self, ticks: int = 1):
        self.tick_count += ticks
        self.current_logs = [f"tick {self.tick_count}"]


@pytest.fixture
def manager(isolated_data_dir, monkeypatch):
    # 隔离落盘与快照的繁重依赖，只考察 step 的会话引用行为。
    monkeypatch.setattr(GameSession, "persist", lambda self: None)
    monkeypatch.setattr(GameSession, "snapshot", lambda self: {"frame": self.sim.tick_count})
    return SessionManager()


def test_step_keeps_using_original_session_when_current_is_swapped(manager):
    """帧中途替换 self.current，不得把后续帧写进新会话。"""
    original = GameSession(_FakeSim(), "game-a")
    manager.current = original

    async def swap_on_frame(_state):
        manager.current = GameSession(_FakeSim(), "game-b")

    asyncio.run(manager.step("game-a", steps=3, on_frame=swap_on_frame))

    assert original.sim.tick_count == 3, "原会话应完整跑完 3 帧"
    assert manager.current.game_id == "game-b"
    assert manager.current.sim.tick_count == 0, "新会话不应被旧 step 推进"
    assert [e["frame"] for e in original.logs] == [1, 2, 3]


def test_step_survives_session_abandoned_mid_run(manager):
    """帧中途把会话置空，后续帧不应 AttributeError。"""
    original = GameSession(_FakeSim(), "game-a")
    manager.current = original

    async def abandon_on_frame(_state):
        manager.current = None

    asyncio.run(manager.step("game-a", steps=2, on_frame=abandon_on_frame))

    assert original.sim.tick_count == 2


def test_step_rejects_unknown_game_id(manager):
    manager.current = GameSession(_FakeSim(), "game-a")

    with pytest.raises(KeyError):
        asyncio.run(manager.step("game-b", steps=1))


def test_mutations_are_serialised_behind_the_step_lock(manager):
    """create/abandon 等改动会话的操作都必须是协程，才能与 step 共用同一把锁。"""
    for name in ("create_game", "abandon", "continue_save", "import_save", "delete_save", "clear_saves"):
        assert asyncio.iscoroutinefunction(getattr(manager, name)), f"{name} 应为 async"
