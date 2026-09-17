"""回归测试：RealityCheckMiddleware 结构化校验 (#27)。

旧实现对 observable_action/internal_thought 做自由文本扫描，导致两类合法动作被误判：
  1. 投票时提到不在场的提案者 → "Target not in same room"；
  2. 购买时提到货架上的商品 → "Claimed item not in inventory"。

结算引擎现在传入结构化 action 字段后，只对「声明出来的交互目标/物品」做硬校验。
"""

from core.laplace_oracle import RealityCheckMiddleware


def _mw():
    return RealityCheckMiddleware()


def test_vote_mentioning_non_present_proposer_is_grounded():
    res = _mw().check(
        action_text="举手赞同 Isabella 的春季市集提案",
        thought_text="这是个很棒的社区活动提议",
        agent_state={"inventory": []},
        room_state={
            "agents_present": ["Tom"],
            "agents_known": ["Tom"],
            "agents_dead": [],
            "known_items": [],
            "room_items": [],
        },
        action={"vote_on_blueprint": "YES"},
    )
    assert res.is_grounded is True
    assert res.should_proceed is True
    assert res.hallucination_flags == []


def test_buy_item_available_in_room_is_grounded():
    res = _mw().check(
        action_text="在咖啡馆点了一份新鲜的 COFFEE",
        thought_text="闻到咖啡馆的香气",
        agent_state={"inventory": []},
        room_state={
            "agents_present": ["Isabella"],
            "agents_known": ["Isabella"],
            "agents_dead": [],
            "known_items": ["COFFEE"],
            "room_items": ["COFFEE"],
        },
        action={"take_item_tag": "COFFEE"},
    )
    assert res.is_grounded is True
    assert res.hallucination_flags == []


def test_declared_attack_target_still_blocked_when_absent():
    res = _mw().check(
        action_text="攻击 Bob",
        thought_text="Bob 就在那边",
        agent_state={"inventory": []},
        room_state={
            "agents_present": ["Alice"],
            "agents_known": ["Alice"],
            "agents_dead": [],
            "known_items": [],
            "room_items": [],
        },
        action={"attack_target": "Bob"},
    )
    assert res.is_grounded is False
    assert "Target not in same room: bob" in res.hallucination_flags


def test_legacy_free_text_path_still_works_without_action():
    """未传 action 时保留旧的自由文本启发式，避免破坏历史调用方。"""
    res = _mw().check(
        action_text="I talk to Charlie about the weather.",
        thought_text="Charlie always knows what to say.",
        agent_state={"inventory": []},
        room_state={
            "agents_present": ["Alice", "Bob"],
            "agents_known": ["Alice", "Bob", "Charlie"],
            "agents_dead": [],
            "known_items": [],
            "room_items": [],
        },
    )
    assert res.is_grounded is False
    assert "Target not in same room: charlie" in res.hallucination_flags
