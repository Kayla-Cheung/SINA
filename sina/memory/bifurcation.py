"""
SINA v4 Memory Subsystem: Dual-Layer Bifurcation Manager.
Implements Axiom 4 (Hierarchical Memory & Context Compaction).
Monitors working context S_t token footprint against threshold theta.
When exceeded, triggers automatic compaction and bifurcation of old events
into structured Layer 2 episodic vectors while preserving active sliding windows.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Callable

from .types import (
    WorkingMemoryItem,
    EpisodicMemory,
    PersonaInvariant,
    MemoryType,
)
from .store import EpisodicVectorStore


class BifurcationManager:
    """
    Manages the Working Memory (Layer 1) stream for a single agent.
    Performs dynamic token monitoring, sliding-window partitioning,
    and automatic distillation into Episodic Memory (Layer 2).
    """

    def __init__(
        self,
        agent_id: str,
        persona: PersonaInvariant,
        vector_store: EpisodicVectorStore,
        token_threshold: int = 1500,
        active_window_size: int = 4,
        compaction_fn: Optional[Callable[[List[WorkingMemoryItem], PersonaInvariant], str]] = None,
    ):
        self.agent_id = agent_id
        self.persona = persona
        self.vector_store = vector_store
        self.token_threshold = max(10, token_threshold)
        self.active_window_size = active_window_size
        self._working_queue: List[WorkingMemoryItem] = []
        self._total_tokens: int = 0
        self.compaction_fn = compaction_fn or self._default_compactor

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def working_queue(self) -> List[WorkingMemoryItem]:
        return list(self._working_queue)

    def append(self, item: WorkingMemoryItem) -> Optional[EpisodicMemory]:
        """
        Append a new observation/action to working memory.
        If token count exceeds theta, triggers compaction and returns the generated EpisodicMemory.
        """
        self._working_queue.append(item)
        self._total_tokens += item.estimated_tokens

        if self._total_tokens > self.token_threshold:
            return self.bifurcate()
        return None

    def bifurcate(self, force: bool = False) -> Optional[EpisodicMemory]:
        """
        Perform the bifurcation operation:
        1. Keep the most recent `active_window_size` items in working memory.
        2. Extract the older items as `stale_slice`.
        3. Compact `stale_slice` into a single EpisodicMemory.
        4. Sinks into Vector Store and updates working memory.
        """
        if not self._working_queue:
            return None

        if len(self._working_queue) <= self.active_window_size and not force:
            return None

        split_idx = max(1, len(self._working_queue) - self.active_window_size)
        stale_slice = self._working_queue[:split_idx]
        self._working_queue = self._working_queue[split_idx:]

        # Recalculate working tokens
        self._total_tokens = sum(item.estimated_tokens for item in self._working_queue)

        # Distill stale items into a structured episode
        episodic_entry = self._distill_slice(stale_slice)

        # Sinks to Layer 2 vector store
        self.vector_store.add(episodic_entry)

        return episodic_entry

    def _distill_slice(self, items: List[WorkingMemoryItem]) -> EpisodicMemory:
        """Distill raw working items into a unified episodic memory entry."""
        tick_start = items[0].tick
        tick_end = items[-1].tick

        # Determine dominant location and involved agents
        locations = [it.location for it in items if it.location != "unknown"]
        dominant_location = locations[-1] if locations else "Main_Venue"

        agents_set = set()
        for it in items:
            if it.source_agent:
                agents_set.add(it.source_agent)
        involved_agents = sorted(list(agents_set))

        # Compact summary text
        summary = self.compaction_fn(items, self.persona)

        # Calculate average emotional tone or heuristic importance
        has_dialogue = any(it.memory_type == MemoryType.DIALOGUE for it in items)
        importance = 7.0 if has_dialogue else 5.0

        return EpisodicMemory(
            memory_id=f"ep_{self.agent_id}_{tick_start}_{tick_end}_{uuid.uuid4().hex[:6]}",
            agent_id=self.agent_id,
            tick_start=tick_start,
            tick_end=tick_end,
            timestamp=datetime.now(timezone.utc),
            location=dominant_location,
            involved_agents=involved_agents,
            summary=summary,
            importance=importance,
            emotional_valence=0.0,
            is_confabulated=False,
        )

    def _default_compactor(self, items: List[WorkingMemoryItem], persona: PersonaInvariant) -> str:
        """
        Deterministic, structured summarizer without requiring immediate external LLM calls.
        Can be overridden with an asynchronous LLM call.
        """
        actions = []
        dialogues = []
        observations = []

        for it in items:
            prefix = f"[T{it.tick}@{it.location}]"
            if it.memory_type == MemoryType.ACTION:
                actions.append(f"{prefix} {it.content}")
            elif it.memory_type == MemoryType.DIALOGUE:
                dialogues.append(f"{prefix} {it.source_agent}: {it.content}")
            else:
                observations.append(f"{prefix} {it.content}")

        parts = []
        if observations:
            parts.append("Perceptions: " + " | ".join(observations[:3]))
        if actions:
            parts.append("Actions: " + " | ".join(actions[:3]))
        if dialogues:
            parts.append("Conversations: " + " | ".join(dialogues[:3]))

        return " -- ".join(parts) if parts else f"Recorded {len(items)} routine environmental events."
