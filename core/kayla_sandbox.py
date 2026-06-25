import os
import json
from datetime import datetime
from memory import Memory, calculate_importance
from retrieval import RetrievalEngine
from sentence_transformers import SentenceTransformer
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv(r"C:\Users\Kayla\Desktop\ai-learning\projects\02-ai-paper-detector\.env")
client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

def load_json_profile():
    """读取原子化的 JSON 记忆库，保留严格的时间戳属性"""
    profile_path = r"C:\Users\Kayla\Desktop\ai-learning\projects\SINA_framework\kayla_profile.json"
    with open(profile_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def run_sandbox():
    print("====== 欢迎来到斯坦福小镇：Kayla Agent 沙盒 (v2.0 原子级记忆库) ======\n")
    print("正在加载大脑海马体 (MiniLM)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    print("\n正在从 JSON 结构化日志中提取记忆并计算重要性...")
    raw_data = load_json_profile()
    
    memories = []
    for i, item in enumerate(raw_data):
        text = item["text"]
        # 解析 JSON 里的时间戳字符串为 Python 的 datetime 对象
        mem_time = datetime.strptime(item["timestamp"], "%Y-%m-%d %H:%M:%S")
        
        vector = model.encode(text) 
        score = calculate_importance(text)
        print(f"[写入] 评分:{score} | 时间:{item['timestamp']} | {text[:40]}...")
        
        # 将历史时间传给 Memory，激活 Recency 衰减机制
        mem = Memory(memory_id=f"k_mem_{i}", text=text, importance_score=score, embedding_vector=vector, created_at=mem_time)
        memories.append(mem)

    print("\n原子化记忆灌注完成！")
    engine = RetrievalEngine()
    
    while True:
        print("\n" + "="*50)
        scenario = input("向沙盒中丢入一个突发事件 (输入 'q' 退出): ")
        if scenario.lower() == 'q':
            break
            
        print("\n[环境感知] 正在进行综合检索 (衰减 + 相似度 + 重要性)...")
        query_vector = model.encode(scenario)
        results = engine.retrieve(memories, query_vector, top_k=3)
        
        retrieved_context = ""
        for res in results:
            print(f" -> 激活记忆 (时间:{res.created_at.strftime('%Y-%m-%d')} | 重要性:{res.importance_score}分): {res.text}")
            retrieved_context += f"- [{res.created_at.strftime('%Y-%m-%d')}] {res.text}\n"

        print("\n[大模型反思] 正在生成 Kayla 的反应...")
        
        system_prompt = (
            "You are simulating an AI Agent named Kayla. "
            "Based ONLY on her retrieved atomic memories, describe how she would react to the CURRENT SCENARIO. "
            "Keep the response in Chinese, extremely concise, raw, analytical. Do not use Hollywood tropes, 'badass' stereotypes, or psychoanalytical jargon."
        )
        
        user_prompt = f"RETRIVED MEMORIES:\n{retrieved_context}\n\nCURRENT SCENARIO: {scenario}\n\nHow does Kayla react?"
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3 # 降低温度，减少废话和戏精表现
        )
        
        print(f"\n[Kayla 的真实反应]:\n{response.choices[0].message.content.strip()}")

if __name__ == "__main__":
    run_sandbox()
