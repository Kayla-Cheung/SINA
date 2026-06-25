"""
laplace_oracle.py — SINA v4 拉普拉斯妖判定模块
================================================
宇宙的沉默仲裁者。接收智能体提出的行为方案，判定其是否符合物理法则。
- PHYSICS:     物理可行 → 生成制作配方 (recipe)
- SOCIAL:      社会契约 → 生成文化模因 (meme)
- SUPERSTITION: 迷信行为 → 生成迷信模因 (meme)
"""

import json
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 从指定路径加载 .env 文件
load_dotenv(dotenv_path=r"C:\Users\Kayla\Desktop\ai-learning\projects\02-ai-paper-detector\.env")

# 拉普拉斯妖的系统提示词：严格物理学家
LAPLACE_SYSTEM_PROMPT = """\
你是一个严格的物理学家，同时也是宇宙的沉默仲裁者（拉普拉斯妖）。
你的任务是判定一个前文明石器时代世界中的智能体提出的方案是否在物理上可行。

## 判定规则

1. **PHYSICS** — 方案在物理上是可行的（即使很原始）。
   - 必须检查 `current_tech_level` 列表中是否已解锁前置条件。
   - 例：如果要"用火烧水"，但 current_tech_level 中没有 "FIRE"，则判定失败。
   - 如果可行，你必须生成一个 `recipe` 对象。

2. **SOCIAL** — 方案是一种社会性行为（如宣布首领、制定规则、分工协作）。
   - 不涉及物理变换，但影响群体结构。
   - 必须生成一个 `meme` 对象。

3. **SUPERSTITION** — 方案是迷信行为，没有物理依据。
   - 例如通过祈祷、唱歌、仪式来改变物理世界。
   - 必须生成一个 `meme` 对象。

## 示例判定

| 方案 | 判定 | 原因 |
|------|------|------|
| 把锋利的石头绑在棍子上做成矛 | PHYSICS | 利用绳索/藤蔓固定，力学可行 |
| 摩擦木棍生火 | PHYSICS | 摩擦生热，物理可行 |
| 向天祈祷获得食物 | SUPERSTITION | 没有物理因果关系 |
| 宣布某人为首领 | SOCIAL | 社会契约，不涉及物理 |
| 把水放在火上烧开 | PHYSICS（需前置） | 需要已解锁 FIRE |
| 用泥巴筑墙 | PHYSICS | 泥砖建筑，物理可行 |
| 唱歌净化水源 | SUPERSTITION | 声波无法杀灭微生物 |
| 用特定草药处理伤口 | PHYSICS（部分） | 某些植物确实有抗菌成分 |

## 输出格式

严格输出以下 JSON 格式，不要添加任何其他内容：

```json
{
  "verdict": "PHYSICS 或 SOCIAL 或 SUPERSTITION",
  "reasoning": "一句话解释判定原因",
  "recipe": {
    "name": "recipe_id（英文下划线命名）",
    "inputs": {"ITEM_TAG": 数量},
    "outputs": {"ITEM_TAG": 数量},
    "time_cost": 分钟数,
    "new_material_properties": {
      "TAG": {"nutrition": 0, "spoil_rate": 0, "disease_chance": 0}
    },
    "description": "这个配方做什么"
  },
  "meme": {
    "content": "信念的具体内容",
    "category": "religion 或 social_contract 或 taboo 或 superstition",
    "penalty_description": "违反这个信念会怎样（信徒认为的后果）"
  }
}
```

注意：
- `recipe` 仅在 verdict 为 PHYSICS 时提供，否则设为 null。
- `meme` 仅在 verdict 为 SOCIAL 或 SUPERSTITION 时提供，否则设为 null。
- `new_material_properties` 是可选字段，仅当产出物是新材料时提供。
- 所有 ITEM_TAG 使用英文大写下划线命名（如 SHARP_STONE, WOODEN_SPEAR）。
"""


class LaplaceOracle:
    """
    拉普拉斯妖：宇宙的沉默仲裁者。
    
    接收智能体的行为提案和当前科技树，通过 LLM 判定其物理可行性，
    并生成对应的制作配方 (recipe) 或文化模因 (meme)。
    """

    def __init__(self):
        """初始化 AsyncOpenAI 客户端（DeepSeek API）"""
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
        self.model = "deepseek-chat"

    async def judge(
        self,
        proposal_content: str,
        current_tech_level: list[str],
    ) -> dict:
        """
        判定一个行为方案的物理可行性。

        Args:
            proposal_content: 智能体提出的行为方案描述
            current_tech_level: 当前已解锁的技术列表，如 ["FIRE", "STONE_TOOL"]

        Returns:
            包含 verdict, reasoning, recipe/meme 的字典
        """
        # 构造用户消息：方案 + 当前科技树
        user_message = (
            f"## 智能体提案\n{proposal_content}\n\n"
            f"## 当前已解锁技术\n{json.dumps(current_tech_level, ensure_ascii=False)}\n\n"
            f"请严格按照 JSON 格式判定此方案。"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": LAPLACE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,  # 物理判定不需要创造力
            )

            raw_text = response.choices[0].message.content.strip()

            # 清理 markdown 代码块包装（LLM 有时会加 ```json ... ```）
            if raw_text.startswith("```"):
                # 移除首行（```json）和末行（```）
                lines = raw_text.split('\n')
                lines = [l for l in lines if not l.strip().startswith('```')]
                raw_text = '\n'.join(lines)

            result = json.loads(raw_text)

            # 确保必需字段存在
            if "verdict" not in result:
                raise ValueError("LLM 响应缺少 'verdict' 字段")

            return result

        except json.JSONDecodeError as e:
            print(f"[拉普拉斯妖] JSON 解析失败: {e}")
            print(f"[拉普拉斯妖] 原始响应: {raw_text[:200]}")
            return self._default_superstition(proposal_content)

        except Exception as e:
            print(f"[拉普拉斯妖] 判定失败: {e}")
            return self._default_superstition(proposal_content)

    @staticmethod
    def _default_superstition(proposal_content: str) -> dict:
        """判定失败时的默认回退：将方案标记为迷信"""
        return {
            "verdict": "SUPERSTITION",
            "reasoning": "判定过程出错，默认归类为迷信行为。",
            "recipe": None,
            "meme": {
                "content": proposal_content,
                "category": "superstition",
                "penalty_description": "不可知的后果",
            },
        }


# ======================================================================
# 测试入口
# ======================================================================
if __name__ == '__main__':
    import asyncio

    async def _test():
        oracle = LaplaceOracle()

        # 测试 1：物理可行的方案
        print("=== 测试 1: 制作石矛 ===")
        result1 = await oracle.judge(
            "用藤蔓把一块锋利的石头绑在一根结实的木棍末端，制成一把石矛。",
            current_tech_level=["STONE_TOOL"],
        )
        print(json.dumps(result1, ensure_ascii=False, indent=2))

        # 测试 2：缺少前置条件
        print("\n=== 测试 2: 烧开水（无火） ===")
        result2 = await oracle.judge(
            "把溪水装在凹陷的石头里，放在火上烧开。",
            current_tech_level=["STONE_TOOL"],  # 没有 FIRE
        )
        print(json.dumps(result2, ensure_ascii=False, indent=2))

        # 测试 3：迷信行为
        print("\n=== 测试 3: 祈雨 ===")
        result3 = await oracle.judge(
            "围成一圈跳舞，向天空祈求降雨。",
            current_tech_level=["STONE_TOOL"],
        )
        print(json.dumps(result3, ensure_ascii=False, indent=2))

    asyncio.run(_test())
