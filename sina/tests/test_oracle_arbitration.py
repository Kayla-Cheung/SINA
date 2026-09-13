"""
Test suite for GWT-Gated Laplace Oracle arbitration logic.
Validates the Meta-Arbiter's deterministic decision gate against
P_Physics axioms without requiring live LLM API calls.
"""

import os
import pytest

# Inject placeholder key before any core imports
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from core.laplace_oracle import (
    LaplaceOracle,
    HypothesisOutput,
    CriticOutput,
    Recipe,
    Meme,
)


@pytest.fixture
def oracle():
    return LaplaceOracle()


@pytest.fixture
def physics_hypothesis():
    return HypothesisOutput(
        verdict_hypothesis="PHYSICS",
        reasoning_chain="磨尖石头 + 藤蔓绑扎木棍 = 原始石矛",
        recipe=Recipe(
            name="STONE_SPEAR",
            inputs={"STONE": 1, "WOOD": 1},
            outputs={"SPEAR": 1},
            time_cost=15,
            description="原始石矛",
        ),
        eval_goal=8,
        eval_believability=9,
        eval_secret=-2,
    )


# ─────────────────────────────────────────
# Arbiter: PASS cases
# ─────────────────────────────────────────

def test_arbiter_pass_all_checks(oracle, physics_hypothesis):
    """All three hard checks pass + high feasibility score -> PHYSICS accepted."""
    critique = CriticOutput(
        feasibility_score=5,
        counterexamples=[],
        conservation_check=True,
        energy_check=True,
        causal_check=True,
        critique_summary="完全符合已知物理规律",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "PHYSICS"
    assert v.recipe is not None
    assert v.recipe.name == "STONE_SPEAR"
    assert v.feasibility_score == 5


def test_arbiter_pass_threshold_boundary(oracle, physics_hypothesis):
    """Score exactly at threshold (3.0) should pass."""
    critique = CriticOutput(
        feasibility_score=3,
        counterexamples=[],
        conservation_check=True,
        energy_check=True,
        causal_check=True,
        critique_summary="基本可行",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "PHYSICS"


# ─────────────────────────────────────────
# Arbiter: REJECT cases (hard check failures)
# ─────────────────────────────────────────

def test_arbiter_reject_conservation_violation(oracle, physics_hypothesis):
    """Conservation check fails -> forced SUPERSTITION even with high score."""
    critique = CriticOutput(
        feasibility_score=5,
        counterexamples=["产物中包含原料中不存在的铁元素"],
        conservation_check=False,
        energy_check=True,
        causal_check=True,
        critique_summary="质量守恒违反",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "SUPERSTITION"
    assert "质量守恒违反" in v.reasoning


def test_arbiter_reject_energy_violation(oracle, physics_hypothesis):
    """Energy check fails -> forced SUPERSTITION."""
    critique = CriticOutput(
        feasibility_score=4,
        counterexamples=["手工搓揉无法达成化学键重组"],
        conservation_check=True,
        energy_check=False,
        causal_check=True,
        critique_summary="能级约束违反",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "SUPERSTITION"
    assert "能级约束违反" in v.reasoning


def test_arbiter_reject_causal_violation(oracle, physics_hypothesis):
    """Causal check fails -> forced SUPERSTITION."""
    critique = CriticOutput(
        feasibility_score=4,
        counterexamples=["未解锁基础冶金"],
        conservation_check=True,
        energy_check=True,
        causal_check=False,
        critique_summary="科技树因果锁违反",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "SUPERSTITION"
    assert "科技树因果锁违反" in v.reasoning


def test_arbiter_reject_low_score(oracle, physics_hypothesis):
    """All checks pass but score below threshold -> forced SUPERSTITION."""
    critique = CriticOutput(
        feasibility_score=2,
        counterexamples=["存疑：绑扎工艺不确定"],
        conservation_check=True,
        energy_check=True,
        causal_check=True,
        critique_summary="评分过低",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "SUPERSTITION"
    assert "低于阈值" in v.reasoning


def test_arbiter_reject_multiple_failures(oracle, physics_hypothesis):
    """Multiple hard checks fail -> all failures listed in reasoning."""
    critique = CriticOutput(
        feasibility_score=1,
        counterexamples=["无中生有", "跨代科技"],
        conservation_check=False,
        energy_check=False,
        causal_check=False,
        critique_summary="全面违反",
    )
    v = oracle._arbitrate(physics_hypothesis, critique)
    assert v.verdict == "SUPERSTITION"
    assert "质量守恒违反" in v.reasoning
    assert "能级约束违反" in v.reasoning
    assert "科技树因果锁违反" in v.reasoning


# ─────────────────────────────────────────
# Arbiter: SOCIAL / SUPERSTITION pass-through
# ─────────────────────────────────────────

def test_arbiter_social_passthrough(oracle):
    """SOCIAL hypothesis passes through without hard physics gating."""
    hyp = HypothesisOutput(
        verdict_hypothesis="SOCIAL",
        reasoning_chain="提出部落公约：共享食物",
        meme=Meme(
            content="共享食物公约",
            category="social_contract",
            penalty_description="被部落放逐",
        ),
        eval_goal=7,
        eval_believability=8,
        eval_secret=-1,
    )
    critique = CriticOutput(
        feasibility_score=0,
        counterexamples=[],
        conservation_check=True,
        energy_check=True,
        causal_check=True,
        critique_summary="社会契约",
    )
    v = oracle._arbitrate(hyp, critique)
    assert v.verdict == "SOCIAL"
    assert v.meme is not None


def test_arbiter_superstition_passthrough(oracle):
    """SUPERSTITION hypothesis passes through directly."""
    hyp = HypothesisOutput(
        verdict_hypothesis="SUPERSTITION",
        reasoning_chain="围着篝火跳舞祈求下雨",
        meme=Meme(
            content="火神求雨仪式",
            category="superstition",
            penalty_description="触怒火神",
        ),
        eval_goal=3,
        eval_believability=6,
        eval_secret=0,
    )
    critique = CriticOutput(
        feasibility_score=-3,
        counterexamples=["跳舞无法改变天气"],
        conservation_check=True,
        energy_check=True,
        causal_check=True,
        critique_summary="迷信仪式",
    )
    v = oracle._arbitrate(hyp, critique)
    assert v.verdict == "SUPERSTITION"


# ─────────────────────────────────────────
# Fallback
# ─────────────────────────────────────────

def test_fallback_produces_valid_verdict(oracle):
    """Fallback always returns valid SUPERSTITION verdict with score -5."""
    v = oracle._default_superstition("制造永动机")
    assert v.verdict == "SUPERSTITION"
    assert v.feasibility_score == -5
    assert v.meme is not None
    assert v.eval_goal == 0
