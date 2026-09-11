---
type: dashboard
tick: 5
clock: "2026-01-01 09:15"
tags: [dashboard, ssot_root]
---

# 🌍 SINA: 模拟世界宏观战情中枢 (World Dashboard)

| 指标项 | 状态与数值 |
| :--- | :--- |
| **仿真步数 (Tick)** | `Tick 5` |
| **世界时间** | `2026-01-01 09:15` (🌸 春季 (Spring)) |
| **人口生态** | 🟢 存活 `5` | 🟡 昏迷 `0` | 🔴 死亡 `0` |
| **空间节点数** | `5` 个房间 |

## 👥 智能体花名册 (Roster)
- [[Agents/Alpha_Leader]] (`动身前往 Dark_Cave`)
- [[Agents/Beta_Hunter]] (`弯腰采集地上的新鲜浆果`)
- [[Agents/Gamma_Scholar]] (`弯腰采集地上的新鲜浆果`)
- [[Agents/Delta_Survivor]] (`举手赞同首领的篝火提案`)
- [[Agents/Epsilon_Rebel]] (`弯腰采集地上的新鲜浆果`)

## 🏛️ 空间拓扑 (Spatial Grid)
- [[Rooms/Open_Plains]] (在场: 0人)
- [[Rooms/Dark_Cave]] (在场: 1人)
- [[Rooms/Dense_Forest]] (在场: 3人)
- [[Rooms/Riverbank]] (在场: 0人)
- [[Rooms/Hilltop]] (在场: 1人)

## 💡 Obsidian 星图操作指引 (Star Map Guide)
1. **快捷键 `Ctrl + G` (或 `Cmd + G`)**：打开全局星图（Global Graph）；
2. **颜色分组已就绪**：
   - 🟢 **绿色**：`#agent` 智能体
   - 🔵 **蓝色**：`#room` 空间节点
   - 🟣 **紫色**：`#memory` 情景记忆
   - 🔴 **红色**：`#event` 历史事件
   - 🟡 **黄色**：`#item` 物质资源
3. **局部心智透视**：点开任意 `Agents/xxx.md`，右侧开启 **Local Graph**，深度设为 `2`，实时透视其人际圈与记忆网络。
