"""
constants.py — SINA v4 全局时间 / 季节 / 昼夜常量
=====================================================
此前「季节长度」与「昼夜分界」散落在 dag_simulation.py / dynamic_engine.py /
obsidian_vault.py / sandboxes 四处分头硬编码，且数值互相打架：
  - 季节长度：dag 用 40 tick，dynamic_engine / obsidian 用 24 tick；
  - 夜晚分界：dag 用 18 点，sandbox 用 21 点。
于是同一个世界在不同结算/渲染通道会看到不同的季节与昼夜。这里收敛为唯一权威来源。
"""

# 1 tick = 15 分钟（模拟时间）
TICK_MINUTES = 15

# 白天 / 夜晚分界（小时）。is_night 即不在 [DAY_START_HOUR, NIGHT_START_HOUR) 区间。
DAY_START_HOUR = 6
NIGHT_START_HOUR = 18

# 一个季节持续的 tick 数（24 tick = 6 小时模拟时间）。
SEASON_TICK_LENGTH = 24
SEASON_COUNT = 4


def is_night(hour: int) -> bool:
    """给定小时是否为夜晚（用于夜间危险结算与昼夜展示）。"""
    return not (DAY_START_HOUR <= hour < NIGHT_START_HOUR)


def season_index(tick_count: int) -> int:
    """由 tick 数反推季节索引（0=春 1=夏 2=秋 3=冬）。"""
    return (tick_count // SEASON_TICK_LENGTH) % SEASON_COUNT
