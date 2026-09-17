# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.game_session import build_template, get_manager
except ImportError:
    from game_session import build_template, get_manager

app = FastAPI(title="SINA Stage 4 Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LLMConfigIn(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    thinking_enabled: Optional[bool] = None


class CreateGameIn(BaseModel):
    map_config: Optional[dict] = None
    agent_configs: Optional[list] = None
    object_configs: Optional[list] = None
    start_time: str = "08:00"


class StepIn(BaseModel):
    steps: int = Field(default=1, ge=1, le=100)


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()


@app.get("/api/config/llm")
async def get_llm_config():
    return get_manager().get_llm_config()


@app.post("/api/config/llm")
async def set_llm_config(body: LLMConfigIn):
    return get_manager().save_llm_config(body.model_dump())


@app.get("/api/templates/initial")
async def get_initial():
    return build_template("smallville")


@app.get("/api/games/current")
async def get_current_game():
    return get_manager().get_current()


@app.post("/api/games")
async def create_game(body: CreateGameIn):
    return get_manager().create_game(map_config=body.map_config, start_time=body.start_time)


@app.post("/api/games/abandon")
async def abandon_game():
    return get_manager().abandon()


@app.get("/api/games/{game_id}")
async def get_game(game_id: str):
    state = get_manager().get_game(game_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return state


@app.post("/api/games/{game_id}/step")
async def step_game(game_id: str, body: Optional[StepIn] = None):
    req = body or StepIn()
    async def on_frame(state: dict):
        await manager.broadcast(json.dumps({"type": "frame_update", "data": state}))

    try:
        return await get_manager().step(game_id, steps=req.steps, on_frame=on_frame)
    except KeyError:
        raise HTTPException(status_code=404, detail="Game not found")


@app.get("/api/games/{game_id}/prompts")
async def get_prompts(game_id: str, agent_id: Optional[str] = None, frame: Optional[int] = None):
    try:
        return get_manager().agent_prompts(game_id, agent_id=agent_id, frame=frame)
    except KeyError:
        raise HTTPException(status_code=404, detail="Game not found")


@app.get("/api/saves")
async def get_saves():
    return get_manager().list_saves()


@app.post("/api/saves/import")
async def import_save(payload: dict[str, Any]):
    try:
        return get_manager().import_save(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError:
        raise HTTPException(status_code=404, detail="Save not found")


@app.post("/api/saves/clear")
async def clear_saves():
    return get_manager().clear_saves()


@app.post("/api/saves/{game_id}/continue")
async def continue_save(game_id: str):
    try:
        return get_manager().continue_save(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Save not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/saves/{game_id}")
async def delete_save(game_id: str):
    try:
        return get_manager().delete_save(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Save not found")


@app.get("/api/saves/{game_id}/download")
async def download_save(game_id: str):
    try:
        return get_manager().download_save(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Save not found")


@app.get("/api/agents/{agent_id}/memories")
async def get_agent_memories(agent_id: str):
    return get_manager().agent_memories(agent_id)


@app.websocket("/ws/games/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str):
    await manager.connect(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ws="websockets")
