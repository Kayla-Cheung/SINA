"""
Unit and Integration Tests for SINA Obsidian Vault Observer.
Verifies Markdown generation, [[wikilinks]] integrity, canvas graph JSON,
and memory synchronization.
"""

import os
import tempfile
import json
import pytest

from core.environment import SandboxEnvironment
from core.agent_state import AgentState
from core.physics_engine import PhysicsEngine
from sina.observer.obsidian_vault import ObsidianVaultObserver
from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.types import PersonaInvariant, MemoryType


class MockSim:
    """Lightweight mock simulation for observer testing."""
    def __init__(self):
        from datetime import datetime
        self.clock = datetime(2026, 1, 1, 10, 0)
        self.tick_count = 1
        self.environment = SandboxEnvironment()
        self.physics = PhysicsEngine()
        self.world_agents = {
            "Agent_Alice": AgentState("Agent_Alice", traits="冷静的管理者"),
            "Agent_Bob": AgentState("Agent_Bob", traits="勤劳的工人"),
        }
        self.world_agents["Agent_Alice"].inventory = {"TORCH": 1, "MEAT": 2}
        self.world_agents["Agent_Bob"].inventory = {"STONE": 3}
        
        # Spawn in rooms
        nodes = self.environment.all_nodes()
        self.environment.spawn_agent("Agent_Alice", nodes[0])
        self.environment.spawn_agent("Agent_Bob", nodes[1])


def test_obsidian_vault_sync_and_file_structure():
    with tempfile.TemporaryDirectory() as tmp_dir:
        observer = ObsidianVaultObserver(vault_dir=tmp_dir)
        sim = MockSim()
        
        memory_mgr = HierarchicalMemoryManager()
        p_alice = PersonaInvariant(
            agent_id="Agent_Alice",
            name="Agent_Alice",
            archetype="Leader",
            core_conviction="维持秩序",
            class_index=0.9,
        )
        memory_mgr.register_agent(p_alice)
        memory_mgr.record_event("Agent_Alice", 1, "在广场视察物资。", location="Town_Square")

        # Sync 1 tick
        logs = ["[移动] Agent_Alice 移动到 Town_Square", "[采集] Agent_Bob 采集了 STONE"]
        observer.sync_tick(sim, settlement_logs=logs, memory_manager=memory_mgr)

        # 1. Verify Directories
        for sub in ["Agents", "Rooms", "Items", "Memories", "Events"]:
            assert os.path.exists(os.path.join(tmp_dir, sub))

        # 2. Verify Dashboard
        dashboard_path = os.path.join(tmp_dir, "00_WORLD_DASHBOARD.md")
        assert os.path.exists(dashboard_path)
        with open(dashboard_path, "r", encoding="utf-8") as f:
            dash_content = f.read()
        assert "[[Agents/Agent_Alice]]" in dash_content
        assert "[[Rooms/" in dash_content

        # 3. Verify Agent Card with Wikilinks
        alice_card = os.path.join(tmp_dir, "Agents", "Agent_Alice.md")
        assert os.path.exists(alice_card)
        with open(alice_card, "r", encoding="utf-8") as f:
            alice_content = f.read()
        assert "[[Rooms/" in alice_content
        assert "[[Items/TORCH]]" in alice_content
        assert "[[Items/MEAT]]" in alice_content

        # 4. Verify Canvas File
        canvas_path = os.path.join(tmp_dir, "World_Canvas.canvas")
        assert os.path.exists(canvas_path)
        with open(canvas_path, "r", encoding="utf-8") as f:
            canvas_data = json.load(f)
        assert len(canvas_data["nodes"]) >= len(sim.environment.all_nodes())
        assert len(canvas_data["edges"]) > 0

        # 5. Verify Event Log
        event_files = os.listdir(os.path.join(tmp_dir, "Events"))
        assert len(event_files) >= 1
        with open(os.path.join(tmp_dir, "Events", event_files[0]), "r", encoding="utf-8") as f:
            event_content = f.read()
        assert "[[Agents/Agent_Alice]]" in event_content
