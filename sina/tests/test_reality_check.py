import os
import pytest

os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-placeholder")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from core.laplace_oracle import RealityCheckMiddleware

@pytest.fixture
def middleware():
    return RealityCheckMiddleware()

@pytest.fixture
def room_state():
    return {
        "agents_present": ["Alice", "Bob"],
        "agents_known": ["Alice", "Bob", "Charlie", "Dave"],
        "agents_dead": ["Dave"],
        "known_items": ["apple", "sword", "shield", "healing_potion"]
    }

@pytest.fixture
def agent_state():
    return {
        "inventory": ["sword", "apple"]
    }

def test_grounded_action(middleware, agent_state, room_state):
    action = "I hand the apple to Bob."
    thought = "Bob looks hungry, I should give him my apple."
    result = middleware.check(action, thought, agent_state, room_state)
    
    assert result.is_grounded is True
    assert result.should_proceed is True
    assert len(result.hallucination_flags) == 0
    assert result.rectified_action == action

def test_target_not_in_room(middleware, agent_state, room_state):
    action = "I talk to Charlie about the weather."
    thought = "Charlie always knows what to say."
    result = middleware.check(action, thought, agent_state, room_state)
    
    assert result.is_grounded is False
    assert result.should_proceed is False
    assert "Target not in same room: charlie" in result.hallucination_flags

def test_target_is_dead(middleware, agent_state, room_state):
    action = "I ask Dave for help."
    thought = "Maybe Dave can carry this."
    # We must be careful if Dave is also not in room.
    # In our fixture, Dave is in agents_known but not agents_present, AND is dead.
    # So it should trigger both. Let's just check if the dead flag is there.
    result = middleware.check(action, thought, agent_state, room_state)
    
    assert result.is_grounded is False
    assert "Target is dead: dave" in result.hallucination_flags
    assert "Target not in same room: dave" in result.hallucination_flags

def test_item_not_in_inventory(middleware, agent_state, room_state):
    action = "I drink the healing_potion."
    thought = "I need health."
    result = middleware.check(action, thought, agent_state, room_state)
    
    assert result.is_grounded is False
    assert "Claimed item not in inventory: healing_potion" in result.hallucination_flags

def test_multiple_hallucinations(middleware, agent_state, room_state):
    action = "I give the shield to Charlie."
    thought = "Charlie needs protection, and Dave would agree."
    result = middleware.check(action, thought, agent_state, room_state)
    
    assert result.is_grounded is False
    assert len(result.hallucination_flags) == 4
    # Charlie not in room, Dave not in room, Dave is dead, shield not in inventory
    assert "Target not in same room: charlie" in result.hallucination_flags
    assert "Target not in same room: dave" in result.hallucination_flags
    assert "Target is dead: dave" in result.hallucination_flags
    assert "Claimed item not in inventory: shield" in result.hallucination_flags
    assert "[SYSTEM: Action failed due to hallucination]" in result.rectified_action
