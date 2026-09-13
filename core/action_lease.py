"""
action_lease.py — SINA v4 行动租约与事件驱动中断引擎 (Action Inertia Engine)
=============================================================================
设计哲学：
  [P1] 行动惯性定律：当智能体做出长程决策（如采集、远足、睡眠）时，
       系统赋予其确定性的多 Tick「行动租约 (Action Lease)」。
       在租约有效期内，智能体由底层 FSM 物理推进，不消耗任何云端 LLM Token。
  [P2] 事件驱动中断：日常状态静默执行，仅当遭遇外部突发扰动（受袭、求生绝境、
       直接对话搭话、关键法案表决）时，触发中断矩阵（Interrupt Matrix）提前收回租约，
       重新唤醒大模型思考回路。
  [P3] 端侧降维：削减 60%~70% 的无效并发轮询，彻底阻断协程风暴与 429 报错。
"""

from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, Field


class InterruptionType(str, Enum):
    """突发扰动事件分类与优先级"""
    DAMAGE_TAKEN = "DAMAGE_TAKEN"           # 受到物理伤害 / 野兽袭击 (Priority 5, 致命)
    HUNGER_CRITICAL = "HUNGER_CRITICAL"     # 饥饿度濒死 / 昏迷临界 (Priority 5, 致命)
    DIRECT_CHAT = "DIRECT_CHAT"             # 被同一房间其他智能体直接搭话 (Priority 4, 社交)
    PROPOSAL_VOTE = "PROPOSAL_VOTE"         # 发起了涉及全员的新提案/法案 (Priority 3, 政治)
    HAZARD_DETECTED = "HAZARD_DETECTED"     # 极端天气 / 毒气蔓延 (Priority 3, 环境)
    TARGET_LOST = "TARGET_LOST"             # 交互目标离开或消失 (Priority 2, 物理)


class InterruptionEvent(BaseModel):
    """中断事件数据载荷"""
    event_type: InterruptionType
    priority: int = Field(default=3, ge=1, le=5)
    source: Optional[str] = Field(default=None, description="触发来源，如袭击者或搭话者名字")
    message: str = Field(description="中断原因描述")


class ActionLease(BaseModel):
    """
    行动租约：代表智能体对某个长程行动的时空承诺。
    """
    action_type: str = Field(description="行动类型，例如 walk / forage / sleep / craft")
    description: str = Field(description="当前行动的自然语言描述")
    total_ticks: int = Field(default=1, ge=1, description="租约总 Tick 数")
    ticks_remaining: int = Field(default=1, ge=0, description="剩余有效 Tick 数")
    interruptible: bool = Field(default=True, description="是否允许被低优先级事件打断")
    payload: Dict[str, Any] = Field(default_factory=dict, description="执行上下文（如目标地点、材料）")

    @property
    def is_active(self) -> bool:
        return self.ticks_remaining > 0

    def tick(self) -> int:
        """扣减一个 Tick 并返回剩余数"""
        if self.ticks_remaining > 0:
            self.ticks_remaining -= 1
        return self.ticks_remaining


