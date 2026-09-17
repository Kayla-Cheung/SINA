"""
存档往返回归测试（#29 房间状态丢失、#30 物理规则丢失）。

覆盖:
- extract_world / save_world_state 必须导出每个房间的 inventory/objects/locked_by。
- 读档后地面资源与智能体背包来自同一时间点，物品种数守恒（不再凭空复制）。
- PhysicsEngine 往返必须保住 world_name 与 material_properties/terrain_hazards/weapon_modifiers。
"""

import json
from pathlib import Path

import pytest

from core.dag_simulation import SinaSimulation
from core.game_session import extract_world, load_world_into_sim
from core.physics_engine import PhysicsEngine, Recipe


# --------------------------------------------------------------------------
# 房间状态往返（#29）
# --------------------------------------------------------------------------

def _new_sim(tmp_path, monkeypatch) -> SinaSimulation:
    monkeypatch.setenv("SINA_DATA_DIR", str(tmp_path))
    return SinaSimulation(world_name="smallville", resume=False)


def test_extract_world_includes_room_state(tmp_path, monkeypatch):
    sim = _new_sim(tmp_path, monkeypatch)
    room = sim.environment.all_nodes()[0]
    room.inventory = {"COFFEE": 2}
    room.objects = ["石凳"]
    room.locked_by = "Alice"

    world = extract_world(sim)
    dumped = {n["name"]: n for n in world["nodes"]}

    assert room.name in dumped
    assert dumped[room.name]["inventory"] == {"COFFEE": 2}
    assert dumped[room.name]["objects"] == ["石凳"]
    assert dumped[room.name]["locked_by"] == "Alice"


def test_save_world_state_persists_room_state(tmp_path, monkeypatch):
    sim = _new_sim(tmp_path, monkeypatch)
    room = sim.environment.all_nodes()[0]
    room.inventory = {"BERRY": 7}
    room.locked_by = "Bob"

    sim.save_world_state()

    payload = json.loads(Path(sim.save_file).read_text(encoding="utf-8"))
    dumped = {n["name"]: n for n in payload["nodes"]}
    assert dumped[room.name]["inventory"] == {"BERRY": 7}
    assert dumped[room.name]["locked_by"] == "Bob"


def test_load_restores_room_state(tmp_path, monkeypatch):
    sim = _new_sim(tmp_path, monkeypatch)
    room = sim.environment.all_nodes()[0]
    room.inventory = {"COFFEE": 0, "PASTRY": 3}
    room.objects = ["桌子"]
    room.locked_by = "Alice"
    world = extract_world(sim)

    # 破坏现场，模拟"又运行了很久"
    room.inventory = {"COFFEE": 99}
    room.objects = []
    room.locked_by = None

    load_world_into_sim(sim, world)

    restored = sim.environment.get_node_by_name(room.name)
    assert restored.inventory == {"COFFEE": 0, "PASTRY": 3}
    assert restored.objects == ["桌子"]
    assert restored.locked_by == "Alice"


def _coffee_total(sim) -> int:
    on_ground = sum(n.inventory.get("COFFEE", 0) for n in sim.environment.all_nodes())
    in_packs = sum(a.inventory.get("COFFEE", 0) for a in sim.world_agents.values())
    return on_ground + in_packs


def test_save_load_conserves_items(tmp_path, monkeypatch):
    """旧版只还原背包、不还原地面：存档后取走 N 个再读档，世界物品总数凭空 +N。"""
    sim = _new_sim(tmp_path, monkeypatch)
    room = sim.environment.all_nodes()[0]
    room.inventory["COFFEE"] = 10
    world = extract_world(sim)
    total_at_save = _coffee_total(sim)

    # 智能体从地面拿走 4 个咖啡
    agent = next(iter(sim.world_agents.values()))
    room.inventory["COFFEE"] -= 4
    agent.inventory["COFFEE"] = agent.inventory.get("COFFEE", 0) + 4
    assert _coffee_total(sim) == total_at_save  # 搬运本身不改变总数

    load_world_into_sim(sim, world)

    assert _coffee_total(sim) == total_at_save


def test_legacy_payload_without_nodes_is_tolerated(tmp_path, monkeypatch):
    """旧存档没有 nodes 字段：读档不得报错，房间保持当前状态。"""
    sim = _new_sim(tmp_path, monkeypatch)
    world = extract_world(sim)
    world.pop("nodes")

    load_world_into_sim(sim, world)  # 不抛异常即可

    assert sim.environment.all_nodes()


# --------------------------------------------------------------------------
# 物理规则往返（#30）
# --------------------------------------------------------------------------

def test_physics_roundtrip_keeps_world_name_and_tables():
    engine = PhysicsEngine(world_name="stone_age")
    engine.material_properties["BERRY"] = {
        "nutrition": 777, "disease_chance": 0.0, "spoil_rate": 0.0,
    }
    engine.terrain_hazards["Cave"] = {"night_predator_chance": 0.0, "predator_damage": 0}
    engine.weapon_modifiers["SPEAR"] = 9.0
    engine.recipes.append(Recipe("烤肉", {"RAW_MEAT": 1}, {"COOKED_MEAT": 1}))

    restored = PhysicsEngine.from_dict(engine.to_dict())

    assert restored.world_name == "stone_age"
    assert restored.material_properties["BERRY"]["nutrition"] == 777
    assert restored.terrain_hazards["Cave"]["predator_damage"] == 0
    assert restored.weapon_modifiers["SPEAR"] == 9.0
    assert [r.name for r in restored.recipes] == ["烤肉"]


def test_physics_from_dict_defaults_world_name():
    engine = PhysicsEngine.from_dict({"recipes": []})
    assert engine.world_name == "smallville"
    assert engine.material_properties


def test_legacy_physics_payload_adopts_sim_world(tmp_path, monkeypatch):
    """旧存档 physics 段没有 world_name：必须跟随 sim 的世界，而不是静默回落 smallville。"""
    sim = _new_sim(tmp_path, monkeypatch)
    legacy = {
        "clock": sim.clock.isoformat(),
        "physics": {"recipes": []},
        "agents": [],
    }

    sim._load_world_state_data(legacy)

    assert sim.physics.world_name == sim.world_name


def test_physics_rules_survive_sim_save_load(tmp_path, monkeypatch):
    """端到端：改过的物理规则表随 sim 存档往返后仍然生效。"""
    sim = _new_sim(tmp_path, monkeypatch)
    sim.physics.material_properties["BERRY"] = {
        "nutrition": 42, "disease_chance": 0.0, "spoil_rate": 0.0,
    }
    sim.save_world_state()

    payload = json.loads(Path(sim.save_file).read_text(encoding="utf-8"))
    load_world_into_sim(sim, payload)

    assert sim.physics.material_properties["BERRY"]["nutrition"] == 42
