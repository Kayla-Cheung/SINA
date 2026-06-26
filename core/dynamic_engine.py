"""
dynamic_engine.py — SINA v4 动态决策引擎
==========================================
负责：
  1. 记忆存储与反思触发（importance 累积 → generate_insights）
  2. 构建原始人类视角的 System Prompt（双层架构：硬物理 + 模因信念）
  3. 调用 DeepSeek LLM 获取下一步行动（JSON 结构化输出）
"""

import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from openai import AsyncOpenAI

from agent_state import AgentState
from reflection import generate_insights

# ──────────────────────────────────────────────
# 全局初始化：加载环境变量，创建异步 OpenAI 客户端
# ──────────────────────────────────────────────
load_dotenv(dotenv_path=r"C:\Users\Kayla\Desktop\ai-learning\projects\02-ai-paper-detector\.env")

client = AsyncOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

MODEL = "deepseek-chat"


# ──────────────────────────────────────────────
# 记忆存储 + 反思触发
# ──────────────────────────────────────────────
async def store_observation(state: AgentState, text: str, sim_time: datetime):
    """
    将一条观察写入 agent 的记忆流。
    - 自动累积 importance；超过阈值时触发深层反思。
    - 记忆流上限 50 条，采用滑动窗口淘汰最旧记忆。
    """
    entry = {
        "time": sim_time.strftime("%H:%M"),
        "text": text,
        "importance": 3,
    }
    state.memory_stream.append(entry)
    state.importance_accumulator += entry["importance"]

    # 滑动窗口：保留最近 50 条记忆
    while len(state.memory_stream) > 50:
        state.memory_stream.pop(0)

    # 重要性累积超过阈值 → 触发反思
    if state.importance_accumulator > 15:
        recent_texts = state.memory_stream[-10:]
        insights = await generate_insights(recent_texts, count=2)
        for insight in insights:
            insight_entry = {
                "time": sim_time.strftime("%H:%M"),
                "text": f"[深层领悟] {insight}",
                "importance": 5,
            }
            state.memory_stream.append(insight_entry)
            # 将领悟追加到 traits，影响后续决策人格
            state.traits += f" [Deep Realization: {insight}]"
        state.importance_accumulator = 0


