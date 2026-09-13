"""
dag_simulation.py — SINA v4 双层架构前文明模拟器 [DAG 重构核心]
================================================================
主推演循环统一架构：
  1. 行动租约与中断引擎 (ActionInertiaEngine)：多 Tick 租约消减 60%~70% 无效 Token
  2. 分层阶层记忆系统 (HierarchicalMemoryManager)：L0 不变本体 + L1 双层工作记忆 + L2 向量库
  3. 现实校验与实体门控 (RealityCheckMiddleware)：结算顶层物理硬拦截
  4. 决策民主化：多数制 (>66%) 替代全票死锁
  5. 原生知识星图 (ObsidianSyncNode)：每一次推演实时驱动 Obsidian Vault 渲染
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta

try:
    from .dag_engine import DAGEngine, DAGNode, NodeResult
    from .action_lease import ActionInertiaEngine, ActionLease
    from .action_intent import ActionIntent
    from .dynamic_engine import determine_next_action, store_observation
    from .settlement_engine import settle_all_intents
    from .physics_engine import Recipe, PhysicsEngine
    from .meme_pool import Meme, MemePool
    from .environment import SandboxEnvironment
    from .laplace_oracle import LaplaceOracle
    from .agent_state import AgentState
except ImportError:
    from dag_engine import DAGEngine, DAGNode, NodeResult
    from action_lease import ActionInertiaEngine, ActionLease
    from action_intent import ActionIntent
    from dynamic_engine import determine_next_action, store_observation
    from settlement_engine import settle_all_intents
    from physics_engine import Recipe, PhysicsEngine
    from meme_pool import Meme, MemePool
    from environment import SandboxEnvironment
    from laplace_oracle import LaplaceOracle
    from agent_state import AgentState

from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.types import PersonaInvariant, MemoryType
from sina.observer.obsidian_vault import ObsidianVaultObserver


class DualLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


class SinaSimulation:
    def __init__(self, world_name: str = "smallville"):
        self.terminal = sys.stdout
        self.world_name = world_name
        self.environment = SandboxEnvironment(world_name=world_name)
        self.physics = PhysicsEngine(world_name=world_name)
        self.meme_pool = MemePool()
        self.oracle = LaplaceOracle()

        # 核心挂载：行动租约状态机与分层记忆管理器
        self.action_inertia_engine = ActionInertiaEngine()
        self.memory_manager = HierarchicalMemoryManager()

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(base_dir, "worlds", world_name, "config", "prompt.json")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.world_prompt = json.load(f)
        else:
            self.world_prompt = {"community_term": "群体"}

        self.community_term = self.world_prompt.get("community_term", "群体")
        self.clock = datetime(2026, 1, 1, 6, 0)
        self.active_proposal = [None]
        self.world_agents = {}
        self.save_file = "world_state_v3_backup.json"
        self.tick_count = 0
        self.current_logs = []

        # 挂载 Obsidian 原生图谱观测器
        vault_dir = os.path.join(base_dir, "obsidian_vault")
        self.observer = ObsidianVaultObserver(vault_dir=vault_dir)

        agents_path = os.path.join(base_dir, "worlds", world_name, "config", "agents.json")
        if os.path.exists(agents_path):
            self._load_from_config(agents_path)
            print(f"✅ 从 {agents_path} 初始化新世界并挂载分层记忆体系")
        elif os.path.exists(self.save_file):
            self._load_world_state(self.save_file)
            print(f"✅ 从存档 {self.save_file} 恢复世界状态")
        else:
            print(f"⚠ 未找到存档或配置文件，请检查 {agents_path}")

    def _register_agent_memory(self, name: str, agent_cfg: dict):
        """将智能体注册到分层阶层记忆系统中"""
        wealth = agent_cfg.get("wealth", 100)
        class_index = agent_cfg.get("class_index", 0.5)
        archetype = agent_cfg.get("archetype", "Forager")
        p = PersonaInvariant(
            agent_id=name,
            name=name,
            core_conviction=f"{name} 努力在{self.community_term}中生存与发展",
            archetype=archetype,
            class_index=class_index,
            wealth_budget=float(wealth),
        )
        self.memory_manager.register_agent(p, token_threshold=max(5, int(wealth / 20.0)))

    def _load_world_state(self, filename: str):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.clock = datetime.fromisoformat(data["clock"])
        if "physics" in data:
            self.physics = PhysicsEngine.from_dict(data["physics"])
        if "meme_pool" in data:
            self.meme_pool = MemePool.from_dict(data["meme_pool"])
        for agent_data in data.get("agents", []):
            agent = AgentState.from_dict(agent_data)
            self.world_agents[agent.name] = agent
            self._register_agent_memory(agent.name, agent_data)
            last_room = agent_data.get("last_room", self.environment.all_nodes()[0].name)
            node = self.environment.get_node_by_name(last_room)
            if node:
                self.environment.spawn_agent(agent.name, node)
            else:
                self.environment.spawn_agent(agent.name, self.environment.all_nodes()[0])
        self.tick_count = data.get("tick_count", 0)

    def _load_from_config(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        for agent_cfg in config.get("agents", []):
            agent = AgentState(
                name=agent_cfg["name"],
                traits=agent_cfg.get("traits", "普通原始人"),
                intentions=agent_cfg.get("intentions", []),
                start_time=self.clock,
            )
            agent.hunger = agent_cfg.get("hunger", 30)
            if agent_cfg.get("inventory"):
                agent.inventory = agent_cfg["inventory"]
            self.world_agents[agent.name] = agent
            self._register_agent_memory(agent.name, agent_cfg)

            start_room = agent_cfg.get("start_room", self.environment.all_nodes()[0].name)
            node = self.environment.get_node_by_name(start_room)
            if node:
                self.environment.spawn_agent(agent.name, node)
            else:
                self.environment.spawn_agent(agent.name, self.environment.all_nodes()[0])

    def save_world_state(self, filename: str = "world_state_v3_backup.json"):
        agents_data = []
        for name, agent in self.world_agents.items():
            agent_dict = agent.to_dict()
            loc_node = self.environment.agent_locations.get(name)
            agent_dict["last_room"] = loc_node.name if loc_node else self.environment.all_nodes()[0].name
            agents_data.append(agent_dict)

        data = {
            "clock": self.clock.isoformat(),
            "physics": self.physics.to_dict(),
            "meme_pool": self.meme_pool.to_dict(),
            "agents": agents_data,
            "tick_count": self.tick_count,
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ======================================================================
# DAG 算子定义
# ======================================================================

class EnvTickNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        print("\n  🌱 Phase 0: 环境生息 [DAG算子]")
        for node in sim.environment.all_nodes():
            sim.physics.resolve_spoilage(node.inventory)
        for agent in sim.world_agents.values():
            if not agent.is_dead:
                sim.physics.resolve_spoilage(agent.inventory)

        seasons = ["春生", "盛夏", "秋收", "凛冬"]
        season_index = (sim.tick_count // 40) % len(seasons)
        current_season = seasons[season_index]
        state["current_season"] = current_season

        # 商业节点资源补给 (如 Cafe, Supermarket)
        cafe_node = sim.environment.get_node_by_name("Cafe")
        if cafe_node:
            cafe_node.inventory["COFFEE"] = cafe_node.inventory.get("COFFEE", 0) + 1
            cafe_node.inventory["PASTRY"] = cafe_node.inventory.get("PASTRY", 0) + 1

        market_node = sim.environment.get_node_by_name("Supermarket")
        if market_node:
            market_node.inventory["BREAD"] = market_node.inventory.get("BREAD", 0) + 1
            market_node.inventory["APPLE"] = market_node.inventory.get("APPLE", 0) + 1

        return NodeResult(next_node="AgentThink")


class AgentThinkNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        print("\n  🧠 Phase 1: 并行思考与租约调度 [DAG算子]")
        think_tasks = []
        intents = []

        for name, agent in sim.world_agents.items():
            # 1. 死亡与掉落
            if agent.is_dead or agent.hunger <= -5:
                if not agent.is_dead:
                    print(f"    💀 {name} 因极度饥饿（饥饿度 {agent.hunger}/30）死去了...")
                    agent.is_dead = True
                    loc_node = sim.environment.agent_locations.get(name)
                    if loc_node and agent.inventory:
                        for item, count in agent.inventory.items():
                            loc_node.inventory[item] = loc_node.inventory.get(item, 0) + count
                        agent.inventory = {}
                continue

            # 2. 昏迷判定
            if agent.hunger <= 0 and not agent.is_comatose:
                print(f"    [昏迷] {name} 因极度饥饿倒地昏迷！")
                agent.is_comatose = True

            if agent.is_comatose:
                print(f"    😵 {name} 处于昏迷状态（饥饿度 {agent.hunger}/30）")
                loc_node = sim.environment.agent_locations.get(name)
                if loc_node:
                    for other in loc_node.agents:
                        if other != name and other in sim.world_agents:
                            other_agent = sim.world_agents[other]
                            if not other_agent.is_dead and not other_agent.is_comatose:
                                other_agent.pending_events.append(
                                    f"{name} 昏迷倒在地上，你可以用 give_item 喂他食物"
                                )
                continue

            loc_node = sim.environment.agent_locations.get(name)
            current_room = loc_node.name if loc_node else sim.environment.all_nodes()[0].name

            # 3. 行动租约与突发中断矩阵评估 (Action Inertia Engine)
            need_think, wake_reason, active_lease = sim.action_inertia_engine.evaluate_agent_lease(
                name, agent.pending_events
            )

            # 4. 租约有效且未受致命扰动：跳过 LLM，由底层物理 FSM 推进
            if not need_think and active_lease:
                print(f"    ⏳ {name} [租约惯性: 剩余{active_lease.ticks_remaining}帧] {active_lease.description}")
                intents.append(ActionIntent(
                    agent_name=name,
                    raw_action={
                        "internal_thought": f"[惯性执行中] {active_lease.description}",
                        "observable_action": active_lease.description,
                    },
                    source_room=current_room,
                ))
                continue

            # 5. 必须唤醒大模型思考回路
            if wake_reason:
                print(f"    🔔 {name} [唤醒思考] 原因: {wake_reason}")

            # 将 pending_events 沉淀到分层记忆管理器
            for event in agent.pending_events:
                sim.memory_manager.record_event(
                    agent_id=name,
                    tick=sim.tick_count,
                    content=event,
                    memory_type=MemoryType.OBSERVATION,
                    location=current_room,
                )
            agent.pending_events.clear()

            # 使用分层记忆管理器组装上下文 (L0 不变本体 + L1 双层工作记忆 + L2 检索)
            memory_context = sim.memory_manager.assemble_prompt_context(name)

            perception = sim.environment.perceive(name)
            meme_context = sim.meme_pool.get_prompt_injection(community_term=sim.community_term)
            known_recipes = sim.physics.get_known_recipes_description()
            active_prop = sim.active_proposal[0]

            async def think(
                _agent=agent,
                _current_room=current_room,
                _perception=perception,
                _meme_context=meme_context,
                _memory_context=memory_context,
                _known_recipes=known_recipes,
                _active_prop=active_prop,
            ):
                action = await determine_next_action(
                    state=_agent,
                    current_time=sim.clock,
                    perception=_perception,
                    meme_context=_meme_context,
                    memory_context=_memory_context,
                    current_room=_current_room,
                    active_proposal=_active_prop,
                    known_recipes_desc=_known_recipes,
                    valid_rooms=[n.name for n in sim.environment.all_nodes()],
                    world_prompt=sim.world_prompt,
                )
                duration = action.get("duration_minutes", 15)
                action_desc = action.get("observable_action", "idle")
                _agent.current_action = action_desc
                _agent.action_end_time = sim.clock + timedelta(minutes=duration)

                # 颁发新的多 Tick 行动租约
                duration_ticks = max(1, duration // 15)
                sim.action_inertia_engine.grant_lease(
                    agent_name=_agent.name,
                    action_type=action.get("action_type", "wander"),
                    description=action_desc,
                    duration_ticks=duration_ticks,
                    payload=action,
                )

                return ActionIntent(
                    agent_name=_agent.name,
                    raw_action=action,
                    source_room=_current_room,
                )

            think_tasks.append(think())

        if think_tasks:
            results = await asyncio.gather(*think_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    print(f"    ⚠ 思考异常: {r}")
                else:
                    intent = r
                    thought = intent.raw_action.get("internal_thought", "")
                    action_desc = intent.raw_action.get("observable_action", "")
                    print(f"    💭 {intent.agent_name}: {thought[:60]}...")
                    print(f"       → {action_desc[:60]}...")
                    intents.append(intent)

        return NodeResult(next_node="PhysicsSettle", payload={"current_intents": intents})


class PhysicsSettleNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        intents = state.get("current_intents", [])
        is_night = not (6 <= sim.clock.hour < 18)

        print("\n  ⚙ Phase 2: 物理结算与真实性拦截 [DAG算子]")
        if intents:
            # 彻底消除 None：传入真实 memory_manager，开启真实性拦截与事件自动沉淀
            logs = await settle_all_intents(
                intents=intents,
                world_agents=sim.world_agents,
                physics=sim.physics,
                environment=sim.environment,
                clock=sim.clock,
                is_night=is_night,
                active_proposal=sim.active_proposal,
                memory_manager=sim.memory_manager,
                tick=sim.tick_count,
            )
            sim.current_logs = logs
            for log_line in logs:
                print(log_line)
        else:
            sim.current_logs = []
            print("    （本 tick 无行动需要结算）")

        return NodeResult(next_node="OracleJudge", payload={"current_intents": intents})


class OracleJudgeNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        proposal = sim.active_proposal[0]
        if proposal:
            alive_names = [n for n, a in sim.world_agents.items() if not a.is_dead and not a.is_comatose]
            all_voted = len(alive_names) > 0 and all(n in proposal.votes for n in alive_names)
            expired = sim.tick_count >= getattr(proposal, "expire_tick", sim.tick_count + 4)

            if all_voted or expired:
                status_reason = "全员出席已投票" if all_voted else f"投票窗口期满 (截止第 {getattr(proposal, 'expire_tick', sim.tick_count)} 帧)"
                print(f"\n  📋 Phase 3: 提案收官裁决 [{status_reason}] [DAG算子]")
                yes_count = proposal.approval_count
                total_voted = len(proposal.votes)

                # 法定多数制：已投选票中赞成率 >= 66%，且至少有 1 票
                if total_voted > 0 and (yes_count / total_voted) >= 0.66:
                    print(f"    ✅ 提案多数通过 ({yes_count}/{total_voted} 赞成)，请求 Oracle 裁决...")
                    tech_level = [r.name for r in sim.physics.recipes]
                    verdict = await sim.oracle.judge(proposal.content, tech_level)
                    proposal.oracle_verdict = verdict
                    proposal.status = "approved"

                    verdict_type = getattr(verdict, "verdict", "SUPERSTITION")
                    reasoning = getattr(verdict, "reasoning", "")
                    print(f"    🔮 Oracle 裁决: {verdict_type} — {reasoning}")

                    broadcast_msg = ""
                    if verdict_type == "PHYSICS":
                        recipe_obj = getattr(verdict, "recipe", None)
                        if recipe_obj:
                            new_recipe = Recipe.from_dict(recipe_obj.model_dump() if hasattr(recipe_obj, 'model_dump') else recipe_obj.dict())
                            sim.physics.recipes.append(new_recipe)
                            if recipe_obj.new_material_properties:
                                sim.physics.material_properties.update(recipe_obj.new_material_properties)
                            broadcast_msg = f"🔬 {sim.community_term}发明成功！新配方「{new_recipe.name}」已被自然法则验证。{new_recipe.description}"
                            print(f"    🔬 新配方: {new_recipe.name}")
                        else:
                            broadcast_msg = f"🔬 自然法则确认了这种做法的可行性: {proposal.content}"
                    elif verdict_type in ("SOCIAL", "SUPERSTITION"):
                        meme_obj = getattr(verdict, "meme", None)
                        if meme_obj:
                            new_meme = Meme(
                                content=meme_obj.content,
                                category=meme_obj.category,
                                proposer=proposal.proposer,
                                penalty_description=meme_obj.penalty_description,
                            )
                            sim.meme_pool.add_meme(new_meme)
                            broadcast_msg = f"📿 新的{sim.community_term}信念诞生: {new_meme.content}"
                            print(f"    📿 新模因: {new_meme.content}")
                        else:
                            broadcast_msg = f"📿 {sim.community_term}共识已形成: {proposal.content}"

                    for name, agent in sim.world_agents.items():
                        if not agent.is_dead:
                            agent.pending_events.append(broadcast_msg)
                            sim.memory_manager.record_event(
                                agent_id=name,
                                tick=sim.tick_count,
                                content=broadcast_msg,
                                location=sim.environment.agent_locations.get(name).name if sim.environment.agent_locations.get(name) else "Cafe",
                            )
                else:
                    proposal.status = "rejected"
                    reject_msg = f"❌ 提案未达多数通过（赞成 {yes_count}/{total_voted}）: {proposal.content}"
                    print(f"\n  📋 Phase 3: {reject_msg}")
                    for name, agent in sim.world_agents.items():
                        if not agent.is_dead:
                            agent.pending_events.append(reject_msg)

                sim.active_proposal[0] = None
            else:
                remaining_ticks = getattr(proposal, "expire_tick", sim.tick_count + 4) - sim.tick_count
                print(f"\n  📋 Phase 3: 提案审议中 (已收 {len(proposal.votes)}/{len(alive_names)} 票，窗口剩余 {remaining_ticks} 帧): 「{proposal.content[:30]}...」")

        return NodeResult(next_node="ObsidianSync", payload=state)


class ObsidianSyncNode(DAGNode):
    """原生知识星图同步算子：全真推演实时驱动 Obsidian Vault 增量上图"""
    async def execute(self, state):
        sim = state["sim"]
        current_intents = state.get("current_intents", [])
        logs = getattr(sim, "current_logs", [])

        if hasattr(sim, "observer") and sim.observer:
            print("\n  🗺 Phase 3.5: Obsidian 星图同步 [DAG算子]")
            sim.observer.sync_tick(
                sim=sim,
                current_intents=current_intents,
                settlement_logs=logs,
                memory_manager=sim.memory_manager,
            )
        return NodeResult(next_node="MemeDecay")


class MemeDecayNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        if sim.tick_count % 10 == 0:
            print("\n  🧬 Phase 4: 模因衰减 [DAG算子]")
            agents_list = list(sim.world_agents.values())
            removed = sim.meme_pool.decay_memes(agents_list)
            if removed:
                for meme in removed:
                    decay_msg = f"🧬 {sim.community_term}信念逐渐淡忘: {meme.content}"
                    print(f"    {decay_msg}")
                    for name, agent in sim.world_agents.items():
                        if not agent.is_dead:
                            agent.pending_events.append(decay_msg)
            else:
                print("    （无模因衰减）")
        return NodeResult(next_node="ClockTick")


class ClockTickNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        target_ticks = state["target_ticks"]

        sim.clock += timedelta(minutes=15)
        sim.save_world_state()
        print(f"\n  💾 存档完成 | 下一 tick: {sim.clock.strftime('%H:%M')}")

        alive = sum(1 for a in sim.world_agents.values() if not a.is_dead and not a.is_comatose)
        comatose = sum(1 for a in sim.world_agents.values() if a.is_comatose)
        dead = sum(1 for a in sim.world_agents.values() if a.is_dead)
        print(f"  👥 存活: {alive} | 昏迷: {comatose} | 死亡: {dead}")

        if sim.tick_count < target_ticks:
            sim.tick_count += 1
            time_str = sim.clock.strftime("%Y-%m-%d %H:%M")
            is_night = not (6 <= sim.clock.hour < 18)
            period = "🌙 夜晚" if is_night else "☀ 白天"
            weather = "阴沉" if sim.tick_count % 7 == 0 else "晴朗"

            print(f"\n{'─' * 60}")
            print(f"  ⏱ Tick {sim.tick_count} | {time_str} | {period} | 天气: {weather} (DAG Engine)")
            print(f"{'─' * 60}")
            return NodeResult(next_node="EnvTick")
        else:
            return NodeResult(next_node=None)


# ======================================================================
# 统一入口主模拟器
# ======================================================================

class DAGSmallvilleSimulation(SinaSimulation):
    """
    SINA 2.0 统一推演引擎：
    驱动真实大模型、行动租约、分层记忆与 Obsidian 原生星图。
    """
    async def run_dag_loop(self, ticks: int = 100):
        print("=" * 60)
        print("  🌍 SINA v4/2.0 — 统一社会世界模型 [DAG 全链路] 启动")
        print("=" * 60)

        engine = DAGEngine()
        engine.register_node(EnvTickNode("EnvTick"))
        engine.register_node(AgentThinkNode("AgentThink"))
        engine.register_node(PhysicsSettleNode("PhysicsSettle"))
        engine.register_node(OracleJudgeNode("OracleJudge"))
        engine.register_node(ObsidianSyncNode("ObsidianSync"))
        engine.register_node(MemeDecayNode("MemeDecay"))
        engine.register_node(ClockTickNode("ClockTick"))

        if ticks > 0:
            self.tick_count += 1
            time_str = self.clock.strftime("%Y-%m-%d %H:%M")
            is_night = not (6 <= self.clock.hour < 18)
            period = "🌙 夜晚" if is_night else "☀ 白天"
            weather = "阴沉" if self.tick_count % 7 == 0 else "晴朗"

            print(f"\n{'─' * 60}")
            print(f"  ⏱ Tick {self.tick_count} | {time_str} | {period} | 天气: {weather} (DAG Engine)")
            print(f"{'─' * 60}")

            await engine.run(
                start_node="EnvTick",
                initial_state={"sim": self, "target_ticks": self.tick_count - 1 + ticks}
            )

        print("\n" + "=" * 60)
        print("  🏁 模拟结束 (DAG 引擎安全停机)")
        print("=" * 60)


if __name__ == "__main__":
    logger = DualLogger("live_simulation_dag.log")
    sys.stdout = logger
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SINA v4 — UNIFIED DAG ENGINE WITH MEMORY & OBSIDIAN    ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    sim = DAGSmallvilleSimulation()
    asyncio.run(sim.run_dag_loop(ticks=3))

    sys.stdout = logger.terminal
    logger.close()
    print("\n日志已保存到 live_simulation_dag.log")
