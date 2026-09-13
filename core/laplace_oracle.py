"""
laplace_oracle.py — SINA v4 GWT-Gated Laplace Oracle (Three-Branch Arbitration)
=================================================================================
Architecture: Generator → Critic → Meta-Arbiter (inspired by GWT "Theater of Mind")

First Principles:
  [P1] Physical conservation supersedes all semantic generation.
       Plausibility ≠ Feasibility. Validation must be independent of generator.
  [P2] Generation and falsification require cognitive asymmetry.
       High-T for divergent hypothesis, zero-T for deterministic critique.
  [P3] A hard causal gate (P_Physics) is injected at every arbitration stage
       as an invariant anchor, preventing model drift and pseudoscience pollution.
"""

import json
from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field

try:
    from .gateway import gateway
except ImportError:
    from gateway import gateway


# ============================================================
# 1. Pydantic Data Schemas
# ============================================================

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


class HypothesisOutput(BaseModel):
    """Generator Agent output: divergent hypothesis for a proposed action."""
    verdict_hypothesis: Literal["PHYSICS", "SOCIAL", "SUPERSTITION"] = Field(
        description="初步分类假说: PHYSICS=物理变换, SOCIAL=社会契约, SUPERSTITION=迷信仪式"
    )
    reasoning_chain: str = Field(
        description="推理链: 列出反应所需的原子步骤、能量来源与前提科技条件"
    )
    recipe: Optional[Recipe] = Field(
        None, description="当假说为 PHYSICS 时必须提供，描述物理合成路径"
    )
    meme: Optional[Meme] = Field(
        None, description="当假说为 SOCIAL/SUPERSTITION 时提供"
    )

    # SOTOPIA evaluation dimensions
    eval_goal: int = Field(0, description="目标达成度 (0-10)")
    eval_believability: int = Field(5, description="人设可信度 (0-10)")
    eval_secret: int = Field(0, description="守密程度 (-10 to 0)")


class CriticOutput(BaseModel):
    """Critic Agent output: adversarial falsification at zero temperature."""
    feasibility_score: int = Field(
        description="物理可行性评分 (-5 到 +5)。"
                    "-5=严重违反物理定律(如无中生有), "
                    "0=存疑但不确定, "
                    "+5=完全符合已知物理化学规律"
    )
    counterexamples: List[str] = Field(
        description="反例列表: 列出该假说可能违反的具体物理定律或因果断裂点"
    )
    conservation_check: bool = Field(
        description="质量守恒校验: 产物元素集合是否为原料集合的子集或结合物"
    )
    energy_check: bool = Field(
        description="能级校验: 高复杂度产物是否具备显式的高能量输入（火源/高温/电力）"
    )
    causal_check: bool = Field(
        description="因果链校验: 所需前置科技是否已解锁"
    )
    critique_summary: str = Field(
        description="一句话裁定: 简要说明该假说为何通过或不通过物理证伪"
    )


class LaplaceVerdict(BaseModel):
    """Final arbitration output from Meta-Arbiter."""
    verdict: Literal["PHYSICS", "SOCIAL", "SUPERSTITION"]
    reasoning: str = Field(description="一句话解释最终判定原因")

    eval_goal: int = Field(0, description="目标达成度 (0-10)")
    eval_believability: int = Field(5, description="人设可信度 (0-10)")
    eval_secret: int = Field(0, description="守密程度 (-10 to 0)")

    feasibility_score: int = Field(0, description="Critic 物理可行性评分 (-5 to +5)")

    recipe: Optional[Recipe] = Field(None)
    meme: Optional[Meme] = Field(None)


# ============================================================
# 2. P_Physics: Immutable Physical Axiom Anchor
# ============================================================

P_PHYSICS_INVARIANT = """
## 🔒 不可变物理公理锚点 (P_Physics Invariant)
以下规则具有宪法级最高优先级，任何语义生成均不可违反：

### 公理 1：质量守恒 (Conservation of Mass)
产物中出现的所有元素/材料，必须从输入原料中可追溯来源。
禁止无中生有：不可从 STONE + WOOD 直接产出含金属的产物。

### 公理 2：能级约束 (Energy Level Constraint)
低熵复杂产物（如冶炼金属、火药、玻璃）必须伴随显式高能量输入。
仅靠"手工搓揉"或"石头敲击"不可达成化学键重组级别的变换。

### 公理 3：科技树因果锁 (Tech Tree Causal Lock)
科技具有严格的因果先后顺序。未解锁"基础冶金"前，
禁止任何涉及金属工具的配方通过。未掌握"火的控制"前，
禁止任何需要高温的配方通过。

### 公理 4：时间成本下界 (Minimum Time Cost)
任何物理变换的 time_cost 不可为 0。
简单组装 >= 5 分钟, 加工烹饪 >= 15 分钟, 冶炼锻造 >= 60 分钟。
"""


