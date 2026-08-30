import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn
from main_simulation import SmallvilleSimulation
from dag_engine import DAGEngine

app = FastAPI(title="SINA Stage 4 Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    sim = SmallvilleSimulation("stone_age")
    engine = DAGEngine(sim)
    
    # 强制在后台无尽推演
    for tick in range(1, 10000):
        if not manager.active_connections:
            await asyncio.sleep(2) # 无人观测时放缓推演以节省算力
            continue
            
        print(f"\n=================== TICK {tick} ===================")
        await engine.run_dag("EnvTick", {"sim": sim})
        
        # 组装物理状态 JSON，推送前端
        state_dump = {
            "tick": tick,
            "time": sim.clock.isoformat(),
            "agents": [a.to_dict() for a in sim.world_agents.values()],
            "nodes": [
                {"name": n.name, "inventory": n.inventory, "agents": list(n.agents)}
                for n in sim.environment.all_nodes()
            ]
        }
        await manager.broadcast(json.dumps({"type": "STATE_UPDATE", "data": state_dump}))
        
        # 强制休眠，赋予前端渲染时间，并压制 Token 爆炸
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    global sim_task
    sim_task = asyncio.create_task(simulation_loop())

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run("server.py:app", host="0.0.0.0", port=8000, reload=False)
