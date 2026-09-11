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

    def __init__(self, vault_path: str, world_name: str = "stone_age"):
        self.clock = datetime(2026, 1, 1, 8, 0)
        self.tick_count = 0
        self.active_proposal = [None]
        self.current_logs = []

        # 1. Spatial Topology
        self.environment = SandboxEnvironment(world_name=world_name)
        
        # 2. Physics Substrate
        self.physics = PhysicsEngine(world_name=world_name)

        # 3. Hierarchical Memory Subsystem
        self.memory_manager = HierarchicalMemoryManager(default_token_threshold=120)

        # 4. Observer: Obsidian Vault Syncer
        self.observer = ObsidianVaultObserver(vault_dir=vault_path)

        # 5. Initialize Agents
        self.world_agents: dict[str, AgentState] = {}
        self._init_society()

    def _init_society(self):
        """Create a diverse 5-agent archetypal society."""
        agents_data = [
            {
                "name": "Alpha_Leader",
                "archetype": "Dominant_Authority",
                "traits": "专断、重视部族秩序、掌控资源分配",
                "conviction": "维持统治威权与族群生存底线",
                "class_index": 0.95,
                "wealth": 3000.0,
                "start_room": "Hilltop",
                "inventory": {"TORCH": 2, "SPEAR": 1, "MEAT": 3},
                "hunger": 25,
            },
            {
                "name": "Beta_Hunter",
                "archetype": "Pragmatic_Worker",
                "traits": "务实、擅长狩猎与采集、体魄强健",
                "conviction": "凭借劳动换取食物与安全",
                "class_index": 0.60,
                "wealth": 1500.0,
                "start_room": "Dense_Forest",
                "inventory": {"STONE": 3, "MEAT": 4},
                "hunger": 20,
            },
            {
                "name": "Gamma_Scholar",
                "archetype": "Analytical_Seeker",
                "traits": "理性、敏锐、探寻物理规律与制作配方",
                "conviction": "探索未知，打破愚昧迷信",
                "class_index": 0.75,
                "wealth": 2000.0,
                "start_room": "Dark_Cave",
                "inventory": {"TORCH": 1, "WOOD": 2},
                "hunger": 18,
            },
            {
                "name": "Delta_Survivor",
                "archetype": "Subordinate_Survivor",
                "traits": "胆小、饥饿、在阶层夹缝中依附求生",
                "conviction": "不择手段活过即将到来的凛冬",
                "class_index": 0.15,
                "wealth": 300.0,
                "start_room": "Open_Plains",
                "inventory": {"BERRY": 1},
                "hunger": 8,
            },
            {
                "name": "Epsilon_Rebel",
                "archetype": "Nihilist_Rebel",
                "traits": "反叛、怀疑权威、伺机抢夺资源打破阶层",
                "conviction": "摧毁旧有秩序，夺取生存自主权",
                "class_index": 0.35,
                "wealth": 600.0,
                "start_room": "Dense_Forest",
                "inventory": {"STONE": 2},
                "hunger": 12,
            },
        ]

        for data in agents_data:
            name = data["name"]
            agent = AgentState(
                name=name,
                traits=data["traits"],
                intentions=["搜集食物", "探索周边", "建立同盟"],
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
        is_night = not (6 <= self.clock.hour < 18)
        
        # 1. Environment Phase: Spoilage & Seasonal respawn
        for node in self.environment.all_nodes():
            self.physics.resolve_spoilage(node.inventory)
        for agent in self.world_agents.values():
            if not agent.is_dead:
                self.physics.resolve_spoilage(agent.inventory)

        # Resource respawn in forest/plains
        df = self.environment.get_node_by_name("Dense_Forest")
        if df:
            df.inventory["BERRY"] = df.inventory.get("BERRY", 0) + 2

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
            room_name = loc_node.name if loc_node else "Town_Square"
            
            obs_text = f"在 {room_name} 感到身体饥饿度为 {agent.hunger}/30。"
            if custom_event and name in ("Alpha_Leader", "Epsilon_Rebel"):
                obs_text += f" 【突发事件】{custom_event}"

            self.memory_manager.record_event(
                agent_id=name,
                tick=self.tick_count,
                content=obs_text,
                memory_type=MemoryType.OBSERVATION,
                location=room_name,
            )

            # Heuristic simulation intention for offline demo
            action_dict = self._simulate_heuristic_intent(name, agent, loc_node)
            agent.current_action = action_dict.get("observable_action", "观察周围")
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
        """Heuristic decision logic for offline demo simulation."""
        # If very hungry and has food, eat
        if agent.hunger < 15:
            for food in ["COOKED_MEAT", "MEAT", "BERRY"]:
                if agent.inventory.get(food, 0) > 0:
                    return {
                        "internal_thought": f"好饿，必须立刻吃下 {food} 维持生命！",
                        "observable_action": f"正在狼吞虎咽地吃 {food}",
                        "eat_item": food,
                    }

        # If in room with berries, pick up
        if current_room.inventory.get("BERRY", 0) > 0:
            return {
                "internal_thought": f"看到地上有浆果，采集备用。",
                "observable_action": "弯腰采集地上的新鲜浆果",
                "take_item_tag": "BERRY",
            }

        # Rebel tries to attack leader if in same room
        if name == "Epsilon_Rebel" and "Alpha_Leader" in current_room.agents:
            return {
                "internal_thought": "这是推翻权威的最佳时机，抢走首领的火把与熟肉！",
                "observable_action": "突然拔出石刀扑向 Alpha_Leader 发动突袭！",
                "attack_target": "Alpha_Leader",
            }

        # Leader proposes blueprint at tick 3
        if name == "Alpha_Leader" and self.tick_count == 3 and self.active_proposal[0] is None:
            return {
                "internal_thought": "必须建立篝火防御夜间野兽，召集全员公决。",
                "observable_action": "高举火把向众人提议建立中央篝火制度",
                "propose_blueprint": "在广场建立永不熄灭的部落中央篝火",
            }

        # Vote YES if proposal is active
        if self.active_proposal[0] is not None and name not in self.active_proposal[0].votes:
            return {
                "internal_thought": "同意这项防御提议，有利于大家活命。",
                "observable_action": "举手赞同首领的篝火提案",
                "vote_on_blueprint": "YES",
            }

        # Roam to adjacent room
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
                "internal_thought": f"巡视周边，前往 {next_room} 搜寻物资。",
                "observable_action": f"动身前往 {next_room}",
                "move_to": next_room,
            }

        return {
            "internal_thought": "静观其变，保存体能。",
            "observable_action": "在原地闭目休憩",
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
