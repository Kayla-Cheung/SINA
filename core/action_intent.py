"""
action_intent.py — 行动意图与提案数据结构
==========================================
SINA v4 双层架构 · 前文明多智能体仿真

设计哲学：
  ActionIntent 封装 LLM 输出的原始行动，并提供优先级排序。
  优先级规则：攻击 > 进食 > 制作 > 移动 > 其他
  这确保了致命行为在同一 tick 内优先结算（物理层硬规则）。

  Proposal 是双层架构的关键接口：
  智能体提出的蓝图/规则提案会经过 Laplace Oracle 裁决，
  决定它成为「物理配方」（客观层）还是「信念/模因」（主观层）。
"""


class ActionIntent:
    """
    封装单个智能体在一个 tick 内的行动意图。

    raw_action 字典来自 LLM 的 JSON 输出，包含以下可能的字段：
      - internal_thought:   内心独白（不可被其他智能体观察）
      - observable_action:  可观察行为描述（会进入其他智能体的感知）
      - duration_minutes:   行动预估耗时（分钟）
      - move_to:            移动目标房间名
      - eat_item:           进食物品标签
      - attack_target:      攻击目标智能体名
      - craft:              制作配方名
      - propose_blueprint:  提案内容（触发 Laplace Oracle）
      - vote_on_blueprint:  对提案的投票 {proposal_id, vote}
      - give_item:          赠与 {target, item_tag, count}
      - take_item_tag:      从房间拾取的物品标签
      - drop_item_tag:      丢弃的物品标签
      - produce_item_tag:   直接产出的物品标签（采集类行为）
    """

    # ── 行动类型 → 结算优先级（数字越小越优先） ──
    _PRIORITY_MAP = {
        "attack_target": 0,   # 攻击：最高优先，先手决定生死
        "eat_item": 1,        # 进食：维持生存
        "craft": 2,           # 制作：改变物质世界
        "move_to": 3,         # 移动：改变空间位置
    }
    _DEFAULT_PRIORITY = 4     # 其他行为（交谈、观察等）

    def __init__(self, agent_name: str, raw_action: dict, source_room: str):
        self.agent_name: str = agent_name
        self.raw_action: dict = raw_action
        self.source_room: str = source_room

    @property
    def priority(self) -> int:
        """
        根据行动类型返回结算优先级。
        在同一 tick 内，优先级高（数值小）的行动先结算。
        """
        for action_key, prio in self._PRIORITY_MAP.items():
            if self.raw_action.get(action_key):
                return prio
        return self._DEFAULT_PRIORITY

    # ── 便捷访问器 ──

    @property
    def internal_thought(self) -> str:
        return self.raw_action.get("internal_thought", "")

    @property
    def observable_action(self) -> str:
        return self.raw_action.get("observable_action", "")

    @property
    def duration_minutes(self) -> int:
        return self.raw_action.get("duration_minutes", 15)

    @property
    def move_to(self) -> str | None:
        return self.raw_action.get("move_to")

    @property
    def eat_item(self) -> str | None:
        return self.raw_action.get("eat_item")

    @property
    def attack_target(self) -> str | None:
        return self.raw_action.get("attack_target")

    @property
    def craft(self) -> str | None:
        return self.raw_action.get("craft")

    @property
    def propose_blueprint(self) -> str | None:
        return self.raw_action.get("propose_blueprint")

    @property
    def vote_on_blueprint(self) -> dict | None:
        return self.raw_action.get("vote_on_blueprint")

    @property
    def give_item(self) -> dict | None:
        return self.raw_action.get("give_item")

    @property
    def take_item_tag(self) -> str | None:
        return self.raw_action.get("take_item_tag")

    @property
    def drop_item_tag(self) -> str | None:
        return self.raw_action.get("drop_item_tag")

    @property
    def produce_item_tag(self) -> str | None:
        return self.raw_action.get("produce_item_tag")

    def __repr__(self) -> str:
        action_type = "other"
        for key in self._PRIORITY_MAP:
            if self.raw_action.get(key):
                action_type = key
                break
        return f"<ActionIntent {self.agent_name}@{self.source_room} type={action_type} prio={self.priority}>"


class Proposal:
    """
    蓝图/规则提案。

    提案流程：
      1. 智能体通过 propose_blueprint 提交内容
      2. 同房间智能体投票（vote_on_blueprint）
      3. 投票通过后交由 Laplace Oracle 裁决：
         - 若提案描述的是可验证的物理过程 → 成为 Recipe（物理层）
         - 若提案描述的是信念、禁忌、仪式等 → 成为 Meme（主观层）
    """

    def __init__(self, proposer: str, content: str):
        self.proposer: str = proposer         # 提案者智能体名
        self.content: str = content           # 提案文本内容
        self.votes: dict = {}                 # {agent_name: 'approve'|'reject', ...}
        self.status: str = "pending"          # 'pending' | 'approved' | 'rejected' | 'oracle_decided'
        self.oracle_verdict: dict | None = None  # Laplace Oracle 裁决结果

    @property
    def approval_count(self) -> int:
        """赞成票数。"""
        return sum(1 for v in self.votes.values() if v == "approve")

    @property
    def rejection_count(self) -> int:
        """反对票数。"""
        return sum(1 for v in self.votes.values() if v == "reject")

    def __repr__(self) -> str:
        return (
            f"<Proposal by={self.proposer} status={self.status} "
            f"votes={self.approval_count}✓/{self.rejection_count}✗>"
        )
