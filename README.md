# SINA (Sociological Integration of Neural Architectures)

> **Status**: Core Engine V3 (Public Infrastructure)
> **Architecture**: Directed Acyclic Graph (DAG) State Machine + Concurrency Settlement Lock

SINA is an industrial-grade, multi-agent sociological simulation engine. Unlike conventional LLM wrappers or naive prompt-chaining bots, SINA treats Multi-Agent Systems (MAS) as a distributed systems problem, solving race conditions and LLM context bloat through strict physical decoupling and DAG execution.

## Core Architectural Pillars

### 1. Engine-Config Decoupling (The Substrate)
SINA enforces a strict dual-layer architecture:
- **The Objective Layer (Physics Engine)**: Hardcoded in Python, determining invariable physical rules (e.g., metabolic rate, resource respawn, traversal distance). Belief cannot alter physics.
- **The Subjective Layer (Meme Pool)**: The cognitive substrate where agents harbor beliefs, share rumors, and debate logic.
*Note: Specific experimental configs (the "Economy of Minds" prompts and exploitation parameters) are strictly decoupled and stored in `.gitignore`'d private vaults to protect academic IP.*

### 2. DAG Concurrency & Settlement Engine
To simulate high-density social friction, SINA eschews naïve iterative loops in favor of a **DAG Operator Pipeline**:
- `AgentThinkNode`: Agents reason asynchronously and in parallel (`asyncio.gather`), emitting free-form probabilistic intents.
- `GodAgent Mesh`: A deterministic translation layer that coerces natural language intents into strict API topological interactions.
- `PhysicsSettleNode`: A centralized settlement lock that guarantees determinism. Multiple agents attempting to consume the same physical resource will trigger strict queue-based rejection, reflecting true economic friction.

### 3. Multi-Agent Memory Consolidation (Quantum Retrieval)
Memory in SINA is not a simple vector search. It implements a cognitive decay model (`Recency + Relevance + Importance`) coupled with a **Quantum Associative Noise (1d20)** algorithm. This perfectly simulates human biological randomness—critical successes yield *[Inspiration]*, while critical failures simulate *[Distraction]*, preventing LLMs from falling into deterministic behavior loops.

## Deployment (Stage 4 Data Aggregation)
SINA operates a headless DAG engine by default, streaming state topology via `FastAPI + WebSockets` to a decoupled React frontend for macroeconomic observation.

```bash
# Boot the backend DAG Engine & Socket Router
cd core
python server.py

# Boot the frontend topology observer
cd frontend
npm run dev
```

## Security & IP Notice
This repository contains the *Public Engine Infrastructure* only. Experimental prompt datasets and the `Wealth/Power` exploitation hyperparameters used for sociological benchmarks are held in private registries until formal publication.
