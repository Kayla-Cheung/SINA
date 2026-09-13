"""
SINA v4 Observer: Obsidian Vault Visualizer & Graph Exporter.
Transforms live multi-agent simulation states into interconnected Markdown notes
with [[wikilinks]], YAML frontmatter, and .canvas maps, enabling native GPU-accelerated
force-directed graph visualization in Obsidian.
"""

import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime


class ObsidianVaultObserver:
    """
    Observer that renders the live simulation state into an Obsidian-compatible vault.
    Supports both:
      - `macro_only=True` (Sociological Swarm Mode): Prunes memory/item/event nodes into
        internal card tables, leaving the Global Graph 100% clean with only Agents & Rooms.
      - `macro_only=False` (Fine-Grained Debug Mode): Generates discrete nodes for every memory,
        event, and item entity.
    """

    def __init__(self, vault_dir: str, macro_only: bool = True, max_recent_events: int = 50):
        self.vault_dir = os.path.abspath(vault_dir)
        self.macro_only = macro_only
        self.max_recent_events = max_recent_events
        self.agents_dir = os.path.join(self.vault_dir, "Agents")
        self.rooms_dir = os.path.join(self.vault_dir, "Rooms")
        self.items_dir = os.path.join(self.vault_dir, "Items")
        self.memories_dir = os.path.join(self.vault_dir, "Memories")
        self.events_dir = os.path.join(self.vault_dir, "Events")
        self._ensure_directories()

    def _write_if_changed(self, file_path: str, content: str) -> bool:
        """Write content only if changed or file does not exist. Returns True if written."""
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    if f.read() == content:
                        return False
            except Exception:
                pass
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def _ensure_directories(self) -> None:
        """Create standard folder layout inside the vault and purge micro files if macro_only."""
        for d in [self.agents_dir, self.rooms_dir]:
            os.makedirs(d, exist_ok=True)

        if not self.macro_only:
            for d in [self.items_dir, self.memories_dir, self.events_dir]:
                os.makedirs(d, exist_ok=True)
        else:
            # Clean up micro-node directories so they do not pollute the macro graph
            for d in [self.items_dir, self.memories_dir, self.events_dir]:
                if os.path.exists(d):
                    for fname in os.listdir(d):
                        if fname.endswith(".md"):
                            try:
                                os.remove(os.path.join(d, fname))
                            except Exception:
                                pass

    def sync_tick(
        self,
        sim: Any,
        current_intents: Optional[List[Any]] = None,
        settlement_logs: Optional[List[str]] = None,
        memory_manager: Optional[Any] = None,
    ) -> None:
        """
        Synchronize the current simulation state into the Obsidian Vault.
        Atomic write triggers Obsidian's native file watcher to immediately update the graph view.
        """
        self._sync_rooms(sim)
        self._sync_agents(sim, memory_manager)
        self._sync_items(sim)
        if settlement_logs:
            self._sync_events(sim.tick_count, settlement_logs, sim)
        self._sync_dashboard(sim, memory_manager)
        self._sync_canvas(sim)

    def _sync_rooms(self, sim: Any) -> None:
        """Render each room node with links to occupying agents and adjacent rooms."""
        all_nodes = sim.environment.all_nodes()
        all_node_names = {node.name for node in all_nodes}

        # Clean up stale room notes from previous world runs
        current_room_files = {f"{node.name}.md" for node in all_nodes}
        for existing in os.listdir(self.rooms_dir):
            if existing.endswith(".md") and existing not in current_room_files:
                try:
                    os.remove(os.path.join(self.rooms_dir, existing))
                except Exception:
                    pass

        for node in all_nodes:
            file_path = os.path.join(self.rooms_dir, f"{node.name}.md")
            
            # Find agents in this room
            agents_in_room = list(node.agents)
            agent_links = [f"- [[Agents/{a}]]" for a in agents_in_room]
            agents_block = "\n".join(agent_links) if agent_links else "- *(空无一人)*"

            # Inventory in this room
            if self.macro_only:
                items_list = [f"- **{k}** × {v}" for k, v in node.inventory.items() if v > 0]
            else:
                items_list = [f"- [[Items/{k}]] × {v}" for k, v in node.inventory.items() if v > 0]
            items_block = "\n".join(items_list) if items_list else "- *(无遗留物资)*"

            # Connected sibling/parent/child leaf rooms
            connected_rooms = []
            if node.parent:
                for sib in node.parent.children:
                    if sib.name != node.name:
                        if not sib.children and sib.name in all_node_names:
                            connected_rooms.append(sib.name)
                        else:
                            for sub in sib.children:
                                if sub.name in all_node_names:
                                    connected_rooms.append(sub.name)

            if not connected_rooms:
                for other in all_nodes:
                    if other.name != node.name:
                        connected_rooms.append(other.name)

            neighbors_list = [f"- [[Rooms/{r}]]" for r in connected_rooms]
            neighbors_block = "\n".join(neighbors_list) if neighbors_list else "- *(独立区域)*"

            content = (
                f"---\n"
                f"type: room\n"
                f"room_name: {node.name}\n"
                f"occupant_count: {len(agents_in_room)}\n"
                f"tags: [room, place, spatial_node]\n"
                f"---\n\n"
                f"# 🏛️ 空间节点：{node.name}\n\n"
                f"## 👥 在场智能体 (Occupants)\n"
                f"{agents_block}\n\n"
                f"## 📦 空间物资 (Inventory)\n"
                f"{items_block}\n\n"
                f"## 🚪 连通区域 (Connected Portals)\n"
                f"{neighbors_block}\n"
            )

            self._write_if_changed(file_path, content)

    def _sync_agents(self, sim: Any, memory_manager: Optional[Any]) -> None:
        """Render each agent with links to current room, inventory, allies, and memory nodes."""
        # Clean up stale agent notes from previous world runs
        current_agent_files = {f"{name}.md" for name in sim.world_agents.keys()}
        for existing in os.listdir(self.agents_dir):
            if existing.endswith(".md") and existing not in current_agent_files:
                try:
                    os.remove(os.path.join(self.agents_dir, existing))
                except Exception:
                    pass

        for name, agent in sim.world_agents.items():
            file_path = os.path.join(self.agents_dir, f"{name}.md")
            loc_node = sim.environment.agent_locations.get(name)
            room_name = loc_node.name if loc_node else "Unknown"

            # Inventory links
            if self.macro_only:
                inv_links = [f"- **{k}** × {v}" for k, v in agent.inventory.items() if v > 0]
            else:
                inv_links = [f"- [[Items/{k}]] × {v}" for k, v in agent.inventory.items() if v > 0]
            inv_block = "\n".join(inv_links) if inv_links else "- *(空手)*"

            # Social nearby links
            nearby_links = [f"- [[Agents/{n}]]" for n in agent.known_nearby if n != name]
            nearby_block = "\n".join(nearby_links) if nearby_links else "- *(孤身一人)*"

            # Memory notes & links
            memory_links = []
            if memory_manager and hasattr(memory_manager, "vector_store"):
                agent_memories = memory_manager.vector_store.get_agent_memories(name)
                for mem in agent_memories[-5:]:  # show recent 5 memories
                    if not self.macro_only:
                        mem_file_name = f"Mem_{name}_{mem.tick_start}_{mem.tick_end}"
                        self._write_single_memory(mem, mem_file_name)
                        confab_tag = " ⚠️(脑补)" if mem.is_confabulated else ""
                        memory_links.append(f"- [[Memories/{mem_file_name}]]{confab_tag}: {mem.summary[:40]}...")
                    else:
                        confab_tag = " ⚠️(虚假脑补)" if mem.is_confabulated else ""
                        memory_links.append(
                            f"- 🧠 **[T{mem.tick_start}-T{mem.tick_end} @ {mem.location}]**{confab_tag} {mem.summary} *(重要度: {mem.importance:.1f}/10)*"
                        )

            # Fallback to internal memory stream if manager not provided
            if not memory_links and agent.memory_stream:
                for idx, m in enumerate(agent.memory_stream[-5:]):
                    memory_links.append(f"- `[{m.get('time', '')}]` {m.get('text', '')[:60]}")

            memory_block = "\n".join(memory_links) if memory_links else "- *(暂无长期记忆)*"

            status_str = "alive"
            if agent.is_dead:
                status_str = "dead"
            elif agent.is_comatose:
                status_str = "comatose"

            content = (
                f"---\n"
                f"type: agent\n"
                f"name: {name}\n"
                f"status: {status_str}\n"
                f"hunger: {agent.hunger}\n"
                f"current_room: \"[[Rooms/{room_name}]]\"\n"
                f"tags: [agent, status/{status_str}]\n"
                f"---\n\n"
                f"# 👤 智能体：{name}\n\n"
                f"## 📍 物理坐标与状态\n"
                f"- **所在房间**：[[Rooms/{room_name}]]\n"
                f"- **生命体征**：饱食度 `{agent.hunger}/30` | 状态 `{status_str.upper()}`\n"
                f"- **当前行为**：`{agent.current_action}`\n"
                f"- **性格/特质**：`{agent.traits}`\n\n"
                f"## 🎒 随身物品 (Inventory)\n"
                f"{inv_block}\n\n"
                f"## 🌐 视野内社交圈 (Known Nearby)\n"
                f"{nearby_block}\n\n"
                f"## 🧠 激活的情景记忆 (Episodic Substrate)\n"
                f"{memory_block}\n"
            )

            self._write_if_changed(file_path, content)

    def _write_single_memory(self, memory: Any, file_name: str) -> None:
        """Write an episodic memory note into Memories folder."""
        file_path = os.path.join(self.memories_dir, f"{file_name}.md")
        confab_str = "true" if memory.is_confabulated else "false"

        involved_links = [f"- [[Agents/{a}]]" for a in memory.involved_agents]
        involved_block = "\n".join(involved_links) if involved_links else "- *(独处)*"

        content = (
            f"---\n"
            f"type: memory\n"
            f"agent: \"[[Agents/{memory.agent_id}]]\"\n"
            f"location: \"[[Rooms/{memory.location}]]\"\n"
            f"ticks: \"T{memory.tick_start}-T{memory.tick_end}\"\n"
            f"importance: {memory.importance}\n"
            f"is_confabulated: {confab_str}\n"
            f"tags: [memory, episodic{' ,confabulation' if memory.is_confabulated else ''}]\n"
            f"---\n\n"
            f"# 🧠 情景记忆：{file_name}\n\n"
            f"- **归属主体**：[[Agents/{memory.agent_id}]]\n"
            f"- **发生地点**：[[Rooms/{memory.location}]]\n"
            f"- **时间范围**：`Tick {memory.tick_start} ~ {memory.tick_end}`\n"
            f"- **重要度**：`{memory.importance:.1f}/10.0` | **虚假脑补**：`{confab_str.upper()}`\n\n"
            f"## 📜 记忆压缩摘要\n"
            f"> {memory.summary}\n\n"
            f"## 👥 关联实体\n"
            f"{involved_block}\n"
        )

        self._write_if_changed(file_path, content)

    def _sync_items(self, sim: Any) -> None:
        """Render items with descriptions and physics properties (skipped in macro_only mode)."""
        if self.macro_only:
            return

        all_item_tags = set()
        for node in sim.environment.all_nodes():
            all_item_tags.update(node.inventory.keys())
        for a in sim.world_agents.values():
            all_item_tags.update(a.inventory.keys())

        for tag in all_item_tags:
            file_path = os.path.join(self.items_dir, f"{tag}.md")
            props = sim.physics.material_properties.get(tag, {})
            nutrition = props.get("nutrition", 0)
            spoil_rate = props.get("spoil_rate", 0.0)
            disease_chance = props.get("disease_chance", 0.0)

            content = (
                f"---\n"
                f"type: item\n"
                f"item_tag: {tag}\n"
                f"nutrition: {nutrition}\n"
                f"spoil_rate: {spoil_rate}\n"
                f"tags: [item, material]\n"
                f"---\n\n"
                f"# 📦 物质实体：{tag}\n\n"
                f"- **营养恢复**：`+{nutrition} hunger`\n"
                f"- **腐败概率**：`{spoil_rate * 100:.1f}% / tick`\n"
                f"- **生病概率**：`{disease_chance * 100:.1f}%`\n"
            )

            self._write_if_changed(file_path, content)

    def _sync_events(self, tick: int, logs: List[str], sim: Any) -> None:
        """Log key settlement events into Events folder and continuous chronicle."""
        if not logs:
            return

        # Scan logs for agent links and room links
        formatted_lines = []
        for line in logs:
            processed_line = line
            for name in sim.world_agents.keys():
                if name in processed_line:
                    processed_line = processed_line.replace(name, f"[[Agents/{name}]]")
            for node in sim.environment.all_nodes():
                if node.name in processed_line:
                    processed_line = processed_line.replace(node.name, f"[[Rooms/{node.name}]]")
            formatted_lines.append(f"- {processed_line.strip()}")

        # 1. In detailed mode, create separate Event notes
        if not self.macro_only:
            file_name = f"Tick_{tick:04d}_Settlement.md"
            file_path = os.path.join(self.events_dir, file_name)
            content = (
                f"---\n"
                f"type: event\n"
                f"tick: {tick}\n"
                f"time: \"{sim.clock.strftime('%Y-%m-%d %H:%M')}\"\n"
                f"tags: [event, tick_log]\n"
                f"---\n\n"
                f"# ⚡ 历史事件：Tick {tick:04d}\n\n"
                f"- **时间戳**：`{sim.clock.strftime('%Y-%m-%d %H:%M')}`\n\n"
                f"## 📜 物理与社会结算流水\n"
                + "\n".join(formatted_lines)
                + "\n"
            )
            self._write_if_changed(file_path, content)

        # 2. Always maintain a continuous live chronicle stream: 01_WORLD_CHRONICLE.md
        chronicle_path = os.path.join(self.vault_dir, "01_WORLD_CHRONICLE.md")
        chronicle_entry = (
            f"### ⏱️ Tick {tick:04d} [{sim.clock.strftime('%Y-%m-%d %H:%M')}]\n"
            + "\n".join(formatted_lines)
            + "\n\n---\n\n"
        )
        if not os.path.exists(chronicle_path):
            header = (
                f"---\n"
                f"type: chronicle\n"
                f"tags: [chronicle, live_stream]\n"
                f"---\n\n"
                f"# 📜 SINA 世界编年史流水线 (Live World Chronicle)\n\n"
                f"> 此文件由仿真引擎实时追加，按时间轴追踪全员行为与历史大事件。\n\n---\n\n"
            )
            with open(chronicle_path, "w", encoding="utf-8") as f:
                f.write(header + chronicle_entry)
        else:
            with open(chronicle_path, "a", encoding="utf-8") as f:
                f.write(chronicle_entry)

    def _sync_dashboard(self, sim: Any, memory_manager: Optional[Any]) -> None:
        """Create or overwrite the root 00_WORLD_DASHBOARD.md file."""
        file_path = os.path.join(self.vault_dir, "00_WORLD_DASHBOARD.md")

        alive_count = sum(1 for a in sim.world_agents.values() if not a.is_dead and not a.is_comatose)
        comatose_count = sum(1 for a in sim.world_agents.values() if a.is_comatose)
        dead_count = sum(1 for a in sim.world_agents.values() if a.is_dead)

        agent_links = [f"- [[Agents/{a}]] (`{sim.world_agents[a].current_action}`)" for a in sim.world_agents]
        room_links = [f"- [[Rooms/{n.name}]] (在场: {len(n.agents)}人)" for n in sim.environment.all_nodes()]

        season_idx = (sim.tick_count // 24) % 4
        season_names = ["🌸 春季 (Spring)", "☀ 夏季 (Summer)", "🍂 秋季 (Autumn)", "❄ 凛冬 (Winter)"]
        current_season = season_names[season_idx]

        content = (
            f"---\n"
            f"type: dashboard\n"
            f"tick: {sim.tick_count}\n"
            f"clock: \"{sim.clock.strftime('%Y-%m-%d %H:%M')}\"\n"
            f"tags: [dashboard, ssot_root]\n"
            f"---\n\n"
            f"# 🌍 SINA: 模拟世界宏观战情中枢 (World Dashboard)\n\n"
            f"| 指标项 | 状态与数值 |\n"
            f"| :--- | :--- |\n"
            f"| **仿真步数 (Tick)** | `Tick {sim.tick_count}` |\n"
            f"| **世界时间** | `{sim.clock.strftime('%Y-%m-%d %H:%M')}` ({current_season}) |\n"
            f"| **人口生态** | 🟢 存活 `{alive_count}` | 🟡 昏迷 `{comatose_count}` | 🔴 死亡 `{dead_count}` |\n"
            f"| **空间节点数** | `{len(sim.environment.all_nodes())}` 个房间 |\n\n"
            f"## 👥 智能体花名册 (Roster)\n"
            + "\n".join(agent_links) + "\n\n"
            f"## 🏛️ 空间拓扑 (Spatial Grid)\n"
            + "\n".join(room_links) + "\n\n"
            f"## 💡 Obsidian 星图操作指引 (Star Map Guide)\n"
            f"1. **快捷键 `Ctrl + G` (或 `Cmd + G`)**：打开全局星图（Global Graph）；\n"
            f"2. **颜色分组已就绪**：\n"
            f"   - 🟢 **绿色**：`#agent` 智能体\n"
            f"   - 🔵 **蓝色**：`#room` 空间节点\n"
            f"   - 🟣 **紫色**：`#memory` 情景记忆\n"
            f"   - 🔴 **红色**：`#event` 历史事件\n"
            f"   - 🟡 **黄色**：`#item` 物质资源\n"
            f"3. **局部心智透视**：点开任意 `Agents/xxx.md`，右侧开启 **Local Graph**，深度设为 `2`，实时透视其人际圈与记忆网络。\n"
        )

        self._write_if_changed(file_path, content)

    def _sync_canvas(self, sim: Any) -> None:
        """Generate an interactive Obsidian .canvas JSON file mapping rooms & agents in 2D space."""
        canvas_path = os.path.join(self.vault_dir, "World_Canvas.canvas")
        nodes = []
        edges = []

        all_nodes = sim.environment.all_nodes()
        cols = 3
        node_width = 320
        node_height = 240
        gap_x = 80
        gap_y = 80

        # Place room nodes in a grid
        room_pos_map = {}
        for idx, room in enumerate(all_nodes):
            row = idx // cols
            col = idx % cols
            x = col * (node_width + gap_x)
            y = row * (node_height + gap_y)
            room_pos_map[room.name] = (x, y)

            nodes.append({
                "id": f"room_{room.name}",
                "type": "file",
                "file": f"Rooms/{room.name}.md",
                "x": x,
                "y": y,
                "width": node_width,
                "height": node_height,
                "color": "4"  # Blue in Obsidian Canvas
            })

        # Connect connected rooms
        edge_id = 0
        seen_edges = set()

        # 1. Connect siblings under the same parent
        parent_groups: Dict[Any, List[Any]] = {}
        for room in all_nodes:
            parent_key = room.parent.name if room.parent else "root"
            parent_groups.setdefault(parent_key, []).append(room)

        for p_name, group in parent_groups.items():
            for i in range(len(group) - 1):
                r1 = group[i].name
                r2 = group[i + 1].name
                edge_pair = tuple(sorted([r1, r2]))
                if edge_pair not in seen_edges and r1 in room_pos_map and r2 in room_pos_map:
                    seen_edges.add(edge_pair)
                    edges.append({
                        "id": f"edge_{edge_id}",
                        "fromNode": f"room_{r1}",
                        "fromSide": "right",
                        "toNode": f"room_{r2}",
                        "toSide": "left",
                        "label": "Portal"
                    })
                    edge_id += 1

        # 2. If multiple groups, connect consecutive groups
        group_list = list(parent_groups.values())
        for g_idx in range(len(group_list) - 1):
            if group_list[g_idx] and group_list[g_idx + 1]:
                r1 = group_list[g_idx][-1].name
                r2 = group_list[g_idx + 1][0].name
                edge_pair = tuple(sorted([r1, r2]))
                if edge_pair not in seen_edges and r1 in room_pos_map and r2 in room_pos_map:
                    seen_edges.add(edge_pair)
                    edges.append({
                        "id": f"edge_{edge_id}",
                        "fromNode": f"room_{r1}",
                        "fromSide": "bottom",
                        "toNode": f"room_{r2}",
                        "toSide": "top",
                        "label": "Zone Bridge"
                    })
                    edge_id += 1

        # Fallback if only single disconnected nodes exist but >=2 nodes total
        if not edges and len(all_nodes) >= 2:
            for i in range(len(all_nodes) - 1):
                r1 = all_nodes[i].name
                r2 = all_nodes[i + 1].name
                edges.append({
                    "id": f"edge_{edge_id}",
                    "fromNode": f"room_{r1}",
                    "fromSide": "right",
                    "toNode": f"room_{r2}",
                    "toSide": "left",
                    "label": "Portal"
                })
                edge_id += 1

        canvas_data = {
            "nodes": nodes,
            "edges": edges
        }

        with open(canvas_path, "w", encoding="utf-8") as f:
            json.dump(canvas_data, f, ensure_ascii=False, indent=2)
