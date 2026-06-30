# SINA: Social Intelligence Network Architecture

**SINA** is not just an agentic framework; it is a computational crucible for sociological emergence. Designed from First Principles, SINA operates as a highly concurrent, fully decoupled directed acyclic graph (DAG) engine where LLM-driven agents interact within a mathematically strictly bound physical and economic topology. 

It rejects the fragile, linear `while True` loops of conventional agent simulations. Instead, it relies on asynchronous state machines, fine-grained spatial concurrency locks (Mutex), and a multi-layered tracing architecture to observe how hierarchical structures, alienation, and consensus protocols natively emerge from primitive neural actors.

## Architectural Axioms

1. **Absolute Engine-Config Decoupling (First Principles)**
   The core engine (`core/`) is a sterile, agnostic simulation vessel. It contains zero domain logic, zero string hardcoding, and zero narrative assumptions. All sociological, linguistic, and material realities are injected dynamically via world configurations (`worlds/`). The engine does not know if it is rendering the Paleolithic era or a Wizarding academy—it only computes vectors and rules.

2. **Asynchronous DAG State Machine (The Cognitive Loop)**
   Agent life-cycles are orchestrated as non-blocking DAGs. When an agent experiences cognitive delay (network latency during LLM reasoning), the orchestrator yields the execution thread. This allows massive parallel simulation (Stanford Smallville baseline scale) without thread-blocking deadlocks.

3. **Spatial & Material Concurrency (Fine-Grained Mutex)**
   Two agents reaching for the same `RAW_MEAT` in the same room at the exact same millisecond will trigger the spatial concurrency manager. SINA implements dynamic resource locks (`asyncio.Lock`) generated at runtime to strictly enforce physical scarcity and prevent dirty writes in the world state.

4. **Sociological Middleware (The Prompt Injector)**
   The belief system (Memes) and identity constraints (Traits/Intentions) are decoupled into a dedicated `prompt.json`. This acts as a middleware that maps abstract LLM tensors into specific cultural syntaxes, ensuring that agent dialogue and reasoning remain structurally sound and culturally isolated.

## The Objective
SINA was built to investigate a singular thesis: If we constrain neural agents with absolute physical scarcity (Hunger, Hazards) and grant them unrestricted cognitive reflection, will they spontaneously invent the constructs of power, class, and exploitation?

This is not a toy sandbox. It is an infrastructure for generative sociology.

---
*Created by Kayla - Systems Architect & AI Sociologist*
