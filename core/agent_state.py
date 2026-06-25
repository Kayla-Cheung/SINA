"""
agent_state.py — 智能体状态数据结构
=====================================
SINA v4 霍格沃茨开学周矩阵 · 社会学仿真引擎

设计哲学：
  AgentState 是纯数据容器，不包含任何 LLM 调用逻辑。
  所有字段均可序列化/反序列化，用于存档和状态回放。
  摒弃原始生存属性，引入 Stamina（精力值）和 Mood（理智/情绪值）。
  当双值极低时，触发 Burnout（耗竭/发疯）状态。
"""

from datetime import datetime
from copy import deepcopy


class AgentState:
    """单个智能体的完整运行时状态。"""

    def __init__(
        self,
        name: str,
        traits: str,
        intentions: list,
        start_time: datetime = None,
    ):
        # ── 身份与性格 ──
        self.name: str = name
        self.traits: str = traits          # 自然语言描述的性格特征（如：野心勃勃的纯血巫师）
        self.intentions: list = intentions  # 初始意图列表（如 ['寻找密室', '结交斯莱特林']）

        # ── 行动状态 ──
        self.current_action: str = "刚刚踏上霍格沃茨特快"
        self.action_end_time: datetime = start_time or datetime.now()

        # ── 感知与记忆 ──
        self.known_nearby: set = set()       # 当前感知到的附近智能体名称
        self.memory_stream: list = []        # 记忆流：[{tick, type, content, importance, ...}, ...]
        self.pending_events: list = []       # 待处理事件队列

        # ── 反思机制 ──
        self.importance_accumulator: int = 0  # 重要性累加器，达到阈值触发反思

        # ── 生存/魔法指标 (v4 重写) ──
        self.stamina: int = 100             # 精力值（满值100，深夜游荡扣除）
        self.mood: int = 100                # 情绪/理智值（满值100，社交冲突或禁林惩罚扣除）
        self.inventory: dict = {}           # 魔法背包：{item_tag: count, ...}

        # ── 生死/发疯状态 ──
        self.is_dead: bool = False          # 是否已出局/退学
        self.is_burnout: bool = False       # 是否处于耗竭/发疯状态（Stamina 或 Mood 极低时触发）

    # ────────────────────────────────────────
    #  序列化
    # ────────────────────────────────────────

    def to_dict(self) -> dict:
        """将智能体状态序列化为可 JSON 化的字典。"""
        return {
            "name": self.name,
            "traits": self.traits,
            "intentions": list(self.intentions),
            "current_action": self.current_action,
            "action_end_time": self.action_end_time.isoformat() if self.action_end_time else None,
            "known_nearby": list(self.known_nearby),
            "memory_stream": deepcopy(self.memory_stream),
            "pending_events": deepcopy(self.pending_events),
            "importance_accumulator": self.importance_accumulator,
            "stamina": self.stamina,
            "mood": self.mood,
            "inventory": dict(self.inventory),
            "is_dead": self.is_dead,
            "is_burnout": self.is_burnout,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        """从字典反序列化为 AgentState 实例。"""
        # 解析 action_end_time
        end_time_raw = data.get("action_end_time")
        end_time = datetime.fromisoformat(end_time_raw) if end_time_raw else None

        agent = cls(
            name=data["name"],
            traits=data["traits"],
            intentions=data.get("intentions", []),
            start_time=end_time,
        )

        agent.current_action = data.get("current_action", "刚刚踏上霍格沃茨特快")
        agent.action_end_time = end_time
        agent.known_nearby = set(data.get("known_nearby", []))
        agent.memory_stream = data.get("memory_stream", [])
        agent.pending_events = data.get("pending_events", [])
        agent.importance_accumulator = data.get("importance_accumulator", 0)
        
        # 兼容旧版本数据（如果读取 v3 存档）
        agent.stamina = data.get("stamina", data.get("hunger", 15) * 5)
        agent.mood = data.get("mood", 100)
        
        agent.inventory = data.get("inventory", {})
        agent.is_dead = data.get("is_dead", False)
        agent.is_burnout = data.get("is_burnout", data.get("is_comatose", False))

        return agent

    # ────────────────────────────────────────
    #  调试表示
    # ────────────────────────────────────────

    def __repr__(self) -> str:
        status = "💀" if self.is_dead else ("😵‍💫" if self.is_burnout else "🧙")
        return f"<AgentState {status} {self.name} STA={self.stamina} MOOD={self.mood} items={len(self.inventory)}>"
