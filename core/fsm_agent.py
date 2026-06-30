from enum import Enum, auto
from typing import Callable, Dict, Any, Awaitable
import asyncio

class AgentState(Enum):
    """定义智能体在 DAG 图中的绝对节点"""
    IDLE = auto()               # 空闲等待
    PERCEIVE = auto()           # 感知环境 (读取 Memory)
    THINK = auto()              # 调用网关推理 (Gateway)
    ACT = auto()                # 物理结算 / 发起提案
    WAIT_FOR_VOTE = auto()      # 挂起：等待其他人投票 (DAG 分支)

class FSMNode:
    """DAG 的基本单元：一个状态节点"""
    def __init__(self, name: AgentState, action: Callable[[Dict[str, Any]], Awaitable[AgentState]]):
        self.name = name
        self.action = action  # 核心：必须返回下一个要流向的状态

class AgentFSM:
    """
    智能体的状态机核心引擎。
    彻底消灭 if/else 屎山，将智能体的生命周期变成一张有向图。
    """
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.context: Dict[str, Any] = {}
        self.current_state = AgentState.IDLE
        self.nodes: Dict[AgentState, FSMNode] = {}

    def register_node(self, node: FSMNode):
        self.nodes[node.name] = node

    async def tick(self):
        """
        世界的单次推演 (Tick)。
        走到哪里，就执行哪里的函数，并严格按返回值流转到下一个节点。
        """
        if self.current_state not in self.nodes:
            print(f"[{self.agent_name}] 处于 {self.current_state} 状态，但没有定义该节点的逻辑。")
            return

        print(f"\n[{self.agent_name}] 🟢 进入节点: {self.current_state.name}")
        
        # 执行当前节点的核心逻辑，拿到下一个要去的状态
        node = self.nodes[self.current_state]
        next_state = await node.action(self.context)
        
        print(f"[{self.agent_name}] ➡️ 状态流转: {self.current_state.name} -> {next_state.name}")
        self.current_state = next_state


# ==========================================
# 实战演示：如何把 SINA 智能体塞进状态机
# ==========================================
async def node_perceive(context: dict) -> AgentState:
    print("  [Perceive] 正在读取周围环境...")
    await asyncio.sleep(0.5) # 模拟读库
    context['perceived_danger'] = False
    return AgentState.THINK

async def node_think(context: dict) -> AgentState:
    print("  [Think] 正在调用 AsyncLLMGateway 思考...")
    await asyncio.sleep(0.5)
    # 大模型决定是否要发起提案
    wants_to_propose = True 
    if wants_to_propose:
        print("  [Think] 大模型决定发起一条规则提案！")
        return AgentState.WAIT_FOR_VOTE
    else:
        return AgentState.ACT

async def node_wait(context: dict) -> AgentState:
    print("  [Wait] 进入挂起状态。在其他人投票完成前，我什么也做不了。")
    return AgentState.IDLE

async def main():
    agent = AgentFSM("Kayla_NPC")
    
    # 1. 注册图节点
    agent.register_node(FSMNode(AgentState.PERCEIVE, node_perceive))
    agent.register_node(FSMNode(AgentState.THINK, node_think))
    agent.register_node(FSMNode(AgentState.WAIT_FOR_VOTE, node_wait))
    
    # 2. 强行拉起状态机
    agent.current_state = AgentState.PERCEIVE
    
    # 模拟世界运行 3 个 Tick
    for _ in range(3):
        await agent.tick()

if __name__ == "__main__":
    asyncio.run(main())
