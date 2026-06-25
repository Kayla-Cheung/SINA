"""
meme_pool.py — 模因池（主观层）
================================
SINA v4 双层架构 · 前文明多智能体仿真

设计哲学：
  模因池是双层架构的「主观层」——由智能体共识动态构建。
  与物理引擎（客观层）不同，模因可以被经验证伪和衰减：
    - 「向天祈祷可以止雨」会因反复失败而被智能体抛弃
    - 「偷窃者会被诅咒」即使物理上无效，但社会惩罚使其持续

  模因通过 get_prompt_injection() 注入到智能体的 LLM prompt 中，
  影响它们的决策和行为——但不改变物理结果。
  这实现了「信念影响行为，但不改变物理」的核心设计目标。

  模因类别：
    🪬 religion          — 宗教信仰（创世神话、神灵崇拜）
    📜 social_contract   — 社会契约（分配规则、领导权）
    🚫 taboo             — 禁忌（食物禁忌、行为禁忌）
    🌀 superstition      — 迷信（因果关联错觉，可被证伪）
    🔧 technology_belief — 技术信念（「火能驱兽」在被 Oracle 确认前属于此类）
"""

from copy import deepcopy


class Meme:
    """
    单个文化模因/信念。

    生命周期：
      1. 由 Laplace Oracle 将提案裁决为「主观层」时创建
      2. 通过 get_prompt_injection() 影响所有智能体的行为
      3. 迷信类模因会被智能体的失败经验逐渐证伪
      4. belief_strength 降至 0 时从模因池中移除
    """

    # 有效的模因类别
    VALID_CATEGORIES = frozenset({
        "religion",
        "social_contract",
        "taboo",
        "superstition",
        "technology_belief",
    })

    def __init__(
        self,
        content: str,
        category: str,
        proposer: str,
        penalty_description: str = None,
    ):
        if category not in self.VALID_CATEGORIES:
            raise ValueError(
                f"无效的模因类别 '{category}'，"
                f"有效值：{', '.join(sorted(self.VALID_CATEGORIES))}"
            )

        self.content: str = content                    # 信念内容（自然语言）
        self.category: str = category                  # 模因类别
        self.proposer: str = proposer                  # 提出者
        self.penalty_description: str = penalty_description  # 违反时的惩罚描述
        self.created_tick: int = 0                     # 创建时的世界 tick
        self.belief_strength: float = 1.0              # 信念强度（0.0 ~ 1.0）
        self.disconfirmation_count: int = 0            # 被证伪次数

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "proposer": self.proposer,
            "penalty_description": self.penalty_description,
            "created_tick": self.created_tick,
            "belief_strength": self.belief_strength,
            "disconfirmation_count": self.disconfirmation_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Meme":
        meme = cls(
            content=data["content"],
            category=data["category"],
            proposer=data["proposer"],
            penalty_description=data.get("penalty_description"),
        )
        meme.created_tick = data.get("created_tick", 0)
        meme.belief_strength = data.get("belief_strength", 1.0)
        meme.disconfirmation_count = data.get("disconfirmation_count", 0)
        return meme

    def __repr__(self) -> str:
        return (
            f"<Meme [{self.category}] strength={self.belief_strength:.1f} "
            f"'{self.content[:30]}...'>"
        )


