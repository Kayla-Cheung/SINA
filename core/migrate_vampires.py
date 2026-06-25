import json
import os
import re
import random

source_file = r"C:\Users\Kayla\Desktop\ai-learning\projects\SINA_v3_Vampire\world_state_v3_backup.json"
output_dir = r"C:\Users\Kayla\Desktop\projects\SINA\worlds\hogwarts\config\characters"

with open(source_file, "r", encoding="utf-8") as f:
    data = json.load(f)

exclude_names = ["Alice", "Bob", "Charlie", "Dave", "Eve", "Grace"]
houses = ["Gryffindor", "Slytherin", "Ravenclaw", "Hufflepuff"]

for agent in data.get("agents", []):
    name = agent.get("name")
    if name in exclude_names:
        continue
    
    # 提取纯净的 trait，去掉被反射引擎污染的 [Deep Realization: ...]
    raw_traits = agent.get("traits", "")
    clean_traits = re.split(r'\[Deep Realization:|\[You owe', raw_traits)[0].strip()
    
    # 构建霍格沃茨人设
    hogwarts_persona = {
        "name": name,
        "house": random.choice(houses),
        "blood_status": random.choice(["Pure-blood", "Half-blood", "Muggle-born"]),
        "personality_traits": [
            clean_traits
        ],
        "interests": ["Defense Against the Dark Arts" if "神父" in clean_traits or "吸血鬼" in clean_traits else "Potions"],
        "inventory": [
            "Wand",
            "A mysterious old book"
        ],
        "starting_location": "Great Hall"
    }
    
    # 写入文件
    safe_name = "".join(x for x in name if x.isalnum())
    if not safe_name: safe_name = "unknown"
    out_path = os.path.join(output_dir, f"{safe_name}.json")
    
    with open(out_path, "w", encoding="utf-8") as out_f:
        json.dump(hogwarts_persona, out_f, ensure_ascii=False, indent=2)

print(f"Migration complete. Extracted characters to {output_dir}")
