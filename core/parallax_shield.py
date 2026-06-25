from pydantic import BaseModel, Field
from typing import Optional, Any, Dict

# =====================================================================
# Principle 1: Cognitive-Executive Separation (认知-执行分离)
# =====================================================================
# Agent 绝对不能直接调用执行函数。它只能实例化并输出这个纯数据对象 (Intent)。
class AgentIntent(BaseModel):
    """
    平民 Agent 产生的意图对象，没有任何执行能力。
    这是进程A（思考层）发给进程B（执行层）的唯一合法数据结构。
    """
    agent_id: str
    action_type: str = Field(description="动作类型，如 'MOVE', 'CRAFT', 'ATTACK', 'TRADE'")
    target: str = Field(description="动作作用的目标")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="额外参数")
    reasoning: str = Field(description="Agent 产生此意图的内部思考过程")

# =====================================================================
# Principle 2: Adversarial Validation (对抗式多级验证 - Shield)
# =====================================================================
class ShieldValidator:
    """
    拉普拉斯护盾 (Shield) - 拦截并审查所有 Intent。
    完美实现论文中的 4 层 Graduated Determinism。
    """
    def __init__(self, oracle_llm):
        # 这里挂载你现有的 LaplaceOracle 实例（作为核武器级别最后的裁决者）
        self.oracle_llm = oracle_llm 

    async def validate(self, intent: AgentIntent, current_state: dict) -> bool:
        """多级拦截流水线 (Pipeline)"""
        
        # -------------------------------------------------------------
        # Tier 0: 静态物理与权限边界拦截 (消耗 0 Token, 0 延迟)
        # -------------------------------------------------------------
        if not self._tier_0_static_check(intent, current_state):
            print(f"🚫 [Shield Tier 0] 静态规则拦截违规操作: {intent.action_type}")
            return False
            
        # -------------------------------------------------------------
        # Tier 1: 轻量启发式/本地 NLP 拦截 (消耗 0 Token)
        # -------------------------------------------------------------
        if not self._tier_1_heuristic_check(intent):
            print(f"🚫 [Shield Tier 1] 本地分类器检测到高危特征，拦截: {intent.action_type}")
            return False
            
        # -------------------------------------------------------------
        # Tier 2: Laplace Oracle 大模型深度审查 (消耗 Token，极少触发)
        # -------------------------------------------------------------
        print(f"⚠️ [Shield Tier 2] 意图复杂，触发 Oracle 大模型审查: {intent.action_type}")
        # 只有过了前两关，才会调用你现有的 DeepSeek 进行物理与社会法则验证
        oracle_verdict = await self.oracle_llm.judge(str(intent), current_state.get('tech_level', []))
        if oracle_verdict.get('verdict') == 'SUPERSTITION':
             print("🚫 [Shield Tier 2] Oracle 判定为迷信行为，剥夺其物理执行效力。")
             return False
             
        # 全部验证通过，允许进入 Settlement Engine 进行物理结算
        print(f"✅ [Shield] 验证通过，放行 Intent: {intent.action_type}")
        return True

    def _tier_0_static_check(self, intent: AgentIntent, state: dict) -> bool:
        """硬性物理规则字典 (YAML / Code 级别的绝对禁忌)"""
        # 例子 1：绝对禁止平民 Agent 越权调用系统级销毁指令
        if intent.action_type == "DELETE_WORLD":
            return False
        # 例子 2：物理状态前置条件拦截（无火源绝对不允许执行烧烤）
        if intent.action_type == "COOK" and "FIRE" not in state.get("tech_level", []):
            return False
        return True

    def _tier_1_heuristic_check(self, intent: AgentIntent) -> bool:
        """本地分类器检查（作为未来弹性扩展的接口）"""
        # TODO: 未来在此处 import transformers 并加载 HuggingFace DeBERTa 模型
        # 目前直接放行，把鉴伪压力抛给 Tier 2
        return True
