"""回归测试：环境资源补给由 map.json 的 restock_rules 声明驱动 (#52)。

此前 EnvTickNode 硬编码 get_node_by_name("Cafe")/"Supermarket"，使引擎与
smallville 地图强耦合：换一张没有 Cafe/Supermarket 的地图（如 stone_age），
补给逻辑静默失效，违背"领域无关世界模型"的声明。
"""

import asyncio

from core.dag_simulation import EnvTickNode
from core.environment import SandboxEnvironment


class _FakePhysics:
    """EnvTickNode 只调用 resolve_spoilage，这里做空实现避免引入物理引擎副作用。"""

    def resolve_spoilage(self, inventory):
        pass


def _make_sim(world_name):
    env = SandboxEnvironment(world_name=world_name)
    sim = type("_Sim", (), {
        "environment": env,
        "physics": _FakePhysics(),
        "world_agents": {},
        "tick_count": 0,
        "current_logs": [],
    })()
    return sim


def _run_envtick(sim):
    state = {"sim": sim}
    result = asyncio.run(EnvTickNode("EnvTick").execute(state))
    return state, result


def test_sandbox_environment_loads_restock_rules_from_map():
    smallville = SandboxEnvironment(world_name="smallville")
    assert len(smallville.restock_rules) == 2
    assert smallville.restock_rules[0]["node"] == "Cafe"

    stone_age = SandboxEnvironment(world_name="stone_age")
    assert stone_age.restock_rules == []


def test_envtick_restocks_only_configured_nodes():
    sim = _make_sim("smallville")
    env = sim.environment

    cafe = env.get_node_by_name("Cafe")
    market = env.get_node_by_name("Supermarket")
    library = env.get_node_by_name("Library")

    cafe_before = dict(cafe.inventory)
    market_before = dict(market.inventory)
    library_before = dict(library.inventory)

    _, result = _run_envtick(sim)

    assert result.next_node == "AgentThink"
    # 配置内节点按规则 +1
    assert cafe.inventory["COFFEE"] == cafe_before["COFFEE"] + 1
    assert cafe.inventory["PASTRY"] == cafe_before["PASTRY"] + 1
    assert market.inventory["BREAD"] == market_before["BREAD"] + 1
    assert market.inventory["APPLE"] == market_before["APPLE"] + 1
    # 未配置的节点不受影响
    assert library.inventory == library_before


def test_envtick_empty_restock_rules_does_not_crash():
    sim = _make_sim("stone_age")
    env = sim.environment

    before = {n.name: dict(n.inventory) for n in env.all_nodes()}

    _, result = _run_envtick(sim)

    assert result.next_node == "AgentThink"
    # stone_age 无补给规则：所有节点库存保持不变
    for node in env.all_nodes():
        assert node.inventory == before[node.name]
