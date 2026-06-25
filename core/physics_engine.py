"""
physics_engine.py — 物理引擎（客观层）
=======================================
SINA v4 双层架构 · 前文明多智能体仿真

设计哲学：
  物理引擎是双层架构的「客观层」——由 Python 硬编码实现。
  无论智能体相信什么，物理规则都不会改变：
    - 生肉有 40% 概率致病，不因祈祷而降低
    - 石矛的伤害倍率固定为 3.0，不因信仰而变化
    - 食物腐败遵循固定概率，不受仪式影响

  这与 meme_pool.py（主观层）形成对比：
  主观层的信念可以被智能体的经验证伪和衰减。

  Recipe 是物理层的核心扩展机制：
  当 Laplace Oracle 将某个提案裁决为物理过程时，
  它会被转化为一个新的 Recipe 并注入物理引擎。
"""

import random
from copy import deepcopy


class Recipe:
    """
    物理配方：描述一个可验证的物质转化过程。

    例如：
      name='烤肉', inputs={'RAW_MEAT':1, 'TORCH':0}, outputs={'COOKED_MEAT':1}
      （TORCH 数量为 0 表示需要持有但不消耗）
    """

    def __init__(
        self,
        name: str,
        inputs: dict,
        outputs: dict,
        time_cost: int = 15,
        description: str = "",
    ):
        self.name: str = name
        self.inputs: dict = inputs      # {item_tag: consumed_count, ...}
        self.outputs: dict = outputs    # {item_tag: produced_count, ...}
        self.time_cost: int = time_cost  # 制作耗时（分钟）
        self.description: str = description

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "time_cost": self.time_cost,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Recipe":
        return cls(
            name=data["name"],
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
            time_cost=data.get("time_cost", 15),
            description=data.get("description", ""),
        )

    def __repr__(self) -> str:
        return f"<Recipe '{self.name}' {self.inputs} → {self.outputs}>"


