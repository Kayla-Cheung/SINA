"""回归测试：统一昼夜/季节常量 (#40) 与小村饥饿度量纲/人格字段 (#39)。

此前季节长度散落为 40 vs 24 tick、夜晚分界散落为 18 vs 21 点，且
smallville 的 agents.json 把饥饿度写成 60~85（远超 0~30 的量纲），并缺少
archetype / class_index / wealth 三个人格分层字段。
"""

import json
from pathlib import Path

from core.constants import (
    DAY_START_HOUR,
    NIGHT_START_HOUR,
    SEASON_TICK_LENGTH,
    is_night,
    season_index,
)


def test_is_night_boundaries():
    assert is_night(DAY_START_HOUR) is False
    assert is_night(NIGHT_START_HOUR - 1) is False
    assert is_night(NIGHT_START_HOUR) is True
    assert is_night(DAY_START_HOUR - 1) is True


def test_season_index_uses_single_tick_length():
    assert season_index(0) == 0
    assert season_index(SEASON_TICK_LENGTH - 1) == 0
    assert season_index(SEASON_TICK_LENGTH) == 1
    assert season_index(SEASON_TICK_LENGTH * 4) == 0


def test_smallville_hunger_within_scale_and_persona_fields():
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "worlds" / "smallville" / "config" / "agents.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert len(data["agents"]) == 6
    for cfg in data["agents"]:
        # 饥饿度量纲必须落在 0~30（0 = 昏迷，30 = 饱腹），旧配置写成 60~85 会永不饥饿。
        assert 0 <= cfg["hunger"] <= 30, f"{cfg['name']} 饥饿度越界: {cfg['hunger']}"
        assert cfg.get("archetype"), f"{cfg['name']} 缺少 archetype"
        assert "class_index" in cfg, f"{cfg['name']} 缺少 class_index"
        assert "wealth" in cfg, f"{cfg['name']} 缺少 wealth"
