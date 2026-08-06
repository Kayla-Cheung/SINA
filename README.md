# SINA Framework (Society Inspired Neural Architecture)

SINA is a data-driven, highly abstracted Multi-Agent Sandbox Engine built for simulating complex sociological and physical interactions. It separates the **Simulation Engine (Core)** from the **World Configuration (Data)**, allowing you to plug in your own worlds, characters, and rules without modifying the underlying physics or cognitive loops.

## 🏗 Architecture (Engine-Config Decoupling)

SINA is designed strictly with a dual-layer architecture:
- **`core/`**: The immutable physics and cognitive engine (DAG execution, Memory, Parallax Shield).
- **`worlds/`**: The data layer. This is where you inject your specific IPs, character prompts, and environment states.

## 🚀 Quick Start

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/your-username/SINA.git
cd SINA
pip install -r requirements.txt
```

### 2. Environment Variables
Copy the `.env.example` file to create your local `.env`:
```bash
cp .env.example .env
```
Fill in your `DEEPSEEK_API_KEY` or other LLM keys inside `.env`.

### 3. Create Your World
Do **not** modify files in `core/`. Instead, build your world in the `worlds/` directory.
1. Copy the `worlds/template/` directory to create a new world (e.g., `worlds/my_world/`).
2. Define your agents, social rules, and map in the config JSON files inside your new world directory.

### 4. Run the Simulation
Execute the main engine and point it to your world:
```bash
python core/main_simulation.py --world worlds/my_world
```

## 🧠 Core Systems

- **DAG Engine**: Replaces traditional `while True` loops with a Directed Acyclic Graph state machine for concurrent, lock-safe agent actions.
- **Parallax Shield**: An underlying interceptor network that guarantees safe boundaries and physics constraints within the sandbox.
- **Laplace Oracle**: Evaluates global states and injects macro-level sociological events into the simulation.

## 📜 License
MIT License. Feel free to fork and build your own simulated universes.
