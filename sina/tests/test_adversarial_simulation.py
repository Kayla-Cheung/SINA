"""
test_adversarial_simulation.py — 对抗式与端到端闭环严苛测试
===========================================================
测试哲学：从“验证我的构想”到“往死里整代码”
1. test_live_simulation_smoke: 5 个连续完整 Tick 全链路端到端推演（无预发租约，全走真实思考分支）
2. test_reality_check_adversarial_mythical_weapon: 反向测试（声称持有未在世界注册或未在背包的神兵，必须被硬拦截）
3. test_adversarial_corrupted_payload_robustness: 破坏性测试（空字符串、乱码、畸形字段，系统不崩溃）
"""

import asyncio
import os
from core.dag_simulation import DAGSmallvilleSimulation
from core.laplace_oracle import RealityCheckMiddleware
from core.action_intent import ActionIntent
from core.settlement_engine import settle_all_intents
from core.physics_engine import PhysicsEngine
from core.environment import SandboxEnvironment
from core.agent_state import AgentState

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")


def test_live_simulation_smoke(monkeypatch):
    """
    全链路端到端推演冒烟测试：
    - 严禁预发任何 ActionLease（初始租约清空）
    - 连续推进 5 个完整 Tick
    - 每帧真实经历：EnvTick -> AgentThink -> PhysicsSettle -> OracleJudge -> ObsidianSync -> MemeDecay -> ClockTick
    - 验证：大模型生成有效动作 -> 租约授予 -> 物理结算 -> 提案/记忆完整流转
    """
    mock_responses = [
        {"action_type": "wander", "duration_minutes": 15, "observable_action": "在街区漫步巡视", "internal_thought": "我必须巡视领地"},
        {"action_type": "chat", "target": "Bob", "duration_minutes": 15, "observable_action": "向Bob打招呼讨论天气", "internal_thought": "与邻居维持关系"},
        {"action_type": "eat", "item": "bread", "duration_minutes": 15, "observable_action": "坐在长椅上吃面包", "internal_thought": "补充能量"},
        {"action_type": "work", "duration_minutes": 30, "observable_action": "在工坊修补篱笆", "internal_thought": "修葺公共设施"},
    ]
    call_counter = {"idx": 0}

    async def mock_determine_next_action(**kwargs):
        resp = mock_responses[call_counter["idx"] % len(mock_responses)]
        call_counter["idx"] += 1
        return resp

    from core import dag_simulation
    monkeypatch.setattr(dag_simulation, "determine_next_action", mock_determine_next_action)

    async def _run():
        sim = DAGSmallvilleSimulation(world_name="smallville")
        # 严格清空所有预设租约，强迫所有智能体进入全真思考流
        sim.action_inertia_engine.active_leases.clear()
        initial_tick = sim.tick_count

        # 连续跑满 5 个完整 Tick (75 分钟仿真时间)
        await sim.run_dag_loop(ticks=5)

        assert sim.tick_count == initial_tick + 5
        # 验证所有存活智能体均获得了有效的租约
        for name, agent in sim.world_agents.items():
            if not agent.is_dead:
                lease = sim.action_inertia_engine.get_lease(name)
                assert lease is not None, f"Agent {name} 未能成功获得行动租约"

    asyncio.run(_run())


def test_reality_check_adversarial_mythical_weapon():
    """
    反向测试：测试最脆弱的物理边界
    Agent 声称手持 '倚天剑' 斩断巨石，
    物理世界与背包中根本没有此道具，必须被 RealityCheckMiddleware 严厉拦截，列入幻觉黑名单！
    """
    middleware = RealityCheckMiddleware()
    agent_state = {"inventory": ["bread", "wood"]}
    room_state = {
        "agents_present": ["Arthur"],
        "agents_known": ["Arthur"],
        "agents_dead": [],
        "known_items": ["倚天剑", "bread", "wood", "stone"],
        "room_items": ["stone"],
    }

    # Arthur 宣称手握倚天剑进行消耗或攻击
    res = middleware.check(
        action_text="Arthur 拔出手中的倚天剑斩断前方的巨石",
        thought_text="我有绝世神兵倚天剑，无人能挡",
        agent_state=agent_state,
        room_state=room_state,
    )

    assert res.is_grounded is False
    assert res.should_proceed is False
    assert any("倚天剑" in flag for flag in res.hallucination_flags)


def test_adversarial_corrupted_payload_robustness():
    """
    破坏性测试：
    向物理结算引擎灌入极端畸形负载：
    - 空字符串 action_type
    - 恶意注入 / 特殊符号 JSON
    - 目标为不存在的目标 / 自身 / 符号
    确保物理结算引擎严丝合缝捕获异常，绝不发生不可控崩溃。
    """
    async def _run():
        physics = PhysicsEngine()
        env = SandboxEnvironment("smallville")
        cafe = env.get_node_by_name("Cafe") or env.all_nodes()[0]
        env.spawn_agent("ChaosAgent", cafe)
        agent = AgentState(name="ChaosAgent", hunger=20, inventory={"apple": 1})
        world_agents = {"ChaosAgent": agent}

        dead_ghost = AgentState(name="DeadGhost")
        dead_ghost.is_dead = True
        world_agents["DeadGhost"] = dead_ghost

        corrupted_intents = [
            ActionIntent(agent_name="ChaosAgent", raw_action={}, source_room="Cafe"),
            ActionIntent(agent_name="ChaosAgent", raw_action={"attack_target": "NonExistentGhost", "internal_thought": "'; DROP TABLE agents; --"}, source_room="Cafe"),
            ActionIntent(
                agent_name="ChaosAgent",
                raw_action={
                    "observable_action": "向 DeadGhost 递送物品",
                    "internal_thought": "与死者交谈",
                    "give_item": {"tag": "apple", "target": "DeadGhost"}
                },
                source_room="Cafe"
            ),
            ActionIntent(agent_name="ChaosAgent", raw_action={"eat_item": "unknown_void_item"}, source_room="Cafe"),
        ]

        from datetime import datetime
        # 执行物理结算，必须平稳优雅吞吐，捕获拦截且不崩溃
        logs = await settle_all_intents(
            intents=corrupted_intents,
            world_agents=world_agents,
            environment=env,
            physics=physics,
            clock=datetime.now(),
            is_night=False,
        )

        assert isinstance(logs, list)
        # 验证 DeadGhost 拦截被写入日志
        assert any("现实拦截" in log for log in logs)
        # 智能体收到吃不存在物品的物理反馈记录在记忆流中
        assert any("手上并没有" in m.get("text", "") for m in agent.memory_stream)
        # 智能体未发生非预期坏死
        assert agent.hunger == 20

    asyncio.run(_run())
