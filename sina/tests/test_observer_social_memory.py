"""
观察器社交圈与记忆节点回归测试（#43、#44）。

#43 已知社交圈 known_nearby 全仓库无人写入 → "视野内社交圈"恒为空；
#44 记忆文件名只用 tick 区间 → 同一 tick 多条记忆互相覆盖。
"""

import os

from sina.memory.types import EpisodicMemory
from sina.observer.obsidian_vault import ObsidianVaultObserver


class _Node:
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.children = []
        self.objects = []
        self.agents = []
        self.inventory = {}
        self.locked_by = None


class _Env:
    def __init__(self, nodes):
        self._nodes = nodes
        self.agent_locations = {}

    def all_nodes(self):
        return self._nodes

    def get_node_by_name(self, name):
        for n in self._nodes:
            if n.name == name:
                return n
        return None


class _Agent:
    def __init__(self, name):
        self.name = name
        self.hunger = 30
        self.current_action = "发呆中"
        self.traits = "普通原始人"
        self.is_dead = False
        self.is_comatose = False
        self.inventory = {}
        self.known_nearby = set()
        self.memory_stream = []


class _VecStore:
    def __init__(self, memories):
        self._memories = memories

    def get_agent_memories(self, agent_id):
        return self._memories


class _MM:
    def __init__(self, memories):
        self.vector_store = _VecStore(memories)


def _agent_card(tmp_path, name):
    return os.path.join(tmp_path, "Agents", f"{name}.md")


# --------------------------------------------------------------------------
# #43 视野内社交圈
# --------------------------------------------------------------------------

def test_roommates_are_rendered_in_social_circle(tmp_path):
    cafe = _Node("Cafe")
    cafe.agents = ["Cara", "Alice", "Bob"]
    env = _Env([cafe])
    agents = {n: _Agent(n) for n in ("Cara", "Alice", "Bob")}
    for n, a in agents.items():
        env.agent_locations[n] = cafe
    sim = type("Sim", (), {"world_agents": agents, "environment": env})()

    ObsidianVaultObserver(str(tmp_path))._sync_agents(sim, None)

    text = open(_agent_card(tmp_path, "Cara"), encoding="utf-8").read()
    # 集合迭代顺序不稳定：渲染结果必须是排序后的稳定顺序
    assert "- [[Agents/Alice]]\n- [[Agents/Bob]]" in text


def test_social_circle_rendering_is_stable(tmp_path):
    cafe = _Node("Cafe")
    cafe.agents = ["Cara", "Bob", "Alice"]
    env = _Env([cafe])
    agents = {n: _Agent(n) for n in ("Cara", "Bob", "Alice")}
    for n, a in agents.items():
        env.agent_locations[n] = cafe
    sim = type("Sim", (), {"world_agents": agents, "environment": env})()

    observer = ObsidianVaultObserver(str(tmp_path))
    observer._sync_agents(sim, None)
    first = open(_agent_card(tmp_path, "Cara"), encoding="utf-8").read()

    # 同样状态再渲染一次：内容必须逐字节一致（dirty-check 不应反复写）
    observer._sync_agents(sim, None)
    second = open(_agent_card(tmp_path, "Cara"), encoding="utf-8").read()
    assert first == second


def test_known_nearby_alone_is_still_shown(tmp_path):
    """known_nearby 有值但当前房间无人时，也不应显示"孤身一人"。"""
    cafe = _Node("Cafe")
    env = _Env([cafe])
    agent = _Agent("Cara")
    agent.known_nearby = {"Bob"}
    env.agent_locations["Cara"] = cafe
    sim = type("Sim", (), {"world_agents": {"Cara": agent}, "environment": env})()

    ObsidianVaultObserver(str(tmp_path))._sync_agents(sim, None)

    text = open(_agent_card(tmp_path, "Cara"), encoding="utf-8").read()
    assert "- [[Agents/Bob]]" in text
    assert "孤身一人" not in text


# --------------------------------------------------------------------------
# #44 记忆节点文件名唯一
# --------------------------------------------------------------------------

def _mem(mid, summary):
    return EpisodicMemory(
        memory_id=mid,
        agent_id="Alice",
        tick_start=3,
        tick_end=3,
        location="Cafe",
        involved_agents=["Bob"],
        summary=summary,
        importance=5.0,
    )


def test_same_tick_memories_no_longer_overwrite(tmp_path):
    mems = [
        _mem("ep_Alice_3_3_aaaaaa", "吃了浆果"),
        _mem("ep_Alice_3_3_bbbbbb", "遇见 Bob"),
    ]
    cafe = _Node("Cafe")
    env = _Env([cafe])
    agent = _Agent("Alice")
    env.agent_locations["Alice"] = cafe
    sim = type("Sim", (), {"world_agents": {"Alice": agent}, "environment": env})()

    ObsidianVaultObserver(str(tmp_path), macro_only=False)._sync_agents(
        sim, _MM(mems)
    )

    memories_dir = os.path.join(tmp_path, "Memories")
    md_files = sorted(f for f in os.listdir(memories_dir) if f.endswith(".md"))
    assert len(md_files) == 2, f"同一 tick 的记忆应各自独立成文：{md_files}"

    card = open(_agent_card(tmp_path, "Alice"), encoding="utf-8").read()
    assert "吃了浆果" in card
    assert "遇见 Bob" in card
