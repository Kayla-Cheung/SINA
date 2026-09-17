"""
retrieval_policy.py — 检索端随机化：本实验的自变量旋钮
================================================================================
`HierarchicalMemoryManager.retrieve_memories()` 原本是纯 top-k：按 composite_score
取前 k 条。本模块把「怎么从排序好的记忆里挑 k 条」抽成一个可替换的策略，
用来对着三个条件做对照：

  A  "topk"   —— 纯 top-k（对照组，ratio=0 时即此）
  B  "random" —— 保留前 (k-n) 条，剩下 n 条从**本不会被检索到的池子**里**均匀随机**取
  C  "tail"   —— 保留前 (k-n) 条，剩下 n 条从同一池子里**按排名顺序**取

B 与 C 的池子、替换数量、平均相关度都一样，只有「选择规则」不同（均匀随机 vs 按排名）。
所以 B − C 的差**只归因于随机性本身**，而不是「相关性变低」这个混淆项。
这是本设计里唯一能把随机性从混淆里拆出来的地方，别省掉 C。

硬约束：无论哪种条件，返回条数恒等于 k（池子不够时从原 top-k 尾部回填）。
否则「上下文长度」会和「随机性」一起变，结论就说不清了。
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .types import MemoryRetrievalResult

VALID_MODES = ("topk", "random", "tail")


@dataclass
class RetrievalConfig:
    """检索策略配置。默认 enabled=False，即原封不动的纯 top-k。"""

    enabled: bool = False
    mode: str = "topk"
    # 随机化比例 p ∈ [0,1]：被替换的槽位 n = floor(p * k)
    ratio: float = 0.0
    # 随机种子。设了才可复现；不设则每次运行不同（不适合做实验）
    seed: Optional[int] = None

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "RetrievalConfig":
        """从环境变量构造。未设置 SINA_RETRIEVAL_MODE 时返回默认（关闭）配置。"""
        env = os.environ if env is None else env
        raw_mode = str(env.get("SINA_RETRIEVAL_MODE", "")).strip().lower()
        cfg = cls()
        if raw_mode not in VALID_MODES:
            if raw_mode:
                print(f"    ⚠ SINA_RETRIEVAL_MODE 非法（{raw_mode}），已禁用检索随机化")
            return cfg

        cfg.enabled = True
        cfg.mode = raw_mode
        try:
            if env.get("SINA_RETRIEVAL_RATIO"):
                cfg.ratio = max(0.0, min(1.0, float(env["SINA_RETRIEVAL_RATIO"])))
            if env.get("SINA_RETRIEVAL_SEED"):
                cfg.seed = int(env["SINA_RETRIEVAL_SEED"])
        except ValueError as exc:
            print(f"    ⚠ SINA_RETRIEVAL_* 环境变量非法，已回落默认值: {exc}")
        return cfg


class RetrievalPolicy:
    """把一份已按 composite_score 降序排好的记忆列表，按 mode 挑出 k 条。

    `ranked` 必须是 **该 agent 全部幸存记忆**（不只是 top-k），因为 B/C 要从
    「本不会被检索到的池子」里取；只给 top-k*2 的候选是取不到尾巴的。
    """

    def __init__(self, config: Optional[RetrievalConfig] = None):
        self.config = config or RetrievalConfig()
        self._rng = random.Random(self.config.seed)
        self.last_meta: Dict[str, object] = {}

    def reseed(self, seed: Optional[int]) -> None:
        """重置抽样序列。每个实验 run 开始前调一次，保证可复现。"""
        self.config.seed = seed
        self._rng = random.Random(seed)

    def select(
        self,
        ranked: List[MemoryRetrievalResult],
        top_k: int,
    ) -> Tuple[List[MemoryRetrievalResult], Dict[str, object]]:
        """返回 (selected, meta)。selected 长度恒为 min(top_k, len(ranked))。"""
        cfg = self.config
        if not ranked:
            self.last_meta = {"mode": cfg.mode, "ratio": cfg.ratio, "k": 0, "injected": 0}
            return [], self.last_meta

        k = max(1, min(top_k, len(ranked)))
        n_requested = 0 if cfg.mode == "topk" else min(k, int(cfg.ratio * k))

        if n_requested == 0:
            selected = list(ranked[:k])
            meta = {
                "mode": cfg.mode,
                "ratio": cfg.ratio,
                "k": k,
                "injected": 0,
                "pool_size": max(0, len(ranked) - k),
                "injected_relevance": 0.0,
                "kept_relevance": _mean_relevance(selected),
            }
            self.last_meta = meta
            return selected, meta

        kept = list(ranked[: k - n_requested])
        pool = list(ranked[k:])  # 本不会被检索到的那些
        take = min(n_requested, len(pool))

        if take <= 0:
            chosen: List[MemoryRetrievalResult] = []
        elif cfg.mode == "tail":
            chosen = pool[:take]
        else:  # "random"
            chosen = self._rng.sample(pool, take)

        # 池子不够就回填原 top-k 尾部，保证返回条数恒为 k
        backfilled = 0
        if take < n_requested:
            need = n_requested - take
            backfill = ranked[k - n_requested : k - n_requested + need]
            chosen.extend(backfill)
            backfilled = len(backfill)

        selected = kept + chosen
        meta = {
            "mode": cfg.mode,
            "ratio": cfg.ratio,
            "k": k,
            "injected": take,
            "backfilled": backfilled,
            "pool_size": len(pool),
            "injected_relevance": _mean_relevance(chosen),
            "kept_relevance": _mean_relevance(kept),
        }
        self.last_meta = meta
        return selected, meta


def _mean_relevance(items: List[MemoryRetrievalResult]) -> float:
    if not items:
        return 0.0
    return float(sum(i.relevance_score for i in items) / len(items))
