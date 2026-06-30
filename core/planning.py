import asyncio
from typing import List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from gateway import gateway

# ================= 数据契约 (Pydantic) =================
class PlanItem(BaseModel):
    action: str = Field(..., description="The action or task description.")
    duration_minutes: int = Field(..., description="Duration of this action in minutes.")

class DailyPlanResponse(BaseModel):
    plans: List[PlanItem] = Field(..., description="List of major daily chunks (5-7 chunks).")

class MicroPlanResponse(BaseModel):
    micro_actions: List[PlanItem] = Field(..., description="List of decomposed micro-actions.")
# =======================================================

class Plan:
    def __init__(self, action: str, start_time: datetime, duration_minutes: int):
        self.action = action
        self.start_time = start_time
        self.duration_minutes = duration_minutes
        
    def __repr__(self):
        end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        return f"[{self.start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}] {self.action}"

async def generate_daily_plan(agent_name: str, agent_summary: str, current_date: datetime) -> List[Plan]:
    """
    自顶向下的粗粒度计划：生成一天的大纲（块状，每块通常 1-4 小时）。
    """
    system_prompt = (
        f"You are {agent_name}. \n"
        f"Summary of your identity and recent memories: {agent_summary}\n"
        f"Today is {current_date.strftime('%Y-%m-%d')}.\n"
        "Describe your broad plan for the day in 5-7 major chunks.\n"
        "CRITICAL: The total duration of all chunks MUST sum up to EXACTLY 1440 minutes (24 hours).\n"
        "Keep the action descriptions in Chinese."
    )
    
    print(f"[{agent_name}] 正在呼叫神经中枢，生成 {current_date.strftime('%Y-%m-%d')} 的宏观粗粒度日程表...")
    
    response_data = await gateway.generate_structured(
        system_prompt=system_prompt,
        user_prompt="Please generate today's macro plan.",
        response_model=DailyPlanResponse,
        temperature=0.6
    )
    
    if not response_data or not response_data.plans:
        print("[警告] 宏观计划生成失败，执行降级待机计划")
        response_data = DailyPlanResponse(plans=[PlanItem(action="发呆待机", duration_minutes=1440)])
    
    plans = []
    # 强制将时间戳对齐到当天的 00:00:00
    current_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for item in response_data.plans:
        plans.append(Plan(item.action, current_time, item.duration_minutes))
        current_time += timedelta(minutes=item.duration_minutes)
        
    return plans

async def decompose_plan(agent_name: str, broad_plan: Plan) -> List[Plan]:
    """
    中/细粒度拆解：将一个粗粒度计划块（如1小时），按需拆解成 5-15 分钟的具体可执行动作。
    """
    system_prompt = (
        f"You are {agent_name}. \n"
        f"Your current broad plan is: '{broad_plan.action}' for {broad_plan.duration_minutes} minutes.\n"
        "Break this down into detailed step-by-step micro-actions (each 5-30 minutes).\n"
        f"CRITICAL: The sum of 'duration_minutes' MUST equal EXACTLY {broad_plan.duration_minutes} minutes.\n"
        "Keep the micro-action descriptions in Chinese."
    )
    
    print(f"\n[{agent_name}] 正在将宏观区块 '{broad_plan.action}' 降维拆解为指令级动作流...")
    
    response_data = await gateway.generate_structured(
        system_prompt=system_prompt,
        user_prompt="Please decompose this block into micro-actions.",
        response_model=MicroPlanResponse,
        temperature=0.4
    )
    
    if not response_data or not response_data.micro_actions:
        print("[警告] 细粒度拆解失败，执行原始区块")
        response_data = MicroPlanResponse(micro_actions=[PlanItem(action=broad_plan.action, duration_minutes=broad_plan.duration_minutes)])
    
    detailed_plans = []
    current_time = broad_plan.start_time
    
    for item in response_data.micro_actions:
        detailed_plans.append(Plan(item.action, current_time, item.duration_minutes))
        current_time += timedelta(minutes=item.duration_minutes)
        
    return detailed_plans

async def main():
    print("=== SINA Top-Down Planning Engine Booting (Live LLM Mode) ===")
    today = datetime(2026, 6, 22)
    
    # 1. 真正调用大模型生成全局宏观计划
    daily_schedule = await generate_daily_plan("Kayla_NPC", "一个正在构建 AI 社会的极客工程师，讨厌被说教，喜欢熬夜写代码。", today)
    
    print("\n--- Global Architecture (Daily Plan) ---")
    for p in daily_schedule:
        print(p)
        
    # 2. 真正调用大模型拆解第二个区块
    if len(daily_schedule) > 1:
        target_block = daily_schedule[1] 
        micro_actions = await decompose_plan("Kayla_NPC", target_block)
        
        print("\n--- Micro Execution Flow (Sub-tasks) ---")
        for p in micro_actions:
            print(p)

if __name__ == "__main__":
    asyncio.run(main())
