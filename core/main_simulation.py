"""
main_simulation.py — SINA v4 主模拟循环
========================================
五阶段 tick 循环：
  Phase 0: 环境 tick（腐烂、天气、资源再生）
  Phase 1: 并行 agent 思考（asyncio.gather）
  Phase 2: 串行物理结算（settlement_engine）
  Phase 3: 提案裁决（LaplaceOracle）
  Phase 4: 模因衰减（MemePool decay）
  Phase 5: 推进时钟 + 存档
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta

from agent_state import AgentState
from action_intent import ActionIntent, Proposal
from physics_engine import PhysicsEngine, Recipe
from meme_pool import MemePool, Meme
from environment import SandboxEnvironment
from laplace_oracle import LaplaceOracle
from dynamic_engine import (
    determine_next_action,
    get_recent_memory_context,
    store_observation,
)
from settlement_engine import settle_all_intents


class SmallvilleSimulation:
    """
    SINA v4 双层架构模拟器。
    - 客观物理层：PhysicsEngine（硬编码，agent 无法篡改）
    - 主观共识层：MemePool（agent 提案 → Oracle 裁决 → 动态写入）
    """

    def __init__(self, world_name: str = "stone_age"):
        self.terminal = sys.stdout
        self.world_name = world_name
        self.environment = SandboxEnvironment(world_name=world_name)
        self.physics = PhysicsEngine(world_name=world_name)
        self.meme_pool = MemePool()
        self.oracle = LaplaceOracle()
        
        # 动态加载 prompt config
        import os, json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompt_path = os.path.join(base_dir, "worlds", world_name, "config", "prompt.json")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.world_prompt = json.load(f)
        else:
            self.world_prompt = {"community_term": "群体"}
            
        self.community_term = self.world_prompt.get("community_term", "群体")

        # ── 模拟时钟 ──
        self.clock = datetime(2026, 1, 1, 6, 0)

        # ── 提案引用（用 list 包装支持引用传递）──
        self.active_proposal: list = [None]

        # ── 全局 agent 字典 ──
        self.world_agents: dict[str, AgentState] = {}

        # ── 存档路径 ──
        self.save_file = "world_state_v3_backup.json"

        # ── tick 计数器 ──
        self.tick_count = 0

        # ── 尝试加载存档，否则从 agents.json 初始化 ──
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

    # ──────────────────────────────────────────
    # 存档加载
    # ──────────────────────────────────────────
    def _load_world_state(self, filename: str):
        """从 JSON 存档恢复完整世界状态。"""
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 恢复时钟
        self.clock = datetime.fromisoformat(data["clock"])

        # 恢复物理引擎配方
        if "physics" in data:
            self.physics = PhysicsEngine.from_dict(data["physics"])

        # 恢复模因池
        if "meme_pool" in data:
            self.meme_pool = MemePool.from_dict(data["meme_pool"])

        # 恢复 agents 并放置到房间
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
        """从 world_config.json 初始化新世界。"""
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

    # ──────────────────────────────────────────
    # 存档保存
    # ──────────────────────────────────────────
    def save_world_state(self, filename: str = "world_state_v3_backup.json"):
        """将完整世界状态序列化到 JSON。"""
        agents_data = []
        for name, agent in self.world_agents.items():
            agent_dict = agent.to_dict()
            # 记录 agent 最后所在房间（agent_locations 存的是 EnvNode 对象）
            loc_node = self.environment.agent_locations.get(name)
            agent_dict["last_room"] = loc_node.name if loc_node else self.environment.all_nodes()[0].name
            agents_data.append(agent_dict)

        state = {
            "clock": self.clock.isoformat(),
            "tick_count": self.tick_count,
            "agents": agents_data,
            "physics": self.physics.to_dict(),
            "meme_pool": self.meme_pool.to_dict(),
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    # ──────────────────────────────────────────
    # 移动执行
    # ──────────────────────────────────────────
    def execute_movement(self, agent_name: str, move_to: str):
        """解析目的地字符串并执行移动。"""
        dest_node = self.environment.get_node_by_name(move_to)
        if dest_node is None:
            print(f"  ❌ [{agent_name}] 无效目的地: {move_to}")
            return

        if dest_node.locked_by and dest_node.locked_by != agent_name:
            print(f"  🚫 [{agent_name}] 通往 {move_to} 的路被 {dest_node.locked_by} 封锁")
            return

        self.environment.move_agent(agent_name, move_to)

    # ──────────────────────────────────────────
    # 主循环
    # ──────────────────────────────────────────
    async def run_master_loop(self, ticks: int = 100):
        """
        五阶段主循环。每个 tick 模拟 15 分钟游戏内时间。
        """
        print("=" * 60)
        print("  🌍 SINA v4 — 双层架构前文明模拟器 启动")
        print("=" * 60)

        for tick in range(ticks):
            self.tick_count += 1
            time_str = self.clock.strftime("%Y-%m-%d %H:%M")
            is_night = not (6 <= self.clock.hour < 18)
            period = "🌙 夜晚" if is_night else "☀ 白天"
            weather = "阴沉" if self.tick_count % 7 == 0 else "晴朗"

            print(f"\n{'─' * 60}")
            print(f"  ⏱ Tick {self.tick_count} | {time_str} | {period} | 天气: {weather}")
            print(f"{'─' * 60}")

            # ════════════════════════════════════
            # Phase 0: 环境 Tick
            # ════════════════════════════════════
            print("\n  📍 Phase 0: 环境更新")

            # 食物腐烂
            for node in self.environment.all_nodes():
                spoiled = self.physics.resolve_spoilage(node.inventory)
                for item in spoiled:
                    print(f"    🦠 [{node.name}] {item} 腐烂了")

            # 季节影响资源再生
            season_idx = (self.tick_count // 24) % 3
            season_names = ["春季", "秋季", "凛冬"]
            current_season = season_names[season_idx]
            
            spawn_amount = 0
            if current_season == "春季":
                if self.tick_count % 2 == 0: spawn_amount = 3
            elif current_season == "秋季":
                if self.tick_count % 4 == 0: spawn_amount = 1
            elif current_season == "凛冬":
                spawn_amount = 0  # 万物凋零
            
            if spawn_amount > 0:
                df = self.environment.get_node_by_name("Dense_Forest")
                op = self.environment.get_node_by_name("Open_Plains")
                if df: df.inventory["BERRY"] = df.inventory.get("BERRY", 0) + spawn_amount
                if op: op.inventory["BERRY"] = op.inventory.get("BERRY", 0) + spawn_amount
                print(f"    🌿 [{current_season}] 自然界生长了 {spawn_amount} 个浆果")
            elif current_season == "凛冬":
                if self.tick_count % 4 == 0:
                    print(f"    ❄️ [{current_season}] 冰雪覆盖，没有任何食物生长。")

            # ════════════════════════════════════
            # Phase 1: 并行 Agent 思考
            # ════════════════════════════════════
            print("\n  🧠 Phase 1: 并行思考")
            think_tasks = []
            alive_agents = []

            for name, agent in self.world_agents.items():
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
                    # 通知同房间 agent 可以喂食
                    loc_node = self.environment.agent_locations.get(name)
                    if loc_node:
                        for other in loc_node.agents:
                            if other != name and other in self.world_agents:
                                other_agent = self.world_agents[other]
                                if not other_agent.is_dead and not other_agent.is_comatose:
                                    other_agent.pending_events.append(
                                        f"{name} 昏迷倒在地上，你可以用 give_item 喂他食物"
                                    )
                    continue

                alive_agents.append(name)

                # 构建上下文
                perception = self.environment.perceive(name)
                meme_context = self.meme_pool.get_prompt_injection(community_term=self.community_term)
                memory_context = get_recent_memory_context(agent)
                known_recipes = self.physics.get_known_recipes_description()
                loc_node = self.environment.agent_locations.get(name)
                current_room = loc_node.name if loc_node else self.environment.all_nodes()[0].name

                # 检查是否有待处理事件或需要重新决策
                has_pending = len(agent.pending_events) > 0
                has_new_faces = bool(agent.known_nearby)
                action_expired = (agent.action_end_time is None) or (self.clock >= agent.action_end_time)

                if has_pending or has_new_faces or action_expired:
                    # 将 pending_events 写入记忆
                    for event in agent.pending_events:
                        await store_observation(agent, event, self.clock)
                    agent.pending_events.clear()

                    active_prop = self.active_proposal[0]

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
                            current_time=self.clock,
                            perception=_perception,
                            meme_context=_meme_context,
                            memory_context=_memory_context,
                            current_room=_current_room,
                            active_proposal=_active_prop,
                            known_recipes_desc=_known_recipes,
                            valid_rooms=[n.name for n in self.environment.all_nodes()],
                            world_prompt=self.world_prompt,
                        )
                        # 更新 agent 行动计时器
                        duration = action.get("duration_minutes", 15)
                        _agent.current_action = action.get("observable_action", "idle")
                        _agent.action_end_time = self.clock + timedelta(minutes=duration)
                        return ActionIntent(
                            agent_name=_agent.name,
                            raw_action=action,
                            source_room=_current_room,
                        )

                    think_tasks.append(think())
                else:
                    print(f"    ⏳ {name} 仍在执行: {agent.current_action}")

            # 并行执行所有思考任务
            intents = []
            if think_tasks:
                results = await asyncio.gather(*think_tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        print(f"    ⚠ 思考异常: {r}")
                    else:
                        intent = r
                        agent = self.world_agents[intent.agent_name]
                        thought = intent.raw_action.get("internal_thought", "")
                        action_desc = intent.raw_action.get("observable_action", "")
                        print(f"    💭 {intent.agent_name}: {thought[:60]}...")
                        print(f"       → {action_desc[:60]}...")
                        intents.append(intent)

            # ════════════════════════════════════
            # Phase 2: 串行物理结算
            # ════════════════════════════════════
            print("\n  ⚙ Phase 2: 串行结算")
            if intents:
                logs = await settle_all_intents(
                    intents=intents,
                    world_agents=self.world_agents,
                    physics=self.physics,
                    environment=self.environment,
                    clock=self.clock,
                    is_night=is_night,
                )
                for log_line in logs:
                    print(log_line)
            else:
                print("    （本 tick 无行动需要结算）")

            # ════════════════════════════════════
            # Phase 3: 提案裁决
            # ════════════════════════════════════
            proposal = self.active_proposal[0]
            if proposal:
                # 检查是否所有存活 agent 都已投票
                alive_names = [
                    n for n, a in self.world_agents.items()
                    if not a.is_dead
                ]
                all_voted = all(n in proposal.votes for n in alive_names)

                if all_voted:
                    print("\n  📋 Phase 3: 提案裁决")
                    yes_count = sum(1 for v in proposal.votes.values() if v == "YES")
                    total = len(proposal.votes)

                    if yes_count == total:
                        # 全票通过 → Oracle 裁决
                        print(f"    ✅ 提案全票通过 ({yes_count}/{total})，请求 Oracle 裁决...")
                        # 收集当前科技水平
                        tech_level = [r.name for r in self.physics.recipes]
                        verdict = await self.oracle.judge(
                            proposal.content, tech_level
                        )
                        proposal.oracle_verdict = verdict
                        proposal.status = "approved"

                        verdict_type = verdict.get("verdict", "SUPERSTITION")
                        reasoning = verdict.get("reasoning", "")
                        print(f"    🔮 Oracle 裁决: {verdict_type} — {reasoning}")

                        broadcast_msg = ""
                        if verdict_type == "PHYSICS":
                            # 添加新配方到物理引擎
                            recipe_data = verdict.get("recipe", {})
                            if recipe_data:
                                new_recipe = Recipe.from_dict(recipe_data)
                                self.physics.recipes.append(new_recipe)
                                # 添加新材料属性
                                new_materials = recipe_data.get("new_material_properties", {})
                                self.physics.material_properties.update(new_materials)
                                broadcast_msg = (
                                    f"🔬 {self.community_term}发明成功！新配方「{new_recipe.name}」"
                                    f"已被自然法则验证。{new_recipe.description}"
                                )
                                print(f"    🔬 新配方: {new_recipe.name}")
                            else:
                                broadcast_msg = f"🔬 自然法则确认了这种做法的可行性: {proposal.content}"
                        elif verdict_type in ("SOCIAL", "SUPERSTITION"):
                            # 添加新模因到模因池
                            meme_data = verdict.get("meme", {})
                            if meme_data:
                                new_meme = Meme(
                                    content=meme_data.get("content", proposal.content),
                                    category=meme_data.get("category", "superstition"),
                                    proposer=proposal.proposer,
                                    penalty_description=meme_data.get("penalty_description"),
                                )
                                self.meme_pool.add_meme(new_meme)
                                broadcast_msg = (
                                    f"📿 新的{self.community_term}信念诞生: {new_meme.content}"
                                )
                                print(f"    📿 新模因: {new_meme.content}")
                            else:
                                broadcast_msg = f"📿 {self.community_term}共识已形成: {proposal.content}"

                        # 广播结果
                        for name, agent in self.world_agents.items():
                            if not agent.is_dead:
                                agent.pending_events.append(broadcast_msg)
                                await store_observation(agent, broadcast_msg, self.clock)
                    else:
                        # 未全票通过 → 驳回
                        proposal.status = "rejected"
                        reject_msg = f"❌ 提案被驳回（赞成 {yes_count}/{total}）: {proposal.content}"
                        print(f"\n  📋 Phase 3: {reject_msg}")
                        for name, agent in self.world_agents.items():
                            if not agent.is_dead:
                                agent.pending_events.append(reject_msg)
                                await store_observation(agent, reject_msg, self.clock)

                    # 清空活跃提案
                    self.active_proposal[0] = None

            # ════════════════════════════════════
            # Phase 4: 模因衰减（每 10 tick）
            # ════════════════════════════════════
            if self.tick_count % 10 == 0:
                print("\n  🧬 Phase 4: 模因衰减")
                agents_list = list(self.world_agents.values())
                removed = self.meme_pool.decay_memes(agents_list)
                if removed:
                    for meme in removed:
                        decay_msg = f"🧬 {self.community_term}信念逐渐淡忘: {meme.content}"
                        print(f"    {decay_msg}")
                        for name, agent in self.world_agents.items():
                            if not agent.is_dead:
                                agent.pending_events.append(decay_msg)
                else:
                    print("    （无模因衰减）")

            # ════════════════════════════════════
            # Phase 5: 推进时钟 + 存档
            # ════════════════════════════════════
            self.clock += timedelta(minutes=15)
            self.save_world_state()
            print(f"\n  💾 存档完成 | 下一 tick: {self.clock.strftime('%H:%M')}")

            # 打印存活状态摘要
            alive = sum(1 for a in self.world_agents.values() if not a.is_dead and not a.is_comatose)
            comatose = sum(1 for a in self.world_agents.values() if a.is_comatose)
            dead = sum(1 for a in self.world_agents.values() if a.is_dead)
            print(f"  👥 存活: {alive} | 昏迷: {comatose} | 死亡: {dead}")

        print("\n" + "=" * 60)
        print("  🏁 模拟结束")
        print("=" * 60)


# ──────────────────────────────────────────────
# DualLogger：同时输出到终端和日志文件
# ──────────────────────────────────────────────
class DualLogger:
    """将标准输出同时写入终端和日志文件。"""

    def __init__(self, filepath: str):
        self.terminal = sys.stdout
        self.log = open(filepath, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # 设置双路日志
    logger = DualLogger("live_simulation.log")
    sys.stdout = logger

    print("╔══════════════════════════════════════════════════════════╗")
    print("║  SINA v4 — 双层架构前文明多智能体模拟                     ║")
    print("║  Objective Physics Layer + Subjective Consensus Layer   ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    sim = SmallvilleSimulation()
    asyncio.run(sim.run_master_loop(ticks=3))

    # 恢复标准输出
    sys.stdout = logger.terminal
    logger.close()
    print("\n日志已保存到 live_simulation.log")
