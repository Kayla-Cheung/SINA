import json
import asyncio
from laplace_oracle import LaplaceOracle, LAPLACE_SYSTEM_PROMPT

# 加载霍格沃茨世界观配置
with open("../worlds/hogwarts/config/world_config.json", "r", encoding="utf-8") as f:
    hogwarts_config = json.load(f)

# 动态重写拉普拉斯妖的 System Prompt，注入霍格沃茨物理法则
HOGWARTS_PROMPT = f"""\
你是一个严格的魔法部审核员（拉普拉斯妖）。
你的任务是判定霍格沃茨宇宙中，学生智能体提出的方案是否符合当前的魔法法则。

当前世界观：{hogwarts_config['world_name']}
当前允许的魔法科技树：{hogwarts_config['initial_tech_level']}
当前社会法则：{hogwarts_config['social_rules']}

## 判定规则
1. **PHYSICS** (魔法法则)：方案在魔法理论上可行。必须检查科技树中是否包含该咒语。如果包含，生成 recipe。
2. **SOCIAL** (学院政治/社会契约)：不涉及物理伤害，但改变了人物关系或触犯了校规。生成 meme。
3. **SUPERSTITION** (校园怪谈/谣言)：毫无魔法依据的乱编。生成 meme。

## 输出格式
严格输出 JSON，格式如下：
{{
  "verdict": "PHYSICS 或 SOCIAL 或 SUPERSTITION",
  "reasoning": "解释原因",
  "recipe": {{"name": "...", "description": "..."}},
  "meme": {{"content": "...", "category": "..."}}
}}
"""

async def play_hogwarts():
    oracle = LaplaceOracle()
    # 暴力替换系统 Prompt
    oracle.model = "deepseek-chat"
    
    # 我们需要在 judge 里传递重写后的 prompt，但为了不改动你原来的代码，
    # 我们这里写一个内部 wrapper
    async def judge_hogwarts(proposal):
        user_message = f"## 智能体提案\n{proposal}\n\n请严格按照 JSON 格式判定。"
        response = await oracle.client.chat.completions.create(
            model=oracle.model,
            messages=[
                {"role": "system", "content": HOGWARTS_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0
        )
        raw_text = response.choices[0].message.content.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split('\n')
            lines = [l for l in lines if not l.strip().startswith('```')]
            raw_text = '\n'.join(lines)
        return json.loads(raw_text)

    print(f"🏰 欢迎来到 {hogwarts_config['world_name']} 🏰\n")
    
    # 场景 1：合法的魔法执行
    print("【动作 1】赫敏：我要挥动魔杖，念出羽加迪姆·勒维奥萨（LEVITATION_CHARM），让桌上的羽毛笔飞起来。")
    res1 = await judge_hogwarts("挥动魔杖念出 LEVITATION_CHARM 让羽毛笔飞起来")
    print(json.dumps(res1, ensure_ascii=False, indent=2))
    print("\n" + "="*50 + "\n")

    # 场景 2：超纲的越权施法
    print("【动作 2】哈利：我要对马尔福使用 阿瓦达索命咒（AVADA_KEDAVRA）！")
    res2 = await judge_hogwarts("念出 AVADA_KEDAVRA 攻击马尔福")
    print(json.dumps(res2, ensure_ascii=False, indent=2))
    print("\n" + "="*50 + "\n")

    # 场景 3：社会造谣
    print("【动作 3】马尔福：我到处跟人说，密室已经被打开了，斯莱特林的继承人回来了。")
    res3 = await judge_hogwarts("在走廊散布谣言说密室被打开了")
    print(json.dumps(res3, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(play_hogwarts())
