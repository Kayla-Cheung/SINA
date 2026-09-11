"""
SINA v4 Memory Subsystem: Core Type Definitions.
Formalizing Layer 0 (P_Self), Layer 1 (Working Context), Layer 2 (Episodic Store),
and Query Interfaces with strict Pydantic models.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Categorical types of agent memory items."""
    OBSERVATION = "OBSERVATION"      # Sensory perception from local spatial grid
    ACTION = "ACTION"                # Agent's own executed physical/social actions
    DIALOGUE = "DIALOGUE"            # Utterances and conversations
    REFLECTION = "REFLECTION"        # High-level introspective insights
    CONFABULATION = "CONFABULATION"  # Class-deprived hallucinated/reconstructed memory


class PersonaInvariant(BaseModel):
    """
    Layer 0: P_Self Core Invariant Anchor.
    Physical-level immutable identity, class index, and primary convictions.
    Pinned at the top of context (Dummy Sentinel Pattern) to prevent persona drift.
    """
    agent_id: str = Field(..., description="Unique immutable agent identifier")
    name: str = Field(..., description="Display name of the agent")
    archetype: str = Field(
        ...,
        description="Core psychological archetype (e.g., Dominant_Authority, Subordinate_Survivor)"
    )
    core_conviction: str = Field(
        ...,
        description="Primary unyielding conviction, existential desire, or trauma anchor"
    )
    class_index: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Social class & power index B_i in [0.0, 1.0]. Determines memory budget & fidelity"
    )
    wealth_budget: float = Field(
        1000.0,
        ge=0.0,
        description="Token & resource compute budget. Low values trigger memory decay & confabulation"
    )
    physiological_state: Dict[str, float] = Field(
        default_factory=lambda: {"stamina": 1.0, "stress": 0.0, "clarity": 1.0},
        description="Real-time physical invariants affecting cognitive load"
    )

    def format_header(self) -> str:
        """Render immutable identity header for system prompt injection."""
        return (
            f"[INVARIANT_CORE_SELF: {self.name} (ID: {self.agent_id})]\n"
            f"- Archetype: {self.archetype}\n"
            f"- Core Conviction: {self.core_conviction}\n"
            f"- Social Class & Power Index: {self.class_index:.2f} (Budget: {self.wealth_budget:.1f} tokens)\n"
            f"- Physiological Load: Stamina={self.physiological_state.get('stamina', 1.0):.2f}, "
            f"Stress={self.physiological_state.get('stress', 0.0):.2f}"
        )


class WorkingMemoryItem(BaseModel):
    """
    Layer 1: Working Context Item (S_t).
    Represents raw, high-resolution perceptions and immediate scratchpad states.
    Subject to token threshold theta monitoring and sliding-window bifurcation.
    """
    item_id: str = Field(..., description="Unique item identifier")
    tick: int = Field(..., description="Simulation tick at creation")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    memory_type: MemoryType = Field(MemoryType.OBSERVATION)
    location: str = Field("unknown", description="Spatial node where the event occurred")
    source_agent: str = Field("", description="Author or originator of the observation")
    content: str = Field(..., description="Raw text content")
    estimated_tokens: int = Field(0, description="Estimated token count of this item")

    def model_post_init(self, __context: Any) -> None:
        if self.estimated_tokens <= 0:
            # Heuristic: 1 token ~ 4 characters in English or ~ 1.5 chars in CJK
            cjk_count = sum(1 for c in self.content if ord(c) > 127)
            ascii_count = len(self.content) - cjk_count
            self.estimated_tokens = max(1, int(cjk_count / 1.5 + ascii_count / 4.0))


class EpisodicMemory(BaseModel):
    """
    Layer 2: Structured Episodic Memory.
    Distilled, compacted multi-tick events stored in vector space.
    """
    memory_id: str = Field(..., description="Unique episodic memory identifier")
    agent_id: str = Field(..., description="Owner agent ID")
    tick_start: int = Field(..., description="First tick included in this episode")
    tick_end: int = Field(..., description="Last tick included in this episode")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: str = Field(..., description="Primary spatial venue of the episode")
    involved_agents: List[str] = Field(default_factory=list, description="Agents present in this episode")
    summary: str = Field(..., description="Compacted high-density narrative summary")
    importance: float = Field(5.0, ge=1.0, le=10.0, description="Poignancy / structural importance")
    emotional_valence: float = Field(0.0, ge=-1.0, le=1.0, description="Affect valence (-1 negative to +1 positive)")
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector embedding")
    is_confabulated: bool = Field(False, description="Flag indicating if memory was generated via class-gated confabulation")


class MemoryQuery(BaseModel):
    """Query parameters for retrieving relevant episodic memories."""
    agent_id: str = Field(..., description="Target agent querying their memory")
    query_text: str = Field(..., description="Text query or current situation prompt")
    query_embedding: Optional[List[float]] = Field(default=None, description="Optional precomputed query vector")
    current_tick: int = Field(..., description="Current simulation tick for recency computation")
    current_location: Optional[str] = Field(default=None, description="Current location for spatial affinity")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of memories to retrieve")
    alpha_recency: float = Field(0.3, ge=0.0, le=2.0, description="Weight for temporal recency")
    alpha_importance: float = Field(0.3, ge=0.0, le=2.0, description="Weight for structural importance")
    alpha_relevance: float = Field(0.7, ge=0.0, le=2.0, description="Weight for semantic similarity")


class MemoryRetrievalResult(BaseModel):
    """Detailed result entry with transparent scoring breakdown."""
    memory: EpisodicMemory
    composite_score: float
    relevance_score: float
    recency_score: float
    importance_score: float
    decay_multiplier: float
    is_confabulated: bool
