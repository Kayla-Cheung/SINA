"""
environment.py — SINA v4 霍格沃茨开学周矩阵
============================================
构建一个带有严格宵禁与魔法资源分布的沙盒拓扑。
每个区域节点(EnvNode)持有魔法物品、空间属性、以及驻留智能体。
"""

class EnvNode:
    """环境节点：空间拓扑中的一个房间或区域"""

    def __init__(self, name: str, parent=None, description: str = ''):
        self.name = name
        self.parent = parent
        self.children: list['EnvNode'] = []
        self.objects: list[str] = []        # 场景中可观察到的实体
        self.agents: list[str] = []         # 当前在此节点的智能体名称
        self.inventory: dict[str, int] = {} # 可用的魔法资源 {TAG: 数量}
        self.locked_by: str | None = None   # 被某智能体独占时的名称
        self.description = description

    def add_child(self, child_node: 'EnvNode') -> 'EnvNode':
        """添加子节点并设置父引用，返回子节点以便链式调用"""
        child_node.parent = self
        self.children.append(child_node)
        return child_node

    def __repr__(self) -> str:
        return f"EnvNode('{self.name}', agents={self.agents}, inv={self.inventory})"


class SandboxEnvironment:
    """
    沙盒环境：管理整个霍格沃茨开学周的拓扑结构与资源。
    
    世界树结构:
        Hogwarts_Matrix (根)
        ├── Castle_Grounds
        │   └── Great_Hall (大礼堂)
        ├── Dungeons
        │   └── Snapes_Dungeon (斯内普的地窖)
        ├── Library_Tower
        │   └── Library (图书馆)
        └── Outskirts
            ├── Black_Lake (黑湖)
            └── Forest_Edge (禁林边缘)
    """

    def __init__(self):
        # === 构建拓扑树 ===
        self.root = EnvNode('Hogwarts_Matrix')

        # 一级区域
        castle_grounds = self.root.add_child(EnvNode('Castle_Grounds'))
        dungeons = self.root.add_child(EnvNode('Dungeons'))
        library_tower = self.root.add_child(EnvNode('Library_Tower'))
        outskirts = self.root.add_child(EnvNode('Outskirts'))

        # 二级房间
        self.great_hall = castle_grounds.add_child(EnvNode(
            'Great_Hall',
            description='霍格沃茨大礼堂。天花板被施了魔法，映出外面的星空。这里是绝对安全的社交节点。'
        ))
        self.snapes_dungeon = dungeons.add_child(EnvNode(
            'Snapes_Dungeon',
            description='斯内普教授的魔药地窖。光线昏暗，气温极低。墙上的玻璃罐里泡着奇怪的标本。极度危险但可能藏有高级魔药。'
        ))
        self.library = library_tower.add_child(EnvNode(
            'Library',
            description='平斯夫人的图书馆。书架高耸入云。这里极其安静，是获取魔法知识的最佳去处。'
        ))
        self.black_lake = outskirts.add_child(EnvNode(
            'Black_Lake',
            description='平静的黑湖，湖面如镜。适合隐秘社交的偏僻角落。'
        ))
        self.forest_edge = outskirts.add_child(EnvNode(
            'Forest_Edge',
            description='禁林边缘。树木漆黑高耸，随时有违规被抓的风险，但偶尔能发现神奇动物留下的材料。'
        ))

        # === 初始化场景实体 ===
        self.great_hall.objects = ['四大学院长桌', '漂浮的蜡烛', '分院帽的凳子']
        self.snapes_dungeon.objects = ['坩埚', '曼德拉草标本', '魔药柜']
        self.library.objects = ['禁书区铁门', '《标准咒语》', '舒适的单人阅读椅']
        self.black_lake.objects = ['巨乌贼的触手痕迹', '光滑的卵石', '湖畔长椅']
        self.forest_edge.objects = ['海格的脚印', '发光的蘑菇', '警告告示牌']

        # === 初始化魔法资源 ===
        # 大礼堂提供巧克力蛙（恢复 Stamina）
        self.great_hall.inventory = {'CHOCOLATE_FROG': 20}
        # 地窖有极少量但高价值的吐真剂和魔药材料
        self.snapes_dungeon.inventory = {'VERITASERUM': 2, 'POTION_INGREDIENTS': 5}
        # 图书馆提供知识，但有咬人书的陷阱
        self.library.inventory = {'MAGIC_KNOWLEDGE': 99, 'BITING_BOOK': 3}
        # 边缘地带
        self.black_lake.inventory = {'SMOOTH_PEBBLE': 5}
        self.forest_edge.inventory = {'GLOWING_MUSHROOM': 3}

        # === 智能体位置追踪 ===
        # {agent_name: EnvNode}
        self.agent_locations: dict[str, EnvNode] = {}

    # ------------------------------------------------------------------
    # 智能体管理
    # ------------------------------------------------------------------

    def spawn_agent(self, agent_name: str, node: EnvNode) -> None:
        """将智能体放置到指定节点（初始化新生入学）"""
        node.agents.append(agent_name)
        self.agent_locations[agent_name] = node

    def move_agent(self, agent_name: str, new_node: EnvNode) -> None:
        """移动智能体（潜行或换区）"""
        old_node = self.agent_locations.get(agent_name)
        if old_node and agent_name in old_node.agents:
            old_node.agents.remove(agent_name)
        new_node.agents.append(agent_name)
        self.agent_locations[agent_name] = new_node
        # 可替换为日志记录器
        # print(f"[环境] {agent_name}: {old_node.name if old_node else '霍格沃茨特快'} → {new_node.name}")

    # ------------------------------------------------------------------
    # 感知
    # ------------------------------------------------------------------

    def perceive(self, agent_name: str) -> str:
        """
        生成智能体对当前位置的感知文本。
        包含：位置描述、可见物体、在场的其他巫师、可用资源。
        """
        node = self.agent_locations.get(agent_name)
        if not node:
            return "你迷失在了有求必应屋的夹缝中。"

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

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def all_nodes(self) -> list[EnvNode]:
        """返回所有二级（可进入的）节点"""
        return [
            self.great_hall,
            self.snapes_dungeon,
            self.library,
            self.black_lake,
            self.forest_edge,
        ]

    def get_node_by_name(self, name: str) -> EnvNode | None:
        """按名称查找节点"""
        for node in self.all_nodes():
            if node.name == name:
                return node
        return None
