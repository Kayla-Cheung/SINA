"""
GodAgent 类型适配回归测试（#37）。

core/models.py 与 core/agent_state.py 各有一套 AgentState，字段不同。
god.py 原先硬编码 `agent.id` / `agent.current_location`，传入运行时智能体
（sim.world_agents 里的 agent_state.AgentState）会 AttributeError 直接冒泡。
"""

import asyncio

import core.god as god_module
from core.agent_state import AgentState as RuntimeAgentState
from core.god import GodAgent
from core.models import AgentState as ContractAgentState


def _obs(**extra):
    base = {"locations": [], "characters": [], "objects": []}
    base.update(extra)
    return base


def test_formats_runtime_agent_state():
    """运行时 AgentState 只有 name：不得再抛 AttributeError。"""
    agent = RuntimeAgentState(name="Alice")

    text = GodAgent()._format_observation(_obs(current_location="Cafe"), agent)

    assert "Alice" in text
    assert "Cafe" in text


def test_formats_contract_agent_state():
    """Pydantic 契约版 AgentState 仍按原字段渲染。"""
    agent = ContractAgentState(
        id="a1", name="Alice", persona="p", current_location="Loc_3", inventory=[]
    )

    text = GodAgent()._format_observation(_obs(), agent)

    assert "id=a1" in text
    assert "Loc_3" in text


def test_observation_failure_returns_reject(monkeypatch):
    """畸形 observation（缺 id 触发 KeyError）必须被兜底，而不是冒泡。"""
    monkeypatch.setattr(
        god_module, "gateway", type("G", (), {"generate_structured": staticmethod(lambda **k: None)})()
    )
    agent = RuntimeAgentState(name="Alice")

    decision = asyncio.run(
        GodAgent().translate("去咖啡馆", agent, _obs(locations=[{"name": "Cafe"}]))
    )

    assert decision.kind == "reject"
    assert decision.reason


def test_llm_failure_returns_reject(monkeypatch):
    class _Boom:
        async def generate_structured(self, **kwargs):
            raise RuntimeError("llm down")

    monkeypatch.setattr(god_module, "gateway", _Boom())
    agent = RuntimeAgentState(name="Alice")

    decision = asyncio.run(
        GodAgent().translate("去咖啡馆", agent, _obs(current_location="Cafe"))
    )

    assert decision.kind == "reject"
    assert "llm down" in decision.reason
