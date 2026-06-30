"""
agent_state.py — 智能体状态数据结构
=====================================
SINA v4 前文明模拟引擎

设计哲学：
  AgentState 是纯数据容器，不包含任何 LLM 调用逻辑。
  所有字段均可序列化/反序列化，用于存档和状态回放。
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
        self.traits: str = traits          
        self.intentions: list = intentions 

        # ── 行动状态 ──
        self.current_action: str = "发呆中"
        self.action_end_time: datetime = start_time or datetime.now()

        # ── 感知与记忆 ──
        self.known_nearby: set = set()       
        self.memory_stream: list = []        
        self.pending_events: list = []       

        # ── 反思机制 ──
        self.importance_accumulator: int = 0  

        # ── 生存指标 ──
        self.hunger: int = 30             
        self.inventory: dict = {}         

        # ── 生死状态 ──
        self.is_dead: bool = False          
        self.is_comatose: bool = False      

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
            "hunger": self.hunger,
            "inventory": dict(self.inventory),
            "is_dead": self.is_dead,
            "is_comatose": self.is_comatose,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentState":
        end_time_raw = data.get("action_end_time")
        end_time = datetime.fromisoformat(end_time_raw) if end_time_raw else None

        agent = cls(
            name=data["name"],
            traits=data["traits"],
            intentions=data.get("intentions", []),
            start_time=end_time,
        )

        agent.current_action = data.get("current_action", "发呆中")
        agent.action_end_time = end_time
        agent.known_nearby = set(data.get("known_nearby", []))
        agent.memory_stream = data.get("memory_stream", [])
        agent.pending_events = data.get("pending_events", [])
        agent.importance_accumulator = data.get("importance_accumulator", 0)
        
        agent.hunger = data.get("hunger", 30)
        
        agent.inventory = data.get("inventory", {})
        agent.is_dead = data.get("is_dead", False)
        agent.is_comatose = data.get("is_comatose", False)

        return agent

    def __repr__(self) -> str:
        status = "💀" if self.is_dead else ("😵‍💫" if self.is_comatose else "👨")
        return f"<AgentState {status} {self.name} HUNGER={self.hunger} items={len(self.inventory)}>"