class ActionInertiaEngine:
    """
    行动惯性引擎：统一调度行动租约与事件中断矩阵。
    """

    # 默认各类动作赋予的行动租约长度（以 Tick 为单位，1 Tick = 15 分钟）
    DEFAULT_LEASE_DURATIONS: Dict[str, int] = {
        "sleep": 4,         # 睡眠：持续 4 个 Tick (1小时)
        "rest": 2,          # 休息：2 个 Tick
        "forage": 2,        # 远途采集：2 个 Tick
        "craft": 2,         # 复杂制作：2 个 Tick
        "walk": 1,          # 移动：默认 1-2 Tick
        "wander": 1,        # 闲逛：1 Tick
        "idle": 1,          # 发呆：1 Tick
    }

    # 中断事件触发词正则启发式规则映射
    INTERRUPT_KEYWORDS: List[Tuple[List[str], InterruptionType, int]] = [
        (["攻击", "偷袭", "造成了", "掠夺", "伤害"], InterruptionType.DAMAGE_TAKEN, 5),
        (["极度饥饿", "濒临饿死", "昏迷", "倒地"], InterruptionType.HUNGER_CRITICAL, 5),
        (["对你说", "搭话", "问道", "悄悄说", "呼唤"], InterruptionType.DIRECT_CHAT, 4),
        (["发起提案", "号召投票", "部落公约"], InterruptionType.PROPOSAL_VOTE, 3),
        (["野兽", "毒气", "暴风雨", "夜幕"], InterruptionType.HAZARD_DETECTED, 3),
    ]

    def __init__(self):
        # 智能体租约映射：agent_name -> ActionLease
        self.active_leases: Dict[str, ActionLease] = {}

    def grant_lease(
        self,
        agent_name: str,
        action_type: str,
        description: str,
        duration_ticks: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        interruptible: bool = True,
    ) -> ActionLease:
        """为智能体颁发新的行动租约"""
        if duration_ticks is None:
            duration_ticks = self.DEFAULT_LEASE_DURATIONS.get(action_type.lower(), 1)

        duration_ticks = max(1, duration_ticks)
        lease = ActionLease(
            action_type=action_type,
            description=description,
            total_ticks=duration_ticks,
            ticks_remaining=duration_ticks,
            interruptible=interruptible,
            payload=payload or {},
        )
        self.active_leases[agent_name] = lease
        return lease

    def get_lease(self, agent_name: str) -> Optional[ActionLease]:
        """获取智能体当前租约"""
        lease = self.active_leases.get(agent_name)
        if lease and lease.is_active:
            return lease
        return None

    def revoke_lease(self, agent_name: str, reason: str = "") -> Optional[ActionLease]:
        """显式吊销/中断租约"""
        lease = self.active_leases.pop(agent_name, None)
        return lease

    def detect_interruption(self, pending_events: List[str]) -> Optional[InterruptionEvent]:
        """
        根据待处理事件流，通过符号模式匹配检测是否存在应当打断行动的高优先级扰动。
        """
        if not pending_events:
            return None

        highest_event: Optional[InterruptionEvent] = None

        for raw_event in pending_events:
            for keywords, itype, priority in self.INTERRUPT_KEYWORDS:
                if any(kw in raw_event for kw in keywords):
                    event_candidate = InterruptionEvent(
                        event_type=itype,
                        priority=priority,
                        message=raw_event,
                    )
                    if highest_event is None or event_candidate.priority > highest_event.priority:
                        highest_event = event_candidate

        return highest_event

    def evaluate_agent_lease(
        self,
        agent_name: str,
        pending_events: List[str],
    ) -> Tuple[bool, Optional[str], Optional[ActionLease]]:
        """
        评估智能体本帧是否需要唤醒 LLM：

        Returns:
            (need_llm_think, wake_reason, active_lease)
            - need_llm_think: True 表示必须唤醒大模型思考，False 表示由租约惯性推进
            - wake_reason: 唤醒原因（如 "租约到期", "收到突发攻击", "被搭话"）
            - active_lease: 若为 False，返回正在执行的有效租约
        """
        lease = self.get_lease(agent_name)

        # 1. 没有活跃租约，必须唤醒思考
        if not lease:
            return True, "无活跃行动租约", None

        # 2. 检查是否有突发外部中断
        interruption = self.detect_interruption(pending_events)
        if interruption:
            # 高优先级（>=3）打断非免疫性租约
            if lease.interruptible or interruption.priority >= 5:
                self.revoke_lease(agent_name, interruption.message)
                return True, f"突发中断 [{interruption.event_type.value}]: {interruption.message}", None

        # 3. 租约正常消耗 1 个 Tick
        remaining = lease.tick()
        if remaining <= 0:
            self.revoke_lease(agent_name, "租约自然耗尽")
            return True, "行动租约耗尽", None

        # 4. 租约依然有效，进入零 Token 物理惯性保持
        return False, None, lease
