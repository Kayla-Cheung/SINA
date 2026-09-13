# -*- coding: utf-8 -*-
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dag_simulation import DAGSmallvilleSimulation as SmallvilleSimulation

app = FastAPI(title="SINA Stage 4 Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/config/llm")
async def get_llm_config():
    return {"success": True, "config": {"provider": "deepseek", "model": "deepseek-chat"}}

@app.get("/api/games/current")
async def get_current_game():
    global last_state_dump
    state = last_state_dump if 'last_state_dump' in globals() else {
        "game_id": "smallville", "frame": 0, "game_time": "12:00", "day": 1, "time_of_day": "noon",
        "map": {"name": "smallville", "locations": [], "edges": []}, "agents": [], "objects": [], "logs": []
    }
    return {"game_id": "smallville", "state": state}

@app.get("/api/games/{game_id}")
async def get_game(game_id: str):
    global last_state_dump
    return last_state_dump if 'last_state_dump' in globals() else {
        "game_id": game_id, "frame": 0, "game_time": "12:00", "day": 1, "time_of_day": "noon",
        "map": {"name": "smallville", "locations": [], "edges": []}, "agents": [], "objects": [], "logs": []
    }

@app.get("/api/saves")
async def get_saves():
    return []

@app.get("/api/templates/initial")
async def get_initial():
    return {
        "map": {"name": "smallville", "locations": [], "edges": []},
        "agents": [],
        "objects": []
    }


@app.post("/api/config/llm")
async def set_llm_config():
    return {"success": True}

@app.post("/api/games")
async def create_game():
    global last_state_dump
    state = last_state_dump if 'last_state_dump' in globals() else {"game_id": "smallville", "frame": 0, "game_time": "12:00", "day": 1, "time_of_day": "noon", "map": {"name": "smallville", "locations": [], "edges": []}, "agents": [], "objects": [], "logs": []}
    return {"game_id": "smallville", "state": state}

@app.post("/api/games/abandon")
async def abandon_game():
    return {"success": True}

@app.post("/api/saves/{game_id}/continue")
async def continue_save(game_id: str):
    global last_state_dump
    state = last_state_dump if 'last_state_dump' in globals() else {"game_id": game_id, "frame": 0, "game_time": "12:00", "day": 1, "time_of_day": "noon", "map": {"name": "smallville", "locations": [], "edges": []}, "agents": [], "objects": [], "logs": []}
    return {"game_id": game_id, "state": state}

@app.post("/api/saves/import")
async def import_save():
    global last_state_dump
    state = last_state_dump if 'last_state_dump' in globals() else {"game_id": "smallville", "frame": 0, "game_time": "12:00", "day": 1, "time_of_day": "noon", "map": {"name": "smallville", "locations": [], "edges": []}, "agents": [], "objects": [], "logs": []}
    return {"game_id": "smallville", "state": state}

@app.post("/api/saves/clear")
async def clear_saves():
    return {"success": True, "saves_deleted": 0, "memories_deleted": 0}

@app.post("/api/games/{game_id}/step")
async def step_game(game_id: str):
    global step_event
    if 'step_event' in globals():
        step_event.set()
    return {"success": True}

@app.get("/api/agents/{agent_id}/memories")
async def get_agent_memories(agent_id: str):
    global last_state_dump
    if 'last_state_dump' in globals():
        for a in last_state_dump.get("agents", []):
            if a["id"] == agent_id:
                return {
                    "agent_id": agent_id,
                    "short_term": a.get("short_term_memory", []),
                    "long_term": []
                }
    return {"agent_id": agent_id, "short_term": [], "long_term": []}

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()
sim_task = None

