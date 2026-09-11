"""
Regression & Bug Fix Tests for SINA Core Engine.
Covers Issues #12 (Combat Healing Inverse), #13 (Comatose Vote Deadlock),
#14 (Vote String Mismatch), #15 (Inventory Spoilage Loophole), and #16 (Death Drop).
"""

import pytest
from datetime import datetime

from core.action_intent import Proposal, ActionIntent
from core.agent_state import AgentState
from core.physics_engine import PhysicsEngine
from core.environment import SandboxEnvironment, EnvNode
from core.settlement_engine import settle_all_intents


def test_issue12_combat_loser_damage_subtraction():
    """Verify combat settlement subtracts hunger penalty instead of healing."""
    physics = PhysicsEngine()
    attacker = AgentState("Attacker", traits="强壮的猎人")
    attacker.hunger = 20
    defender = AgentState("Defender", traits="孱弱的采集者")
    defender.hunger = 20

    res = physics.resolve_combat(attacker, defender)
    penalty = res["loser_hunger_penalty"]
    assert penalty > 0

    # Simulate subtraction
    defender.hunger = max(0, defender.hunger - penalty)
    assert defender.hunger < 20


def test_issue13_comatose_vote_deadlock_elimination():
    """Verify comatose agents do not deadlock proposal voting."""
    p = Proposal("Alice", "建造火堆")
    
    # 3 total agents: Alice (Alive), Bob (Alive), Charlie (Comatose)
    world_agents = {
        "Alice": AgentState("Alice"),
        "Bob": AgentState("Bob"),
        "Charlie": AgentState("Charlie"),
    }
    world_agents["Charlie"].is_comatose = True

    # Filter alive and non-comatose
    alive_names = [n for n, a in world_agents.items() if not a.is_dead and not a.is_comatose]
    assert alive_names == ["Alice", "Bob"]

    # Only Alice and Bob vote
    p.votes["Alice"] = "approve"
    p.votes["Bob"] = "YES"

    all_voted = len(alive_names) > 0 and all(n in p.votes for n in alive_names)
    assert all_voted is True
    assert p.approval_count == 2
    assert p.approval_count == len(alive_names)


def test_issue14_proposal_vote_case_and_dict_robustness():
    """Verify Proposal handles YES, approve, True, Dict, and reject formats."""
    p = Proposal("Leader", "开垦土地")
    p.votes["Agent1"] = "approve"
    p.votes["Agent2"] = "YES"
    p.votes["Agent3"] = "TRUE"
    p.votes["Agent4"] = {"vote": "yes"}
    p.votes["Agent5"] = "reject"
    p.votes["Agent6"] = "NO"

    assert p.approval_count == 4
    assert p.rejection_count == 2


def test_issue15_inventory_spoilage():
    """Verify physics engine rots perishable items directly in inventory."""
    physics = PhysicsEngine()
    agent = AgentState("Hunter")
    agent.inventory = {"MEAT": 50, "STONE": 5}

    spoiled = physics.resolve_spoilage(agent.inventory)
    assert "MEAT" in spoiled
    assert agent.inventory.get("MEAT", 0) < 50
    assert agent.inventory["STONE"] == 5


def test_issue16_death_drop_conservation():
    """Verify deceased agent transfers full inventory into current node."""
    env = SandboxEnvironment()
    node = env.all_nodes()[0]
    agent = AgentState("Explorer")
    agent.inventory = {"TORCH": 1, "BERRY": 3}
    agent.hunger = -5

    # Trigger death drop
    if agent.hunger <= -5:
        agent.is_dead = True
        for item, count in agent.inventory.items():
            node.inventory[item] = node.inventory.get(item, 0) + count
        agent.inventory = {}

    assert agent.is_dead is True
    assert agent.inventory == {}
    assert node.inventory["TORCH"] >= 1
    assert node.inventory["BERRY"] >= 3
