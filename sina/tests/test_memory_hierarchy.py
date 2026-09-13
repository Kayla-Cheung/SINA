"""
Unit and Integration Tests for SINA v4 Memory Hierarchy Subsystem.
Verifies Layer 0 Invariants, Layer 1 Bifurcation & Token Bounds,
Layer 2 Vector Search, and Class-Gated Sociological Decay.
"""

import os
import tempfile

from sina.memory.types import (
    MemoryType,
    PersonaInvariant,
    WorkingMemoryItem,
    EpisodicMemory,
    MemoryQuery,
)
from sina.memory.store import EpisodicVectorStore
from sina.memory.decay import ClassGatedDecayEngine
from sina.memory.bifurcation import BifurcationManager
from sina.memory.manager import HierarchicalMemoryManager


def test_persona_invariant_header():
    p = PersonaInvariant(
        agent_id="agent_wang_xifeng",
        name="王熙凤",
        archetype="Dominant_Authority",
        core_conviction="维持贾府财政威权与自身利益不可撼动",
        class_index=0.95,
        wealth_budget=5000.0,
    )
    header = p.format_header()
    assert "王熙凤" in header
    assert "Dominant_Authority" in header
    assert "0.95" in header


def test_working_memory_token_estimation():
    item = WorkingMemoryItem(
        item_id="item_1",
        tick=1,
        location="Rongxi_Hall",
        source_agent="王熙凤",
        content="账房今日亏空银两五百两，各房月例削减三分。",
    )
    assert item.estimated_tokens > 5
    assert item.location == "Rongxi_Hall"


def test_bifurcation_manager_token_bounds():
    persona = PersonaInvariant(
        agent_id="agent_tanchun",
        name="贾探春",
        archetype="Idealist_Reformer",
        core_conviction="兴利除弊，重塑家族秩序",
        class_index=0.8,
        wealth_budget=2000.0,
    )
    store = EpisodicVectorStore(dimension=128)
    # Low threshold for testing
    bm = BifurcationManager(
        agent_id="agent_tanchun",
        persona=persona,
        vector_store=store,
        token_threshold=50,
        active_window_size=2,
    )

    # Add 10 items to trigger multiple bifurcations
    bifurcation_events = []
    for i in range(10):
        item = WorkingMemoryItem(
            item_id=f"item_{i}",
            tick=i + 1,
            location="Grand_View_Garden",
            source_agent="探春",
            content=f"第 {i+1} 步：调查大观园包揽承包收益与花木管理细则，与平儿反复核对数字。",
        )
        res = bm.append(item)
        if res is not None:
            bifurcation_events.append(res)

    # Verify bifurcation triggered
    assert len(bifurcation_events) >= 1
    # Verify working memory is bounded
    assert len(bm.working_queue) <= 4
    # Verify episodes were successfully sunken to Layer 2 store
    assert len(store) >= 1


def test_episodic_vector_store_search_and_persistence():
    store = EpisodicVectorStore(dimension=64)
    mem1 = EpisodicMemory(
        memory_id="ep_1",
        agent_id="agent_xifeng",
        tick_start=1,
        tick_end=10,
        location="Account_Office",
        involved_agents=["王熙凤", "平儿"],
        summary="王熙凤在账房扣押丫鬟月钱放高利贷，平儿暗中担忧。",
        importance=8.5,
    )
    mem2 = EpisodicMemory(
        memory_id="ep_2",
        agent_id="agent_xifeng",
        tick_start=11,
        tick_end=20,
        location="Jia_Mother_Room",
        involved_agents=["王熙凤", "贾母"],
        summary="王熙凤承欢贾母膝下，巧言令色博得满堂欢笑。",
        importance=6.0,
    )

    store.add(mem1)
    store.add(mem2)

    # Search with dummy query vector
    q_vec = store._generate_fallback_vector("账房月钱亏空")
    results = store.search(q_vec, agent_id="agent_xifeng", top_k=2)
    assert len(results) == 2

    # Test SQLite persistence
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        inserted = store.persist_to_sqlite(db_path, game_id="game_red_chamber_001")
        assert inserted == 2

        new_store = EpisodicVectorStore(dimension=64)
        loaded = new_store.load_from_sqlite(db_path, game_id="game_red_chamber_001")
        assert loaded == 2
        assert len(new_store) == 2
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_class_gated_decay_and_confabulation():
    decay_engine = ClassGatedDecayEngine(base_half_life_ticks=50.0)

    # Rich / High-Class Agent
    _p_rich = PersonaInvariant(
        agent_id="agent_rich",
        name="贾母",
        archetype="Matriarch",
        core_conviction="维持家族富贵安宁",
        class_index=1.0,
    )
    decay_rich = decay_engine.calculate_recency_decay(current_tick=100, memory_tick=10, class_index=1.0)

    # Impoverished Agent
    p_poor = PersonaInvariant(
        agent_id="agent_poor",
        name="小红",
        archetype="Subordinate_Survivor",
        core_conviction="在阶层夹缝中求生",
        class_index=0.1,
    )
    decay_poor = decay_engine.calculate_recency_decay(current_tick=100, memory_tick=10, class_index=0.1)

    # Rich agent should retain much higher memory fidelity than poor agent over 90 ticks
    assert decay_rich > decay_poor

    # Test confabulation synthesis for poor agent
    q = MemoryQuery(
        agent_id="agent_poor",
        query_text="为什么我不敢在正房多说话？",
        current_tick=100,
        current_location="Rongxi_Hall",
    )
    confab = decay_engine.generate_confabulation(p_poor, q)
    assert confab.is_confabulated is True
    assert "模糊脑补记忆" in confab.summary


def test_hierarchical_memory_manager_integration():
    mgr = HierarchicalMemoryManager(default_token_threshold=100)

    p_baoyu = PersonaInvariant(
        agent_id="agent_baoyu",
        name="贾宝玉",
        archetype="Nihilist_Rebel",
        core_conviction="追寻赤诚真情，抗拒仕途经济",
        class_index=0.9,
    )
    mgr.register_agent(p_baoyu)

    # Feed events
    for i in range(5):
        mgr.record_event(
            agent_id="agent_baoyu",
            tick=i + 1,
            content=f"宝玉在怡红院读《西厢记》，第 {i+1} 次与黛玉对视体会无声之悲。",
            memory_type=MemoryType.OBSERVATION,
            location="Yihong_Court",
            source_agent="宝玉",
        )

    prompt = mgr.assemble_prompt_context(
        agent_id="agent_baoyu",
        current_situation="贾政突然派小厮传唤宝玉去书房问话。",
        current_tick=10,
        current_location="Yihong_Court",
    )

    assert "[INVARIANT_CORE_SELF: 贾宝玉" in prompt
    assert "[LAYER 2: RECALLED EPISODIC EXPERIENCES (RAG)]" in prompt
    assert "[LAYER 1: IMMEDIATE WORKING STREAM" in prompt
    assert "西厢记" in prompt
