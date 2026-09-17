"""
SINA v4 Memory Subsystem: Episodic Vector Store.
High-throughput in-memory contiguous NumPy array vector search with
SQLite cold persistence and agent-scoped indexing.
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import numpy as np

from .types import EpisodicMemory


class EpisodicVectorStore:
    """
    In-memory vector store optimized for agent simulations.
    Maintains contiguous 2D numpy arrays for BLAS-accelerated batch cosine similarity,
    avoiding pointer-chasing and per-row deserialization overhead.
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self._memories: List[EpisodicMemory] = []
        self._id_to_index: Dict[str, int] = {}
        self._agent_index_map: Dict[str, List[int]] = {}
        # Preallocated contiguous vector matrix (N, D)
        self._vectors: np.ndarray = np.empty((0, self.dimension), dtype=np.float32)
        self._normalized_vectors: np.ndarray = np.empty((0, self.dimension), dtype=np.float32)

    def __len__(self) -> int:
        return len(self._memories)

    def add(self, memory: EpisodicMemory, vector: Optional[List[float]] = None) -> None:
        """Add a single episodic memory with its dense vector representation."""
        if vector is None:
            if memory.embedding is not None:
                vector = memory.embedding
            else:
                # Deterministic pseudo-embedding for testing/cold environments without API keys
                vector = self._generate_fallback_vector(memory.summary)

        memory.embedding = vector
        vec_arr = np.array(vector, dtype=np.float32)
        if vec_arr.shape[0] != self.dimension:
            # Dynamically adjust dimension on first real vector if initialized empty
            if len(self._memories) == 0:
                self.dimension = vec_arr.shape[0]
                self._vectors = np.empty((0, self.dimension), dtype=np.float32)
                self._normalized_vectors = np.empty((0, self.dimension), dtype=np.float32)
            else:
                raise ValueError(
                    f"Vector dimension mismatch: expected {self.dimension}, got {vec_arr.shape[0]}"
                )

        norm = np.linalg.norm(vec_arr)
        normed_vec = (vec_arr / norm) if norm > 1e-8 else vec_arr

        idx = len(self._memories)
        self._memories.append(memory)
        self._id_to_index[memory.memory_id] = idx
        self._agent_index_map.setdefault(memory.agent_id, []).append(idx)

        # Append to contiguous matrices
        self._vectors = np.vstack([self._vectors, vec_arr.reshape(1, -1)])
        self._normalized_vectors = np.vstack([self._normalized_vectors, normed_vec.reshape(1, -1)])

    def batch_add(self, memories: List[EpisodicMemory], vectors: Optional[List[List[float]]] = None) -> None:
        """Add multiple memories in batch."""
        if vectors is None:
            vectors = [m.embedding or self._generate_fallback_vector(m.summary) for m in memories]
        for mem, vec in zip(memories, vectors, strict=False):
            self.add(mem, vec)

    def search(
        self,
        query_vector: List[float],
        agent_id: Optional[str] = None,
        top_k: int = 5
    ) -> List[Tuple[EpisodicMemory, float]]:
        """
        Perform vectorized cosine similarity search.
        If agent_id is provided, masks candidates strictly to that agent's light-cone.
        """
        if len(self._memories) == 0:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        if q_vec.shape[0] != self.dimension:
            # Fallback if dimension is mismatched: resize or return empty
            return []

        q_norm = np.linalg.norm(q_vec)
        q_normed = (q_vec / q_norm) if q_norm > 1e-8 else q_vec

        if agent_id is not None:
            indices = self._agent_index_map.get(agent_id, [])
            if not indices:
                return []
            sub_matrix = self._normalized_vectors[indices]
            sims = np.dot(sub_matrix, q_normed)

            # Top-k selection
            sorted_local_indices = np.argsort(-sims)[:top_k]
            results = []
            for local_idx in sorted_local_indices:
                global_idx = indices[local_idx]
                results.append((self._memories[global_idx], float(sims[local_idx])))
            return results
        else:
            sims = np.dot(self._normalized_vectors, q_normed)
            sorted_indices = np.argsort(-sims)[:top_k]
            return [(self._memories[i], float(sims[i])) for i in sorted_indices]

    def get_agent_memories(self, agent_id: str) -> List[EpisodicMemory]:
        """Retrieve all episodic memories belonging to a specific agent."""
        indices = self._agent_index_map.get(agent_id, [])
        return [self._memories[i] for i in indices]

    def _generate_fallback_vector(self, text: str) -> List[float]:
        """Generate a deterministic bag-of-char-ngrams pseudo-embedding vector.

        旧实现用内置 `hash(text)` 播种 RandomState，有两个致命缺陷：
          1. `str.__hash__` 受 PYTHONHASHSEED 影响，每次进程启动都不同 —— 跨进程不可复现，
             存进 SQLite 的向量换一个进程读出来就和 query 向量对不上；
          2. hash 值没有词形重叠 —— 「捡起苹果」与「采摘苹果」会得到完全无关的向量。

        这里改为对字符三元组做 sha256 摘要后散列进固定维度并累加（feature hashing）：
        跨进程确定、相似文本在向量空间相近、无第三方依赖。真正的语义 embedding
        属于 #18 / sqlite-vec 的后续工作，本实现保证离线/无 API 环境可稳定复现。
        """
        norm_text = (text or "").strip().lower()
        vec = np.zeros(self.dimension, dtype=np.float32)
        if norm_text:
            n = 3
            span = max(1, len(norm_text) - n + 1)
            for i in range(span):
                gram = norm_text[i:i + n]
                digest = hashlib.sha256(gram.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dimension
                # 用次高位字节决定符号，得到 signed hashing trick，避免只加不减的偏置。
                sign = 1.0 if digest[4] & 1 else -1.0
                vec[idx] += sign
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist() if norm > 1e-8 else vec.tolist()

    def persist_to_sqlite(self, db_path: str, game_id: str) -> int:
        """Cold storage persistence: Dump in-memory records into SQLite table."""
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodic_memories_v4 (
                    memory_id TEXT PRIMARY KEY,
                    game_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    tick_start INTEGER NOT NULL,
                    tick_end INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    location TEXT NOT NULL,
                    involved_agents TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    importance REAL NOT NULL,
                    emotional_valence REAL NOT NULL,
                    embedding TEXT NOT NULL,
                    is_confabulated INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ep_game_agent
                ON episodic_memories_v4(game_id, agent_id)
            """)

            inserted = 0
            for mem in self._memories:
                cursor.execute("""
                    INSERT OR REPLACE INTO episodic_memories_v4
                    (memory_id, game_id, agent_id, tick_start, tick_end, timestamp,
                     location, involved_agents, summary, importance, emotional_valence,
                     embedding, is_confabulated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    mem.memory_id,
                    game_id,
                    mem.agent_id,
                    mem.tick_start,
                    mem.tick_end,
                    mem.timestamp.isoformat(),
                    mem.location,
                    json.dumps(mem.involved_agents),
                    mem.summary,
                    mem.importance,
                    mem.emotional_valence,
                    json.dumps(mem.embedding) if mem.embedding else "[]",
                    1 if mem.is_confabulated else 0
                ))
                inserted += 1

            conn.commit()
            return inserted
        finally:
            conn.close()

    def load_from_sqlite(self, db_path: str, game_id: str) -> int:
        """Load episodic memories from SQLite database into fast in-memory matrix."""
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT memory_id, agent_id, tick_start, tick_end, timestamp,
                       location, involved_agents, summary, importance,
                       emotional_valence, embedding, is_confabulated
                FROM episodic_memories_v4
                WHERE game_id = ?
                ORDER BY tick_start ASC
            """, (game_id,))
            rows = cursor.fetchall()
        finally:
            conn.close()

        loaded_count = 0
        for row in rows:
            (mem_id, agent_id, t_start, t_end, ts_str, loc, inv_str, summary,
             imp, val, emb_str, is_conf) = row

            try:
                emb = json.loads(emb_str)
            except Exception:
                emb = None

            mem = EpisodicMemory(
                memory_id=mem_id,
                agent_id=agent_id,
                tick_start=t_start,
                tick_end=t_end,
                timestamp=datetime.fromisoformat(ts_str),
                location=loc,
                involved_agents=json.loads(inv_str) if inv_str else [],
                summary=summary,
                importance=imp,
                emotional_valence=val,
                embedding=emb,
                is_confabulated=bool(is_conf)
            )
            self.add(mem, emb)
            loaded_count += 1

        return loaded_count
