"""
回归测试：资源 → 阶级 回写边 (#social-mobility)。
================================================================
此前 class 是常量（无写入口），AgentState 也不存 class/wealth，读档回落 0.5/100。
这些用例锁住三件事：
  1. 默认关闭 —— 不开启时既有行为一字不变；
  2. 回写生效 —— class_index 与 token 预算随资源一起动；
  3. 存读档不丢 —— class/wealth 必须活过一次 save → load。
"""

import os

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from core.dag_simulation import DAGSmallvilleSimulation
from core.social_mobility import (
    MobilityConfig,
    SocialMobilityEngine,
    default_resource_valuation,
)
from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.types import PersonaInvariant


def _persona(agent_id="a", class_index=0.5, wealth_budget=100.0):
    return PersonaInvariant(
        agent_id=agent_id,
        name=agent_id,
        archetype="Forager",
        core_conviction="生存",
        class_index=class_index,
        wealth_budget=wealth_budget,
    )


# ── 1. 默认关闭，不改变既有行为 ────────────────────────────────────────
def test_mobility_disabled_by_default_from_env():
    assert MobilityConfig.from_env({}).enabled is False
    assert MobilityConfig().enabled is False


def test_mobility_step_is_noop_when_disabled():
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    sim.mobility.config = MobilityConfig()  # 显式关闭，免受外部环境变量影响
    before = {n: sim.memory_manager.get_persona(n).class_index for n in sim.world_agents}

    assert sim.mobility.maybe_step(sim) is None

    after = {n: sim.memory_manager.get_persona(n).class_index for n in sim.world_agents}
    assert before == after


# ── 2. 回写生效：class 与 token 预算一起动 ──────────────────────────────
def test_update_social_standing_writes_class_and_budget():
    mgr = HierarchicalMemoryManager(default_token_threshold=1000)
    # 显式阈值走 dag 的那条路径：max(5, int(wealth/20))
    mgr.register_agent(_persona("poor", class_index=0.1, wealth_budget=100.0), token_threshold=5)
    mgr.register_agent(_persona("rich", class_index=0.1, wealth_budget=100.0), token_threshold=5)

    assert mgr._personas["poor"].class_index == 0.1

    mgr.update_social_standing("poor", class_index=0.9, wealth_budget=400.0)

    assert mgr.get_persona("poor").class_index == 0.9
    assert mgr.get_persona("poor").wealth_budget == 400.0
    # 阈值按财富比例缩放：5 * (400/100) = 20
    assert mgr._bifurcation_managers["poor"].token_threshold == 20
    # 未触碰的 agent 不受影响（BifurcationManager 自身有 max(10, …) 下限）
    assert mgr.get_persona("rich").class_index == 0.1
    assert mgr._bifurcation_managers["rich"].token_threshold == 10


def test_update_social_standing_clamps_and_handles_unknown_agent():
    mgr = HierarchicalMemoryManager()
    mgr.register_agent(_persona("a"))
    mgr.update_social_standing("a", class_index=5.0)
    assert mgr.get_persona("a").class_index == 1.0
    mgr.update_social_standing("a", class_index=-3.0)
    assert mgr.get_persona("a").class_index == 0.0
    assert mgr.update_social_standing("nobody") is None


def test_quantile_mobility_orders_class_by_resources():
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    sim.mobility.config = MobilityConfig(enabled=True, mode="quantile", interval_ticks=1, ema=1.0)

    # 清空所有人背包，只留下可比的资源
    for agent in sim.world_agents.values():
        agent.inventory = {}
    sim.world_agents["Tom"].inventory = {"MONEY": 1000}
    sim.world_agents["Klaus"].inventory = {"MONEY": 1}

    sim.mobility.step(sim)

    assert sim.memory_manager.get_persona("Tom").class_index > sim.memory_manager.get_persona("Klaus").class_index
    assert len(sim.mobility.history) == 1
    assert sim.mobility.history[0]["tick"] == sim.tick_count


def test_ema_smooths_toward_target():
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    # 让一人独占全部资源 → quantile 目标为 1.0；ema=0.5 时半程靠拢
    for agent in sim.world_agents.values():
        agent.inventory = {}
    sim.world_agents["Tom"].inventory = {"MONEY": 1000}
    sim.memory_manager.get_persona("Tom").class_index = 0.0

    sim.mobility.config = MobilityConfig(enabled=True, mode="quantile", interval_ticks=1, ema=0.5)
    sim.mobility.step(sim)

    # 0.0 → 目标 1.0 走一半 = 0.5（Tom 资源最高必为分位 1.0）
    assert abs(sim.memory_manager.get_persona("Tom").class_index - 0.5) < 1e-9


def test_absolute_mode_uses_thresholds():
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    for agent in sim.world_agents.values():
        agent.inventory = {}
    sim.world_agents["Tom"].inventory = {"MONEY": 500}

    sim.mobility.config = MobilityConfig(
        enabled=True, mode="absolute", interval_ticks=1, ema=1.0,
        absolute_low=0.0, absolute_high=1000.0,
    )
    sim.mobility.step(sim)

    assert abs(sim.memory_manager.get_persona("Tom").class_index - 0.5) < 1e-9


def test_valuation_is_pluggable():
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    for agent in sim.world_agents.values():
        agent.inventory = {}

    cfg = MobilityConfig(
        enabled=True, interval_ticks=1, ema=1.0,
        valuation_fn=lambda agent, sim, cfg: 1.0 if agent.name == "Sam" else 0.0,
    )
    sim.mobility.config = cfg
    sim.mobility.step(sim)

    assert sim.memory_manager.get_persona("Sam").class_index == 1.0


def test_default_valuation_uses_item_table_and_fallback():
    cfg = MobilityConfig()

    class _A:
        inventory = {"MONEY": 10, "UNKNOWN_ITEM": 2}
        hunger = 30

    # MONEY 面值 1.0；未知物品走 fallback 5.0
    assert default_resource_valuation(_A(), None, cfg) == 10 * 1.0 + 2 * 5.0


# ── 3. 存读档不丢 class / wealth ────────────────────────────────────────
def test_save_load_roundtrip_preserves_class_and_wealth(tmp_path):
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    sim.memory_manager.update_social_standing("Tom", class_index=0.13, wealth_budget=777.0)

    save_path = str(tmp_path / "state.json")
    sim.save_world_state(save_path)

    # resume 默认(None) + 显式 save_file → 走读档分支
    reloaded = DAGSmallvilleSimulation(world_name="smallville", save_file=save_path)
    assert abs(reloaded.memory_manager.get_persona("Tom").class_index - 0.13) < 1e-9
    assert abs(reloaded.memory_manager.get_persona("Tom").wealth_budget - 777.0) < 1e-9
    # 阈值也应随读回的财富一并复原：max(5, int(777/20)) = 38
    assert reloaded.memory_manager._bifurcation_managers["Tom"].token_threshold == 38


def test_history_dump_writes_json(tmp_path):
    sim = DAGSmallvilleSimulation(world_name="smallville", resume=False)
    sim.mobility.config = MobilityConfig(enabled=True, interval_ticks=1, ema=1.0)
    sim.mobility.step(sim)

    out = str(tmp_path / "nested" / "mobility.json")
    assert sim.mobility.dump_history(out) == out
    assert os.path.exists(out)