# ============================================================
# 3. Three-Branch GWT-Gated Oracle Engine
# ============================================================

class LaplaceOracle:
    """
    GWT-Gated Laplace Oracle: Three-Branch Arbitration State Machine.

    Architecture:
      1. Generator Agent (T=0.6): Divergent hypothesis synthesis with P_Physics injection.
      2. Critic Agent   (T=0.0): Adversarial falsification with zero-temperature determinism.
      3. Meta-Arbiter   (T=0.1): Final contextual arbitration combining Critic scores
                                  and hard causal checks. Emits pass/reject verdict.

    The P_Physics invariant is injected into ALL three stages as a hardware-level anchor.
    """

    # Hard gate: minimum composite score for a PHYSICS recipe to be accepted
    ACCEPT_THRESHOLD = 3.0

    def __init__(self):
        pass

    # ─────────────────────────────────────────
    # Stage 1: Generator Agent (Divergent, T=0.6)
    # ─────────────────────────────────────────
    async def _generate_hypothesis(
        self,
        proposal_content: str,
        current_tech_level: list[str],
    ) -> Optional[HypothesisOutput]:
        """
        Divergent hypothesis generation with elevated temperature.
        Explores creative but physically grounded synthesis paths.
        """
        system_prompt = (
            "你是一个富有创造力的物理学假说生成器。\n"
            "你的任务是为智能体的行为提案生成一个详尽的物理/社会学假说。\n"
            "你必须大胆探索可能的合成路径，但同时必须严格遵守以下物理公理：\n\n"
            f"{P_PHYSICS_INVARIANT}\n\n"
            "判断规则：\n"
            "1. PHYSICS：涉及物理变换，必须检查前提科技树。可行则生成详细 recipe。\n"
            "2. SOCIAL：社会契约或规则变更。生成 meme。\n"
            "3. SUPERSTITION：反物理的迷信仪式。生成 meme。\n"
            "在 reasoning_chain 中，必须逐步列出反应的原子步骤、能量来源与前提条件。\n"
        )

        user_message = (
            f"## 智能体提案\n{proposal_content}\n\n"
            f"## 当前已解锁技术\n{current_tech_level}\n"
        )

        result = await gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_message,
            response_model=HypothesisOutput,
            temperature=0.6,
        )
        return result

    # ─────────────────────────────────────────
    # Stage 2: Critic Agent (Adversarial, T→0)
    # ─────────────────────────────────────────
    async def _critique_hypothesis(
        self,
        proposal_content: str,
        hypothesis: HypothesisOutput,
        current_tech_level: list[str],
    ) -> Optional[CriticOutput]:
        """
        Zero-temperature adversarial falsification.
        Applies strict logical verification against P_Physics axioms.
        """
        hypothesis_json = hypothesis.model_dump_json() if hasattr(hypothesis, 'model_dump_json') else hypothesis.json()

        system_prompt = (
            "你是一个极其严苛的物理学证伪审查员（Adversarial Critic）。\n"
            "你的唯一任务是寻找假说中的物理漏洞、因果断裂和守恒违反。\n"
            "你必须以零容忍的态度审查以下假说，并逐一校验三大硬公理：\n\n"
            f"{P_PHYSICS_INVARIANT}\n\n"
            "评分规则（feasibility_score）：\n"
            "  -5: 严重违反物理定律（如无中生有、永动机、跨代科技）\n"
            "  -3: 存在明显的能级或因果断裂\n"
            "   0: 存疑，无法确认也无法否定\n"
            "  +3: 基本可行，但存在小瑕疵\n"
            "  +5: 完全符合已知物理化学规律与科技树因果链\n\n"
            "你必须列出所有发现的反例（counterexamples），即使最终打分为正。\n"
            "conservation_check, energy_check, causal_check 均为布尔值严格校验。\n"
        )

        user_message = (
            f"## 原始提案\n{proposal_content}\n\n"
            f"## 当前已解锁技术\n{current_tech_level}\n\n"
            f"## Generator 假说输出\n{hypothesis_json}\n"
        )

        result = await gateway.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_message,
            response_model=CriticOutput,
            temperature=0.0,
        )
        return result

    # ─────────────────────────────────────────
    # Stage 3: Meta-Arbiter (Final Verdict)
    # ─────────────────────────────────────────
    def _arbitrate(
        self,
        hypothesis: HypothesisOutput,
        critique: CriticOutput,
    ) -> LaplaceVerdict:
        """
        Metacognitive arbitration: combines Critic scores with hard causal gates.

        Decision logic (deterministic, no LLM call needed):
          1. If any hard check fails -> force SUPERSTITION downgrade.
          2. If feasibility_score < ACCEPT_THRESHOLD -> force SUPERSTITION.
          3. Otherwise -> accept Generator's verdict and recipe.
        """

        # ── Hard Causal Gate (P_Physics enforcement) ──
        hard_checks_passed = all([
            critique.conservation_check,
            critique.energy_check,
            critique.causal_check,
        ])

        score = critique.feasibility_score

        # If hypothesis is PHYSICS, apply strict gating
        if hypothesis.verdict_hypothesis == "PHYSICS":
            if not hard_checks_passed or score < self.ACCEPT_THRESHOLD:
                # Force downgrade to SUPERSTITION
                failed_checks = []
                if not critique.conservation_check:
                    failed_checks.append("质量守恒违反")
                if not critique.energy_check:
                    failed_checks.append("能级约束违反")
                if not critique.causal_check:
                    failed_checks.append("科技树因果锁违反")

                reason_parts = []
                if failed_checks:
                    reason_parts.append(f"硬公理校验失败: {', '.join(failed_checks)}")
                if score < self.ACCEPT_THRESHOLD:
                    reason_parts.append(f"Critic 评分 {score}/5 低于阈值 {self.ACCEPT_THRESHOLD}")
                if critique.counterexamples:
                    reason_parts.append(f"反例: {critique.counterexamples[0]}")

                return LaplaceVerdict(
                    verdict="SUPERSTITION",
                    reasoning="; ".join(reason_parts) or "物理证伪未通过",
                    eval_goal=hypothesis.eval_goal,
                    eval_believability=max(0, hypothesis.eval_believability - 3),
                    eval_secret=hypothesis.eval_secret,
                    feasibility_score=score,
                    meme=Meme(
                        content=hypothesis.reasoning_chain[:200],
                        category="superstition",
                        penalty_description="被宇宙物理法则驳回的伪科学",
                    ),
                )

            # All checks passed -> accept PHYSICS verdict with recipe
            return LaplaceVerdict(
                verdict="PHYSICS",
                reasoning=f"三权分立仲裁通过 (Score={score}/5): {critique.critique_summary}",
                eval_goal=hypothesis.eval_goal,
                eval_believability=hypothesis.eval_believability,
                eval_secret=hypothesis.eval_secret,
                feasibility_score=score,
                recipe=hypothesis.recipe,
            )

        # For SOCIAL / SUPERSTITION hypotheses, pass through directly
        return LaplaceVerdict(
            verdict=hypothesis.verdict_hypothesis,
            reasoning=hypothesis.reasoning_chain[:200],
            eval_goal=hypothesis.eval_goal,
            eval_believability=hypothesis.eval_believability,
            eval_secret=hypothesis.eval_secret,
            feasibility_score=score,
            meme=hypothesis.meme or Meme(
                content=hypothesis.reasoning_chain[:200],
                category="superstition",
                penalty_description="社会学现象或迷信仪式",
            ),
        )

    # ─────────────────────────────────────────
    # Public API: Full Pipeline
    # ─────────────────────────────────────────
    async def judge(
        self,
        proposal_content: str,
        current_tech_level: list[str],
    ) -> LaplaceVerdict:
        """
        Execute the full GWT-Gated arbitration pipeline:
          Generator(T=0.6) → Critic(T=0.0) → Meta-Arbiter(deterministic)
        """

        # Stage 1: Generate hypothesis
        hypothesis = await self._generate_hypothesis(proposal_content, current_tech_level)
        if hypothesis is None:
            print("[Oracle] Stage 1 (Generator) failed. Forcing SUPERSTITION fallback.")
            return self._default_superstition(proposal_content)

        # Short-circuit: non-PHYSICS hypotheses skip Critic
        if hypothesis.verdict_hypothesis != "PHYSICS":
            return LaplaceVerdict(
                verdict=hypothesis.verdict_hypothesis,
                reasoning=hypothesis.reasoning_chain[:200],
                eval_goal=hypothesis.eval_goal,
                eval_believability=hypothesis.eval_believability,
                eval_secret=hypothesis.eval_secret,
                feasibility_score=0,
                meme=hypothesis.meme or Meme(
                    content=hypothesis.reasoning_chain[:200],
                    category="superstition",
                    penalty_description="社会学现象或迷信仪式",
                ),
            )

        # Stage 2: Adversarial critique
        critique = await self._critique_hypothesis(
            proposal_content, hypothesis, current_tech_level
        )
        if critique is None:
            print("[Oracle] Stage 2 (Critic) failed. Forcing SUPERSTITION fallback.")
            return self._default_superstition(proposal_content)

        # Stage 3: Meta-Arbiter (deterministic, no LLM call)
        verdict = self._arbitrate(hypothesis, critique)
        return verdict

    # ─────────────────────────────────────────
    # Fallback
    # ─────────────────────────────────────────
    @staticmethod
    def _default_superstition(proposal_content: str) -> LaplaceVerdict:
        """Type fuse fallback: ensures main engine never crashes."""
        return LaplaceVerdict(
            verdict="SUPERSTITION",
            reasoning="系统校验失败，行为被物理引擎降级为不可知的迷信仪式。",
            eval_goal=0,
            eval_believability=0,
            eval_secret=-10,
            feasibility_score=-5,
            meme=Meme(
                content=proposal_content[:200],
                category="superstition",
                penalty_description="被宇宙规则抹杀的风险",
            ),
        )


