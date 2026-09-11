"""
settlement_engine.py — SINA v4 物理结算引擎
============================================
负责串行结算所有智能体的行动意图。
核心修改：重构时序逻辑。阶段 A（获取）-> 阶段 B（加工）-> 阶段 C（消耗）-> 阶段 D（社交与移动）
允许智能体在同一个 Tick 内完成“捡拾 + 进食”的连贯动作。
"""

from datetime import datetime

try:
    from .agent_state import AgentState
    from .physics_engine import PhysicsEngine
    from .environment import SandboxEnvironment
except ImportError:
    from agent_state import AgentState
    from physics_engine import PhysicsEngine
    from environment import SandboxEnvironment

async def store_observation(agent: AgentState, text: str, clock: datetime):
    """将观察写入记忆流并增加重要性"""
    agent.memory_stream.append({
        "time": clock.strftime("%H:%M"),
        "text": text,
        "importance": 1
    })
    agent.importance_accumulator += 1

async def settle_all_intents(
    intents: list,
    world_agents: dict,
    physics,
    environment,
    clock: datetime,
    is_night: bool,
    active_proposal: list = None,
) -> list[str]:
    logs = []
    time_str = clock.strftime("%H:%M")

    # 按优先级排序：攻击(0) > 进食(1) > 制造(2) > 移动(3) > 其他(4)
    # 虽然这里有优先级排序，但每个 agent 的复合动作会在同一次循环中被顺序处理
    sorted_intents = sorted(intents, key=lambda i: i.priority)

    for intent in sorted_intents:
        agent_name = intent.agent_name
        action = intent.raw_action
        agent = world_agents.get(agent_name)

        if not agent or agent.is_dead or agent.is_comatose:
            continue

        # 基础代谢
        agent.hunger -= 1

        current_node = environment.agent_locations.get(agent_name)
        if not current_node:
            continue

        feedback_events = []

        # ────────────────────────────────────
        # 1. 战斗结算 (抢夺资源)
        # ────────────────────────────────────
        target_name = action.get("attack_target")
        if target_name and target_name in current_node.agents and target_name != agent_name:
            target_agent = world_agents.get(target_name)
            if target_agent and not target_agent.is_dead:
                combat_res = physics.resolve_combat(agent, target_agent)
                winner = combat_res["winner"]
                loser = combat_res["loser"]
                loot = combat_res["loot_transferred"]
                
                target_agent.hunger = max(0, target_agent.hunger - combat_res["loser_hunger_penalty"])
                
                if winner == agent_name:
                    desc = f"你击败了 {target_name}，抢到了 {loot if loot else '空气'}。"
                    t_desc = f"【遭到攻击】你被 {agent_name} 击败，失去了 {loot if loot else '什么也没失去'}，且受了重伤（饥饿大降）！"
                else:
                    desc = f"你试图攻击 {target_name} 却被反杀，失去了 {loot if loot else '尊严'}，受了重伤（饥饿大降）！"
                    t_desc = f"【遭到攻击】{agent_name} 试图攻击你，但被你击退并抢走了 {loot if loot else '空气'}。"
                    agent.hunger = max(0, agent.hunger - combat_res["loser_hunger_penalty"])

                feedback_events.append(f"[物理现实] {desc}")
                target_agent.pending_events.append(t_desc)
                logs.append(f"  [战斗] {agent_name} 攻击了 {target_name}，胜者: {winner}")

        # ────────────────────────────────────
        # 2. 夜间危险结算
        # ────────────────────────────────────
        if is_night:
            has_fire = agent.inventory.get("TORCH", 0) > 0
            hazard_res = physics.resolve_night_hazard(agent, current_node.name, has_fire)
            if hazard_res.get("attacked"):
                agent.hunger = max(0, agent.hunger - hazard_res.get("damage", 3))
                feedback_events.append(f"[物理现实] {hazard_res.get('description')}")
                logs.append(f"  [夜间危险] {agent_name} 被野兽袭击！")

        # ────────────────────────────────────
        # 3. 拾取物品（阶段 A）
        # ────────────────────────────────────
        take_tag = action.get("take_item_tag")
        if take_tag:
            if current_node.inventory.get(take_tag, 0) > 0:
                current_node.inventory[take_tag] -= 1
                if current_node.inventory[take_tag] <= 0:
                    del current_node.inventory[take_tag]
                agent.inventory[take_tag] = agent.inventory.get(take_tag, 0) + 1
                feedback_events.append(f"[物理现实] 你从地上捡起了一份 {take_tag}。")
                logs.append(f"  [拾取] {agent_name} 在 {current_node.name} 捡起了 {take_tag}。")
            else:
                feedback_events.append(f"[物理现实] 你想捡 {take_tag}，但这里没有。")

        # ────────────────────────────────────
        # 4. 劳动生产物品（阶段 A，消耗 1 饥饿度）
        # ────────────────────────────────────
        produce_tag = action.get("produce_item_tag")
        if produce_tag:
            agent.hunger -= 1
            agent.inventory[produce_tag] = agent.inventory.get(produce_tag, 0) + 1
            feedback_events.append(f"[物理现实] 你消耗体力，从环境中获取了一份 {produce_tag}。")
            logs.append(f"  [生产] {agent_name} 消耗体力生产了 {produce_tag}。")

        # ────────────────────────────────────
        # 5. 合成/制造结算（阶段 B）
        # ────────────────────────────────────
        craft_recipe = action.get("craft")
        if craft_recipe:
            craft_result = physics.resolve_craft(agent, craft_recipe)
            if craft_result.get("success"):
                produced = craft_result.get("produced", {})
                feedback_events.append(f"[物理现实] 你成功制作出了 {produced}！")
                logs.append(f"  [制造成功] {agent_name} 制作了 {produced}。")
            else:
                reason = craft_result.get("reason", "未知原因")
                feedback_events.append(f"[物理现实] 你尝试制作 {craft_recipe}，但失败了：{reason}")
                logs.append(f"  [制造失败] {agent_name} 制作 {craft_recipe} 失败: {reason}")

        # ────────────────────────────────────
        # 6. 进食结算（阶段 C）
        # ────────────────────────────────────
        eat_item = action.get("eat_item")
        if eat_item:
            if agent.inventory.get(eat_item, 0) > 0:
                agent.inventory[eat_item] -= 1
                if agent.inventory[eat_item] <= 0:
                    del agent.inventory[eat_item]

                eat_result = physics.resolve_eat(agent, eat_item)
                restored = eat_result.get("hunger_restored", 0)
                agent.hunger = min(30, agent.hunger + restored)

                if restored == 0:
                    feedback_events.append(f"[物理现实] 你把 {eat_item} 塞进嘴里咀嚼，但毫无营养。")
                    logs.append(f"  [进食无效] {agent_name} 吃了 {eat_item}。")
                else:
                    feedback_events.append(f"[物理现实] 你吃下了 {eat_item}，恢复了 {restored} 点饥饿值。")
                    logs.append(f"  [进食] {agent_name} 吃了 {eat_item}，恢复 {restored} 饥饿值。")

                if eat_result.get("side_effect") == "disease":
                    disease_penalty = eat_result.get("hunger_penalty", -2)
                    agent.hunger = max(0, agent.hunger + disease_penalty)
                    feedback_events.append(f"[物理现实] {eat_result.get('disease_description')}")
                    logs.append(f"  [疾病] {agent_name} 因吃 {eat_item} 感染疾病！")
            else:
                feedback_events.append(f"[物理现实] 你想吃 {eat_item}，但手上并没有。")

        # ────────────────────────────────────
        # 7. 赠送物品（阶段 D）
        # ────────────────────────────────────
        give_data = action.get("give_item")
        if give_data and isinstance(give_data, dict):
            t_tag = give_data.get("tag")
            t_target = give_data.get("target")
            if t_tag and t_target:
                if agent.inventory.get(t_tag, 0) > 0 and t_target in current_node.agents:
                    target_state = world_agents.get(t_target)
                    if target_state:
                        agent.inventory[t_tag] -= 1
                        if agent.inventory[t_tag] <= 0:
                            del agent.inventory[t_tag]
                        target_state.inventory[t_tag] = target_state.inventory.get(t_tag, 0) + 1

                        mat_props = physics.material_properties.get(t_tag, {})
                        if getattr(target_state, 'is_comatose', False) and mat_props.get("nutrition", 0) > 0:
                            target_state.is_comatose = False
                            target_state.hunger = 5
                            feedback_events.append(f"[物理现实] 你喂食救醒了昏迷的 {t_target}！")
                            target_state.pending_events.append(f"【救命之恩】{agent_name} 救醒了你！")
                            target_state.traits += f" [你欠 {agent_name} 一条命。]"
                            logs.append(f"  [救活] {agent_name} 救活了 {t_target}！")
                        else:
                            feedback_events.append(f"[物理现实] 你把 {t_tag} 递给了 {t_target}。")
                            target_state.pending_events.append(f"{agent_name} 递给了你一份 {t_tag}。")
                            logs.append(f"  [交易] {agent_name} 给了 {t_target} 一份 {t_tag}。")
                else:
                    feedback_events.append(f"[物理现实] 赠送失败，对方不在或你没有 {t_tag}。")

        # ────────────────────────────────────
        # 8. 放下物品（阶段 D）
        # ────────────────────────────────────
        drop_tag = action.get("drop_item_tag")
        if drop_tag:
            if agent.inventory.get(drop_tag, 0) > 0:
                agent.inventory[drop_tag] -= 1
                if agent.inventory[drop_tag] <= 0:
                    del agent.inventory[drop_tag]
                current_node.inventory[drop_tag] = current_node.inventory.get(drop_tag, 0) + 1
                feedback_events.append(f"[物理现实] 你放下了 {drop_tag}。")
                logs.append(f"  [放下] {agent_name} 放下了 {drop_tag}。")

        # ────────────────────────────────────
        # 8.5. 蓝图提案与投票结算 (Social & Law)
        # ────────────────────────────────────
        propose_bp = action.get("propose_blueprint")
        if propose_bp and active_proposal is not None:
            if active_proposal[0] is None:
                try:
                    from .action_intent import Proposal
                except ImportError:
                    from action_intent import Proposal
                active_proposal[0] = Proposal(agent_name, propose_bp)
                feedback_events.append(f"[提案发布] 你成功发起了新提案: '{propose_bp}'。")
                logs.append(f"  [提案发起] {agent_name} 提出了提案: '{propose_bp}'")
                for a_name, a_obj in world_agents.items():
                    if a_name != agent_name and not a_obj.is_dead and not a_obj.is_comatose:
                        a_obj.pending_events.append(
                            f"【新提案提醒】{agent_name} 发起了提案：「{propose_bp}」，请在下一轮考虑投票！"
                        )
            else:
                feedback_events.append(f"[提案冲突] 当前已有活跃提案正在审议中，无法重复发起。")

        vote_bp = action.get("vote_on_blueprint")
        if vote_bp and active_proposal is not None and active_proposal[0] is not None:
            active_proposal[0].votes[agent_name] = vote_bp
            feedback_events.append(f"[投票记录] 你对提案投了: {vote_bp}")
            logs.append(f"  [提案投票] {agent_name} 投票: {vote_bp}")

        # ────────────────────────────────────
        # 9. 社交广播 & 内心想法
        # ────────────────────────────────────
        observable = action.get("observable_action", "")
        if observable:
            for other_name in current_node.agents:
                if other_name != agent_name and other_name in world_agents:
                    world_agents[other_name].pending_events.append(f"{agent_name} 刚刚做了: {observable}")

        internal = action.get("internal_thought", "")
        if observable:
            logs.append(f"  [{agent_name}] 内心: {internal[:80]}")
            logs.append(f"  [{agent_name}] 行为: {observable[:80]}")

        # ────────────────────────────
        # 9.5. 记忆管理算子 (Memory Operations)
        # ────────────────────────────
        search_memory = action.get("search_memory")
        if search_memory:
            # 简单的局部匹配，模拟 Retrieval Engine 介入
            matches = [mem["text"] for mem in agent.memory_stream if search_memory.lower() in mem["text"].lower()]
            if matches:
                feedback_events.append(f"[记忆检索成功] 关于'{search_memory}'的最相关记忆: {matches[-1]}")
                logs.append(f"  [记忆检索] {agent_name} 成功回忆起了关于 '{search_memory}' 的信息。")
            else:
                feedback_events.append(f"[记忆检索失败] 脑海中没有关于 '{search_memory}' 的相关记忆。")
                logs.append(f"  [记忆检索] {agent_name} 试图回忆 '{search_memory}'，但失败了。")

        discard_thought = action.get("discard_memory_thought")
        if discard_thought:
            feedback_events.append(f"[精神净化] 成功将执念 '{discard_thought}' 抛于脑后。")
            logs.append(f"  [精神净化] {agent_name} 抛弃了执念: {discard_thought}")

        # ────────────────────────────────────
        # 10. 移动
        # ────────────────────────────────────
        move_to = action.get("move_to")
        if move_to:
            dest = environment.get_node_by_name(move_to)
            if dest and dest != current_node:
                if dest.locked_by and dest.locked_by != agent_name:
                    feedback_events.append(f"[物理现实] 你想去 {move_to}，但被 {dest.locked_by} 封锁了。")
                else:
                    environment.move_agent(agent_name, dest)
                    logs.append(f"  [移动] {agent_name} 移动到 {dest.name}")

        # ────────────────────────────────────
        # 11. 写入记忆
        # ────────────────────────────────────
        memory_text = f"行为: {observable}"
        if internal:
            memory_text += f" | 内心: {internal}"
        await store_observation(agent, memory_text, clock)

        for event in feedback_events:
            await store_observation(agent, event, clock)

    return logs
