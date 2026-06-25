import os
from datetime import datetime 
from dotenv import load_dotenv
from openai import OpenAI

# ================= 全局初始化区 =================
env_path = r"C:\Users\Kayla\Desktop\ai-learning\projects\02-ai-paper-detector\.env"
load_dotenv(env_path)

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError(f"无法在 {env_path} 中找到 DEEPSEEK_API_KEY")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

SYSTEM_PROMPT = (
    "On the scale of 1 to 10, where 1 is purely mundane (e.g. brushing teeth, making bed) "
    "and 10 is extremely poignant (e.g., a break up, college acceptance), "
    "rate the likely poignancy of the following piece of memory."
)
# ===============================================

def calculate_importance(text: str) -> int:
    prompt = f"{SYSTEM_PROMPT}\nMemory: {text}\nRating:"
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}],
            temperature=0.0
        )
        result_str = response.choices[0].message.content.strip()
        
        # 大模型经常会夹带私货，比如返回 "Rating: 10\n\nThe memory..."
        # 所以必须用正则表达式强行把第一组数字抠出来
        import re
        match = re.search(r'\d+', result_str)
        if match:
            return int(match.group())
        else:
            return 1
        
    except Exception as e:
        print(f"[警告] 重要性打分服务崩溃或返回非数字，默认赋 1 分。原因: {e}")
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