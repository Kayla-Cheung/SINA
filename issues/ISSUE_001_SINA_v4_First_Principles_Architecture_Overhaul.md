# [RFC #001] SINA v4: First-Principles Transition from Flat Utopian Sandbox to Structured Sociological Dynamical System

- **Author**: Kayla Cheung (Lead Systems Architect)
- **Date**: 2026-09-09
- **Target Version**: `SINA v4.0.0-alpha`
- **Status**: Proposed / Ready for Sprint

---

## 1. 第一性原理公理体系 (First-Principles Axioms)

SINA（Sociological Integration of Neural Architectures）的核心命题，是通过机制设计在多智能体系统中演化出**非扁平的、具有物理摩擦力与阶级张力的真实人类社会行为（如欺诈、联盟、攀比、阶层固化与悲剧宿命）**。

从第一性原理出发，真实人类社会系统的演化受制于以下 4 大不可违背的物理与认知公理：

| 公理编号 | 第一性原理公理 (Axiom) | 物理/数学定义 | 对 SINA 的系统约束 |
| :--- | :--- | :--- | :--- |
| **Axiom 1** | **认知局部性与信息光锥 (Cognitive Locality)** | 任何单体观察者无法拥有全局视界，观测受限于物理空间与通信介质。 | **严禁全局广播**；信息必须通过空间网格与人际拓扑逐级衰减与遮挡。 |
| **Axiom 2** | **算力与资源稀缺性 (Resource Scarcity)** | 维持高分辨率记忆与精准推理需要消耗物理能量（Token / 货币）。 | **阶级与算力绑定**；贫困 Agent 必须经历物理级记忆衰退与被迫脑补（Confabulation）。 |
| **Axiom 3** | **非平衡态与反死锁性 (Anti-Stagnation)** | 封闭 Multi-Agent 系统在无外界扰动下必然坍塌为同质化回音室（$H(W) \to 0$）。 | **动态温度注入**；系统必须实时监控思维信息熵并自动注入随机性打破死锁。 |
| **Axiom 4** | **分层记忆连续性 (Hierarchical Memory)** | 工作记忆容量有限，连续经验必须经过分叉、去重与概念沉淀。 | **双层记忆分叉**；工作上下文 $S_t$ 超限时必须自动压缩沉淀至长期向量库。 |

---

## 2. 现有 SINA (v1~v3) 的结构性硬伤分析

对照上述公理，当前 SINA 实现（参考 Smallville / Sotopia 范式）存在 4 大致命的架构反模式：

### ❌ 硬伤 1：线性记忆流导致的算力爆炸与均质化 (Linear Stream Fallacy)
* **现状**：所有 Agent 维护一条未经分叉的线性文本列表，检索时全量计算 Recency / Importance / Relevance。
* **物理破绽**：违背 Axiom 4。运行 100 个 Tick 后 Context Window 迅速打满，无法区分“即时感知工作流”、“长期情景记忆”与“固有核心自我”。

### ❌ 硬伤 2：被动 BIBO 与同质化回音室死锁 (BIBO & Stagnation)
* **现状**：Agent 纯靠环境事件被动驱动（Bounded-Input Bounded-Output），缺乏内在自发运转节律。
* **物理破绽**：违背 Axiom 3。Agent 之间多轮交互后迅速陷入复读与社交谄媚（Sycophancy），社会演化停止。

### ❌ 硬伤 3：无物理遮挡的空间信息泄漏 ($O(N^2)$ Leakage)
* **现状**：环境事件以近乎全局广播的形式下发给所有 Agent。
* **物理破绽**：违背 Axiom 1。贾府里的丫鬟能“瞬间感知”贾母正房里的私密密谋，信息不对称彻底失效，导致权力机制无法生效。

### ❌ 硬伤 4：群体全量调用导致的吞吐崩溃 (Swarm Compute Blowout)
* **现状**：每一个 Tick 对所有 Agent 执行全量 LLM 推理。
* **物理破绽**：违背 Axiom 2。50 个 Agent 运行 10 轮需要数千次 API 调用，延迟过高且无法用于严肃的数字化文学沙盒推演。

---

## 3. SINA v4 四大重构支柱 (Core Architectural Overhaul)

```mermaid
graph TD
    subgraph SINA v4 Engine Architecture
        Spatial[Layer 1-3 Hierarchical Spatial Graph<br/>Spatial Grid Hash & Occlusion] -->|Local Visible Events| Engine[GWA Cognitive Tick Engine<br/>4-Phase FSM]
        
        Engine --> Spotlight[Spotlight Attention Node]
        Spotlight --> MemSys[Hierarchical Memory Subsystem]
        
        subgraph MemSys [Memory Hierarchy & Class Gating]
            Pself[Invariant State P_Self]
            STM[Working Context St<br/>Cap: theta]
            LTM[Episodic Vector Store]
            Bifurcate[Bifurcation Manager<br/>Class-Gated Memory Decay]
        end
        
        MemSys --> Gen[Candidate Generator Swarm]
        Gen --> Entropy[Critic & Entropy Monitor<br/>H_W Tracking]
        Entropy -->|T_gen = T_base + alpha*exp(-beta*H)| Arbitrator[Metacognitive Arbitrator]
        Arbitrator --> Broadcast[Local Broadcast & Actuator]
        Broadcast --> Spatial
    end
```

