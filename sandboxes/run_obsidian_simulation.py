"""
Interactive Multi-Agent Simulation Sandbox with Real-Time Obsidian Vault Graph Sync.
Runs discrete ticks, executes memory bifurcation/settlement, and writes live Markdown notes
directly into `obsidian_vault/` for instant Force-Directed Star Map rendering in Obsidian.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.environment import SandboxEnvironment, EnvNode
from core.agent_state import AgentState
from core.physics_engine import PhysicsEngine
from core.action_intent import ActionIntent, Proposal
from core.settlement_engine import settle_all_intents
from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.types import PersonaInvariant, MemoryType
from sina.observer.obsidian_vault import ObsidianVaultObserver


class StandaloneWorld:
    """A clean, standalone multi-agent simulation world for interactive experimentation."""

    def __init__(self, vault_path: str, world_name: str = "smallville"):
        self.clock = datetime(2026, 1, 1, 8, 0)
        self.tick_count = 0
        self.active_proposal = [None]
        self.current_logs = []

        # 1. Spatial Topology
        self.environment = SandboxEnvironment(world_name=world_name)
        
        # 2. Physics Substrate
        self.physics = PhysicsEngine(world_name=world_name)

        # 3. Hierarchical Memory Subsystem
        self.memory_manager = HierarchicalMemoryManager(default_token_threshold=150)

        # 4. Observer: Obsidian Vault Syncer (Pure Macro Sociological Swarm)
        self.observer = ObsidianVaultObserver(vault_dir=vault_path, macro_only=True)

        # 5. Initialize Agents
        self.world_agents: dict[str, AgentState] = {}
        self._init_society()

    def _init_society(self):
        """Create a diverse 6-agent modern town society (Smallville)."""
        agents_data = [
            {
                "name": "Isabella",
                "archetype": "Merchant_Host",
                "traits": "热情、专注、经营一家温馨的街角咖啡馆",
                "conviction": "营造温暖社区空间，维持咖啡馆生计与人际联结",
                "class_index": 0.75,
                "wealth": 2800.0,
                "start_room": "Cafe",
                "inventory": {"COFFEE": 5, "PASTRY": 3, "MONEY": 80},
                "hunger": 25,
            },
            {
                "name": "Tom",
                "archetype": "Creative_Writer",
                "traits": "内向、喜欢安静、自由小说撰稿人",
                "conviction": "追求文学纯粹性与精神宁静，记录小镇日常",
                "class_index": 0.55,
                "wealth": 1500.0,
                "start_room": "Library",
                "inventory": {"BOOK": 2, "MONEY": 50},
                "hunger": 20,
            },
            {
                "name": "Klaus",
                "archetype": "Ambitious_Student",
                "traits": "充满活力、求知欲强、在校备考大学生",
                "conviction": "通过学术考试提升社会阶层与探索前沿知识",
                "class_index": 0.45,
                "wealth": 900.0,
                "start_room": "Park",
                "inventory": {"BOOK": 1, "APPLE": 2, "MONEY": 20},
                "hunger": 22,
            },
            {
                "name": "Maria",
                "archetype": "Naturalist_Educator",
                "traits": "细心、热爱自然与教育、植物学家与公立学校教师",
                "conviction": "守护小镇生态多样性与培育下一代科学素养",
                "class_index": 0.70,
                "wealth": 2200.0,
                "start_room": "School",
                "inventory": {"BREAD": 2, "WATER": 3},
                "hunger": 24,
            },
            {
                "name": "Sam",
                "archetype": "Pragmatic_Engineer",
                "traits": "务实、动手能力强、小镇综合维护工程师",
                "conviction": "保障小镇公共基础设施运转与邻里互助协作",
                "class_index": 0.60,
                "wealth": 1800.0,
                "start_room": "Supermarket",
                "inventory": {"WATER": 2, "MONEY": 40},
                "hunger": 20,
            },
            {
                "name": "Ryan",
                "archetype": "Cyber_Nomad",
                "traits": "焦虑、工作狂、远程软件工程师",
                "conviction": "通过技术效率掌控财富，寻求数字游民的自由",
                "class_index": 0.85,
                "wealth": 3800.0,
                "start_room": "Cafe",
                "inventory": {"COFFEE": 2, "MONEY": 120},
                "hunger": 18,
            },
        ]

        for data in agents_data:
            name = data["name"]
            agent = AgentState(
                name=name,
                traits=data["traits"],
                intentions=["经营生活", "探索小镇", "建立社区联结"],
                start_time=self.clock,
            )
            agent.hunger = data["hunger"]
            agent.inventory = data["inventory"]
            self.world_agents[name] = agent

            # Place in spatial node
            node = self.environment.get_node_by_name(data["start_room"])
            if node:
                self.environment.spawn_agent(name, node)

            # Register into Hierarchical Memory Subsystem
            p = PersonaInvariant(
                agent_id=name,
                name=name,
                archetype=data["archetype"],
                core_conviction=data["conviction"],
                class_index=data["class_index"],
                wealth_budget=data["wealth"],
            )
            self.memory_manager.register_agent(p, token_threshold=int(data["wealth"] / 20.0))

    async def step(self, custom_event: str = None) -> list[str]:
        """Execute 1 discrete tick of simulation."""
        self.tick_count += 1
        self.clock += timedelta(minutes=15)
        is_night = not (6 <= self.clock.hour < 21)
        
        # 1. Environment Phase: Spoilage & Town Resource Replenishment
        for node in self.environment.all_nodes():
            self.physics.resolve_spoilage(node.inventory)
        for agent in self.world_agents.values():
            if not agent.is_dead:
                self.physics.resolve_spoilage(agent.inventory)

        # Commercial inventory replenishment (Cafe & Supermarket)
        cafe_node = self.environment.get_node_by_name("Cafe")
        if cafe_node:
            cafe_node.inventory["COFFEE"] = cafe_node.inventory.get("COFFEE", 0) + 1
            cafe_node.inventory["PASTRY"] = cafe_node.inventory.get("PASTRY", 0) + 1

        market_node = self.environment.get_node_by_name("Supermarket")
        if market_node:
            market_node.inventory["BREAD"] = market_node.inventory.get("BREAD", 0) + 1
            market_node.inventory["APPLE"] = market_node.inventory.get("APPLE", 0) + 1

        # 2. Agent Decision & Synthetic Intent Phase
        intents = []
        for name, agent in self.world_agents.items():
            if agent.is_dead:
                continue

            # Metabolism
            agent.hunger = max(-5, agent.hunger - 1)
            if agent.hunger <= -5:
                agent.is_dead = True
                loc = self.environment.agent_locations.get(name)
                if loc and agent.inventory:
                    for item, count in agent.inventory.items():
                        loc.inventory[item] = loc.inventory.get(item, 0) + count
                    agent.inventory = {}
                continue

            if agent.hunger <= 0 and not agent.is_comatose:
                agent.is_comatose = True

            if agent.is_comatose:
                continue

            # Record observation into Hierarchical Memory
            loc_node = self.environment.agent_locations.get(name)
            room_name = loc_node.name if loc_node else "Cafe"
            
            obs_text = f"在小镇 {room_name} 感到身体精力为 {agent.hunger}/30。"
            if custom_event and name in ("Isabella", "Tom", "Ryan"):
                obs_text += f" 【小镇热点】{custom_event}"

            self.memory_manager.record_event(
                agent_id=name,
                tick=self.tick_count,
                content=obs_text,
                memory_type=MemoryType.OBSERVATION,
                location=room_name,
            )

            # Heuristic simulation intention for modern town
            action_dict = self._simulate_heuristic_intent(name, agent, loc_node)
            agent.current_action = action_dict.get("observable_action", "在小镇漫步")
            intents.append(ActionIntent(agent_name=name, raw_action=action_dict, source_room=room_name))

        # 3. Settle Phase
        logs = await settle_all_intents(
            intents=intents,
            world_agents=self.world_agents,
            physics=self.physics,
            environment=self.environment,
            clock=self.clock,
            is_night=is_night,
            active_proposal=self.active_proposal,
            memory_manager=self.memory_manager,
            tick=self.tick_count,
        )
        self.current_logs = logs

        # 4. Sync State to Obsidian Vault
        self.observer.sync_tick(
            sim=self,
            current_intents=intents,
            settlement_logs=logs,
            memory_manager=self.memory_manager,
        )

        return logs

    def _simulate_heuristic_intent(self, name: str, agent: AgentState, current_room: EnvNode) -> dict:
        """Heuristic decision logic for modern Smallville town simulation."""
        # 1. If hungry (< 18) and has modern food/beverage, consume
        if agent.hunger < 18:
            for food in ["PASTRY", "BREAD", "APPLE", "COFFEE"]:
                if agent.inventory.get(food, 0) > 0:
                    return {
                        "internal_thought": f"有点饿了，先享用一份 {food} 补充能量。",
                        "observable_action": f"正在品尝美味的 {food}",
                        "eat_item": food,
                    }

        # 2. If in Cafe with pastries/coffee, take/buy
        if current_room and current_room.name == "Cafe":
            for item in ["COFFEE", "PASTRY"]:
                if current_room.inventory.get(item, 0) > 0 and agent.inventory.get(item, 0) == 0:
                    return {
                        "internal_thought": f"闻到咖啡馆的香气，购买一份 {item}。",
                        "observable_action": f"在咖啡馆点了一份新鲜的 {item}",
                        "take_item_tag": item,
                    }

        # 3. If in Supermarket, purchase bread or apples
        if current_room and current_room.name == "Supermarket":
            for item in ["BREAD", "APPLE"]:
                if current_room.inventory.get(item, 0) > 0 and agent.inventory.get(item, 0) == 0:
                    return {
                        "internal_thought": f"在超市货架前选购日常食品 {item}。",
                        "observable_action": f"从货架取下 {item} 并完成结账",
                        "take_item_tag": item,
                    }

        # 4. Isabella initiates community proposal at tick 3
        if name == "Isabella" and self.tick_count == 3 and self.active_proposal[0] is None:
            return {
                "internal_thought": "为了活跃小镇氛围，提议在小镇公园举办周末春季文化沙龙与农夫市集。",
                "observable_action": "向居民委员会提交了「举办小镇春季市集与读书沙龙」的社区提案",
                "propose_blueprint": "在小镇公园举办春季社区市集与文化读书沙龙",
            }

        # 5. Vote YES if town proposal is active
        if self.active_proposal[0] is not None and name not in self.active_proposal[0].votes:
            return {
                "internal_thought": "这是个很棒的社区活动提议，投赞成票支持！",
                "observable_action": "举手赞同 Isabella 的春季市集提案",
                "vote_on_blueprint": "YES",
            }

        # 6. Roam across modern town portals
        candidates = []
        if current_room:
            if current_room.parent:
                for sib in current_room.parent.children:
                    if sib.name != current_room.name:
                        candidates.append(sib.name)
            for child in current_room.children:
                candidates.append(child.name)

        if candidates:
            next_room = candidates[self.tick_count % len(candidates)]
            return {
                "internal_thought": f"处理完手头事务，动身前往 {next_room}。",
                "observable_action": f"漫步前往小镇 {next_room}",
                "move_to": next_room,
            }

        return {
            "internal_thought": "坐在长椅上静静享受小镇的静谧时光。",
            "observable_action": "在原地休憩沉思",
        }


async def main():
    vault_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "obsidian_vault")
    print("================================================================")
    print("🌌 SINA: Obsidian Vault 实时星图推演沙盒启动")
    print(f"📁 Obsidian 目标仓库路径: {vault_dir}")
    print("================================================================")
    print("💡 建议操作：")
    print("  1. 打开 Obsidian 软件 -> '打开文件夹作为库 (Open folder as vault)'")
    print(f"  2. 选择路径: {vault_dir}")
    print("  3. 在 Obsidian 中按 `Ctrl + G` 打开【全局星图 (Graph View)】")
    print("----------------------------------------------------------------")

    world = StandaloneWorld(vault_path=vault_dir)
    
    # Pre-sync initial state
    world.observer.sync_tick(world, memory_manager=world.memory_manager)
    print("✅ 初始世界节点已写入 Vault。开始交互式推演循环...\n")

    auto_run_count = 0
    step_interval = 0.8
    while True:
        if auto_run_count > 0:
            cmd = ""
            auto_run_count -= 1
            await asyncio.sleep(step_interval)
        else:
            try:
                cmd = input(f"[Tick {world.tick_count:02d} | 回车推演 1 步 / 'play <N> [秒数]' 自动平滑播放 / 'inject <事件>' / 'q' 退出] > ").strip()
            except (EOFError, KeyboardInterrupt):
                break

        if cmd.lower() in ("q", "quit", "exit"):
            break

        custom_event = None
        if cmd.startswith("play ") or cmd.startswith("run "):
            parts = cmd.split()
            try:
                auto_run_count = max(0, int(parts[1]) - 1)
            except Exception:
                auto_run_count = 10
            try:
                if len(parts) >= 3:
                    step_interval = float(parts[2])
                else:
                    step_interval = 0.8
            except Exception:
                step_interval = 0.8
            print(f"▶️ [自动推演中] 将连续推演 {auto_run_count + 1} 步，每步间隔 {step_interval:.1f}s...")
        elif cmd.startswith("inject "):
            custom_event = cmd[7:].strip()
            print(f"⚡ [上帝干预] 注入突发事件: {custom_event}")

        logs = await world.step(custom_event=custom_event)
        
        # Display Tick Summary
        alive = sum(1 for a in world.world_agents.values() if not a.is_dead and not a.is_comatose)
        comatose = sum(1 for a in world.world_agents.values() if a.is_comatose)
        dead = sum(1 for a in world.world_agents.values() if a.is_dead)
        print(f"\n⏱ Tick {world.tick_count:02d} [{world.clock.strftime('%H:%M')}] | 👥 存活: {alive} | 昏迷: {comatose} | 死亡: {dead}")
        for log_line in logs[:5]:
            print(f"  {log_line}")
        print("  ✓ [Obsidian Vault] 双链、星图与编年史已实时刷新！\n")


if __name__ == "__main__":
    asyncio.run(main())
