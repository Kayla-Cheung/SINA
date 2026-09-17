"""
回归测试：联想 vs 幻觉的可数指标 N / ungrounded_rate。
================================================================
关键在于把两者分开：两个都认识的实体第一次被连起来 = 联想；
有一个根本没见过的实体 = 幻觉。混在一起就说明不了任何事。
"""

import os

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from sina.memory.novelty import (
    aggregate_novelty,
    build_memory_entity_index,
    compute_novelty,
    extract_pairs,
    mentioned_entities,
)
from sina.memory.types import EpisodicMemory

KNOWN = {"Alice", "Bob", "Tom", "Cafe", "Library"}


def _mem(mid, summary, location="Cafe", involved=None):
    return EpisodicMemory(
        memory_id=mid,
        agent_id="Alice",
        tick_start=1,
        tick_end=1,
        location=location,
        involved_agents=involved or [],
        summary=summary,
    )


def test_mentioned_entities_is_case_insensitive():
    assert mentioned_entities("alice went to CAFE", KNOWN) == {"Alice", "Cafe"}
    assert mentioned_entities("", KNOWN) == set()


def test_extract_pairs_unordered_and_deduped():
    pairs = extract_pairs("Alice 和 Bob 在 Cafe，后来又见到 Bob", KNOWN)
    assert pairs == {frozenset({"Alice", "Bob"}), frozenset({"Alice", "Cafe"}), frozenset({"Bob", "Cafe"})}


def test_memory_index_collects_seen_and_cooccurring():
    seen, cooccur = build_memory_entity_index(
        [_mem("m1", "Alice 在 Cafe 遇到 Bob"), _mem("m2", "Alice 独自在 Library")],
        KNOWN,
    )
    assert seen == {"Alice", "Cafe", "Bob", "Library"}
    assert frozenset({"Alice", "Bob"}) in cooccur
    assert frozenset({"Alice", "Library"}) in cooccur
    # Alice/Tom 从未共现，也没提过 Tom
    assert frozenset({"Alice", "Tom"}) not in cooccur


def test_novel_link_is_association_not_hallucination():
    """Bob 和 Library 都见过，但从未同时出现 → 输出把它们连起来 = 联想。"""
    seen, cooccur = build_memory_entity_index(
        [_mem("m1", "Alice 在 Cafe 遇到 Bob"), _mem("m2", "Alice 独自在 Library")],
        KNOWN,
    )
    res = compute_novelty("我想到 Bob 也许在 Library", seen, cooccur, KNOWN)
    assert res["novel_links"] == 1
    assert res["ungrounded"] == 0
    assert res["N"] == 1.0


def test_unknown_entity_counts_as_ungrounded_not_novel():
    seen, cooccur = build_memory_entity_index([_mem("m1", "Alice 在 Cafe")], KNOWN)
    res = compute_novelty("Alice 和 Tom 在 Cafe", seen, cooccur, KNOWN)
    # Tom 从未出现在记忆里 → 含 Tom 的两对都算幻觉（Alice+Tom, Tom+Cafe），不算联想
    assert res["ungrounded"] == 2
    assert res["novel_links"] == 0
    assert res["known_links"] == 1  # Alice+Cafe 已共现
    assert res["N"] == 0.0


def test_known_link_is_neither_novel_nor_ungrounded():
    seen, cooccur = build_memory_entity_index([_mem("m1", "Alice 在 Cafe 遇到 Bob")], KNOWN)
    res = compute_novelty("Alice 和 Bob 又在 Cafe 碰面", seen, cooccur, KNOWN)
    assert res["known_links"] == 3  # Alice+Bob, Alice+Cafe, Bob+Cafe 全都已共现
    assert res["novel_links"] == 0
    assert res["ungrounded"] == 0


def test_no_entities_gives_zero_denominator_safely():
    res = compute_novelty("今天天气不错", set(), set(), KNOWN)
    assert res["total_pairs"] == 0
    assert res["N"] == 0.0


def test_aggregate_weights_by_pair_count_not_by_text():
    per_text = [
        {"total_pairs": 10, "novel_links": 5, "ungrounded": 1},
        {"total_pairs": 0, "novel_links": 0, "ungrounded": 0},
    ]
    agg = aggregate_novelty(per_text)
    assert agg["N"] == 0.5
    assert agg["ungrounded_rate"] == 0.1
    assert agg["total_pairs"] == 10


def test_location_and_involved_agents_count_as_seen():
    """记忆的 location / involved_agents 也是「见过」，不能只扫 summary。"""
    seen, _ = build_memory_entity_index([_mem("m1", "无事发生", location="Library", involved=["Tom"])], KNOWN)
    assert "Library" in seen and "Tom" in seen
