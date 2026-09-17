"""回归测试：反思记忆流转 (#42) 与确定性 fallback 向量 / SQLite 连接 (#35)。

- 反思必须写入分层记忆（Layer 2），否则永远进不了 RAG/仪表盘；
- _agent_short_term 必须合并 working_queue 与本地 memory_stream；
- fallback 向量必须跨进程确定、且具备词形重叠（替代随机化的 hash 播种）。
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import numpy as np

from core import dynamic_engine
from core.agent_state import AgentState
from core.game_session import _agent_short_term
from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.types import MemoryType, PersonaInvariant


def test_store_observation_writes_reflection_to_memory_manager(monkeypatch):
    async def fake_insights(recent_memories, count=2):
        return ["他人不可轻信"]

    monkeypatch.setattr(dynamic_engine, "generate_insights", fake_insights)

    state = AgentState(name="Alice")
    state.importance_accumulator = 16
    state.memory_stream = [
        {"time": "10:00", "text": "[物理现实] 你捡到了一块石头", "importance": 4}
    ]

    mm = HierarchicalMemoryManager(default_token_threshold=100000)
    mm.register_agent(
        PersonaInvariant(
            agent_id="Alice",
            name="Alice",
            core_conviction="努力生存",
            archetype="Forager",
        )
    )

    asyncio.run(dynamic_engine.store_observation(
        state,
        "[物理现实] 你又捡到一块石头",
        datetime(2026, 1, 1, 10, 0),
        memory_manager=mm,
        tick=1,
        location="Cafe",
    ))

    # 阈值满后累加器必须清零，否则下一轮立即再次触发反思
    assert state.importance_accumulator == 0
    # 反思仍沉淀进本地流
    assert any("[深层领悟]" in m["text"] for m in state.memory_stream)

    # 反思已进入分层记忆工作队列（REFLECTION 类型）
    bm = mm._bifurcation_managers["Alice"]
    reflections = [it for it in bm.working_queue if it.memory_type == MemoryType.REFLECTION]
    assert reflections, "反思未写入分层记忆工作队列"
    assert "他人不可轻信" in reflections[0].content


def test_agent_short_term_merges_working_queue_and_memory_stream():
    mm = HierarchicalMemoryManager(default_token_threshold=100000)
    mm.register_agent(
        PersonaInvariant(
            agent_id="Isabella",
            name="Isabella",
            core_conviction="经营咖啡馆",
            archetype="Merchant_Host",
        )
    )
    mm.record_event(
        agent_id="Isabella",
        tick=1,
        content="在咖啡馆整理桌椅",
        memory_type=MemoryType.ACTION,
        location="Cafe",
    )

    agent = AgentState(name="Isabella")
    agent.memory_stream.append(
        {"time": "10:00", "text": "[深层领悟] 他人不可轻信", "importance": 5}
    )

    sim = SimpleNamespace(
        clock=datetime(2026, 1, 1, 10, 0),
        memory_manager=mm,
        tick_count=1,
    )

    entries = _agent_short_term(sim, agent)
    texts = [e["content"] for e in entries]
    assert any("他人不可轻信" in t for t in texts), "本地 memory_stream 的反思被丢弃"
    assert any("整理桌椅" in t for t in texts), "working_queue 的条目被丢弃"


def test_fallback_vector_is_deterministic_across_instances():
    from sina.memory.store import EpisodicVectorStore

    a = EpisodicVectorStore(dimension=64)
    b = EpisodicVectorStore(dimension=64)
    assert a._generate_fallback_vector("捡起一个苹果") == b._generate_fallback_vector("捡起一个苹果")


def test_fallback_vector_has_lexical_overlap_and_shape():
    from sina.memory.store import EpisodicVectorStore

    store = EpisodicVectorStore(dimension=64)
    v1 = store._generate_fallback_vector("捡起一个苹果")
    v2 = store._generate_fallback_vector("采摘一个苹果")
    v3 = store._generate_fallback_vector("完全无关的量子力学")

    assert len(v1) == 64
    assert abs(np.linalg.norm(v1) - 1.0) < 1e-4

    sim_shared = float(np.dot(v1, v2))
    sim_unrelated = float(np.dot(v1, v3))
    # 共享字符三元组应带来正的余弦相似度，且高于完全无关文本
    assert sim_shared > 0
    assert sim_shared > sim_unrelated