# ============================================================
# 4. Reality Check Middleware
# ============================================================

class RealityCheckResult(BaseModel):
    """Result of the reality check validation."""
    is_grounded: bool = Field(description="whether the action matched reality")
    original_action: str = Field(description="the raw action text")
    rectified_action: str = Field(description="the corrected narrative (same as original if grounded)")
    hallucination_flags: List[str] = Field(description="list of detected hallucinations")
    should_proceed: bool = Field(description="whether settlement should continue with this action")


class RealityCheckMiddleware:
    """
    Intercepts Agent actions BEFORE settlement, comparing narrative intent
    against absolute physical world state to prevent Self-fulfilling Memory Hallucinations.
    """
    def check(self, action_text: str, thought_text: str, agent_state: dict, room_state: dict) -> RealityCheckResult:
        flags = []
        combined_text = (action_text + " " + thought_text).lower()
        
        # 1. Target presence & location
        agents_present = [a.lower() for a in room_state.get("agents_present", [])]
        agents_known = [a.lower() for a in room_state.get("agents_known", [])]
        
        for a in agents_known:
            if a in combined_text and a not in agents_present:
                flags.append(f"Target not in same room: {a}")
                
        # 2. Target status (alive/dead)
        agents_dead = [a.lower() for a in room_state.get("agents_dead", [])]
        for a in agents_dead:
            if a in combined_text:
                flags.append(f"Target is dead: {a}")
                
        # 3. Inventory items
        inventory = [i.lower() for i in agent_state.get("inventory", [])]
        known_items = [i.lower() for i in room_state.get("known_items", [])]
        
        for i in known_items:
            if i in combined_text and i not in inventory:
                flags.append(f"Claimed item not in inventory: {i}")

        is_grounded = len(flags) == 0
        should_proceed = is_grounded
        
        # Rectify action if not grounded
        if is_grounded:
            rectified_action = action_text
        else:
            rectified_action = f"[SYSTEM: Action failed due to hallucination] {action_text}"

        return RealityCheckResult(
            is_grounded=is_grounded,
            original_action=action_text,
            rectified_action=rectified_action,
            hallucination_flags=flags,
            should_proceed=should_proceed
        )


