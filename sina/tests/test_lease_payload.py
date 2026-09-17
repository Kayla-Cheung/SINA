"""
行动租约惯性执行回归测试（#41）。

多 tick 租约期间，AgentThinkNode 构造的惯性 intent 必须携带完整结构化
payload（move_to/eat_item/take_item_tag/produce_item_tag/craft 等），
否则物理层无从结算、租约等于空转。同时锁住 infer_action_type 的类型反推。
"""

import asyncio

from core.action_intent import ActionIntent
from core.action_lease import ActionInertiaEngine, infer_action_type
from core.agent_state import AgentState
from core.dag_simulation import AgentThinkNode


def test_infer_action_type():
    assert infer_action_type({"move_to": "Cafe"}) == "walk"
    assert infer_action_type({"craft": "烤肉"}) == "craft"
    assert infer_action_type({"take_item_tag": "BERRY"}) == "forage"
    assert infer_action_type({"produce_item_tag": "BERRY"}) == "forage"
    assert infer_action_type({"eat_item": "BERRY"}) == "idle"
    assert infer_action_type({"attack_target": "Bob"}) == "idle"
    assert infer_action_type({}) == "wander"


def test_lease_roundtrips_payload():
    engine = ActionInertiaEngine()
    engine.grant_lease(
        agent_name="Alice",
        action_type="forage",
        description="采集浆果",
        duration_ticks=3,
        payload={"produce_item_tag": "BERRY"},
    )

    lease = engine.get_lease("Alice")

    assert lease is not None
    assert lease.action_type == "forage"
    assert lease.payload == {"produce_item_tag": "BERRY"}


def test_inertia_intent_carries_structured_payload():
    class _Node:
        def __init__(self, name):
            self.name = name

    class _Env:
        def __init__(self):
            self.agent_locations = {}

    env = _Env()
    env.agent_locations["Alice"] = _Node("Cafe")

    inertia = ActionInertiaEngine()
    inertia.grant_lease(
        agent_name="Alice",
        action_type="forage",
        description="采集浆果",
        duration_ticks=3,
        payload={"produce_item_tag": "BERRY"},
    )

    agent = AgentState(name="Alice", hunger=30)
    sim = type("Sim", (), {
        "world_agents": {"Alice": agent},
        "environment": env,
        "action_inertia_engine": inertia,
    })()

    result = asyncio.run(AgentThinkNode("AgentThink").execute({"sim": sim}))
    intents = result.payload["current_intents"]

    assert len(intents) == 1
    raw = intents[0].raw_action
    # 旧代码这里只有 internal_thought / observable_action，produce_item_tag 会丢失
    assert raw.get("produce_item_tag") == "BERRY"
    assert raw.get("internal_thought", "").startswith("[惯性执行中]")
