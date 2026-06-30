from typing import List
from pydantic import BaseModel, Field
from gateway import gateway

class InsightResponse(BaseModel):
    insights: List[str] = Field(..., description="A list of high-level insights")

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
        "RULE: YOUR INSIGHTS MUST BE WRITTEN IN CHINESE (中文)."
    )
    
    user_prompt = f"Recent Logs:\n{memory_context}\n\nGenerate {count} Insights:"
    
    # 走 Gateway 统一调用，自动完成 JSON 强制校验和退避重试
    response_data = await gateway.generate_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=InsightResponse
    )
    
    if response_data:
        return response_data.insights
    else:
        print("[反思模块崩溃] Gateway 多次重试后依然失败，返回空数据")
        return []
