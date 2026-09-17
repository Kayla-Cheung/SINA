"""
劳动产出白名单回归测试（#32）。

LLM 只要在 intent 里声明 produce_item_tag，旧代码就会无条件凭空造出该物品，
绕过 PhysicsEngine 的材质表与配方表。这里锁定：未定义 tag 必须被驳回，
且代价（1 点饥饿）不得被扣除。
"""

import asyncio
from datetime import datetime

from core.action_intent import ActionIntent
from core.agent_state import AgentState
from core.environment import SandboxEnvironment
from core.physics_engine import PhysicsEngine, Recipe
from core.settlement_engine import settle_all_intents


def _produce(tag: str, physics: PhysicsEngine):
    env = SandboxEnvironment("smallville")
    room = env.get_node_by_name("Cafe") or env.all_nodes()[0]
    env.spawn_agent("Alice", room)
    agent = AgentState(name="Alice", hunger=20)
    intent = ActionIntent(
        agent_name="Alice",
        raw_action={"produce_item_tag": tag},
        source_room=room.name,
    )

    logs = asyncio.run(
        settle_all_intents(
            intents=[intent],
            world_agents={"Alice": agent},
            physics=physics,
            environment=env,
            clock=datetime(2026, 1, 1, 8, 0),
            is_night=False,
        )
    )
    return agent, logs


def test_undefined_tag_is_rejected():
    agent, logs = _produce("钻石", PhysicsEngine("smallville"))

    assert "钻石" not in agent.inventory
    assert agent.hunger == 20, "被驳回的生产不应扣除饥饿度"
    assert any("生产失败" in line for line in logs)


def test_material_tag_is_producible():
    agent, logs = _produce("BERRY", PhysicsEngine("smallville"))

    assert agent.inventory.get("BERRY") == 1
    assert agent.hunger == 19
    assert any("生产" in line for line in logs)


def test_recipe_output_is_producible():
    physics = PhysicsEngine("smallville")
    physics.recipes.append(Recipe("造镐", {"STONE": 1}, {"钻石镐": 1}))

    agent, _ = _produce("钻石镐", physics)

    assert agent.inventory.get("钻石镐") == 1


def test_empty_tag_is_not_producible():
    physics = PhysicsEngine("smallville")
    assert physics.is_producible("") is False
    assert physics.is_producible("BERRY") is True
