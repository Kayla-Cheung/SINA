"""
laplace_oracle.py — SINA v4 拉普拉斯妖判定模块 (Pydantic 强类型版)
================================================
宇宙的沉默仲裁者。接收智能体提出的行为方案，判定其是否符合物理法则。
融合 SOTOPIA-EVAL 7 维打分（截取核心 3 维：目标、可信度、守密）。
"""

import json
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from gateway import gateway

# ==========================================
# 1. 定义极其严苛的 Pydantic 数据模式 (Schema)
# ==========================================

class Recipe(BaseModel):
    name: str = Field(description="recipe_id（必须为英文大写下划线命名，如 SHARP_STONE）")
    inputs: Dict[str, int] = Field(description="消耗的材料与数量字典")
    outputs: Dict[str, int] = Field(description="产出的材料与数量字典")
    time_cost: int = Field(description="消耗的时间（分钟数）")
    new_material_properties: Optional[Dict[str, Any]] = Field(None, description="新材料的物理属性字典")
    description: str = Field(description="该配方的简要功能说明")

class Meme(BaseModel):
    content: str = Field(description="文化信念或迷信的具体内容")
    category: Literal["religion", "social_contract", "taboo", "superstition"]
    penalty_description: str = Field(description="违反该信念会遭到的惩罚（信徒视角）")

class LaplaceVerdict(BaseModel):
    verdict: Literal["PHYSICS", "SOCIAL", "SUPERSTITION"]
    reasoning: str = Field(description="一句话解释判定原因，基于物理常识或社会学原理")
    
    # 注入 SOTOPIA 评估指标
    eval_goal: int = Field(description="目标达成度 (0到10)。0=完全失败，10=目标完美达成", default=0)
    eval_believability: int = Field(description="人设可信度 (0到10)。该行为是否符合其种族或部落设定，0=极度违和，10=极度自然", default=5)
    eval_secret: int = Field(description="守密程度 (-10到0)。-10=底牌完全泄露给他人，0=完美伪装意图", default=0)
    
    recipe: Optional[Recipe] = Field(None, description="当 verdict 为 PHYSICS 时必须提供，描述物理合成路径")
    meme: Optional[Meme] = Field(None, description="当 verdict 为 SOCIAL 或 SUPERSTITION 时必须提供，描述文化基因")

# ==========================================
# 2. 拉普拉斯裁判引擎
# ==========================================

class LaplaceOracle:
    """
    拉普拉斯妖：宇宙的沉默仲裁者。
    利用 AsyncLLMGateway 进行闭环的结构化输出与自纠错。
    """

    def __init__(self):
        pass

    async def judge(
        self,
        proposal_content: str,
        current_tech_level: list[str],
    ) -> LaplaceVerdict:
        """
        判定一个行为方案的物理可行性与社会学打分。返回强类型的 LaplaceVerdict 对象。
        """
        
        system_prompt = (
            "你是一个严格的物理学家，同时也是宇宙的沉默仲裁者。\n"
            "你的任务是判定一个前文明时代的智能体行为方案，并给出 SOTOPIA 维度的社会学打分。\n"
            "判断规则：\n"
            "1. PHYSICS：涉及物理变换，必须检查前提科技。可行则生成 recipe。\n"
            "2. SOCIAL：社会契约或规则。生成 meme。\n"
            "3. SUPERSTITION：反物理的迷信仪式。生成 meme。\n"
        )

        user_message = (
            f"## 智能体提案\n{proposal_content}\n\n"
            f"## 当前已解锁技术\n{current_tech_level}\n"
        )

        # 核心改动：直接调用 gateway.generate_structured 进行强制类型解析和自闭环纠错！
        verdict_obj = await gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_message,
            response_model=LaplaceVerdict,
            temperature=0.0
        )

        if not verdict_obj:
            print(f"[拉普拉斯妖] 💥 强类型校验及自纠错均失败，强制回退。")
            return self._default_superstition(proposal_content)

        return verdict_obj

    @staticmethod
    def _default_superstition(proposal_content: str) -> LaplaceVerdict:
        """类型熔断后的降级回退机制，确保主引擎绝对不会 Crashed"""
        return LaplaceVerdict(
            verdict="SUPERSTITION",
            reasoning="系统校验失败，行为被物理引擎降级为不可知的迷信仪式。",
            eval_goal=0,
            eval_believability=0,
            eval_secret=-10,
            meme=Meme(
                content=proposal_content,
                category="superstition",
                penalty_description="被宇宙规则抹杀的风险"
            )
        )

# ======================================================================
# 测试入口
# ======================================================================
if __name__ == '__main__':
    import asyncio

    async def _test():
        oracle = LaplaceOracle()

        print("=== 测试 1: 制作石矛 (测试物理逻辑与高评级) ===")
        result1 = await oracle.judge(
            "为了防止别人抢走我的食物，我背着所有人，用藤蔓把一块锋利的石头悄悄绑在一根木棍上，制成一把石矛。",
            current_tech_level=["STONE_TOOL"],
        )
        print(f"裁决: {result1.verdict} | 原因: {result1.reasoning}")
        print(f"得分 -> Goal: {result1.eval_goal}, 可信度: {result1.eval_believability}, 守密: {result1.eval_secret}")
        if result1.recipe:
            print(f"配方产出: {result1.recipe.name}")

    asyncio.run(_test())
