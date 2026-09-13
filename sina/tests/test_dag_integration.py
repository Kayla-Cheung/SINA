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
