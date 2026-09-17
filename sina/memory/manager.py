"""
SINA v4 Memory Subsystem: Hierarchical Memory Facade Manager.
Integrates Layer 0 (P_Self Invariant), Layer 1 (Working Context & Bifurcation),
Layer 2 (Episodic Vector Store), and Sociological Class-Gated Decay into a unified interface.
"""

from typing import Dict, List, Optional
import uuid

from .types import (
    PersonaInvariant,
    WorkingMemoryItem,
    EpisodicMemory,
    MemoryType,
    MemoryQuery,
    MemoryRetrievalResult,
)
from .store import EpisodicVectorStore
from .decay import ClassGatedDecayEngine
from .bifurcation import BifurcationManager
from .retrieval_policy import RetrievalPolicy, RetrievalConfig


class HierarchicalMemoryManager:
    """
    Unified entry point for SINA's 4-tier memory subsystem.
    Ensures mathematical boundedness of context size, cognitive locality,
    and sociological memory differentiation across simulated agents.
    """

    def __init__(
        self,
        vector_store: Optional[EpisodicVectorStore] = None,
        decay_engine: Optional[ClassGatedDecayEngine] = None,
        default_token_threshold: int = 1500,
        retrieval_policy: Optional[RetrievalPolicy] = None,
    ):
        # 必须显式判 None：EpisodicVectorStore 定义了 __len__，空 store 是 falsy，
        # 用 `or` 会把调用方传进来的空 store 悄悄丢掉、换成一个新实例。
        self.vector_store = vector_store if vector_store is not None else EpisodicVectorStore()
        self.decay_engine = decay_engine if decay_engine is not None else ClassGatedDecayEngine()
        self.default_token_threshold = default_token_threshold
        # 检索策略：默认关闭（纯 top-k），行为与引入本参数前一致。
        self.retrieval_policy = retrieval_policy or RetrievalPolicy(RetrievalConfig())
        self.last_retrieval_meta: Optional[dict] = None
        self._personas: Dict[str, PersonaInvariant] = {}
        self._bifurcation_managers: Dict[str, BifurcationManager] = {}
        # 注册时显式给定的 token 预算基线 (阈值, 当时财富)。社会地位变动时
        # 用它按财富比例重算，使「阶级更高 → token 预算更大」这条耦合在
        # 动态流动下依然成立。
        self._explicit_threshold: Dict[str, Optional[tuple]] = {}

    def _compute_token_threshold(self, agent_id: str, persona: PersonaInvariant) -> int:
        """按注册时的口径重算工作记忆 token 预算（供 register / 回写共用）。

        · 注册时显式给过阈值 → 按财富变化比例缩放该阈值；
        · 未显式给过       → 用 wealth_budget 驱动的默认公式。
        """
        base = self._explicit_threshold.get(agent_id)
        if base is None:
            return int(
                self.default_token_threshold
                * max(0.5, min(2.0, persona.wealth_budget / 1000.0))
            )
        base_threshold, base_wealth = base
        scale = 1.0 if base_wealth <= 0 else max(0.0, persona.wealth_budget) / base_wealth
        return int(round(base_threshold * scale))

    def register_agent(
        self,
        persona: PersonaInvariant,
        token_threshold: Optional[int] = None,
    ) -> None:
        """Register an agent into the memory hierarchy."""
        agent_id = persona.agent_id
        self._personas[agent_id] = persona

        # 显式阈值（falsy 视同未给，与旧 `token_threshold or ...` 语义一致）
        self._explicit_threshold[agent_id] = (
            (token_threshold, persona.wealth_budget) if token_threshold else None
        )

        # Dynamic token threshold based on wealth budget if not explicitly set
        # Wealthier agents can maintain larger working contexts before forced compaction
        self._bifurcation_managers[agent_id] = BifurcationManager(
            agent_id=agent_id,
            persona=persona,
            vector_store=self.vector_store,
            token_threshold=self._compute_token_threshold(agent_id, persona),
        )

    def get_persona(self, agent_id: str) -> Optional[PersonaInvariant]:
        """只读访问注册过的 persona（存档、观测器都用它取当前社会地位）。"""
        return self._personas.get(agent_id)

    def update_social_standing(
        self,
        agent_id: str,
        class_index: Optional[float] = None,
        wealth_budget: Optional[float] = None,
    ) -> Optional[PersonaInvariant]:
        """回写智能体的社会地位，并同步其工作记忆预算。

        这是 PersonaInvariant 唯一的写入口，用来补上
        ``class → 记忆保真度 → 行为 → 资源 → class`` 里此前缺失的最后一段。
        Layer 0 名义上名为 "Invariant"（见 types.py 的 docstring），但没有任何
        地方真正冻结它，因此这里显式地、集中地写，而不是让调用方各自改字段。

        返回更新后的 persona；该 agent 未注册时返回 None。
        """
        persona = self._personas.get(agent_id)
        if persona is None:
            return None

        if class_index is not None:
            persona.class_index = float(max(0.0, min(1.0, class_index)))
        if wealth_budget is not None:
            persona.wealth_budget = float(max(0.0, wealth_budget))

        bm = self._bifurcation_managers.get(agent_id)
        if bm is not None:
            bm.token_threshold = max(10, self._compute_token_threshold(agent_id, persona))

        return persona

    def record_event(
        self,
        agent_id: str,
        tick: int,
        content: str,
        memory_type: MemoryType = MemoryType.OBSERVATION,
        location: str = "unknown",
        source_agent: str = "",
    ) -> Optional[EpisodicMemory]:
        """Record an incoming event into the agent's Layer 1 working memory."""
        bm = self._bifurcation_managers.get(agent_id)
        if bm is None:
            raise KeyError(f"Agent {agent_id} is not registered in MemoryManager.")

        item = WorkingMemoryItem(
            item_id=f"w_{agent_id}_{tick}_{uuid.uuid4().hex[:6]}",
            tick=tick,
            memory_type=memory_type,
            location=location,
            source_agent=source_agent or agent_id,
            content=content,
        )
        return bm.append(item)

    def _evaluate_candidates(
        self,
        candidates,
        query: MemoryQuery,
        persona: PersonaInvariant,
    ) -> List[MemoryRetrievalResult]:
        """对候选记忆逐个算 composite_score，丢弃被阶层衰减器丢弃的，按分降序返回。

        两条检索路径（纯 top-k 与随机化）共用它，保证打分口径完全一致 ——
        否则 A/B/C 的差别里会混进「打分方式不同」这个混淆项。
        """
        results: List[MemoryRetrievalResult] = []
        for mem, raw_sim in candidates:
            eval_res = self.decay_engine.evaluate_memory_item(
                memory=mem,
                query=query,
                persona=persona,
                raw_similarity=raw_sim,
            )
            if eval_res is not None:
                results.append(eval_res)
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results

    def retrieve_memories(self, query: MemoryQuery) -> List[MemoryRetrievalResult]:
        """
        Query Layer 2 episodic memory with vector search and apply class-gated decay.
        If recall is barren for impoverished agents, synthesizes a confabulated memory.
        """
        agent_id = query.agent_id
        persona = self._personas.get(agent_id)
        if persona is None:
            return []

        # Vector search from store
        q_vec = query.query_embedding or self.vector_store._generate_fallback_vector(query.query_text)

        if self.retrieval_policy.config.enabled:
            # 随机化路径：需要该 agent **全部**幸存的记忆（B/C 条件要从
            # 「本不会被检索到的池子」里取样，只取 top-k*2 是够不到的）。
            candidates = self.vector_store.search(
                query_vector=q_vec,
                agent_id=agent_id,
                top_k=max(1, len(self.vector_store)),
            )
            ranked = self._evaluate_candidates(candidates, query, persona)
            final_results, meta = self.retrieval_policy.select(ranked, query.top_k)
            final_results = list(final_results)
            self.last_retrieval_meta = meta
        else:
            candidates = self.vector_store.search(
                query_vector=q_vec,
                agent_id=agent_id,
                top_k=query.top_k * 2,  # oversample to allow for decay and dropout
            )
            results = self._evaluate_candidates(candidates, query, persona)
            final_results = results[:query.top_k]
            self.last_retrieval_meta = None

        # Check for confabulation trigger on poor agents with low recall
        if len(final_results) == 0 and persona.class_index < 0.4:
            confab_mem = self.decay_engine.generate_confabulation(persona, query)
            final_results.append(
                MemoryRetrievalResult(
                    memory=confab_mem,
                    composite_score=0.9,
                    relevance_score=0.8,
                    recency_score=0.5,
                    importance_score=0.8,
                    decay_multiplier=1.0,
                    is_confabulated=True,
                )
            )

        return final_results

    def assemble_prompt_context(
        self,
        agent_id: str,
        current_situation: str,
        current_tick: int,
        current_location: str = "unknown",
        top_k_episodes: int = 3,
    ) -> str:
        """
        Assemble the complete, bounded prompt context across all 3 active layers:
        1. Layer 0: [INVARIANT_CORE_SELF]
        2. Layer 2: [RETRIEVED_EPISODIC_EXPERIENCES] (RAG)
        3. Layer 1: [ACTIVE_WORKING_STREAM] (Recent High-Resolution Window)
        """
        persona = self._personas.get(agent_id)
        bm = self._bifurcation_managers.get(agent_id)
        if persona is None or bm is None:
            raise KeyError(f"Agent {agent_id} is not registered.")

        # 1. Layer 0 Header
        header_l0 = persona.format_header()

        # 2. Layer 2 Episodic Retrieval
        query = MemoryQuery(
            agent_id=agent_id,
            query_text=current_situation,
            current_tick=current_tick,
            current_location=current_location,
            top_k=top_k_episodes,
        )
        retrieved_episodes = self.retrieve_memories(query)

        episodes_lines = []
        for res in retrieved_episodes:
            m = res.memory
            confab_tag = " [CONFABULATION/脑补]" if m.is_confabulated else ""
            episodes_lines.append(
                f"- [T{m.tick_start}-T{m.tick_end}@{m.location}]{confab_tag} {m.summary}"
            )
        episodes_block = "\n".join(episodes_lines) if episodes_lines else "- (No long-term memories triggered)"

        # 3. Layer 1 Working Memory Stream
        working_items = bm.working_queue
        working_lines = []
        for it in working_items:
            working_lines.append(
                f"- [T{it.tick}@{it.location}|{it.memory_type.value}] {it.source_agent}: {it.content}"
            )
        working_block = "\n".join(working_lines) if working_lines else "- (Working context empty)"

        # Final Assembly
        return (
            f"===================================================\n"
            f"{header_l0}\n"
            f"---------------------------------------------------\n"
            f"[LAYER 2: RECALLED EPISODIC EXPERIENCES (RAG)]\n"
            f"{episodes_block}\n"
            f"---------------------------------------------------\n"
            f"[LAYER 1: IMMEDIATE WORKING STREAM (Active Window: {len(working_items)} items, ~{bm.total_tokens} tokens)]\n"
            f"{working_block}\n"
            f"==================================================="
        )
