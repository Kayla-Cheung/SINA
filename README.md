# SINA (Sociological & Introspective Neural Architecture)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%20%7C%20Vite-61DAFB.svg?logo=react&logoColor=white)](https://react.dev/)

> **Status**: SINA v4 (Public Core Engine Infrastructure)  
> **Architecture**: Distributed Multi-Agent System · DAG Execution Pipeline · 4-Tier Hierarchical Memory · Concurrency Settlement Lock

SINA is an open-source, industrial-grade multi-agent sociological simulation engine. Rather than treating multi-agent systems (MAS) as naive prompt chains or monolithic chat wrappers, SINA models simulated societies as **distributed systems under physical and computational constraints**.

---

## 🏛️ First-Principles Axioms

SINA is constructed upon four non-negotiable physical and sociological axioms:

| Axiom | Principle | Computational Definition | SINA System Invariant |
| :--- | :--- | :--- | :--- |
| **Axiom 1** | **Cognitive Locality** | Observers have finite light-cones; no global broadcast exists in reality. | **Spatial Topology Isolation**: Events propagate strictly through local graph nodes. Cross-room leakage is strictly $0.0\%$. |
| **Axiom 2** | **Resource Scarcity** | High-fidelity cognitive maintenance requires physical energy and capital. | **Class-Gated Memory Fidelity**: Impoverished agents experience memory decay, retrieval dropout, and forced confabulation. |
| **Axiom 3** | **Anti-Stagnation** | Closed multi-agent loops inevitably collapse into sycophantic echo chambers ($H(W) \to 0$). | **Entropy & Temperature Modulation**: Real-time cognitive entropy tracking injects adaptive perturbations. |
| **Axiom 4** | **Hierarchical Memory** | Working memory context is strictly bounded ($O(1)$ upper bound per tick). | **Dual-Layer Bifurcation**: Automatic compaction and sinking from working context ($S_t$) to episodic vector storage. |

---

## 📐 System Architecture

```mermaid
graph TD
    subgraph SINA Subsystem Topology
        Env[Spatial Grid & Environment Substrate] -->|Local Visible Events| Gateway[Gateway / DAG Pipeline]
        
        Gateway --> ParallelThink[AgentThinkNode Swarm<br/>asyncio.gather]
        ParallelThink --> GodAgent[GodAgent / Translation Mesh<br/>Pydantic Structured Contracts]
        GodAgent --> PhysicsLock[Physics Settle Lock<br/>Resource Race Resolution]
        PhysicsLock --> Env

        subgraph Hierarchical Memory Subsystem [sina.memory]
            P_Self["Layer 0: P_Self Invariant Anchor<br/>(Immutable Persona / Class Index)"]
            Working["Layer 1: Working Context S_t<br/>(Sliding Window / θ Threshold)"]
            Bifurcate{"Bifurcation Manager<br/>Tokens(S_t) > θ ?"}
            Episodic["Layer 2: Episodic Vector Store<br/>(Contiguous NumPy BLAS Matrix)"]
            Decay["Class-Gated Decay Engine<br/>(Noise / Half-Life / Confabulation)"]
            
            P_Self --> Working
            Working --> Bifurcate
            Bifurcate -->|Compaction Sink| Episodic
            Episodic --> Decay
            Decay -->|RAG Recall| Working
        end

        ParallelThink <--> Hierarchical Memory Subsystem
        PhysicsLock -->|State Broadcast| WS[FastAPI WebSocket Stream]
        WS --> UI[React / Vite Observer Dashboard]
    end
```

---

## 🧠 Core Subsystems

### 1. Hierarchical Memory Subsystem (`sina.memory`)
* **Layer 0 (`PersonaInvariant`)**: Stack-allocated sentinel anchor preventing persona drift across thousands of simulation ticks.
* **Layer 1 (`BifurcationManager`)**: Real-time token budget monitoring. When $S_t > \theta$, historical slices are distilled and sunken into Layer 2, keeping working context bounded in $O(1)$ space.
* **Layer 2 (`EpisodicVectorStore`)**: Flat, contiguous 2D NumPy matrices executing batch cosine similarity via single-pass BLAS operations ($Q \cdot M^T$), with SQLite cold persistence.
* **Sociological Decay & Confabulation (`ClassGatedDecayEngine`)**: Wealthier agents retain crisp memory fidelity; lower-class agents experience exponential decay and generate rationalized false consciousness when memory gaps occur.

### 2. DAG Concurrency & Physical Settlement (`core/`)
* **Parallel Intention Generation**: Agents evaluate environmental stimuli asynchronously via `AgentThinkNode`.
* **Deterministic Physics Settlement**: Physical conflicts (e.g., competing for limited food or attacking) pass through `concurrency_lock.py` and `settlement_engine.py`, enforcing physical laws that subjective beliefs cannot override.

### 3. Spatial Topology & Frontend Observer (`frontend/`)
* Headless simulation state is streamed over WebSockets to a React + Tailwind + Vite observation dashboard with real-time map topology, memory inspectors, and chat logs.

---

## 🚀 Quickstart

### Prerequisites
* Python 3.11+
* Node.js 18+ (for frontend dashboard)

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/Kayla-Cheung/SINA.git
cd SINA

# Install backend dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env to supply your DEEPSEEK_API_KEY / OPENAI_API_KEY
```

### 2. Run Test Suite
```bash
# Verify SINA v4 Memory Hierarchy & Bifurcation engine
pytest sina/tests/ -v
```

### 3. Launch Simulation Server & Observer
```bash
# Terminal 1: Launch Backend Engine
cd core
python server.py

# Terminal 2: Launch Frontend Observer Dashboard
cd frontend
npm install
npm run dev
```

---

## 🔒 Security & Engine-Config Decoupling Notice

This repository contains the **Public Engine Infrastructure** only. In accordance with SINA's *Engine-Config Decoupling* architecture:
- Concrete literary/sociological scenarios (e.g., *Dream of the Red Chamber*, *Stanford Town*, private macro-economies) and specific hyperparameter configurations are kept in `.gitignore`'d private vaults.
- Core simulation primitives, memory state machines, and mathematical settlement engines are fully open-sourced under the MIT License.
