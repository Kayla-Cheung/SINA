"""
Pydantic data models for the Multi-Agent Graph World game engine.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any


# ===== Map Models =====

class Location(BaseModel):
    """A node in the graph map."""
    id: str
    name: str
    description: str


class Edge(BaseModel):
    """An undirected edge between two locations."""
    from_: str = Field(alias="from")
    to: str
    distance: int  # meters

    model_config = {"populate_by_name": True}


class MapConfig(BaseModel):
    """Map configuration."""
    name: str
    locations: List[Location]
    edges: List[Edge]


# ===== Agent Models =====

class AgentConfig(BaseModel):
    """Agent configuration from JSON."""
    id: str
    name: str
    persona: str
    initial_location: str
    inventory: List[str] = []
    initial_memories: List[str] = []


# ===== Object Models =====

class GameObjectConfig(BaseModel):
    """Game object configuration."""
    id: str
    name: str
    description: str
    location: str
    type: Literal["state", "portable"]
    current_state: str = ""
    current_owner: Optional[str] = None  # For portable type: who holds it (None = at location)


# ===== Game State Models =====

class MemoryEntry(BaseModel):
    """A single memory entry."""
    timestamp: str  # HH:MM format
    content: str
    is_reflection: bool = False
    frame: int = 0


class ToolCall(BaseModel):
    """A tool call made by an agent."""
    tool: str  # walk / chat / recall / reflect / interact / update_status / plan
    args: Dict[str, Any]


class AgentState(BaseModel):
    """Runtime state of an agent."""
    id: str
    name: str
    persona: str
    current_location: str
    inventory: List[str]
    status: str = ""  # What the agent is currently doing (from update_status)
    short_term_memory: List[MemoryEntry] = []
    pending_action: Optional[ToolCall] = None
    moving: bool = False
    next_location: Optional[str] = None
    # Day plan (30-min blocks); cleared when the calendar day rolls over
    daily_plan: Optional[str] = None
    daily_plan_day: Optional[int] = None


class ChatRequest(BaseModel):
    """A pending chat request between two agents."""
    initiator_id: str
    target_id: str
    initiator_message: str
    target_message: Optional[str] = None


class FrameLog(BaseModel):
    """Log entry for a single frame."""
    frame: int
    game_time: str  # HH:MM
    events: List[str] = []


class GameState(BaseModel):
    """Overall game state."""
    game_id: str
    frame: int = 0
    game_time: str = "08:00"  # HH:MM
    day: int = 1
    time_of_day: str = "Monday Morning"
    map: MapConfig
    agents: List[AgentState]
    objects: List[GameObjectConfig]
    logs: List[FrameLog] = []