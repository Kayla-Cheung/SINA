"""
social_mobility.py — 资源 → 阶级 回写边（补上 SINA 社会学闭环里断掉的那一段）
================================================================================
SINA 自称的因果链是：

    class_index → 记忆保真度 → 行为 → 资源存量 → class_index
     (Layer 0)     (decay.py)                    ^^^^^^^^^^^
                                                 这一段此前不存在

前两段有代码：ClassGatedDecayEngine 用 class_index 调衰减 / 丢弃 / 噪声，
BifurcationManager 用 wealth_budget 调工作记忆 token 预算。但最后一段没有：

  · persona.class_index 在 register_agent 之后就是常量，全仓库没有写入口；
  · AgentState 里根本没有 class / wealth 字段，to_dict() 也不导出；
  · save_world_state 存的正是 AgentState.to_dict()，于是每次存档都会把
    class/wealth 丢掉，读档回落成 0.5 / 100（sina/tests/conftest.py 的注释
    也记着这件事）。

本模块只做一件事：每 N 个 tick 把每个智能体的资源存量折算成一个新的
class_index，回写进 PersonaInvariant，并同步其工作记忆 token 预算。
不碰 confabulation 那个桩，也不重构任何既有逻辑。

⚠ 模型归属（重要）
------------------
default_resource_valuation() 是**占位估值**，不是经济学模型：它只按一张手工
价值表把背包折算成标量。而「资源如何变成地位」恰恰是要研究的对象本身，
所以估值函数、映射方式、惰性系数全部做成了可注入参数。
替换 valuation_fn / mode / ema，就是替换你的社会流动模型。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# 占位价值表：默认只认 MONEY 面值，其余用手工估值。
# 这不是经济学建模，只是一个让 class 能随背包单调变动的代理。
DEFAULT_ITEM_VALUES: Dict[str, float] = {
    "MONEY": 1.0,
    "GOLD": 50.0,
    "COFFEE_BEANS": 8.0,
    "LAPTOP": 400.0,
    "BOOK": 30.0,
    "NOTEBOOK": 10.0,
    "TOOLBOX": 120.0,
    "FOOD": 4.0,
    "WOOD": 3.0,
    "STONE": 3.0,
}
DEFAULT_ITEM_FALLBACK_VALUE = 5.0

_HUNGER_MAX = 30.0  # worlds/*/config/agents.json：0 = 昏迷边缘，30 = 饱腹


def default_resource_valuation(agent, sim, config: "MobilityConfig") -> float:
    """占位估值：背包内物品按价值表求和（可选加饥饿项）。

    ⚠ 这是占位实现。请替换成你自己的「资源→地位」价值函数：
    它决定「谁算富」，也就是决定这个实验的自变量取值。
    """
    total = 0.0
    for item_name, qty in (agent.inventory or {}).items():
        unit = config.item_values.get(str(item_name).upper(), DEFAULT_ITEM_FALLBACK_VALUE)
        total += float(qty) * float(unit)
    if config.hunger_weight:
        total += float(getattr(agent, "hunger", 0)) * float(config.hunger_weight)
    return max(0.0, total)


@dataclass
class MobilityConfig:
    """社会流动模型的全部可调旋钮。默认 enabled=False，不改变既有行为。"""

    enabled: bool = False

    # 映射方式：
    #   "quantile" —— 按资源排名取群体内分位（零和：有人上升必有人下降）
    #   "absolute" —— 按绝对阈值线性映射（可与零和脱钩，允许整体上升）
    mode: str = "quantile"

    # 每多少 tick 结算一次阶级
    interval_ticks: int = 10

    # 惰性系数：1.0 = 立即跳到目标；<1 = 每步只走 ema 比例（社会惯性）
    ema: float = 1.0

    class_floor: float = 0.0
    class_ceiling: float = 1.0

    # mode="absolute" 时的线性映射区间
    absolute_low: float = 0.0
    absolute_high: float = 5000.0

    # >0 则把饥饿度计入地位；默认 0.0，不偷偷注入这个假设
    hunger_weight: float = 0.0

    item_values: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_ITEM_VALUES))

    # 可注入的估值函数 (agent, sim, config) -> float；None 用占位实现
    valuation_fn: Optional[Callable] = None

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "MobilityConfig":
        """从环境变量构造。未设置 SINA_MOBILITY 时返回默认（关闭）配置。

        支持的变量：
          SINA_MOBILITY=1            总开关
          SINA_MOBILITY_MODE         quantile | absolute
          SINA_MOBILITY_INTERVAL     整数 tick
          SINA_MOBILITY_EMA          [0,1] 浮点
          SINA_MOBILITY_HUNGER_WEIGHT 浮点
        """
        env = os.environ if env is None else env
        enabled = str(env.get("SINA_MOBILITY", "")).strip().lower() in ("1", "true", "yes", "on")
        cfg = cls(enabled=enabled)
        if not enabled:
            return cfg

        raw_mode = str(env.get("SINA_MOBILITY_MODE", "")).strip().lower()
        if raw_mode:
            cfg.mode = raw_mode
        try:
            if env.get("SINA_MOBILITY_INTERVAL"):
                cfg.interval_ticks = max(1, int(env["SINA_MOBILITY_INTERVAL"]))
            if env.get("SINA_MOBILITY_EMA"):
                cfg.ema = max(0.0, min(1.0, float(env["SINA_MOBILITY_EMA"])))
            if env.get("SINA_MOBILITY_HUNGER_WEIGHT"):
                cfg.hunger_weight = float(env["SINA_MOBILITY_HUNGER_WEIGHT"])
        except ValueError as exc:  # 环境变量写错不该炸掉整个仿真
            print(f"    ⚠ SINA_MOBILITY_* 环境变量非法，已回落默认值: {exc}")
        return cfg


class SocialMobilityEngine:
    """把资源存量周期性回写成 class_index 的那条边。

    每次 step() 会：
      1. 用 valuation_fn 把每个存活智能体的资源折成一个标量；
      2. 按 mode 把标量映射到 [0,1] 的目标阶级；
      3. 用 ema 从旧阶级朝目标滑动，clamp 到 floor/ceiling；
      4. 通过 memory_manager.update_social_standing() 回写，
         使其立刻影响衰减引擎与工作记忆预算；
      5. 记入 self.history —— 这是实验的 meter，不是日志。
    """

    def __init__(self, config: Optional[MobilityConfig] = None):
        self.config = config or MobilityConfig()
        self.history: List[dict] = []

    # ── 主入口 ──────────────────────────────────────────────────────────
    def maybe_step(self, sim) -> Optional[Dict[str, float]]:
        """按 interval_ticks 节流地结算一次；未启用时恒为 None。"""
        if not self.config.enabled:
            return None
        interval = max(1, int(self.config.interval_ticks))
        if sim.tick_count % interval != 0:
            return None
        return self.step(sim)

    def step(self, sim) -> Dict[str, float]:
        cfg = self.config
        valuate = cfg.valuation_fn or default_resource_valuation

        alive = [name for name, st in sim.world_agents.items() if not st.is_dead]
        if not alive:
            return {}

        resources = {
            name: float(valuate(sim.world_agents[name], sim, cfg)) for name in alive
        }
        targets = self._targets(resources)

        applied: Dict[str, float] = {}
        for name in alive:
            persona = sim.memory_manager.get_persona(name)
            if persona is None:
                continue
            old = float(persona.class_index)
            target = targets[name]
            new = old + (target - old) * max(0.0, min(1.0, cfg.ema))
            new = max(cfg.class_floor, min(cfg.class_ceiling, new))
            sim.memory_manager.update_social_standing(
                name, class_index=new, wealth_budget=resources[name]
            )
            applied[name] = new

        entry = {
            "tick": sim.tick_count,
            "class_index": dict(applied),
            "resource": dict(resources),
        }
        self.history.append(entry)
        self._log(entry)
        return applied

    # ── 映射 ────────────────────────────────────────────────────────────
    def _targets(self, resources: Dict[str, float]) -> Dict[str, float]:
        cfg = self.config

        if cfg.mode == "absolute":
            span = cfg.absolute_high - cfg.absolute_low
            if span <= 0:
                return {name: 0.5 for name in resources}
            return {
                name: max(0.0, min(1.0, (r - cfg.absolute_low) / span))
                for name, r in resources.items()
            }

        # quantile：按资源升序取分位（零和）
        names = sorted(resources, key=lambda n: (resources[n], n))
        if len(names) == 1:
            return {names[0]: 0.5}
        return {name: i / (len(names) - 1) for i, name in enumerate(names)}

    # ── 轨迹落盘 ────────────────────────────────────────────────────────
    def dump_history(self, path: str) -> str:
        """把每一步的阶级/资源轨迹写成 JSON。实验结论要靠它，别只留在内存里。"""
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
        return path

    def _log(self, entry: dict) -> None:
        ordered = sorted(entry["class_index"].items(), key=lambda kv: kv[1], reverse=True)
        pretty = " | ".join(f"{n}:{c:.2f}" for n, c in ordered)
        print(
            f"\n  🪜 社会流动结算 [mode={self.config.mode}, ema={self.config.ema:g}]"
            f"\n     阶级重排 → {pretty}"
        )
