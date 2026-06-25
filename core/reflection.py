import os
from openai import AsyncOpenAI
from typing import List

# 全局初始化大模型
from dotenv import load_dotenv
load_dotenv(r"C:\Users\Kayla\Desktop\ai-learning\projects\02-ai-paper-detector\.env")

client = AsyncOpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

async def generate_insights(recent_memories: list, count: int = 2) -> List[str]:
    """
    接收一组近期的底层记忆，调用大模型强行提炼出高级认知（Insights）
    """
    if not recent_memories:
        return []
        
    # 把所有记忆拼成一段带有时间戳的文本供大模型阅读
    memory_context = ""
    for mem in recent_memories:
        memory_context += f"- [{mem.get('time', 'Unknown Time')}] {mem.get('text', '')}\n"
        
    system_prompt = (
        "You are an analytical psychology engine inside an AI simulation. "
        "Read the following recent memory logs of the agent. "
        f"Synthesize exactly {count} high-level insights. "
        "CRITICAL: Do NOT just analyze the agent themselves. Your insights MUST focus on extracting knowledge about OTHER agents (their personalities, motives), complex relationships, hidden world rules, or the overall state of the environment. "
        "Example good insights: 'Bob is hoarding food and cannot be trusted', 'The vampire is afraid of sunlight', 'There is a severe food shortage in the kitchen causing everyone to turn hostile'. "
        "Insights MUST be highly analytical, factual, and strictly derived from the logs provided. "
        "Format each insight on a new line starting with '- '.\n"
        "RULE: YOUR INSIGHTS MUST BE WRITTEN IN CHINESE (中文)."
    )
    
    user_prompt = f"Recent Logs:\n{memory_context}\n\nGenerate {count} Insights:"
    
    try:
        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        
        # 简单解析大模型返回的文本，提取出带有 "-" 的独立条目
        insights = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                # 去掉前面的破折号或星号
                insights.append(line.lstrip("-* ").strip())
                
        return insights
        
    except Exception as e:
        print(f"[反思模块崩溃] {e}")
        return []
