"""
SINA v4 Memory Subsystem.
Exports primary models, managers, and decay engines.
"""

from .types import (
    MemoryType,
    PersonaInvariant,
    WorkingMemoryItem,
    EpisodicMemory,
    MemoryQuery,
    MemoryRetrievalResult,
)
from .store import EpisodicVectorStore
from .decay import ClassGatedDecayEngine
from .bifurcation import BifurcationManager
from .manager import HierarchicalMemoryManager

__all__ = [
    "MemoryType",
    "PersonaInvariant",
    "WorkingMemoryItem",
    "EpisodicMemory",
    "MemoryQuery",
    "MemoryRetrievalResult",
    "EpisodicVectorStore",
    "ClassGatedDecayEngine",
    "BifurcationManager",
    "HierarchicalMemoryManager",
]