class PhysicsEngine:
    """
    客观物理引擎。

    负责结算所有与物质世界交互的行为：
    进食、制作、战斗、夜间野兽袭击、食物腐败。
    所有结果由硬编码规则 + 随机数决定，不受信念影响。
    """

    def __init__(self):
        # ── 材料属性表（不可变客观属性） ──
        self.material_properties: dict = {
            "RAW_MEAT":    {"nutrition": 12, "spoil_rate": 0.3, "disease_chance": 0.4},
            "COOKED_MEAT": {"nutrition": 20, "spoil_rate": 0.1, "disease_chance": 0.0},
            "BERRY":       {"nutrition": 6, "spoil_rate": 0.5, "disease_chance": 0.05},
            "DIRT":        {"nutrition": 0, "spoil_rate": 0.0, "disease_chance": 0.8},
            "WATER":       {"nutrition": 1, "spoil_rate": 0.0, "disease_chance": 0.1},
            "WOOD":        {"nutrition": 0, "spoil_rate": 0.0, "disease_chance": 1.0},
            "STONE":       {"nutrition": 0, "spoil_rate": 0.0, "disease_chance": 1.0},
            "HERB":        {"nutrition": 0, "spoil_rate": 0.2, "disease_chance": 0.0},
            "TORCH":       {"nutrition": 0, "spoil_rate": 0.0, "disease_chance": 0.0},
            "SPEAR":       {"nutrition": 0, "spoil_rate": 0.0, "disease_chance": 0.0},
        }

        # ── 配方列表（可通过 Laplace Oracle 动态扩展） ──
        self.recipes: list[Recipe] = []

        # ── 地形危险度（夜间野兽袭击概率与伤害） ──
        self.terrain_hazards: dict = {
            "Open_Plains":  {"night_predator_chance": 0.3, "predator_damage": 5},
            "Dense_Forest": {"night_predator_chance": 0.5, "predator_damage": 7},
            "Riverbank":    {"night_predator_chance": 0.1, "predator_damage": 3},
            "Dark_Cave":    {"night_predator_chance": 0.0, "predator_damage": 0},
        }

        # ── 武器伤害倍率 ──
        self.weapon_modifiers: dict = {
            "FIST":  1.0,
            "STONE": 1.5,
            "SPEAR": 3.0,
            "TORCH": 2.0,
        }

    # ────────────────────────────────────────
    #  进食结算
    # ────────────────────────────────────────

    def resolve_eat(self, agent, item_tag: str) -> dict:
        """
        结算进食行为。

        物理规则：
          - 营养值直接恢复 hunger
          - 疾病概率由材料属性决定，与信仰无关
          - 吃不可食用物（如木头）几乎必定致病

        Returns:
            {hunger_restored, side_effect, disease_description?, hunger_penalty?}
        """
        props = self.material_properties.get(item_tag)

        # 未知物品：默认有毒
        if props is None:
            return {
                "hunger_restored": 0,
                "side_effect": "disease",
                "disease_description": f"{agent.name} 吃了未知物质 {item_tag}，严重腹泻。",
                "hunger_penalty": 3,
            }

        result = {
            "hunger_restored": props["nutrition"],
            "side_effect": "none",
        }

        # 疾病判定
        if random.random() < props["disease_chance"]:
            penalty = max(1, props["nutrition"])  # 至少扣 1 点
            result["side_effect"] = "disease"
            result["disease_description"] = (
                f"{agent.name} 吃了 {item_tag} 后感到剧烈腹痛，身体虚弱了许多。"
            )
            result["hunger_penalty"] = penalty

        return result

    # ────────────────────────────────────────
    #  制作结算
    # ────────────────────────────────────────

    def resolve_craft(self, agent, recipe_name: str) -> dict:
        """
        结算制作行为。

        物理规则：
          - 必须持有所有输入材料且数量足够
          - 消耗数量为 0 的输入表示「需要持有但不消耗」
          - 成功后扣除输入、产出输出

        Returns:
            {success, reason?, produced?}
        """
        # 查找配方
        recipe = None
        for r in self.recipes:
            if r.name == recipe_name:
                recipe = r
                break

        if recipe is None:
            return {"success": False, "reason": f"未知配方：{recipe_name}"}

        # 检查输入材料
        for item_tag, required_count in recipe.inputs.items():
            held = agent.inventory.get(item_tag, 0)
            # 数量为 0 表示仅需持有（至少 1 个）
            min_required = required_count if required_count > 0 else 1
            if held < min_required:
                return {
                    "success": False,
                    "reason": f"缺少材料 {item_tag}（需要 {min_required}，持有 {held}）",
                }

        # 扣除消耗的输入
        for item_tag, consumed in recipe.inputs.items():
            if consumed > 0:
                agent.inventory[item_tag] = agent.inventory.get(item_tag, 0) - consumed
                if agent.inventory[item_tag] <= 0:
                    del agent.inventory[item_tag]

        # 产出
        produced = {}
        for item_tag, count in recipe.outputs.items():
            agent.inventory[item_tag] = agent.inventory.get(item_tag, 0) + count
            produced[item_tag] = count

        return {"success": True, "produced": produced}

    # ────────────────────────────────────────
    #  战斗结算
    # ────────────────────────────────────────

    def resolve_combat(self, attacker, defender) -> dict:
        """
        结算战斗行为。

        物理规则：
          - 战斗力 = hunger × 武器倍率 × 随机波动(0.7~1.3)
          - 战斗力高者获胜
          - 败者损失 hunger，部分物品被掠夺
          - 赤手空拳（FIST）倍率为 1.0

        Returns:
            {winner, loser, loot_transferred, loser_hunger_penalty}
        """
        # 确定武器
        def _get_best_weapon(agent) -> tuple[str, float]:
            best_weapon = "FIST"
            best_modifier = self.weapon_modifiers["FIST"]
            for weapon, modifier in self.weapon_modifiers.items():
                if weapon != "FIST" and agent.inventory.get(weapon, 0) > 0:
                    if modifier > best_modifier:
                        best_weapon = weapon
                        best_modifier = modifier
            return best_weapon, best_modifier

        atk_weapon, atk_mod = _get_best_weapon(attacker)
        def_weapon, def_mod = _get_best_weapon(defender)

        # 计算战斗力（hunger × 武器倍率 × 随机波动）
        atk_power = max(1, attacker.hunger) * atk_mod * random.uniform(0.7, 1.3)
        def_power = max(1, defender.hunger) * def_mod * random.uniform(0.7, 1.3)

        if atk_power >= def_power:
            winner, loser = attacker, defender
        else:
            winner, loser = defender, attacker

        # 败者 hunger 惩罚
        loser_penalty = random.randint(3, 6)

        # 掠夺败者随机一件物品
        loot_transferred = {}
        loser_items = list(loser.inventory.keys())
        if loser_items:
            stolen_tag = random.choice(loser_items)
            stolen_count = 1
            loser.inventory[stolen_tag] = loser.inventory.get(stolen_tag, 0) - stolen_count
            if loser.inventory[stolen_tag] <= 0:
                del loser.inventory[stolen_tag]
            winner.inventory[stolen_tag] = winner.inventory.get(stolen_tag, 0) + stolen_count
            loot_transferred[stolen_tag] = stolen_count

        return {
            "winner": winner.name,
            "loser": loser.name,
            "loot_transferred": loot_transferred,
            "loser_hunger_penalty": loser_penalty,
        }

    # ────────────────────────────────────────
    #  夜间野兽袭击
    # ────────────────────────────────────────

    def resolve_night_hazard(self, agent, terrain_name: str, has_fire: bool) -> dict:
        """
        结算夜间野兽袭击。

        物理规则：
          - 袭击概率由地形决定
          - 持有火把/篝火将袭击概率降低 90%
          - 洞穴内不会有野兽袭击

        Returns:
            {attacked, damage?, description?}
        """
        hazard = self.terrain_hazards.get(terrain_name)

        if hazard is None:
            return {"attacked": False}

        chance = hazard["night_predator_chance"]

        # 火焰驱逐效果：降低 90% 概率
        if has_fire:
            chance *= 0.1

        if random.random() < chance:
            damage = hazard["predator_damage"]
            return {
                "attacked": True,
                "damage": damage,
                "description": (
                    f"夜幕降临，一头野兽从 {terrain_name} 的阴影中扑向 {agent.name}，"
                    f"造成了 {damage} 点伤害（饱食度下降）。"
                ),
            }

        return {"attacked": False}

    # ────────────────────────────────────────
    #  食物腐败
    # ────────────────────────────────────────

    def resolve_spoilage(self, room_inventory: dict) -> list:
        """
        结算房间内物品的腐败。

        物理规则：
          - 每个 tick 对房间内每件物品按 spoil_rate 独立判定
          - 腐败的物品直接从房间库存中移除

        Args:
            room_inventory: {item_tag: count, ...}（会被原地修改）

        Returns:
            list of spoiled item tags
        """
        spoiled = []

        for item_tag in list(room_inventory.keys()):
            props = self.material_properties.get(item_tag)
            if props is None:
                continue

            spoil_rate = props["spoil_rate"]
            if spoil_rate <= 0:
                continue

            count = room_inventory[item_tag]
            remaining = 0
            for _ in range(count):
                if random.random() < spoil_rate:
                    spoiled.append(item_tag)
                else:
                    remaining += 1

            if remaining > 0:
                room_inventory[item_tag] = remaining
            else:
                del room_inventory[item_tag]

        return spoiled

    # ────────────────────────────────────────
    #  配方描述（供 LLM prompt 注入）
    # ────────────────────────────────────────

    def get_known_recipes_description(self) -> str:
        """
        返回所有已发现配方的人类可读描述。
        用于注入到智能体的 LLM prompt 中。
        """
        if not self.recipes:
            return "目前部落尚未发现任何制作配方。"

        lines = ["已知的制作配方："]
        for i, recipe in enumerate(self.recipes, 1):
            inputs_str = ", ".join(
                f"{tag}×{cnt}" if cnt > 0 else f"{tag}(需持有)"
                for tag, cnt in recipe.inputs.items()
            )
            outputs_str = ", ".join(
                f"{tag}×{cnt}" for tag, cnt in recipe.outputs.items()
            )
            lines.append(
                f"  {i}. 【{recipe.name}】{inputs_str} → {outputs_str}"
                f"（耗时 {recipe.time_cost} 分钟）"
            )
            if recipe.description:
                lines.append(f"     {recipe.description}")

        return "\n".join(lines)

    # ────────────────────────────────────────
    #  序列化（仅保存动态部分：配方列表）
    # ────────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化物理引擎的动态状态（配方列表）。"""
        return {
            "recipes": [r.to_dict() for r in self.recipes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhysicsEngine":
        """从字典反序列化。材料属性和地形由构造函数硬编码恢复。"""
        engine = cls()
        engine.recipes = [
            Recipe.from_dict(r) for r in data.get("recipes", [])
        ]
        return engine

    def __repr__(self) -> str:
        return (
            f"<PhysicsEngine materials={len(self.material_properties)} "
            f"recipes={len(self.recipes)} terrains={len(self.terrain_hazards)}>"
        )
