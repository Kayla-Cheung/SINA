import json
import os
import re

state_file = "world_state_v3_backup.json"
out_file = "world_state_v4_party.json"

if os.path.exists(state_file):
    with open(state_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    for agent in data.get('agents', []):
        # 真正清空记忆流
        agent['memory_stream'] = []
        # 清空物品栏
        agent['inventory'] = []
        # 恢复体力
        agent['hunger'] = 30
        agent['status'] = 'idle'
        agent['action_end_time'] = None
        agent['current_action'] = "刚从一场大梦中醒来"
        
        # 清理由于反思引擎追加到 traits 里的 [Deep Realization: ...] 噪音
        if 'traits' in agent:
            clean_traits = re.sub(r'\[Deep Realization:.*?\]', '', agent['traits']).strip()
            # 清理可能存在的 You owe your life to
            clean_traits = re.sub(r'\[You owe your life to.*?\]', '', clean_traits).strip()
            agent['traits'] = clean_traits
        
    data['tick_count'] = 0
    data['clock'] = "2026-06-24T08:00:00"
    
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("Done")
