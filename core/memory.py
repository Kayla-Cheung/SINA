import os
from datetime import datetime 
from gateway import gateway
import re

SYSTEM_PROMPT = (
    "On the scale of 1 to 10, where 1 is purely mundane (e.g. brushing teeth, making bed) "
    "and 10 is extremely poignant (e.g., a break up, college acceptance), "
    "rate the likely poignancy of the following piece of memory."
)

async def calculate_importance(text: str) -> int:
    prompt = f"Memory: {text}\nRating:"
    
    result_str = await gateway.generate_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=prompt,
        temperature=0.0
    )
    
    if not result_str:
        return 1
        
    match = re.search(r'\d+', result_str)
    if match:
        return int(match.group())
    else:
        return 1

class Memory:
    def __init__(self, memory_id: str, text: str, importance_score: int, embedding_vector: list, created_at: datetime = None):
        self.memory_id = memory_id
        self.text = text
        self.created_at = created_at if created_at else datetime.now()
        self.last_accessed_at = self.created_at
        self.importance_score = importance_score
        self.embedding_vector = embedding_vector

    def __repr__(self):
        return f"<Memory {self.memory_id}: {self.text}>"