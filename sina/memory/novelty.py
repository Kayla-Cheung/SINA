"""
novelty.py — 「联想」与「幻觉」的可数指标
================================================================================
随机化检索的预期效果是「agent 更能联想」。但「联想」不是可数对象，先把它拆成两种
**可数**的东西：

  联想 (novel link)   —— 输出里同时出现的两个实体，在该 agent 的记忆里**都出现过**，
                         但**从未在同一段记忆里共现过**。也就是「两个都认识，第一次被连起来」。
  幻觉 (ungrounded)   —— 输出里出现的一对实体，其中**至少一个在该 agent 记忆里根本不存在**。
                         这不是联想，是编造。

于是：
  N = novel_links / total_output_pairs

N 高、ungrounded 低 → 真在联想；N 高、ungrounded 也高 → 它只是开始胡说。
**这个区分就是 confabulation 那条线**，不要只看 N。

实现是纯字符串/集合运算：给定一张已知实体表（世界里的 agent 名、房间名、物品名），
不依赖任何 LLM 判官，因此可复现、可审计。
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

Pair = frozenset


def _norm(text: str) -> str:
    return (text or "").lower()


def mentioned_entities(text: str, known_entities: Iterable[str]) -> Set[str]:
    """文本里出现过的已知实体（大小写无关的子串匹配）。"""
    lowered = _norm(text)
    if not lowered:
        return set()
    return {e for e in known_entities if e and _norm(e) in lowered}


def extract_pairs(text: str, known_entities: Iterable[str]) -> Set[Pair]:
    """文本里同时出现过的实体对（无序、去重）。"""
    entities = sorted(mentioned_entities(text, known_entities))
    return {frozenset(p) for p in combinations(entities, 2)}


def build_memory_entity_index(
    memories: Sequence, known_entities: Iterable[str]
) -> Tuple[Set[str], Set[Pair]]:
    """从某 agent 的全部情景记忆里建索引。

    返回 (seen_entities, cooccurring_pairs)：
      · seen_entities      该 agent 记忆里出现过的实体
      · cooccurring_pairs  曾在同一段记忆里共现过的实体对（即「记忆里已经连好」的那些）
    """
    seen: Set[str] = set()
    cooccur: Set[Pair] = set()
    for mem in memories or []:
        text = getattr(mem, "summary", "") or ""
        # involved_agents / location 也是记忆的一部分，一并算作「见过」
        text = " ".join([text, getattr(mem, "location", "") or "", " ".join(getattr(mem, "involved_agents", []) or [])])
        ents = mentioned_entities(text, known_entities)
        seen |= ents
        for pair in combinations(sorted(ents), 2):
            cooccur.add(frozenset(pair))
    return seen, cooccur


def compute_novelty(
    text: str,
    seen_entities: Set[str],
    cooccurring_pairs: Set[Pair],
    known_entities: Iterable[str],
) -> Dict[str, object]:
    """单段输出的联想/幻觉分解。"""
    pairs = extract_pairs(text, known_entities)

    novel_links: List[Pair] = []
    known_links: List[Pair] = []
    ungrounded: List[Pair] = []

    for pair in pairs:
        a, b = tuple(pair)
        if a not in seen_entities or b not in seen_entities:
            ungrounded.append(pair)
        elif pair in cooccurring_pairs:
            known_links.append(pair)
        else:
            novel_links.append(pair)

    total = len(pairs)
    return {
        "total_pairs": total,
        "novel_links": len(novel_links),
        "known_links": len(known_links),
        "ungrounded": len(ungrounded),
        "N": (len(novel_links) / total) if total else 0.0,
        "novel_examples": ["+".join(sorted(p)) for p in novel_links[:5]],
        "ungrounded_examples": ["+".join(sorted(p)) for p in ungrounded[:5]],
    }


def aggregate_novelty(per_text: List[Dict[str, object]]) -> Dict[str, float]:
    """把多段输出的指标合成 run 级数字（按对总数加权，而非按段平均）。"""
    total = sum(int(r["total_pairs"]) for r in per_text)
    novel = sum(int(r["novel_links"]) for r in per_text)
    ungrounded = sum(int(r["ungrounded"]) for r in per_text)
    if total == 0:
        return {"N": 0.0, "ungrounded_rate": 0.0, "total_pairs": 0}
    return {
        "N": novel / total,
        "ungrounded_rate": ungrounded / total,
        "total_pairs": total,
        "novel_links": novel,
        "ungrounded": ungrounded,
    }


def known_entities_from_sim(sim, extra: Optional[Iterable[str]] = None) -> Set[str]:
    """从沙盒里收集实体表：agent 名 + 房间名 + 物理材质名（+ 供扩展的 extra）。"""
    entities: Set[str] = set(sim.world_agents.keys())
    entities |= {n.name for n in sim.environment.all_nodes()}
    entities |= set(getattr(sim.physics, "material_properties", {}) or {})
    if extra:
        entities |= {e for e in extra if e}
    return entities
