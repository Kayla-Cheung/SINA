"""
回归测试：检索端随机化（自变量旋钮）。
================================================================
锁住三件事：
  1. 默认关闭 —— 不开启时 retrieve_memories 与原 top-k 逐条一致；
  2. 三个条件的行为 —— A=纯 top-k，B=随机替换，C=按排名替换；
  3. 硬约束 —— 无论哪种条件，返回条数恒为 k（含池子不足时的回填）。
"""

import os

import pytest

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.retrieval_policy import (
    RetrievalConfig,
    RetrievalPolicy,
)
from sina.memory.store import EpisodicVectorStore
from sina.memory.types import (
    EpisodicMemory,
    MemoryQuery,
    MemoryRetrievalResult,
    PersonaInvariant,
)


def _result(mid: str, score: float, relevance: float = None) -> MemoryRetrievalResult:
    return MemoryRetrievalResult(
        memory=EpisodicMemory(
            memory_id=mid,
            agent_id="a",
            tick_start=1,
            tick_end=1,
            location="Cafe",
            summary=f"mem {mid}",
        ),
        composite_score=score,
        relevance_score=relevance if relevance is not None else score,
        recency_score=1.0,
        importance_score=0.5,
        decay_multiplier=1.0,
        is_confabulated=False,
    )


def _ranked(n: int):
    return [_result(f"m{i}", score=1.0 - i * 0.01, relevance=1.0 - i * 0.01) for i in range(n)]


# ── 1. 默认关闭 ────────────────────────────────────────────────────────
def test_disabled_by_default():
    assert RetrievalConfig().enabled is False
    assert RetrievalConfig.from_env({}).enabled is False
    # 非法 mode 不炸，且保持关闭
    assert RetrievalConfig.from_env({"SINA_RETRIEVAL_MODE": "bogus"}).enabled is False
    # 合法 mode 打开
    cfg = RetrievalConfig.from_env({"SINA_RETRIEVAL_MODE": "random", "SINA_RETRIEVAL_RATIO": "0.4"})
    assert cfg.enabled and cfg.mode == "random" and cfg.ratio == pytest.approx(0.4)


def test_topk_mode_is_exactly_prefix():
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="topk", ratio=0.5))
    ranked = _ranked(10)
    selected, meta = policy.select(ranked, top_k=4)
    assert [s.memory.memory_id for s in selected] == ["m0", "m1", "m2", "m3"]
    assert meta["injected"] == 0


# ── 2. 三个条件的行为 ──────────────────────────────────────────────────
def test_tail_mode_takes_next_ranked_items():
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="tail", ratio=0.5))
    ranked = _ranked(10)
    selected, meta = policy.select(ranked, top_k=4)

    # 保留 m0,m1；用排名紧随其后的 m4,m5 补上后两个槽
    assert [s.memory.memory_id for s in selected] == ["m0", "m1", "m4", "m5"]
    assert meta["injected"] == 2


def test_random_mode_draws_from_same_pool_as_tail():
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="random", ratio=0.5, seed=7))
    ranked = _ranked(10)
    selected, meta = policy.select(ranked, top_k=4)

    ids = [s.memory.memory_id for s in selected]
    assert ids[:2] == ["m0", "m1"]                 # 保留段与 C 相同
    assert meta["injected"] == 2
    assert set(ids[2:]) <= {"m4", "m5", "m6", "m7", "m8", "m9"}  # 只从 ranked[k:] 取
    # 不变量：随机选择不改变「相关性损失」的量级 —— B 与 C 同池同量
    assert meta["pool_size"] == 6


def test_random_mode_is_reproducible_with_seed():
    """同种子必须给出完全相同的选择，否则跑批结果无法归因。"""
    cfg = RetrievalConfig(enabled=True, mode="random", ratio=0.5, seed=123)
    a, _ = RetrievalPolicy(cfg).select(_ranked(10), top_k=4)
    b, _ = RetrievalPolicy(cfg).select(_ranked(10), top_k=4)
    assert [x.memory.memory_id for x in a] == [x.memory.memory_id for x in b]

    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="random", ratio=0.5, seed=1))
    first, _ = policy.select(_ranked(10), top_k=4)
    policy.reseed(1)
    second, _ = policy.select(_ranked(10), top_k=4)
    assert [x.memory.memory_id for x in first] == [x.memory.memory_id for x in second]


# ── 3. 硬约束：条数恒为 k ──────────────────────────────────────────────
@pytest.mark.parametrize("mode", ["topk", "random", "tail"])
@pytest.mark.parametrize("ratio", [0.0, 0.5, 1.0])
@pytest.mark.parametrize("n_memories,top_k", [(10, 4), (3, 5), (4, 4), (1, 3)])
def test_returned_count_always_equals_k(mode, ratio, n_memories, top_k):
    ranked = _ranked(n_memories)
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode=mode, ratio=ratio, seed=1))
    selected, meta = policy.select(ranked, top_k=top_k)
    assert len(selected) == min(top_k, n_memories)
    assert len({s.memory.memory_id for s in selected}) == len(selected)  # 不重复


def test_random_ratio_one_replaces_whole_topk():
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="tail", ratio=1.0))
    selected, meta = policy.select(_ranked(10), top_k=3)
    assert [s.memory.memory_id for s in selected] == ["m3", "m4", "m5"]
    assert meta["injected"] == 3


# ── 4. 集成：默认关闭 vs 开启 ──────────────────────────────────────────
def _mgr(policy=None):
    store = EpisodicVectorStore(dimension=64)
    mgr = HierarchicalMemoryManager(vector_store=store, retrieval_policy=policy)
    mgr.register_agent(
        PersonaInvariant(
            agent_id="Alice",
            name="Alice",
            archetype="Forager",
            core_conviction="生存",
            class_index=1.0,  # 高阶层：不触发 dropout / confabulation，隔离检索变量
            wealth_budget=5000.0,
        )
    )
    for i in range(8):
        store.add(
            EpisodicMemory(
                memory_id=f"e{i}",
                agent_id="Alice",
                tick_start=i,
                tick_end=i,
                location="Cafe",
                summary=f"Alice 在 Cafe 遇到了 Tom 第{i}次",
            )
        )
    return mgr


def test_manager_default_path_is_untouched():
    mgr = _mgr()
    assert mgr.retrieval_policy.config.enabled is False
    query = MemoryQuery(agent_id="Alice", query_text="Cafe Tom", current_tick=10, top_k=3)
    res = mgr.retrieve_memories(query)
    assert len(res) == 3
    assert mgr.last_retrieval_meta is None


def test_manager_enabled_path_records_meta():
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="random", ratio=0.5, seed=3))
    mgr = _mgr(policy)
    query = MemoryQuery(agent_id="Alice", query_text="Cafe Tom", current_tick=10, top_k=4)
    res = mgr.retrieve_memories(query)

    assert len(res) == 4
    assert mgr.last_retrieval_meta is not None
    assert mgr.last_retrieval_meta["mode"] == "random"
    assert mgr.last_retrieval_meta["k"] == 4


def test_tail_condition_injects_lower_relevance_than_kept():
    """C 条件的注入项相关度必须低于保留项 —— 这正是 B 要对照掉的那部分损失。"""
    policy = RetrievalPolicy(RetrievalConfig(enabled=True, mode="tail", ratio=0.5, seed=3))
    mgr = _mgr(policy)
    query = MemoryQuery(agent_id="Alice", query_text="Cafe Tom", current_tick=10, top_k=4)
    mgr.retrieve_memories(query)
    meta = mgr.last_retrieval_meta
    assert meta["injected_relevance"] <= meta["kept_relevance"]
