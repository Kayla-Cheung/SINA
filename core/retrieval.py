import numpy as np
from datetime import datetime
from typing import List
from memory import Memory

class RetrievalEngine:
    def __init__(self, decay_factor=0.995):
        self.decay_factor = decay_factor

    def calculate_recency(self, memory: Memory) -> float:
        time_diff = (datetime.now() - memory.last_accessed_at).total_seconds() / 3600
        return self.decay_factor ** time_diff
        pass

    def calculate_relevance(self, memory_factor: list, query_vector: list) -> float:
        v1 = np.array(memory_factor)
        v2 = np.array(query_vector)
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)

        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0

        relevance = dot_product / norm_v1 / norm_v2
        return float(relevance)
    
    def retrieve(self, memories: List[Memory], query_vector: list,top_k: int = 5) -> List[Memory]:
        scored_memories = []

        for memory in memories:
            recency_score = self.calculate_recency(memory)
            relevance_score = self.calculate_relevance(memory.embedding_vector, query_vector)
            importance_score = memory.importance_score

            final_score = recency_score + relevance_score + importance_score
            scored_memories.append((final_score, memory))
            memory.last_accessed_at = datetime.now()
        
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        top_memories = [mem for score, mem in scored_memories[:top_k]]
        
        # --- Quantum Associative Noise (TRPG Dice Roll) ---
        import random
        import copy
        if len(scored_memories) > top_k:
            dice = random.randint(1, 20)
            
            # Extract the bottom 50% of memories (unrelated/noise)
            bottom_half = [mem for score, mem in scored_memories[len(scored_memories)//2:]]
            
            if bottom_half:
                if dice == 20: # Critical Success (Inspiration)
                    flashback = copy.copy(random.choice(bottom_half))
                    flashback.text = f"[灵光一闪/Inspiration] {flashback.text}"
                    top_memories[-1] = flashback # Replace the least relevant memory in Top-K
                elif dice == 1: # Critical Failure (Distraction)
                    distraction = copy.copy(random.choice(bottom_half))
                    distraction.text = f"[走神/Distraction] {distraction.text}"
                    top_memories[-1] = distraction

        return top_memories
