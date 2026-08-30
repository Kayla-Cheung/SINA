import asyncio
import sys
from datetime import timedelta


from dag_engine import DAGEngine, DAGNode, NodeResult


import os
import sys
import json
from datetime import datetime

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

from environment import SandboxEnvironment
from physics_engine import PhysicsEngine
from meme_pool import MemePool
from laplace_oracle import LaplaceOracle
from agent_state import AgentState

class SinaSimulation:
    def __init__(self, world_name: str = "stone_age"):
        self.terminal = sys.stdout
        self.world_name = world_name
        self.environment = SandboxEnvironment(world_name=world_name)
        self.physics = PhysicsEngine(world_name=world_name)
        self.meme_pool = MemePool()
        self.oracle = LaplaceOracle()
        
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

        if os.path.exists(self.save_file):
            self._load_world_state(self.save_file)
            print(f"✅ 从存档 {self.save_file} 恢复世界状态")
        else:
            agents_path = os.path.join(base_dir, "worlds", world_name, "config", "agents.json")
            if os.path.exists(agents_path):
                self._load_from_config(agents_path)
                print(f"✅ 从 {agents_path} 初始化新世界")
            else:
                print(f"⚠ 未找到存档或配置文件，请创建 {agents_path}")

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
            "tick_count": self.tick_count
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

from action_intent import ActionIntent
from dynamic_engine import determine_next_action, get_recent_memory_context, store_observation
from settlement_engine import settle_all_intents
from physics_engine import Recipe
from meme_pool import Meme


# ══════════════════════════════════════════════════
# 1. 物理模块化：将原有流程切分为 6 个独立的执行算子
# ══════════════════════════════════════════════════

class EnvTickNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        print("\n  📍 Phase 0: 环境更新 [DAG算子]")
        
        # 食物腐烂
        for node in sim.environment.all_nodes():
            spoiled = sim.physics.resolve_spoilage(node.inventory)
            for item in spoiled:
                print(f"    🦠 [{node.name}] {item} 腐烂了")
                
        # 季节影响资源再生
        season_idx = (sim.tick_count // 24) % 3
        season_names = ["春季", "秋季", "凛冬"]
        current_season = season_names[season_idx]
        
        spawn_amount = 0
        if current_season == "春季":
            if sim.tick_count % 2 == 0: spawn_amount = 3
        elif current_season == "秋季":
            if sim.tick_count % 4 == 0: spawn_amount = 1
        elif current_season == "凛冬":
            spawn_amount = 0
            
        if spawn_amount > 0:
            df = sim.environment.get_node_by_name("Dense_Forest")
            op = sim.environment.get_node_by_name("Open_Plains")
            if df: df.inventory["BERRY"] = df.inventory.get("BERRY", 0) + spawn_amount
            if op: op.inventory["BERRY"] = op.inventory.get("BERRY", 0) + spawn_amount
            print(f"    🌿 [{current_season}] 自然界生长了 {spawn_amount} 个浆果")
        elif current_season == "凛冬":
            if sim.tick_count % 4 == 0:
                print(f"    ❄️ [{current_season}] 冰雪覆盖，没有任何食物生长。")
                
        return NodeResult(next_node="AgentThink")

class AgentThinkNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        print("\n  🧠 Phase 1: 并行思考 [DAG算子]")
        think_tasks = []
        alive_agents = []
        
        for name, agent in sim.world_agents.items():
            if agent.is_dead or agent.hunger <= -5:
                if not agent.is_dead:
                    print(f"    💀 {name} 因极度饥饿（饥饿度 {agent.hunger}/30）悲惨地死去了...")
                    agent.is_dead = True
                continue
            
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

            alive_agents.append(name)

            perception = sim.environment.perceive(name)
            meme_context = sim.meme_pool.get_prompt_injection(community_term=sim.community_term)
            memory_context = get_recent_memory_context(agent)
            known_recipes = sim.physics.get_known_recipes_description()
            loc_node = sim.environment.agent_locations.get(name)
            current_room = loc_node.name if loc_node else sim.environment.all_nodes()[0].name

            has_pending = len(agent.pending_events) > 0
            has_new_faces = bool(agent.known_nearby)
            action_expired = (agent.action_end_time is None) or (sim.clock >= agent.action_end_time)

            if has_pending or has_new_faces or action_expired:
                for event in agent.pending_events:
                    await store_observation(agent, event, sim.clock)
                agent.pending_events.clear()

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
                    _agent.current_action = action.get("observable_action", "idle")
                    _agent.action_end_time = sim.clock + timedelta(minutes=duration)
                    return ActionIntent(
                        agent_name=_agent.name,
                        raw_action=action,
                        source_room=_current_room,
                    )

                think_tasks.append(think())
            else:
                print(f"    ⏳ {name} 仍在执行: {agent.current_action}")

        intents = []
        if think_tasks:
            results = await asyncio.gather(*think_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    print(f"    ⚠ 思考异常: {r}")
                else:
                    intent = r
                    agent = sim.world_agents[intent.agent_name]
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
        
        print("\n  ⚙ Phase 2: 串行结算 [DAG算子]")
        if intents:
            logs = await settle_all_intents(
                intents=intents,
                world_agents=sim.world_agents,
                physics=sim.physics,
                environment=sim.environment,
                clock=sim.clock,
                is_night=is_night,
            )
            for log_line in logs:
                print(log_line)
        else:
            print("    （本 tick 无行动需要结算）")
            
        return NodeResult(next_node="OracleJudge")


class OracleJudgeNode(DAGNode):
    async def execute(self, state):
        sim = state["sim"]
        proposal = sim.active_proposal[0]
        if proposal:
            alive_names = [n for n, a in sim.world_agents.items() if not a.is_dead]
            all_voted = all(n in proposal.votes for n in alive_names)

            if all_voted:
                print("\n  📋 Phase 3: 提案裁决 [DAG算子]")
                yes_count = sum(1 for v in proposal.votes.values() if v == "YES")
                total = len(proposal.votes)

                if yes_count == total:
                    print(f"    ✅ 提案全票通过 ({yes_count}/{total})，请求 Oracle 裁决...")
                    tech_level = [r.name for r in sim.physics.recipes]
                    verdict = await sim.oracle.judge(proposal.content, tech_level)
                    proposal.oracle_verdict = verdict
                    proposal.status = "approved"

                    verdict_type = verdict.get("verdict", "SUPERSTITION")
                    reasoning = verdict.get("reasoning", "")
                    print(f"    🔮 Oracle 裁决: {verdict_type} — {reasoning}")

                    broadcast_msg = ""
                    if verdict_type == "PHYSICS":
                        recipe_data = verdict.get("recipe", {})
                        if recipe_data:
                            new_recipe = Recipe.from_dict(recipe_data)
                            sim.physics.recipes.append(new_recipe)
                            new_materials = recipe_data.get("new_material_properties", {})
                            sim.physics.material_properties.update(new_materials)
                            broadcast_msg = f"🔬 {sim.community_term}发明成功！新配方「{new_recipe.name}」已被自然法则验证。{new_recipe.description}"
                            print(f"    🔬 新配方: {new_recipe.name}")
                        else:
                            broadcast_msg = f"🔬 自然法则确认了这种做法的可行性: {proposal.content}"
                    elif verdict_type in ("SOCIAL", "SUPERSTITION"):
                        meme_data = verdict.get("meme", {})
                        if meme_data:
                            new_meme = Meme(
                                content=meme_data.get("content", proposal.content),
                                category=meme_data.get("category", "superstition"),
                                proposer=proposal.proposer,
                                penalty_description=meme_data.get("penalty_description"),
                            )
                            sim.meme_pool.add_meme(new_meme)
                            broadcast_msg = f"📿 新的{sim.community_term}信念诞生: {new_meme.content}"
                            print(f"    📿 新模因: {new_meme.content}")
                        else:
                            broadcast_msg = f"📿 {sim.community_term}共识已形成: {proposal.content}"
                    for name, agent in sim.world_agents.items():
                        if not agent.is_dead:
                            agent.pending_events.append(broadcast_msg)
                            await store_observation(agent, broadcast_msg, sim.clock)
                else:
                    proposal.status = "rejected"
                    reject_msg = f"❌ 提案被驳回（赞成 {yes_count}/{total}）: {proposal.content}"
                    print(f"\n  📋 Phase 3: {reject_msg}")
                    for name, agent in sim.world_agents.items():
                        if not agent.is_dead:
                            agent.pending_events.append(reject_msg)
                            await store_observation(agent, reject_msg, sim.clock)

                sim.active_proposal[0] = None
                
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
        
        # 环形路由判断：如果没有跑完目标 Ticks，返回到 EnvTick
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


# ══════════════════════════════════════════════════
# 2. 模拟器继承与重载
# ══════════════════════════════════════════════════

class DAGSmallvilleSimulation(SinaSimulation):
    """
    继承原有的存档读写和变量定义。
    抛弃旧的 run_master_loop，注入纯净的 DAGEngine 作为世界驱动心脏。
    """
    async def run_dag_loop(self, ticks: int = 100):
        print("=" * 60)
        print("  🌍 SINA v4 — 双层架构前文明模拟器 [DAG 重构版] 启动")
        print("=" * 60)
        
        # 构建 DAG
        engine = DAGEngine()
        engine.register_node(EnvTickNode("EnvTick"))
        engine.register_node(AgentThinkNode("AgentThink"))
        engine.register_node(PhysicsSettleNode("PhysicsSettle"))
        engine.register_node(OracleJudgeNode("OracleJudge"))
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
            
            # 把主模拟器作为 global_state 喂给所有 Node
            await engine.run(start_node="EnvTick", initial_state={"sim": self, "target_ticks": self.tick_count - 1 + ticks})
            
        print("\n" + "=" * 60)
        print("  🏁 模拟结束 (DAG 引擎安全停机)")
        print("=" * 60)


if __name__ == "__main__":
    logger = DualLogger("live_simulation_dag.log")
    sys.stdout = logger
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SINA v4 — DAG ENGINE REFACTOR                           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    sim = DAGSmallvilleSimulation()
    # 临时打个 3 Tick 的包络测试
    asyncio.run(sim.run_dag_loop(ticks=3))
    
    sys.stdout = logger.terminal
    logger.close()
    print("\n日志已保存到 live_simulation_dag.log")
