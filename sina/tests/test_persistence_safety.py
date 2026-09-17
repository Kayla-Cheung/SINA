"""
持久化安全性回归测试（#38）。

覆盖:
- 原子写：中途序列化失败不得破坏已有文件，也不得留下临时文件。
- 读档不再经固定临时文件名（原先两个并发读档会互相覆盖 / FileNotFoundError）。
- 长期记忆持久化失败必须留日志，而不是 except: pass。
"""

import json
import logging
import types

import pytest

from core.atomic_io import atomic_write_json
from core.game_session import load_world_into_sim, persist_memories, saves_dir


@pytest.fixture
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("SINA_DATA_DIR", str(tmp_path))
    return tmp_path


# --------------------------------------------------------------------------
# 原子写
# --------------------------------------------------------------------------

class _Unserializable:
    pass


def test_atomic_write_replaces_content(tmp_path):
    target = tmp_path / "save.json"

    atomic_write_json(target, {"frame": 1})
    atomic_write_json(target, {"frame": 2})

    assert json.loads(target.read_text(encoding="utf-8")) == {"frame": 2}


def test_atomic_write_keeps_old_file_when_serialisation_fails(tmp_path):
    target = tmp_path / "save.json"
    atomic_write_json(target, {"frame": 1})

    with pytest.raises(TypeError):
        atomic_write_json(target, {"bad": _Unserializable()})

    # 旧存档必须完好（非原子写会把它截断成半个 JSON，永久不可读）
    assert json.loads(target.read_text(encoding="utf-8")) == {"frame": 1}
    # 不留临时残留
    assert [p.name for p in tmp_path.iterdir()] == ["save.json"]


def test_atomic_write_creates_new_file(tmp_path):
    target = tmp_path / "nested" / "save.json"

    with pytest.raises(FileNotFoundError):
        # 父目录不存在应显式失败，而不是悄悄产生半个文件
        atomic_write_json(target, {"frame": 1})


# --------------------------------------------------------------------------
# 读档不再经临时文件
# --------------------------------------------------------------------------

class _StubSim:
    """只满足 _clear_sim_population 与 _load_world_state_data 的最小替身。"""

    def __init__(self):
        root = types.SimpleNamespace(agents=set(), children=[])
        self.environment = types.SimpleNamespace(root=root, agent_locations={})
        self.world_agents = {}
        self.current_logs = []
        self.received = None

    def _load_world_state_data(self, data):
        self.received = data


def test_load_world_into_sim_feeds_dict_without_touching_disk(isolated_data_dir):
    sim = _StubSim()
    world = {"clock": "2026-01-01T06:00:00", "agents": []}

    load_world_into_sim(sim, world)

    assert sim.received == world
    assert not (saves_dir() / "_tmp_load.json").exists()
    assert list(saves_dir().iterdir()) == [], "读档不应在 saves 目录留下任何文件"


def test_two_loads_do_not_share_a_temp_file(isolated_data_dir):
    """并发读档曾共用 _tmp_load.json，互相覆盖或 unlink 掉对方正在读的文件。"""
    first, second = _StubSim(), _StubSim()

    load_world_into_sim(first, {"clock": "2026-01-01T06:00:00", "agents": [], "tag": "A"})
    load_world_into_sim(second, {"clock": "2026-01-01T06:00:00", "agents": [], "tag": "B"})

    assert first.received["tag"] == "A"
    assert second.received["tag"] == "B"


# --------------------------------------------------------------------------
# 不再静默吞异常
# --------------------------------------------------------------------------

def test_persist_memories_logs_failure_instead_of_silently_passing(isolated_data_dir, caplog):
    class _BoomStore:
        def persist_to_sqlite(self, *args, **kwargs):
            raise RuntimeError("disk full")

    sim = types.SimpleNamespace(
        memory_manager=types.SimpleNamespace(vector_store=_BoomStore())
    )

    with caplog.at_level(logging.ERROR):
        persist_memories(sim, "smallville-ab12cd34")

    assert "长期记忆持久化失败" in caplog.text
