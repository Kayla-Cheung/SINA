import asyncio

vampire_health = 100

# ================================
# 核心引入：这就是那把著名的“并发锁”
# ================================
health_lock = asyncio.Lock()

async def attack_with_lock(agent_name: str, damage: int):
    global vampire_health
    
    # 【1. 抢占排他权】
    # 任何 Agent 想要修改血量，必须先在门口拿到这把锁。
    # 如果锁在别人手里，它就会被强制挂起等待，直到前一个人完事。
    async with health_lock:
        print(f"[{agent_name}] 拿到了锁！当前读取血量为: {vampire_health}")
        
        # 同样模拟 0.1 秒的底层 I/O 延迟
        temp_health = vampire_health
        await asyncio.sleep(0.1) 
        
        # 安全地写回内存
        vampire_health = temp_health - damage
        print(f"[{agent_name}] 攻击结算完成！覆盖写入血量为: {vampire_health}")
        
        # 离开 with 代码块时，锁会自动归还给系统

async def main():
    print("====================================")
    print(" 实验 2: 锁机制（Mutex）的绝对统治力")
    print("====================================\n")
    
    global vampire_health
    vampire_health = 100
    print(f"初始血量: {vampire_health}\n")
    
    # 两个 Agent 再次在同一时刻发起攻击
    await asyncio.gather(
        attack_with_lock("Agent_A (物理攻击)", 10),
        attack_with_lock("Agent_B (魔法攻击)", 20)
    )
    
    print(f"\n[系统结算] 最终血量: {vampire_health} (完美的 70！)\n")

if __name__ == "__main__":
    asyncio.run(main())
