from datetime import datetime
from memory import Memory, calculate_importance
from sentence_transformers import SentenceTransformer

class GenerativeAgent:
    def __init__(self, name: str, reflection_threshold: int = 150):
        self.name = name
        self.memory_stream = []
        self.importance_sum = 0
        self.reflection_threshold = reflection_threshold
        self.state = AgentState()
        
        print(f"[{self.name}] 正在初始化大脑皮层 (加载 Embedding 模型)...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
    def add_memory(self, text: str, created_at: datetime = None):
        """
        核心方法：向记忆流中写入新记忆。
        自动完成 Embedding 和重要度打分，并维护反思触发器的阈值。
        """
        vector = self.encoder.encode(text)
        score = calculate_importance(text)
        
        mem_id = f"{self.name}_mem_{len(self.memory_stream)}"
        mem = Memory(
            memory_id=mem_id, 
            text=text, 
            importance_score=score, 
            embedding_vector=vector, 
            created_at=created_at
        )
        
        self.memory_stream.append(mem)
        self.importance_sum += score
        
        print(f"[{self.name}] 写入记忆 (阈值积累: {self.importance_sum}/{self.reflection_threshold}) -> {text}")
        
        # 检查是否突破了反思阈值
        if self.importance_sum >= self.reflection_threshold:
            self.reflect()
            
    def reflect(self):
        """
        大脑的反思机制
        """
        print(f"\n[{self.name}] [TRIGGER] 触发深度反思机制！信息量已达标 ({self.importance_sum} >= {self.reflection_threshold})")
        
        # 【极其关键的架构修复】必须在这里立刻清零！
        # 因为后续的 self.add_memory 会再次累加分数，如果在最后清零，会导致无限递归死循环。
        self.importance_sum = 0
        
        # 提取最近的记忆（比如最后 10 条）
        recent_memories = self.memory_stream[-10:]
        
        from reflection import generate_insights
        insights = generate_insights(recent_memories, count=2)
        
        print(f"[{self.name}] [INSIGHT] 提炼出 {len(insights)} 条高级认知，正在存回海马体...")
        for insight in insights:
            # 将高级认知作为一条全新的记忆存进去
            self.add_memory(f"[REFLECTION] {insight}")

if __name__ == "__main__":
    # 简单的本地单元测试
    agent = GenerativeAgent(name="NPC_Test", reflection_threshold=20)
    
    # 强制灌入几条无聊的日常，看看会不会触发反思
    agent.add_memory("The NPC drank a glass of water.")
    agent.add_memory("The NPC looked out the window.")
    agent.add_memory("The NPC received a full scholarship to Stanford.")
    agent.add_memory("The NPC discovered a hidden room in the basement.")
    agent.add_memory("The NPC decided to adopt a stray dog.")
    agent.add_memory("The NPC got fired from their job.") # 这条肯定破20分
