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
    ):
        self.vector_store = vector_store or EpisodicVectorStore()
        self.decay_engine = decay_engine or ClassGatedDecayEngine()
        self.default_token_threshold = default_token_threshold
        self._personas: Dict[str, PersonaInvariant] = {}
        self._bifurcation_managers: Dict[str, BifurcationManager] = {}

    def register_agent(
        self,
        persona: PersonaInvariant,
        token_threshold: Optional[int] = None,
    ) -> None:
        """Register an agent into the memory hierarchy."""
        agent_id = persona.agent_id
        self._personas[agent_id] = persona

        # Dynamic token threshold based on wealth budget if not explicitly set
        # Wealthier agents can maintain larger working contexts before forced compaction
        threshold = token_threshold or int(
            self.default_token_threshold * max(0.5, min(2.0, persona.wealth_budget / 1000.0))
        )

        self._bifurcation_managers[agent_id] = BifurcationManager(
            agent_id=agent_id,
            persona=persona,
            vector_store=self.vector_store,
            token_threshold=threshold,
        )

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
        candidates = self.vector_store.search(
            query_vector=q_vec,
            agent_id=agent_id,
            top_k=query.top_k * 2,  # oversample to allow for decay and dropout
        )

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

        # Sort by composite score descending
        results.sort(key=lambda x: x.composite_score, reverse=True)
        final_results = results[:query.top_k]

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
