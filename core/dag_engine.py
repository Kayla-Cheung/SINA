from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class NodeResult:
    """节点执行结果"""
    next_node: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None

class DAGNode:
    """DAG/FSM 独立执行节点，物理隔离状态逻辑"""
    def __init__(self, name: str):
        self.name = name

    async def execute(self, state: Dict[str, Any]) -> NodeResult:
        raise NotImplementedError("Subclasses must implement execute()")

class DAGEngine:
    """
    DAG 状态机引擎 (Orchestrator)
    替代掉传统 while True，接管所有的流转控制权
    """
    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}
        self.global_state: Dict[str, Any] = {}

    def register_node(self, node: DAGNode):
        self.nodes[node.name] = node

    async def run(self, start_node: str, initial_state: Dict[str, Any] = None):
        if initial_state:
            self.global_state.update(initial_state)

        current_node_name = start_node

        while current_node_name:
            if current_node_name not in self.nodes:
                raise ValueError(f"Fatal: Node '{current_node_name}' not found in DAG.")

            node = self.nodes[current_node_name]

            try:
                result = await node.execute(self.global_state)

                if result.payload:
                    self.global_state.update(result.payload)

                current_node_name = result.next_node

            except Exception as e:
                # 不再静默 break：节点异常必须冒泡，否则调用方会把「失败的一帧」当作成功，
                # 导致 tick_count 已自增而 clock 未推进的失步，并复用陈旧的 current_logs。
                print(f"[Engine] Fatal Error in {current_node_name}: {e}")
                import traceback
                traceback.print_exc()
                raise RuntimeError(f"DAG 节点 '{current_node_name}' 执行失败: {e}") from e

        return self.global_state