# ──────────────────────────────────────────────
# 近期记忆上下文格式化
# ──────────────────────────────────────────────
def get_recent_memory_context(state: AgentState, limit: int = 8) -> str:
    """返回格式化的近期记忆片段，供 LLM prompt 使用。"""
    recent = state.memory_stream[-limit:]
    if not recent:
        return "（脑海一片空白，没有任何记忆）"
    lines = []
    for mem in recent:
        lines.append(f"  [{mem['time']}] {mem['text']}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# LLM 决策：构建 prompt → 调用 DeepSeek → 解析 JSON
# ──────────────────────────────────────────────
async def determine_next_action(
    state: AgentState,
    current_time: datetime,
    perception: str,
    meme_context: str,
    memory_context: str,
    current_room: str,
    active_proposal,
    known_recipes_desc: str,
) -> dict:
    """
    为一个原始人类 agent 生成下一步行动。
    双层架构：
      - 硬物理层（不可违反）
      - 模因信念层（主观共识，可在内心怀疑）
    """
    time_str = current_time.strftime("%H:%M")
    is_night = not (6 <= current_time.hour < 18)
    
    # 季节演算
    from datetime import datetime as dt
    start_time = dt(2026, 1, 1, 6, 0)
    ticks = int((current_time - start_time).total_seconds() / 900)
    season_idx = (ticks // 24) % 3
    season_names = ["春季(丰饶，遍地浆果)", "秋季(衰退，资源减产)", "凛冬(死亡，严寒且没有任何植物生长)"]
    current_season = season_names[season_idx]
    
    period = "【夜晚—危险！】" if is_night else "【白天】"
    period += f" 🌍 当前季节: {current_season}"

    # ── 构建 inventory 描述 ──
    inv_items = []
    for tag, count in state.inventory.items():
        inv_items.append(f"{tag}×{count}")
    inv_desc = "、".join(inv_items) if inv_items else "空无一物"

    # ── 活跃提案描述 ──
    proposal_section = ""
    if active_proposal:
        proposal_section = f"""
═══ 部落提案（等待你的表决）═══
提案者: {active_proposal.proposer}
内容: {active_proposal.content}
你可以在 vote_on_blueprint 字段投 "YES" 或 "NO"。
══════════════════════════════"""

    # ── 系统提示词 ──
    system_prompt = f"""你是「{state.name}」，一个生活在文明诞生之前的原始人类。
你的性格特征：{state.traits}
你的意图：{', '.join(state.intentions) if state.intentions else '尚无明确意图'}

现在是 {time_str} {period}

═══ 硬物理层（不可违反的自然法则）═══
▸ 饥饿度: {state.hunger}/30（0 = 昏迷，必须被他人喂食）
▸ 你的物品: {inv_desc}
▸ 当前位置: {current_room}
▸ 环境感知: {perception}
══════════════════════════════

═══ 部落信念（你从他人那里听来的共识）═══
{meme_context if meme_context else '（目前没有任何部落共识）'}
══════════════════════════════

═══ 已知配方 ═══
{known_recipes_desc if known_recipes_desc else '（尚未发现任何配方）'}
══════════════════════════════
{proposal_section}
═══ 你的近期记忆 ═══
{memory_context}
══════════════════════════════

═══ 生存法则（热力学优先级）═══
如果你的饥饿度 ≤ 5，你必须把「寻找食物和进食」作为最高优先级！
饥饿会杀死你。社交、探索、一切其他欲望都排在活命之后。
* 技巧：在同一个 15 分钟内，你可以同时填写 `"take_item_tag": "BERRY"` 和 `"eat_item": "BERRY"`，系统会先帮你捡起来再让你立刻吃掉。通过 `produce_item_tag` 劳动获取食物也同样适用组合动作。
══════════════════════════════

═══ 语言规则 ═══
你是原始人，词汇量极其有限。
所有说出口的话必须用【简短的中文句子】，像原始人一样说话。
例如：「火…好…暖」「那边…有果子」「你…不好…走开」
内心想法可以更复杂，但外在语言必须原始。
══════════════════════════════

请严格以如下 JSON 格式回复（不要添加任何 JSON 之外的文字）：
{{
  "internal_thought": "（你内心真实的想法，可以复杂，可以怀疑部落信念）",
  "observable_action": "（你实际做的事 + 说出口的原始中文，第一人称描述）",
  "duration_minutes": 15,
  "move_to": null,
  "eat_item": null,
  "attack_target": null,
  "craft": null,
  "take_item_tag": null,
  "give_item": null,
  "drop_item_tag": null,
  "produce_item_tag": null,
  "propose_blueprint": null,
  "vote_on_blueprint": null
}}

字段说明：
- move_to: 移动目的地，可选 "Dark_Cave" / "Riverbank" / "Dense_Forest" / "Open_Plains" / "Hilltop"，或 null
- eat_item: 要吃的物品 tag（从你的背包中），或 null
- attack_target: 要攻击的对象名字（必须在同一房间），或 null
- craft: 要制作的配方名称，或 null
- take_item_tag: 从当前房间地面拾取的物品 tag，或 null
- give_item: 赠送物品，格式 {{"tag": "物品名", "target": "对方名字"}}，或 null
- drop_item_tag: 将物品放到当前房间地面，或 null
- produce_item_tag: 通过劳动凭空生产一件物品（消耗 1 饥饿度），或 null
- propose_blueprint: 提出一个发明或社会规则的提案（字符串描述），或 null
- vote_on_blueprint: 对当前活跃提案投票 "YES" 或 "NO"，或 null
- duration_minutes: 这个行动持续多少分钟（5-30）
"""

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "根据当前处境，决定你下一步的行动。"},
            ],
            temperature=0.75,
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()

        # 清理 markdown 包裹（```json ... ```）
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        from action_intent import ActionSchema
        
        try:
            # 【绝对契约】通过 Pydantic 强类型校验 LLM 输出
            action_obj = ActionSchema.model_validate_json(raw)
            return action_obj.model_dump()
        except Exception as pydantic_err:
            print(f"  ⚠ [{state.name}] Pydantic 契约撕毁 (格式不符): {pydantic_err}")
            raise  # 触发 fallback 或留给未来的重试回路

    except Exception as e:
        print(f"  ⚠ [{state.name}] LLM 决策失败: {e}")
        return _fallback_action(state)


# ──────────────────────────────────────────────
# 安全兜底行动
# ──────────────────────────────────────────────
def _fallback_action(state: AgentState) -> dict:
    """当 LLM 调用失败时，返回一个安全的默认行动。"""
    # 如果快饿死了，尝试吃背包里的第一个物品
    eat_item = None
    if state.hunger <= 5 and state.inventory:
        eat_item = next(iter(state.inventory))

    return {
        "internal_thought": "脑袋嗡嗡的，一时想不清楚……",
        "observable_action": "茫然地四处张望",
        "duration_minutes": 10,
        "move_to": None,
        "eat_item": eat_item,
        "attack_target": None,
        "craft": None,
        "take_item_tag": None,
        "give_item": None,
        "drop_item_tag": None,
        "produce_item_tag": None,
        "propose_blueprint": None,
        "vote_on_blueprint": None,
    }