### 支柱 1：基于 GWT 的离散认知周期内核 (`sina.kernel.tick`)
* **4 阶段同步状态机**：
  1. `Perceive & Retrieve`：从局部空间网格拉取事件，通过 Attention Node 检索 RAG 与 $P_{\text{Self}}$，拼装为 $S_t = STM_t \cup INPUT_t \cup RAG_t \cup P_{\text{Self}}$。
  2. `Think`：生成多条候选动作/思维假设。
  3. `Arbitrate`：Critic 计算多样性熵 $H(W)$，若 $H(W) < \epsilon$ 则自适应拉高生成温度 $T_{\text{gen}}$ 强制注入激进扰动；Metacognitive 节点仲裁出获胜思维 $W_t$。
  4. `Update & Broadcast`：更新本地状态并向局部可见半径广播动作。
* **分级算力门控 (Gated Multi-Rate)**：仅对处于聚光灯下（遭遇冲突/高惊讶度）的 Agent 运行全量 Tick，背景 Agent 降级为轻量 FSM。

---

### 支柱 2：双层记忆分叉与阶级衰减机制 (`sina.memory.bifurcation`)
* **动态阈值分叉**：
  * 工作记忆设置硬性 Token 上限 $\theta$。当 $STM_t > \theta$ 时，触发 `BifurcationManager`：
  * 将高频事件轨迹提炼为结构化摘要，写入 LTM 向量库；$STM_t$ 仅保留主观不变量 $P_{\text{Self}}$ 与滑动窗口。
* **阶级算力剥夺与虚假记忆脑补 (Class-Gated Confabulation)**：
  * 引入 `Token_Budget`（财富）与 `Power_Index`（权力）；
  * **高阶级 Agent**：拥有充足预算维护高维高精度 LTM 检索；
  * **底层贫困 Agent**：LTM 向量强制引入时间衰减与随机掩码；在 Reflection 阶段由于上下文缺失，被迫诱导大模型产生**自我合理化的虚假记忆（False Consciousness）**。

---

### 支柱 3：三层拓扑空间图与物理信息遮挡 (`sina.spatial.topology`)
* **层级图模型**：
  * `Layer 1: Macro Zone`（如：荣国府大院）
  * `Layer 2: Venue / Room`（如：怡红院、荣禧堂、账房）
  * `Layer 3: Affordance Entity`（如：账本、茶几、药碗）
* **物理隔离**：基于 **Spatial Grid Hash**，事件传播半径严格限制在 Layer 2 单个房间内。跨房间信息传播必须由 Agent 物理移动并口头转述，天然形成信息不对称与传播失真。

---

### 支柱 4：角色聚类与主观不变量注入 (`sina.cognition.persona`)
* **Persona Archetypes**：
  * 将群内数十个角色聚类为若干核心心理学原型（如：专断权威型、依附生存型、反叛虚无型），共享微调权重或基座系统提示词。
* **硬件级不变量注入 (Hardware Invariant Injection)**：
  * 每个单体的独特灵魂由 $P_{\text{Self}}$（核心执念、生理状态、阶级烙印）在每一个 Tick 中以物理不可篡改的形式注入上下文头部。

---

## 4. 实施排期与任务分解 (Actionable Roadmap)

- [ ] **Phase 1: 认知内核 (`sina/kernel/tick.py`)**
  - 实现 `CognitiveTickEngine` 4-Phase 同步循环。
  - 实现香农信息熵计算器与自适应温度调节器 $T_{\text{gen}} = T_{\text{base}} + \alpha e^{-\beta H(W)}$。
- [ ] **Phase 2: 记忆分叉与衰减器 (`sina/memory/bifurcation.py`)**
  - 实现 $\theta$ 阈值监控与双层状态分叉。
  - 实现基于阶级/财富权重的记忆降采样与遗忘算子。
- [ ] **Phase 3: 拓扑空间与信息遮挡 (`sina/spatial/topology.py`)**
  - 实现三层空间层级图与局部空间哈希广播。
- [ ] **Phase 4: 红楼梦/贾府危机闭环沙盒 (`sandboxes/jia_mansion_v4.py`)**
  - 挂载王熙凤（账房危机）、探春（改革阻力）、元春（失宠种子）配置，实测非平衡态悲剧演化。

---

## 5. 验收标准 (Acceptance Criteria)
1. **抗同质化测试**：连续运行 50 个 Tick，系统信息熵 $H(W)$ 维持在安全区间，无死循环复读。
2. **信息隔离测试**：房间 A 内发生的刺杀/密谋事件，位于房间 B 的 Agent 在未经物理转述前检索召回率为绝对 $0.0\%$。
3. **记忆分叉稳定性**：长时间运行下，单体单步 Token 开销严格有界（$< \theta + 500$ tokens）。
