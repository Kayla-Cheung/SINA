"""
测试隔离与观察器误删回归测试（#28）。

覆盖:
- SinaSimulation 的输出路径跟随 SINA_DATA_DIR，不再写穿仓库工作区。
- 观察器 promise 清理时只删除带 sina_managed 标记的自有笔记，不得碰用户自建笔记。
"""

from pathlib import Path

import pytest

from core.dag_simulation import SinaSimulation
from sina.observer.obsidian_vault import MANAGED_MARKER, ObsidianVaultObserver


# --------------------------------------------------------------------------
# 输出路径可注入
# --------------------------------------------------------------------------

def test_simulation_paths_follow_sina_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SINA_DATA_DIR", str(tmp_path))

    sim = SinaSimulation(world_name="smallville", resume=False)

    assert Path(sim.save_file) == tmp_path / "world_state_v3_backup.json"
    assert Path(sim.observer.vault_dir) == (tmp_path / "obsidian_vault").resolve()


def test_save_world_state_writes_under_sina_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SINA_DATA_DIR", str(tmp_path))
    sim = SinaSimulation(world_name="smallville", resume=False)

    sim.save_world_state()

    assert (tmp_path / "world_state_v3_backup.json").exists()


# --------------------------------------------------------------------------
# 观察器只清理自己的笔记
# --------------------------------------------------------------------------

class _Node:
    def __init__(self, name):
        self.name = name
        self.agents = set()
        self.inventory = {}
        self.children = []
        self.parent = None


class _Env:
    def __init__(self, nodes):
        self._nodes = nodes
        self.agent_locations = {}

    def all_nodes(self):
        return self._nodes


class _Sim:
    def __init__(self, nodes):
        self.environment = _Env(nodes)
        self.world_agents = {}
        self.tick_count = 1


def test_generated_notes_carry_managed_marker(tmp_path):
    observer = ObsidianVaultObserver(vault_dir=str(tmp_path), macro_only=True)

    observer._sync_rooms(_Sim([_Node("Cafe")]))

    written = (tmp_path / "Rooms" / "Cafe.md").read_text(encoding="utf-8")
    assert MANAGED_MARKER in written


def test_stale_cleanup_spares_unmanaged_notes(tmp_path):
    rooms = tmp_path / "Rooms"
    rooms.mkdir(parents=True)
    # 用户自建的笔记（无标记）
    (rooms / "我的日记.md").write_text("# 今天天气不错\n", encoding="utf-8")
    # 旧版本观察器留下的、没有标记的文件
    (rooms / "OldRoom.md").write_text("type: room\nroom_name: OldRoom\n", encoding="utf-8")
    # 本观察器生成的、当前世界已不存在的过期笔记
    (rooms / "Ghost.md").write_text(
        f"---\ntype: room\n{MANAGED_MARKER}\nroom_name: Ghost\n---\n", encoding="utf-8"
    )

    observer = ObsidianVaultObserver(vault_dir=str(tmp_path), macro_only=True)
    observer._sync_rooms(_Sim([_Node("Cafe")]))

    assert (rooms / "我的日记.md").exists(), "用户自建笔记必须保留"
    assert (rooms / "OldRoom.md").exists(), "无标记的文件不应被删"
    assert not (rooms / "Ghost.md").exists(), "带标记的过期笔记应被清理"
    assert (rooms / "Cafe.md").exists()


def test_macro_prune_spares_unmanaged_micro_notes(tmp_path):
    items = tmp_path / "Items"
    items.mkdir(parents=True)
    (items / "用户清单.md").write_text("- 牛奶\n", encoding="utf-8")
    (items / "Stale.md").write_text(
        f"---\ntype: item\n{MANAGED_MARKER}\nitem_tag: Stale\n---\n", encoding="utf-8"
    )

    ObsidianVaultObserver(vault_dir=str(tmp_path), macro_only=True)

    assert (items / "用户清单.md").exists()
    assert not (items / "Stale.md").exists()


def test_user_vault_note_survives_a_real_room_sync(tmp_path):
    """端到端：把 vault_dir 指向"用户库"，同步若干次后用户笔记仍在。"""
    (tmp_path / "用户笔记.md").write_text("不要删我\n", encoding="utf-8")
    observer = ObsidianVaultObserver(vault_dir=str(tmp_path), macro_only=True)
    sim = _Sim([_Node("Cafe"), _Node("Park")])

    for _ in range(3):
        observer._sync_rooms(sim)

    assert (tmp_path / "用户笔记.md").read_text(encoding="utf-8") == "不要删我\n"
