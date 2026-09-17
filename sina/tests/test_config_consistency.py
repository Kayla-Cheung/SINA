"""
世界配置交叉引用一致性测试（#45）。

一次性防住"物品 tag 未在 physics 定义 / 房间缺 terrain_hazard / start_room 打偏 /
prompt key 缺失"这类配置漂移：遍历两个世界的 config/*.json，做集合差断言。
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORLDS = ["smallville", "stone_age"]

# dynamic_engine.py 读取的 prompt key（与 #45 核对清单一致）
PROMPT_KEYS = {
    "community_term",
    "identity_rules",
    "survival_rules",
    "language_rules",
    "format_thought",
    "format_action",
}


def _load(world: str, name: str) -> dict:
    with open(REPO_ROOT / "worlds" / world / "config" / name, encoding="utf-8") as f:
        return json.load(f)


def _leaf_nodes(node: dict, out: list) -> None:
    children = node.get("children", [])
    if not children:
        if node.get("name") != "World_Matrix":
            out.append(node)
        return
    for child in children:
        _leaf_nodes(child, out)


def _collect_inventory_tags(node: dict, tags: set) -> None:
    tags.update(node.get("inventory", {}).keys())
    for child in node.get("children", []):
        _collect_inventory_tags(child, tags)


@pytest.mark.parametrize("world", WORLDS)
def test_room_names_have_terrain_hazard(world):
    map_data = _load(world, "map.json")
    physics = _load(world, "physics.json")

    rooms = []
    _leaf_nodes(map_data, rooms)
    room_names = {r["name"] for r in rooms}
    hazards = set(physics.get("terrain_hazards", {}).keys())

    missing = room_names - hazards
    assert not missing, f"{world}: 房间缺少 terrain_hazard 定义: {missing}"


@pytest.mark.parametrize("world", WORLDS)
def test_item_tags_are_defined_in_physics(world):
    map_data = _load(world, "map.json")
    agents = _load(world, "agents.json")
    physics = _load(world, "physics.json")
    materials = set(physics.get("material_properties", {}).keys())

    tags = set()
    _collect_inventory_tags(map_data, tags)
    for a in agents.get("agents", []):
        tags.update(a.get("inventory", {}).keys())

    missing = tags - materials
    assert not missing, f"{world}: 物品 tag 未在 material_properties 定义: {missing}"


@pytest.mark.parametrize("world", WORLDS)
def test_start_rooms_hit_map_leaves(world):
    map_data = _load(world, "map.json")
    agents = _load(world, "agents.json")

    rooms = []
    _leaf_nodes(map_data, rooms)
    room_names = {r["name"] for r in rooms}
    start_rooms = {a.get("start_room") for a in agents.get("agents", []) if a.get("start_room")}

    missing = start_rooms - room_names
    assert not missing, f"{world}: start_room 打偏（地图上无此房间）: {missing}"


@pytest.mark.parametrize("world", WORLDS)
def test_prompt_keys_are_present(world):
    prompt = _load(world, "prompt.json")

    missing = PROMPT_KEYS - set(prompt.keys())
    assert not missing, f"{world}: prompt.json 缺失 dynamic_engine 读取的 key: {missing}"


@pytest.mark.parametrize("world", WORLDS)
def test_material_fields_are_complete(world):
    physics = _load(world, "physics.json")
    required = {"nutrition", "spoil_rate", "disease_chance"}

    for tag, props in physics.get("material_properties", {}).items():
        missing = required - set(props.keys())
        assert not missing, f"{world}: {tag} 的材质属性缺字段 {missing}"


@pytest.mark.parametrize("world", WORLDS)
def test_terrain_fields_are_complete(world):
    physics = _load(world, "physics.json")
    required = {"night_predator_chance", "predator_damage"}

    for room, props in physics.get("terrain_hazards", {}).items():
        missing = required - set(props.keys())
        assert not missing, f"{world}: {room} 的 terrain_hazard 缺字段 {missing}"
