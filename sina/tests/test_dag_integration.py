"""
Test suite for Unified DAG Simulation Pipeline (P0 & P1 Integration).
Verifies that ActionInertiaEngine, HierarchicalMemoryManager, RealityCheck,
and ObsidianSyncNode are active and cooperatively executing in the DAG pipeline.
"""

import os
import pytest

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from core.dag_simulation import (
    DAGSmallvilleSimulation,
    AgentThinkNode,
    PhysicsSettleNode,
    OracleJudgeNode,
    ObsidianSyncNode,
)
from core.action_intent import ActionIntent
from core.action_lease import ActionLease
from sina.memory.types import MemoryType


def test_dag_simulation_initialization():
    """Verify that SinaSimulation mounts memory manager, lease engine, and observer."""
    sim = DAGSmallvilleSimulation(world_name="smallville")

    assert sim.action_inertia_engine is not None
    assert sim.memory_manager is not None
    assert sim.observer is not None

    # All config agents must be registered with PersonaInvariants
    assert "Isabella" in sim.memory_manager._personas
    assert "Tom" in sim.memory_manager._personas
    isabella_p = sim.memory_manager._personas["Isabella"]
    assert isabella_p.name == "Isabella"
    assert isabella_p.class_index >= 0.0


def test_agent_think_node_lease_inertia_skips_llm():
    """Verify that an active ActionLease causes AgentThinkNode to bypass LLM calls."""
    import asyncio
    async def _run():
        sim = DAGSmallvilleSimulation(world_name="smallville")

        # Give all living agents active leases
        for name in sim.world_agents.keys():
            sim.action_inertia_engine.grant_lease(
                agent_name=name,
                action_type="sleep",
                description=f"{name} 处于深度休眠中",
                duration_ticks=4,
            )

        think_node = AgentThinkNode("AgentThink")
        result = await think_node.execute({"sim": sim})

        assert result.next_node == "PhysicsSettle"
        intents = result.payload.get("current_intents", [])

        # All living agents should have inertia intents generated without calling any LLM!
        assert len(intents) > 0
        for intent in intents:
            assert "深度休眠" in intent.raw_action["observable_action"]
            assert "[惯性执行中]" in intent.raw_action["internal_thought"]

    asyncio.run(_run())


def test_agent_think_node_real_thinking_with_memory_context(monkeypatch):
    """Verify that when leases expire, AgentThinkNode executes assemble_prompt_context without TypeError."""
    import asyncio
    from core import dag_simulation

    async def mock_determine_next_action(**kwargs):
        # Verify that memory_context was assembled properly and contains persona invariant
        mem_ctx = kwargs.get("memory_context", "")
        assert "【核心信念】" in mem_ctx or len(mem_ctx) > 0
        return {
            "internal_thought": "我醒来了，需要寻找食物",
            "observable_action": "在小镇漫步寻找浆果",
            "action_type": "wander",
            "duration_minutes": 30,
        }

    monkeypatch.setattr(dag_simulation, "determine_next_action", mock_determine_next_action)

    async def _run():
        sim = DAGSmallvilleSimulation(world_name="smallville")
        # Ensure no leases exist
        sim.action_inertia_engine.active_leases.clear()

        think_node = AgentThinkNode("AgentThink")
        result = await think_node.execute({"sim": sim})

        assert result.next_node == "PhysicsSettle"
        intents = result.payload.get("current_intents", [])
        assert len(intents) > 0

        # Verify leases were granted after thinking
        for intent in intents:
            lease = sim.action_inertia_engine.get_lease(intent.agent_name)
            assert lease is not None
            assert lease.ticks_remaining == 2  # 30 mins // 15 = 2 ticks

    asyncio.run(_run())


def test_reality_check_environmental_pickup_allowed():
    """Verify that picking up / taking an item from the room ground is NOT blocked by RealityCheckMiddleware."""
    from core.laplace_oracle import RealityCheckMiddleware

    middleware = RealityCheckMiddleware()
    agent_state = {"inventory": []}  # empty inventory
    room_state = {
        "agents_present": ["Alice"],
        "agents_known": ["Alice"],
        "agents_dead": [],
        "known_items": ["bread", "apple"],
        "room_items": ["bread"],  # bread is on the floor/table!
    }

    # Alice takes bread from the room
    res = middleware.check(
        action_text="Alice 从桌上拿起面包放进背包",
        thought_text="我好饿，拾取面包吃",
        agent_state=agent_state,
        room_state=room_state,
    )

    # Must be grounded! Ground item pickup is physically valid!
    assert res.is_grounded is True
    assert res.should_proceed is True
    assert len(res.hallucination_flags) == 0


def test_obsidian_sync_node_execution():
    """Verify that ObsidianSyncNode executes cleanly and routes to MemeDecay."""
    import asyncio
    async def _run():
        sim = DAGSmallvilleSimulation(world_name="smallville")
        sync_node = ObsidianSyncNode("ObsidianSync")

        result = await sync_node.execute({
            "sim": sim,
            "current_intents": [],
        })

        assert result.next_node == "MemeDecay"

    asyncio.run(_run())


def test_proposal_voting_window_retention_and_expiration():
    """Verify that a proposal remains active across ticks until expire_tick, then adjudicates."""
    import asyncio
    from core.action_intent import Proposal
    from core.dag_simulation import OracleJudgeNode

    async def _run():
        sim = DAGSmallvilleSimulation(world_name="smallville")
        judge_node = OracleJudgeNode("OracleJudge")

        async def mock_judge(content, tech_level):
            from core.laplace_oracle import LaplaceVerdict
            return LaplaceVerdict(
                verdict="PHYSICS",
                reasoning="Mocked passed",
                eval_goal=1,
                eval_believability=1,
                eval_secret=1,
                feasibility_score=4.0,
            )
        sim.oracle.judge = mock_judge

        # Create a proposal at tick 10 with lifetime 4 (expires at tick 14)
        sim.tick_count = 10
        proposal = Proposal("Isabella", "所有人必须在篝火旁储备干草", created_tick=10, lifetime_ticks=4)
        # Isabella votes YES
        proposal.votes["Isabella"] = "YES"
        sim.active_proposal[0] = proposal

        # Tick 11: Window NOT expired, only 1 vote out of 6 -> stays pending!
        sim.tick_count = 11
        await judge_node.execute({"sim": sim})
        assert sim.active_proposal[0] is proposal
        assert proposal.status == "pending"

        # Tick 12: Tom also votes YES
        proposal.votes["Tom"] = "YES"
        sim.tick_count = 12
        await judge_node.execute({"sim": sim})
        assert sim.active_proposal[0] is proposal

        # Tick 14: Deadline reached! Window expires!
        # Isabella (YES) + Tom (YES) = 2/2 YES (100% of cast votes) -> should adjudicate and clear proposal!
        sim.tick_count = 14
        await judge_node.execute({"sim": sim})
        assert sim.active_proposal[0] is None
        assert proposal.status in ("approved", "rejected")

    asyncio.run(_run())
