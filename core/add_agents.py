import json

new_agents = [
    {
        'name': 'Judy',
        'traits': '极强的正义感、维护规则、小镇治安官',
        'intentions': ['巡视街道', '维持秩序'],
        'current_action': '刚从一场大梦中醒来',
        'action_end_time': None,
        'known_nearby': [],
        'memory_stream': [],
        'pending_events': [],
        'importance_accumulator': 1,
        'hunger': 30,
        'inventory': {},
        'is_dead': False,
        'is_comatose': False,
        'last_room': 'Supermarket',
        'status': 'idle'
    },
    {
        'name': 'Arthur',
        'traits': '绝对理智、铁面无私、负责审判和调解纠纷的法官',
        'intentions': ['查阅法律条文', '等待处理案件'],
        'current_action': '刚从一场大梦中醒来',
        'action_end_time': None,
        'known_nearby': [],
        'memory_stream': [],
        'pending_events': [],
        'importance_accumulator': 1,
        'hunger': 30,
        'inventory': {},
        'is_dead': False,
        'is_comatose': False,
        'last_room': 'Cafe',
        'status': 'idle'
    },
    {
        'name': 'Lewis',
        'traits': '掌控欲强、富有野心、负责小镇统筹的市长',
        'intentions': ['规划小镇未来', '发表演讲'],
        'current_action': '刚从一场大梦中醒来',
        'action_end_time': None,
        'known_nearby': [],
        'memory_stream': [],
        'pending_events': [],
        'importance_accumulator': 1,
        'hunger': 30,
        'inventory': {},
        'is_dead': False,
        'is_comatose': False,
        'last_room': 'Town_Square',
        'status': 'idle'
    },
    {
        'name': 'Leo',
        'traits': '狡猾、生存能力强、反叛的无政府主义流浪汉',
        'intentions': ['寻找食物', '制造混乱'],
        'current_action': '刚从一场大梦中醒来',
        'action_end_time': None,
        'known_nearby': [],
        'memory_stream': [],
        'pending_events': [],
        'importance_accumulator': 1,
        'hunger': 30,
        'inventory': {},
        'is_dead': False,
        'is_comatose': False,
        'last_room': 'Dense_Forest',
        'status': 'idle'
    }
]

with open('core/world_state_v3_backup.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# avoid duplicates
existing_names = [a['name'] for a in data['agents']]
for ag in new_agents:
    if ag['name'] not in existing_names:
        data['agents'].append(ag)

with open('core/world_state_v3_backup.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Added 4 new agents successfully.')