async def simulation_loop():

    sim = SmallvilleSimulation("smallville")

    agent_locations = {}
    for n in sim.environment.all_nodes():
        for agent_name in n.agents:
            agent_locations[agent_name] = n.name

    def map_agent(a):
        return {
            "id": a.name,
            "name": a.name,
            "persona": a.traits,
            "current_location": agent_locations.get(a.name, "Cafe"),
            "inventory": list(a.inventory.keys()),
            "status": a.current_action if a.current_action else "Idle",
            "short_term_memory": [{"timestamp": getattr(m, "timestamp", "00:00"), "content": m.get("content", str(m)) if isinstance(m, dict) else getattr(m, "content", str(m)), "is_reflection": False, "frame": getattr(m, "frame", 0)} for m in a.memory_stream[-5:]],
            "moving": False,
            "next_location": None
        }

    global last_state_dump
    last_state_dump = {
        "game_id": "smallville",
        "frame": 0,
        "game_time": sim.clock.isoformat(),
        "day": 1,
        "time_of_day": "noon",
        "map": {"name": "smallville", "locations": [{"id": n.name, "name": n.name, "description": ""} for n in sim.environment.all_nodes()], "edges": []},
        "agents": [map_agent(a) for a in sim.world_agents.values()],
        "objects": [],
        "logs": []
    }


    # 【手动单步执行模式】
    global step_event
    step_event = asyncio.Event()

    # 无限循环模拟引擎
    for tick in range(1, 100000):
        # 阻塞等待前端调用 /step 接口
        await step_event.wait()
        step_event.clear()

        await sim.run_dag_loop(1)

        # Extinction Event check
        all_comatose = len(sim.world_agents) > 0 and all(getattr(a, 'is_comatose', False) or getattr(a, 'is_dead', False) for a in sim.world_agents.values())
        if all_comatose:
            print("[SINA] Extinction Event detected. Rebooting simulation...")
            import subprocess
            subprocess.run(["python", "reset_memory.py"])
            sim = SmallvilleSimulation("smallville")

        # Assemble state dump
        agent_locations = {}
        for n in sim.environment.all_nodes():
            for agent_name in n.agents:
                agent_locations[agent_name] = n.name

        def map_agent(a, locations=agent_locations):
            return {
                "id": a.name,
                "name": a.name,
                "persona": a.traits,
                "current_location": locations.get(a.name, "Cafe"),
                "inventory": list(a.inventory.keys()),
                "status": a.current_action if a.current_action else "Idle",
                "short_term_memory": [{"timestamp": getattr(m, "timestamp", "00:00"), "content": m.get("content", str(m)) if isinstance(m, dict) else getattr(m, "content", str(m)), "is_reflection": False, "frame": getattr(m, "frame", 0)} for m in a.memory_stream[-5:]],
                "moving": False,
                "next_location": None
            }

        state_dump = {
            "game_id": "smallville",
            "frame": tick,
            "game_time": sim.clock.isoformat(),
            "day": 1,
            "time_of_day": "noon",
            "map": {"name": "smallville", "locations": [{"id": n.name, "name": n.name, "description": ""} for n in sim.environment.all_nodes()], "edges": []},
            "agents": [map_agent(a) for a in sim.world_agents.values()],
            "objects": [],
            "logs": [{
                "frame": tick,
                "game_time": sim.clock.isoformat(),
                "events": getattr(sim, 'current_logs', [])
            }]
        }
        last_state_dump = state_dump
        await manager.broadcast(json.dumps({"type": "frame_update", "data": state_dump}))

        # 寮哄埗浼戠湢锛岃祴浜堝墠绔覆鏌撴椂闂达紝骞跺帇鍒?Token 鐖嗙偢
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    global sim_task, last_state_dump

    # 寮哄埗鍦ㄦ帴鍙椾换浣?HTTP 璇锋眰鍓嶏紝鍏堝悓姝ュ垵濮嬪寲寮曟搸鍜岀姸鎬侊紝闃叉鍓嶇杩囨棭鑾峰彇鍒扮┖鍦板浘

    sim = SmallvilleSimulation("smallville")
    agent_locations = {}
    for n in sim.environment.all_nodes():
        for agent_name in n.agents:
            agent_locations[agent_name] = n.name

    def map_agent(a):
        return {
            "id": a.name,
            "name": a.name,
            "persona": a.traits,
            "current_location": agent_locations.get(a.name, "Cafe"),
            "inventory": list(a.inventory.keys()),
            "status": a.current_action if a.current_action else "Idle",
            "short_term_memory": [{"timestamp": getattr(m, "timestamp", "00:00"), "content": m.get("content", str(m)) if isinstance(m, dict) else getattr(m, "content", str(m)), "is_reflection": False, "frame": getattr(m, "frame", 0)} for m in a.memory_stream[-5:]],
            "moving": False,
            "next_location": None
        }

    last_state_dump = {
        "game_id": "smallville",
        "frame": 0,
        "game_time": sim.clock.isoformat(),
        "day": 1,
        "time_of_day": "noon",
        "map": {"name": "smallville", "locations": [{"id": n.name, "name": n.name, "description": ""} for n in sim.environment.all_nodes()], "edges": []},
        "agents": [map_agent(a) for a in sim.world_agents.values()],
        "objects": [],
        "logs": []
    }


    sim_task = asyncio.create_task(simulation_loop())

@app.websocket("/ws/games/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await manager.connect(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False, ws="websockets")
