"""
environment.py — SINA v4 前文明原始拓扑矩阵
============================================
构建一个带有自然资源分布的沙盒拓扑。
每个区域节点(EnvNode)持有自然资源、空间属性、以及驻留智能体。
"""

class EnvNode:
    """环境节点：空间拓扑中的一个区域"""

    def __init__(self, name: str, parent=None, description: str = ''):
        self.name = name
        self.parent = parent
        self.children: list['EnvNode'] = []
        self.objects: list[str] = []        
        self.agents: list[str] = []         
        self.inventory: dict[str, int] = {} 
        self.locked_by: str | None = None   
        self.description = description

    def add_child(self, child_node: 'EnvNode') -> 'EnvNode':
        child_node.parent = self
        self.children.append(child_node)
        return child_node

    def __repr__(self) -> str:
        return f"EnvNode('{self.name}', agents={self.agents}, inv={self.inventory})"


import json
import os

class SandboxEnvironment:
    """
    沙盒环境：管理整个前文明的拓扑结构与资源。
    """
    def __init__(self, world_name: str = "stone_age"):
        self.root = EnvNode('World_Matrix')
        self.agent_locations: dict[str, EnvNode] = {}
        
        # 动态加载地图 JSON
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        map_path = os.path.join(base_dir, "worlds", world_name, "config", "map.json")
        
        if os.path.exists(map_path):
            with open(map_path, "r", encoding="utf-8") as f:
                map_data = json.load(f)
            self._build_tree(self.root, map_data.get("children", []))
        else:
            print(f"⚠ Warning: Map config not found at {map_path}")

    def _build_tree(self, parent_node: EnvNode, children_data: list):
        for child_data in children_data:
            child_node = parent_node.add_child(EnvNode(
                child_data.get("name"),
                description=child_data.get("description", "")
            ))
            child_node.objects = child_data.get("objects", [])
            child_node.inventory = child_data.get("inventory", {})
            
            if "children" in child_data:
                self._build_tree(child_node, child_data["children"])

    def spawn_agent(self, agent_name: str, node: EnvNode) -> None:
        node.agents.append(agent_name)
        self.agent_locations[agent_name] = node

    def move_agent(self, agent_name: str, new_node: EnvNode) -> None:
        old_node = self.agent_locations.get(agent_name)
        if old_node and agent_name in old_node.agents:
            old_node.agents.remove(agent_name)
        new_node.agents.append(agent_name)
        self.agent_locations[agent_name] = new_node

    def perceive(self, agent_name: str) -> str:
        node = self.agent_locations.get(agent_name)
        if not node:
            return "你迷失在了虚空中。"

        lines = [
            f"【当前位置】{node.name}",
            f"【环境描述】{node.description}",
        ]

        if node.objects:
            lines.append(f"【可见物体】{'、'.join(node.objects)}")

        others = [a for a in node.agents if a != agent_name]
        if others:
            lines.append(f"【在场的其他人】{'、'.join(others)}")
        else:
            lines.append("【在场的其他人】四周无人，非常安静")

        if node.inventory:
            available = [tag for tag, qty in node.inventory.items() if qty > 0]
            if available:
                lines.append(f"【可互动的物品】{'、'.join(available)}")

        return '\n'.join(lines)

    def all_nodes(self) -> list[EnvNode]:
        """动态返回所有的物理叶子节点（即实际房间）"""
        nodes = []
        def traverse(node):
            if not node.children and node.name != 'World_Matrix':
                nodes.append(node)
            for c in node.children:
                traverse(c)
        traverse(self.root)
        return nodes

    def get_node_by_name(self, name: str) -> EnvNode | None:
        for node in self.all_nodes():
            if node.name == name:
                return node
        # Fallback to traversing everything if it's a structural node
        nodes = []
        def traverse_all(node):
            nodes.append(node)
            for c in node.children:
                traverse_all(c)
        traverse_all(self.root)
        for n in nodes:
            if n.name == name: return n
        return None
