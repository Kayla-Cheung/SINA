"""
引擎健壮性回归测试。

覆盖:
- #31 DAGEngine.run 不再吞掉节点异常（否则 tick 已自增而 clock 未推进，
  且会复用上一帧的 current_logs 造成时间线重复事件）。
- #36 dict.get(..., all_nodes()[0].name) 默认值提前求值导致空地图 IndexError。
"""

import asyncio
import types

import pytest

from core.dag_engine import DAGEngine, DAGNode, NodeResult
from core.dag_simulation import SinaSimulation


class _BoomNode(DAGNode):
    async def execute(self, state):
        raise RuntimeError("boom")


class _OkNode(DAGNode):
    def __init__(self, name, next_node=None):
        super().__init__(name)
        self._next = next_node

    async def execute(self, state):
        state["visited"] = state.get("visited", []) + [self.name]
        return NodeResult(next_node=self._next)


class _FakeEnv:
    """只实现 all_nodes() 的最小环境替身，避免实例化 Observer 造成磁盘副作用。"""

    def __init__(self, nodes):
        self._nodes = nodes

    def all_nodes(self):
        return self._nodes


# --------------------------------------------------------------------------
# #31 — 异常必须冒泡
# --------------------------------------------------------------------------

def test_dag_engine_propagates_node_exception():
    engine = DAGEngine()
    engine.register_node(_BoomNode("Boom"))

    with pytest.raises(RuntimeError, match="Boom"):
        asyncio.run(engine.run(start_node="Boom"))


def test_dag_engine_does_not_report_success_after_failure():
    """失败节点之后的分支不得再被推进。"""
    engine = DAGEngine()
    engine.register_node(_BoomNode("Boom"))
    engine.register_node(_OkNode("After"))

    with pytest.raises(RuntimeError):
        asyncio.run(engine.run(start_node="Boom"))

    assert "After" not in engine.global_state.get("visited", [])


def test_dag_engine_still_runs_happy_path():
    engine = DAGEngine()
    engine.register_node(_OkNode("A", next_node="B"))
    engine.register_node(_OkNode("B"))

    state = asyncio.run(engine.run(start_node="A"))

    assert state["visited"] == ["A", "B"]


# --------------------------------------------------------------------------
# #36 — 空地图必须给出清晰错误，而不是 IndexError
# --------------------------------------------------------------------------

def _stub_sim(nodes):
    return types.SimpleNamespace(world_name="empty_world", environment=_FakeEnv(nodes))


def test_first_room_name_raises_clear_error_on_empty_map():
    stub = _stub_sim([])

    with pytest.raises(ValueError, match="地图为空"):
        SinaSimulation._first_room_name(stub)


def test_first_room_name_returns_first_node_when_present():
    node = types.SimpleNamespace(name="Cafe")
    stub = _stub_sim([node, types.SimpleNamespace(name="Park")])

    assert SinaSimulation._first_room_name(stub) == "Cafe"
