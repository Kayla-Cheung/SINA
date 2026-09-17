"""
SINA v4 Memory Subsystem: Class-Gated Decay & Confabulation Engine.
Implements Axiom 2 (Resource Scarcity) and Class-Gated Memory Fidelity.
Lower-class agents suffer from higher exponential decay, memory dropout,
and are compelled to confabulate (template-generated rationalized memories) under cognitive deficit.
"""

import math
import random
from typing import Optional
import numpy as np

from .types import (
    EpisodicMemory,
    PersonaInvariant,
    MemoryQuery,
    MemoryRetrievalResult,
)


class ClassGatedDecayEngine:
    """
    Simulates sociological memory inequality and cognitive decay.
    High-class agents preserve high-fidelity long-term memories.
    Impoverished / subordinate agents experience memory erosion and false consciousness.
    """

    def __init__(
        self,
        base_half_life_ticks: float = 100.0,
        noise_scale: float = 0.2,
        confabulation_threshold: float = 0.35,
        seed: Optional[int] = None,
        rng: Optional[random.Random] = None,
    ):
        self.base_half_life = base_half_life_ticks
        self.noise_scale = noise_scale
        self.confabulation_threshold = confabulation_threshold
        # 丢弃与噪声原本用的是未播种的全局 RNG，跨进程/跨 run 不可复现 ——
        # 做 A/B/C 对照时这会把条件间的差异和随机波动混在一起。
        # rng 为 None 时保持旧行为（用全局 RNG），传入后完全可复现。
        self.rng = rng if rng is not None else (random.Random(seed) if seed is not None else None)

    def calculate_recency_decay(
        self,
        current_tick: int,
        memory_tick: int,
        class_index: float,
    ) -> float:
        """
        Calculate temporal decay multiplier based on time elapsed and class power index B_i.
        Formula: Decay = exp( - delta_t / (tau * (B_i + 0.1)) )
        """
        delta_t = max(0, current_tick - memory_tick)
        effective_tau = self.base_half_life * (class_index + 0.1)
        decay = math.exp(-delta_t / max(1.0, effective_tau))
        return max(0.0, min(1.0, decay))

    def evaluate_memory_item(
        self,
        memory: EpisodicMemory,
        query: MemoryQuery,
        persona: PersonaInvariant,
        raw_similarity: float,
    ) -> Optional[MemoryRetrievalResult]:
        """
        Compute the composite score for an episodic memory candidate,
        injecting class-based decay, importance, and noise.
        """
        class_idx = persona.class_index
        decay_mult = self.calculate_recency_decay(
            query.current_tick, memory.tick_end, class_idx
        )

        # Class-gated memory dropout: poor agents randomly miss older memories
        if class_idx < 0.4:
            dropout_prob = (1.0 - class_idx) * 0.4 * (1.0 - decay_mult)
            roll = self.rng.random() if self.rng is not None else random.random()
            if roll < dropout_prob:
                return None  # Memory dropped / forgotten

        # Normalization
        norm_importance = (memory.importance - 1.0) / 9.0  # scale to [0, 1]
        norm_recency = decay_mult
        norm_relevance = max(0.0, min(1.0, raw_similarity))

        # Add Gaussian noise inversely proportional to class power (higher for poor agents)
        noise = 0.0
        if class_idx < 0.8:
            sigma = self.noise_scale * (1.0 - class_idx)
            if self.rng is not None:
                noise = float(self.rng.gauss(0.0, sigma))
            else:
                noise = float(np.random.normal(0, sigma))

        composite_score = (
            query.alpha_relevance * norm_relevance
            + query.alpha_recency * norm_recency
            + query.alpha_importance * norm_importance
            + noise
        )

        return MemoryRetrievalResult(
            memory=memory,
            composite_score=max(0.0, composite_score),
            relevance_score=norm_relevance,
            recency_score=norm_recency,
            importance_score=norm_importance,
            decay_multiplier=decay_mult,
            is_confabulated=memory.is_confabulated,
        )

    def generate_confabulation(
        self,
        persona: PersonaInvariant,
        query: MemoryQuery,
        reason: str = "Cognitive gap filled under survival stress",
    ) -> EpisodicMemory:
        """
        Synthesize a confabulated (false) episodic memory to simulate rationalized false
        consciousness when memory recall is insufficient and class index is low.

        注意：当前实现是按 archetype 分支的固定模板字符串，非 LLM 叙事（见 #56）。
        """
        confab_id = f"confab_{persona.agent_id}_{query.current_tick}_{random.randint(1000, 9999)}"

        # Archetype-conditioned rationalization templates
        if "Survivor" in persona.archetype or "Subordinate" in persona.archetype:
            summary = (
                f"【模糊脑补记忆】在过去的某个危机关头，由于地位卑微，我曾隐约被某位主子暗中责难并顺从照办。"
                f"（为了在当前环境中自我合理化：{query.query_text}）"
            )
        elif "Rebel" in persona.archetype:
            summary = (
                "【潜意识执念】我依稀记得曾目睹过统治秩序背后的虚伪与脆弱，"
                "时刻提醒自己不可彻底信任体制。"
            )
        else:
            summary = (
                f"【脑补叙事】过去曾发生过一件模糊但关键的事，印证了我的核心执念：'{persona.core_conviction}'。"
            )

        return EpisodicMemory(
            memory_id=confab_id,
            agent_id=persona.agent_id,
            tick_start=max(0, query.current_tick - 50),
            tick_end=max(0, query.current_tick - 20),
            location=query.current_location or "Unknown_Backstage",
            involved_agents=[persona.agent_id],
            summary=summary,
            importance=8.0,
            emotional_valence=-0.5 if persona.class_index < 0.5 else 0.2,
            is_confabulated=True,
        )
