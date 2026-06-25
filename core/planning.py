import json
from typing import List, Dict
from datetime import datetime, timedelta

class Plan:
    def __init__(self, action: str, start_time: datetime, duration_minutes: int):
        self.action = action
        self.start_time = start_time
        self.duration_minutes = duration_minutes
        
    def __repr__(self):
        end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        return f"[{self.start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}] {self.action}"

def generate_daily_plan(agent_name: str, agent_summary: str, current_date: datetime) -> List[Plan]:
    """
    自顶向下的粗粒度计划：生成一天的大纲（块状，每块通常 1-4 小时）。
    在真实的 SINA 架构中，这里会发起一个 LLM API 调用。
    """
    prompt = f"""
    You are {agent_name}. 
    Summary of your identity and recent memories: {agent_summary}
    Today is {current_date.strftime('%Y-%m-%d')}.
    Describe your broad plan for the day in 5-7 major chunks.
    Format your response as a JSON list of objects with 'action' and 'duration_minutes'.
    The total duration must be exactly 1440 minutes (24 hours).
    """
    print(f"[{agent_name}] 正在生成 {current_date.strftime('%Y-%m-%d')} 的宏观粗粒度日程表...")
    
    # 这里的 mock_response 模拟了 LLM 返回的结构化 JSON
    mock_response = [
        {"action": "Sleep", "duration_minutes": 480},
        {"action": "Morning routine and breakfast", "duration_minutes": 60},
        {"action": "Deep work: Architecting SINA Multi-Agent framework", "duration_minutes": 240},
        {"action": "Lunch and physical resting", "duration_minutes": 60},
        {"action": "Attend programming class and review Physics", "duration_minutes": 180},
        {"action": "Dinner and social reading", "duration_minutes": 120},
        {"action": "Night coding sprints and winding down", "duration_minutes": 300}
    ]
    
    plans = []
    # 强制将时间戳对齐到当天的 00:00:00
    current_time = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    for item in mock_response:
        plans.append(Plan(item['action'], current_time, item['duration_minutes']))
        current_time += timedelta(minutes=item['duration_minutes'])
        
    return plans

def decompose_plan(agent_name: str, broad_plan: Plan) -> List[Plan]:
    """
    中/细粒度拆解：将一个粗粒度计划块（如1小时），按需拆解成 5-15 分钟的具体可执行动作。
    这个函数会在模拟器时间推进到该模块时，被动态调用（Lazy Evaluation）。
    """
    prompt = f"""
    You are {agent_name}. 
    Your current broad plan is: "{broad_plan.action}" for {broad_plan.duration_minutes} minutes.
    Break this down into detailed step-by-step micro-actions (each 5-30 minutes).
    Format as a JSON list with 'action' and 'duration_minutes'.
    The total duration must equal {broad_plan.duration_minutes} minutes.
    """
    print(f"\n[{agent_name}] 正在将宏观区块 '{broad_plan.action}' 降维拆解为指令级动作流...")
    
    # Mock LLM 返回的细粒度拆解结果
    # 假设我们传入的是 60 分钟的 Morning routine 任务
    mock_response = [
        {"action": "Wake up and process overnight thoughts", "duration_minutes": 10},
        {"action": "Brush teeth and quick wash", "duration_minutes": 15},
        {"action": "Brew black coffee", "duration_minutes": 10},
        {"action": "Drink coffee while reviewing today's to-do list", "duration_minutes": 25}
    ]
    
    detailed_plans = []
    current_time = broad_plan.start_time
    
    for item in mock_response:
        detailed_plans.append(Plan(item['action'], current_time, item['duration_minutes']))
        current_time += timedelta(minutes=item['duration_minutes'])
        
    return detailed_plans

if __name__ == "__main__":
    # 执行单元测试
    print("=== SINA Top-Down Planning Engine Booting ===")
    today = datetime(2026, 6, 22)
    
    # 1. 生成全局宏观计划
    daily_schedule = generate_daily_plan("Kayla_NPC", "An engineering student building an AI society.", today)
    
    print("\n--- Global Architecture (Daily Plan) ---")
    for p in daily_schedule:
        print(p)
        
    # 2. 模拟系统时钟推进，触发对第二个区块（早晨日常）的即时拆解
    target_block = daily_schedule[1] 
    micro_actions = decompose_plan("Kayla_NPC", target_block)
    
    print("\n--- Micro Execution Flow (Sub-tasks) ---")
    for p in micro_actions:
        print(p)