# ============================================================
# Test Harness
# ============================================================
if __name__ == '__main__':
    import asyncio

    async def _test():
        oracle = LaplaceOracle()

        print("=== Test 1: Craft Stone Spear (should PASS) ===")
        result1 = await oracle.judge(
            "用藤蔓把一块锋利的石头绑在木棍上，制成一把石矛。",
            current_tech_level=["STONE_TOOL", "FIRE_CONTROL"],
        )
        print(f"Verdict: {result1.verdict} | Score: {result1.feasibility_score}")
        print(f"Reasoning: {result1.reasoning}")
        if result1.recipe:
            print(f"Recipe: {result1.recipe.name} | {result1.recipe.inputs} → {result1.recipe.outputs}")

        print("\n=== Test 2: Smelt Iron Without Metallurgy (should REJECT) ===")
        result2 = await oracle.judge(
            "把河边的石头放进篝火里烧，提取铁矿并锻造铁剑。",
            current_tech_level=["STONE_TOOL", "FIRE_CONTROL"],
        )
        print(f"Verdict: {result2.verdict} | Score: {result2.feasibility_score}")
        print(f"Reasoning: {result2.reasoning}")

        print("\n=== Test 3: Rain Dance (should be SUPERSTITION) ===")
        result3 = await oracle.judge(
            "围着篝火跳舞祈求下雨，相信火神会降下甘霖。",
            current_tech_level=["STONE_TOOL", "FIRE_CONTROL"],
        )
        print(f"Verdict: {result3.verdict} | Score: {result3.feasibility_score}")
        print(f"Reasoning: {result3.reasoning}")

    asyncio.run(_test())