class MemePool:
    """
    文化模因池——管理部落的集体信念系统。

    职责：
      1. 维护活跃模因列表
      2. 生成 prompt 注入文本（影响智能体的 LLM 决策）
      3. 自然衰减：根据智能体记忆中的证伪证据削弱迷信类模因
    """

    # 类别 → emoji 图标映射
    _CATEGORY_ICONS = {
        "religion":          "🪬",
        "social_contract":   "📜",
        "taboo":             "🚫",
        "superstition":      "🌀",
        "technology_belief": "🔧",
    }

    # 证伪关键词（用于在智能体记忆中搜索反面证据）
    _DISCONFIRMATION_KEYWORDS = [
        "没有效果",
        "并没有",
        "不管用",
        "no effect",
        "失败了",
        "没有发生",
        "毫无作用",
    ]

    def __init__(self):
        self.active_memes: list[Meme] = []

    # ────────────────────────────────────────
    #  模因管理
    # ────────────────────────────────────────

    def add_meme(self, meme: Meme) -> None:
        """向模因池添加新的信念。"""
        self.active_memes.append(meme)

    # ────────────────────────────────────────
    #  Prompt 注入生成
    # ────────────────────────────────────────

    def get_prompt_injection(self) -> str:
        """
        生成信念系统的 prompt 注入文本。

        该文本会被附加到每个智能体的系统提示中，
        使 LLM 在决策时将这些信念纳入考量。
        智能体可以私下怀疑，但公开违抗需要勇气。
        """
        if not self.active_memes:
            return ""

        lines = [
            "═══ 部落信念体系 ═══",
            "以下是部落当前共同持有的信念和规则。",
            "作为部落成员，你在内心深处了解这些信念。",
            "",
        ]

        # 按类别分组输出
        categories_seen = {}
        for meme in self.active_memes:
            if meme.category not in categories_seen:
                categories_seen[meme.category] = []
            categories_seen[meme.category].append(meme)

        for category, memes in categories_seen.items():
            icon = self._CATEGORY_ICONS.get(category, "❓")
            category_label = {
                "religion": "宗教信仰",
                "social_contract": "社会契约",
                "taboo": "禁忌",
                "superstition": "迷信传说",
                "technology_belief": "技术信念",
            }.get(category, category)

            lines.append(f"{icon} 【{category_label}】")
            for meme in memes:
                strength_bar = "●" * int(meme.belief_strength * 5) + "○" * (5 - int(meme.belief_strength * 5))
                lines.append(f"  • {meme.content} [{strength_bar}]")
                if meme.penalty_description:
                    lines.append(f"    ⚠ 违反后果：{meme.penalty_description}")
            lines.append("")

        lines.append(
            "💭 你可以在内心私下怀疑这些信念，"
            "但公开违抗部落共识需要极大的勇气，"
            "并可能招致社会惩罚。"
        )

        return "\n".join(lines)

    # ────────────────────────────────────────
    #  模因自然衰减
    # ────────────────────────────────────────

    def decay_memes(self, world_agents: list) -> list[Meme]:
        """
        检查迷信类模因的证伪证据，衰减其信念强度。

        机制：
          - 仅对 'superstition' 类别的模因进行证伪检测
          - 扫描所有智能体的近期记忆，搜索证伪关键词
          - 每发现一条证伪证据，belief_strength 减少 0.1
          - belief_strength 降至 0 或以下时，模因被移除

        Args:
            world_agents: 所有智能体的 AgentState 列表

        Returns:
            被移除的模因列表
        """
        removed_memes = []
        surviving_memes = []

        for meme in self.active_memes:
            # 仅对迷信类模因进行证伪衰减
            if meme.category != "superstition":
                surviving_memes.append(meme)
                continue

            # 搜索所有智能体的记忆流中的证伪证据
            disconfirmation_found = False
            for agent in world_agents:
                for memory in agent.memory_stream:
                    memory_content = memory.get("content", "") if isinstance(memory, dict) else str(memory)
                    for keyword in self._DISCONFIRMATION_KEYWORDS:
                        if keyword in memory_content:
                            disconfirmation_found = True
                            break
                    if disconfirmation_found:
                        break
                if disconfirmation_found:
                    break

            if disconfirmation_found:
                meme.disconfirmation_count += 1
                meme.belief_strength -= 0.1

            # 判断是否存活
            if meme.belief_strength <= 0:
                removed_memes.append(meme)
            else:
                surviving_memes.append(meme)

        self.active_memes = surviving_memes
        return removed_memes

    # ────────────────────────────────────────
    #  序列化
    # ────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "active_memes": [m.to_dict() for m in self.active_memes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemePool":
        pool = cls()
        pool.active_memes = [
            Meme.from_dict(m) for m in data.get("active_memes", [])
        ]
        return pool

    def __repr__(self) -> str:
        category_counts = {}
        for meme in self.active_memes:
            category_counts[meme.category] = category_counts.get(meme.category, 0) + 1
        counts_str = ", ".join(f"{k}={v}" for k, v in category_counts.items())
        return f"<MemePool total={len(self.active_memes)} {counts_str}>"
