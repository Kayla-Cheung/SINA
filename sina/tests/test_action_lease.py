"""
Test suite for Action Inertia Engine (Issue #17) and Gateway Semaphore Throttle (Issue #3).
Validates multi-tick lease commitment, event interruption matrix, and rate-limiting gates.
"""

import os
import pytest

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from core.action_lease import (
    ActionLease,
    ActionInertiaEngine,
)
from core.gateway import gateway


# ─────────────────────────────────────────
# 1. ActionLease Unit Tests
# ─────────────────────────────────────────

def test_action_lease_lifecycle():
    lease = ActionLease(
        action_type="forage",
        description="正在采集浆果",
        total_ticks=3,
        ticks_remaining=3,
    )
    assert lease.is_active is True
    assert lease.ticks_remaining == 3

    assert lease.tick() == 2
    assert lease.is_active is True

    assert lease.tick() == 1
    assert lease.is_active is True

    assert lease.tick() == 0
    assert lease.is_active is False
    # Extra tick doesn't go below 0
    assert lease.tick() == 0


# ─────────────────────────────────────────
# 2. ActionInertiaEngine Unit Tests
# ─────────────────────────────────────────

@pytest.fixture
def engine():
    return ActionInertiaEngine()


def test_grant_and_get_lease(engine):
    lease = engine.grant_lease(
        agent_name="Ryan",
        action_type="sleep",
        description="进入深度睡眠",
        duration_ticks=4,
    )
    assert lease.ticks_remaining == 4
    assert engine.get_lease("Ryan") is lease
    assert engine.get_lease("Isabella") is None


def test_evaluate_agent_without_lease(engine):
    need_think, reason, active_lease = engine.evaluate_agent_lease("Ryan", pending_events=[])
    assert need_think is True
    assert "无活跃行动租约" in reason
    assert active_lease is None


def test_evaluate_agent_lease_progression(engine):
    engine.grant_lease("Ryan", "craft", "制作石矛", duration_ticks=2)

    # Tick 1: Still active, no interruption -> LLM Think Skipped!
    need_think, reason, active_lease = engine.evaluate_agent_lease("Ryan", pending_events=[])
    assert need_think is False
    assert reason is None
    assert active_lease is not None
    assert active_lease.ticks_remaining == 1

    # Tick 2: Lease expires on this tick -> Awakened for next decision
    need_think, reason, active_lease = engine.evaluate_agent_lease("Ryan", pending_events=[])
    assert need_think is True
    assert "行动租约耗尽" in reason
    assert active_lease is None


def test_event_interruption_damage(engine):
    """Critical damage taken must immediately break active sleep lease."""
    engine.grant_lease("Ryan", "sleep", "睡眠中", duration_ticks=4)

    events = ["夜幕中野兽从灌木扑来，对你造成了 4 点伤害！"]
    need_think, reason, active_lease = engine.evaluate_agent_lease("Ryan", pending_events=events)

    assert need_think is True
    assert "DAMAGE_TAKEN" in reason
    assert engine.get_lease("Ryan") is None


def test_event_interruption_social_chat(engine):
    """Direct conversation interruption breaks idle/wandering lease."""
    engine.grant_lease("Isabella", "wander", "闲逛中", duration_ticks=2)

    events = ["Tom 走过来对你说：『下午好，我们要去平原吗？』"]
    need_think, reason, active_lease = engine.evaluate_agent_lease("Isabella", pending_events=events)

    assert need_think is True
    assert "DIRECT_CHAT" in reason
    assert engine.get_lease("Isabella") is None


def test_non_disruptive_event_ignored(engine):
    """Background noise / minor events do not interrupt active lease."""
    engine.grant_lease("Tom", "forage", "在森林深处采浆果", duration_ticks=3)

    events = ["一阵微风吹过树梢，树叶沙沙作响。"]
    need_think, reason, active_lease = engine.evaluate_agent_lease("Tom", pending_events=events)

    assert need_think is False
    assert reason is None
    assert active_lease.ticks_remaining == 2


# ─────────────────────────────────────────
# 3. Gateway Semaphore Concurrency Throttle Test
# ─────────────────────────────────────────

def test_gateway_semaphore_initialized():
    assert hasattr(gateway, "semaphore")
    assert gateway.semaphore._value >= 1
