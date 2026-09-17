"""
Dashboard session layer: serialize the existing DAG simulator into the
frontend GameState contract and persist saves. Does not change tick rules.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

try:
    from core.dag_simulation import DAGSmallvilleSimulation, serialize_node_states
    from core.action_lease import ActionInertiaEngine
    from core.environment import EnvNode, SandboxEnvironment
    from core.gateway import get_gateway, reconfigure_gateway
    from core.atomic_io import atomic_write_json
except ImportError:
    from dag_simulation import DAGSmallvilleSimulation, serialize_node_states
    from action_lease import ActionInertiaEngine
    from environment import EnvNode, SandboxEnvironment
    from gateway import get_gateway, reconfigure_gateway
    from atomic_io import atomic_write_json

from sina.memory.manager import HierarchicalMemoryManager
from sina.memory.types import MemoryType

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWN_WORLDS = ("smallville", "stone_age")


def data_dir() -> Path:
    override = os.environ.get("SINA_DATA_DIR")
    path = Path(override) if override else (REPO_ROOT / "data")
    path.mkdir(parents=True, exist_ok=True)
    (path / "saves").mkdir(parents=True, exist_ok=True)
    return path


def saves_dir() -> Path:
    path = data_dir() / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path


# game_id 只允许这套字符集：既排除了路径分隔符与 ".."，也排除了 Windows 非法字符 :*?"<>|
_GAME_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def is_valid_game_id(game_id: Any) -> bool:
    return isinstance(game_id, str) and bool(_GAME_ID_RE.match(game_id))


def _save_path(game_id: str, suffix: str = ".json") -> Path:
    """把 game_id 解析为 saves_dir 内的安全路径，阻断 `../` 与绝对路径穿越。

    未经校验的 game_id 曾可让 download/continue/delete 读到或删掉保存目录之外的
    任意 .json（Windows 上反斜杠同样被 pathlib 当分隔符）。
    """
    if not is_valid_game_id(game_id):
        raise ValueError(f"Invalid game_id: {game_id!r}")
    root = saves_dir().resolve()
    path = (root / f"{game_id}{suffix}").resolve()
    if path.parent != root:
        raise ValueError(f"Invalid game_id: {game_id!r}")
    return path


def llm_config_path() -> Path:
    return data_dir() / "llm_config.json"


def resolve_world_name(raw: Optional[str]) -> str:
    if not raw:
        return "smallville"
    key = raw.strip().lower().replace(" ", "_")
    aliases = {
        "smallville": "smallville",
        "stone_age": "stone_age",
        "stoneage": "stone_age",
        "world_matrix": "stone_age",
    }
    if key in aliases:
        return aliases[key]
    worlds_root = REPO_ROOT / "worlds"
    if (worlds_root / key / "config" / "map.json").exists():
        return key
    return "smallville"


def _walk_nodes(node: EnvNode) -> list[EnvNode]:
    out = [node]
    for child in node.children:
        out.extend(_walk_nodes(child))
    return out


def map_from_environment(env: SandboxEnvironment, world_name: str) -> dict:
    locations = []
    for node in env.all_nodes():
        locations.append({
            "id": node.name,
            "name": node.name,
            "description": node.description or "",
        })
    edges = []
    seen = set()
    for node in _walk_nodes(env.root):
        siblings = [c for c in node.children if not c.children]
        for i, a in enumerate(siblings):
            for b in siblings[i + 1:]:
                pair = tuple(sorted((a.name, b.name)))
                if pair in seen:
                    continue
                seen.add(pair)
                edges.append({"from": a.name, "to": b.name, "distance": 80})
        for child in node.children:
            if not child.children:
                continue
            # Structural parent is not a leaf; skip parent-leaf edges.
    return {"name": world_name, "locations": locations, "edges": edges}


def _memory_entry(content: str, timestamp: str, frame: int, is_reflection: bool = False) -> dict:
    return {
        "timestamp": timestamp,
        "content": content,
        "is_reflection": is_reflection,
        "frame": frame,
    }


def _agent_short_term(sim, agent) -> list[dict]:
    clock_str = sim.clock.strftime("%H:%M")
    bm = sim.memory_manager._bifurcation_managers.get(agent.name)
    entries = []
    if bm:
        for item in bm.working_queue[-8:]:
            entries.append(_memory_entry(
                content=item.content,
                timestamp=clock_str,
                frame=int(getattr(item, "tick", sim.tick_count) or 0),
                is_reflection=getattr(item, "memory_type", None) == MemoryType.REFLECTION,
            ))
    # 本地记忆流也一并合并：此前一旦 working_queue 非空就提前 return，
    # 导致 store_observation 写入的 [深层领悟] 反思永远进不了仪表盘。
    for mem in agent.memory_stream[-8:]:
        if isinstance(mem, dict):
            text = mem.get("content") or mem.get("text") or str(mem)
            ts = mem.get("timestamp") or mem.get("time") or clock_str
            frame = int(mem.get("frame", sim.tick_count) or 0)
            is_ref = bool(mem.get("is_reflection")) or str(text).startswith("[深层领悟]")
        else:
            text = getattr(mem, "content", str(mem))
            ts = getattr(mem, "timestamp", clock_str)
            frame = int(getattr(mem, "frame", sim.tick_count) or 0)
            is_ref = bool(getattr(mem, "is_reflection", False))
        entries.append(_memory_entry(str(text), str(ts), frame, is_ref))

    # 两条流会写入同一条 memory_text，按 (content, frame) 去重后按时间排序取最近 8 条。
    deduped = {}
    for e in entries:
        deduped.setdefault((e["content"], e["frame"]), e)
    merged = sorted(deduped.values(), key=lambda e: e["frame"])
    return merged[-8:]


def _time_of_day(clock: datetime) -> str:
    hour = clock.hour
    if 6 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 22:
        return "evening"
    return "night"


def _day_number(clock: datetime) -> int:
    epoch = datetime(2026, 1, 1)
    return max(1, (clock.date() - epoch.date()).days + 1)


def project_objects(sim) -> list[dict]:
    objects = []
    for node in sim.environment.all_nodes():
        for tag, qty in (node.inventory or {}).items():
            if qty <= 0:
                continue
            objects.append({
                "id": f"{node.name}:{tag}",
                "name": f"{tag} x{qty}",
                "description": tag,
                "location": node.name,
                "type": "portable",
                "current_state": "",
                "current_owner": None,
            })
    for agent in sim.world_agents.values():
        loc = sim.environment.agent_locations.get(agent.name)
        loc_name = loc.name if loc else ""
        for tag, qty in (agent.inventory or {}).items():
            if qty <= 0:
                continue
            objects.append({
                "id": f"agent:{agent.name}:{tag}",
                "name": f"{tag} x{qty}",
                "description": tag,
                "location": loc_name,
                "type": "portable",
                "current_state": "",
                "current_owner": agent.name,
            })
    return objects


def serialize_game_state(sim, game_id: str, logs: Optional[list] = None) -> dict:
    agent_locations = {}
    for node in sim.environment.all_nodes():
        for agent_name in node.agents:
            agent_locations[agent_name] = node.name

    agents = []
    for agent in sim.world_agents.values():
        agents.append({
            "id": agent.name,
            "name": agent.name,
            "persona": agent.traits,
            "current_location": agent_locations.get(agent.name, ""),
            "inventory": list((agent.inventory or {}).keys()),
            "status": agent.current_action if agent.current_action else "Idle",
            "short_term_memory": _agent_short_term(sim, agent),
            "moving": False,
            "next_location": None,
            "daily_plan": None,
            "daily_plan_day": None,
        })

    world_name = getattr(sim, "world_name", "smallville")
    return {
        "game_id": game_id,
        "frame": int(getattr(sim, "tick_count", 0) or 0),
        "game_time": sim.clock.strftime("%H:%M"),
        "day": _day_number(sim.clock),
        "time_of_day": _time_of_day(sim.clock),
        "map": map_from_environment(sim.environment, world_name),
        "agents": agents,
        "objects": project_objects(sim),
        "logs": list(logs or []),
    }


def build_template(world_name: str = "smallville") -> dict:
    world_name = resolve_world_name(world_name)
    env = SandboxEnvironment(world_name=world_name)
    agents_path = REPO_ROOT / "worlds" / world_name / "config" / "agents.json"
    agents = []
    objects = []
    if agents_path.exists():
        with open(agents_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for cfg in raw.get("agents", []):
            inv = cfg.get("inventory") or {}
            if isinstance(inv, dict):
                inv_list = list(inv.keys())
            else:
                inv_list = list(inv)
            agents.append({
                "id": cfg["name"],
                "name": cfg["name"],
                "persona": cfg.get("traits", ""),
                "initial_location": cfg.get("start_room", ""),
                "inventory": inv_list,
                "initial_memories": cfg.get("intentions", []),
            })
    objects = []
    for node in env.all_nodes():
        for tag, qty in (node.inventory or {}).items():
            if qty <= 0:
                continue
            objects.append({
                "id": f"{node.name}:{tag}",
                "name": tag,
                "description": tag,
                "location": node.name,
                "type": "portable",
                "current_state": "",
                "current_owner": None,
            })
    return {
        "map": map_from_environment(env, world_name),
        "agents": agents,
        "objects": objects,
    }


def extract_world(sim) -> dict:
    agents_data = []
    fallback_room = sim.environment.all_nodes()[0].name if sim.environment.all_nodes() else "Cafe"
    for name, agent in sim.world_agents.items():
        agent_dict = agent.to_dict()
        loc_node = sim.environment.agent_locations.get(name)
        agent_dict["last_room"] = loc_node.name if loc_node else fallback_room
        agents_data.append(agent_dict)
    return {
        "clock": sim.clock.isoformat(),
        "physics": sim.physics.to_dict(),
        "meme_pool": sim.meme_pool.to_dict(),
        "agents": agents_data,
        # 房间的地面资源/占用锁同样要落盘，否则读档会退回地图初始库存，
        # 而智能体背包照常还原 —— 反复存读即可凭空复制物品。
        "nodes": serialize_node_states(sim.environment),
        "tick_count": sim.tick_count,
        "world_name": getattr(sim, "world_name", "smallville"),
    }


def apply_start_time(sim, start_time: Optional[str]) -> None:
    if not start_time:
        return
    try:
        parts = start_time.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        sim.clock = sim.clock.replace(hour=hour % 24, minute=minute % 60, second=0, microsecond=0)
    except (ValueError, IndexError, TypeError):
        return


def _clear_sim_population(sim) -> None:
    for node in _walk_nodes(sim.environment.root):
        node.agents.clear()
    sim.environment.agent_locations.clear()
    sim.world_agents.clear()
    sim.memory_manager = HierarchicalMemoryManager()
    sim.action_inertia_engine = ActionInertiaEngine()
    sim.active_proposal = [None]
    sim.current_logs = []


def load_world_into_sim(sim, world: dict) -> None:
    _clear_sim_population(sim)
    # 直接把 dict 灌进 sim：原先要落盘到固定的 _tmp_load.json，两个并发读档会互相
    # 覆盖、或一个把另一个正要读的文件 unlink 掉。
    sim._load_world_state_data(world)


def persist_memories(sim, game_id: str) -> None:
    db_path = _save_path(game_id, ".memories.db")
    try:
        sim.memory_manager.vector_store.persist_to_sqlite(str(db_path), game_id)
    except Exception:
        # 静默失败会让用户以为存过、读档却发现长期记忆是空的，必须留下痕迹
        logger.exception("长期记忆持久化失败 (game_id=%s, db=%s)", game_id, db_path)


def restore_memories(sim, game_id: str) -> None:
    db_path = _save_path(game_id, ".memories.db")
    if not db_path.exists():
        return
    try:
        sim.memory_manager.vector_store.load_from_sqlite(str(db_path), game_id)
    except Exception:
        logger.exception("长期记忆恢复失败 (game_id=%s, db=%s)", game_id, db_path)


class GameSession:
    def __init__(self, sim, game_id: str, logs: Optional[list] = None):
        self.sim = sim
        self.game_id = game_id
        self.logs = list(logs or [])

    def snapshot(self) -> dict:
        return serialize_game_state(self.sim, self.game_id, self.logs)

    def to_save_payload(self) -> dict:
        state = self.snapshot()
        return {
            "game_id": self.game_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "world_name": getattr(self.sim, "world_name", "smallville"),
            "world": extract_world(self.sim),
            # logs 只存在 state 里（原先顶层再存一份，存档体积直接翻倍）。
            # list_saves / _attach_from_payload 都已用 `or` 兼容旧格式的顶层 logs。
            "state": state,
        }

    def persist(self) -> None:
        payload = self.to_save_payload()
        atomic_write_json(_save_path(self.game_id), payload)
        persist_memories(self.sim, self.game_id)

    def append_frame_log(self) -> dict:
        entry = {
            "frame": int(self.sim.tick_count),
            "game_time": self.sim.clock.strftime("%H:%M"),
            "events": list(getattr(self.sim, "current_logs", []) or []),
        }
        self.logs.append(entry)
        return entry


class SessionManager:
    def __init__(self):
        self.current: Optional[GameSession] = None
        self._step_lock = asyncio.Lock()
        self._load_llm_config()

    def _load_llm_config(self) -> None:
        path = llm_config_path()
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        reconfigure_gateway(
            api_key=data.get("api_key") or None,
            base_url=data.get("base_url") or None,
            model=data.get("model") or None,
            embedding_base_url=data.get("embedding_base_url"),
            embedding_api_key=data.get("embedding_api_key"),
            embedding_model=data.get("embedding_model"),
            embedding_provider=data.get("embedding_provider"),
            thinking_enabled=data.get("thinking_enabled"),
        )

    def save_llm_config(self, payload: dict) -> dict:
        gw = get_gateway()
        reconfigure_gateway(
            api_key=payload.get("api_key"),
            base_url=payload.get("base_url"),
            model=payload.get("model"),
            embedding_base_url=payload.get("embedding_base_url"),
            embedding_api_key=payload.get("embedding_api_key"),
            embedding_model=payload.get("embedding_model"),
            embedding_provider=payload.get("embedding_provider"),
            thinking_enabled=payload.get("thinking_enabled"),
        )
        path = llm_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(gw.serializable_config(), f, ensure_ascii=False, indent=2)
        return {"success": True, "config": gw.public_config()}

    def get_llm_config(self) -> dict:
        return {"success": True, "config": get_gateway().public_config()}

    async def create_game(self, map_config: Optional[dict] = None, start_time: Optional[str] = None) -> dict:
        world_name = resolve_world_name((map_config or {}).get("name"))
        # 重量级构建放在锁外，只在替换当前会话的瞬间持锁。
        sim = DAGSmallvilleSimulation(world_name=world_name, resume=False)
        apply_start_time(sim, start_time)
        game_id = f"{world_name}-{uuid.uuid4().hex[:8]}"
        session = GameSession(sim, game_id)
        async with self._step_lock:
            self.current = session
            session.persist()
            state = session.snapshot()
        return {"game_id": game_id, "state": state}

    async def abandon(self) -> dict:
        async with self._step_lock:
            self.current = None
        return {"success": True}

    def get_current(self) -> dict:
        if not self.current:
            return {"game_id": None, "state": None}
        return {"game_id": self.current.game_id, "state": self.current.snapshot()}

    def get_game(self, game_id: str) -> Optional[dict]:
        if self.current and self.current.game_id == game_id:
            return self.current.snapshot()
        try:
            path = _save_path(game_id)
        except ValueError:
            return None
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("state")
            except (OSError, json.JSONDecodeError):
                pass
        return None

    async def step(
        self,
        game_id: str,
        steps: int = 1,
        on_frame: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> dict:
        if not self.current or self.current.game_id != game_id:
            raise KeyError(game_id)
        steps = max(1, int(steps or 1))
        results = []
        async with self._step_lock:
            # 锁内重新取一次会话，整个循环只用这个局部引用：否则 create_game/abandon
            # 在帧中途替换 self.current 会让帧日志写进别的游戏，或 AttributeError → 500。
            session = self.current
            if not session or session.game_id != game_id:
                raise KeyError(game_id)
            for _ in range(steps):
                await session.sim.run_dag_loop(1)
                entry = session.append_frame_log()
                results.append(entry)
                session.persist()
                state = session.snapshot()
                if on_frame:
                    await on_frame(state)
        return {
            "frames_executed": steps,
            "results": results,
        }

    def list_saves(self) -> dict:
        items = []
        for path in sorted(saves_dir().glob("*.json")):
            if path.name.startswith("_"):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            state = data.get("state") or {}
            items.append({
                "game_id": data.get("game_id") or path.stem,
                "saved_at": data.get("saved_at"),
                "frame": state.get("frame", 0),
                "game_time": state.get("game_time"),
                "day": state.get("day"),
                "time_of_day": state.get("time_of_day"),
                "map_name": (state.get("map") or {}).get("name") or data.get("world_name"),
                "agent_count": len(state.get("agents") or []),
                "frame_count": len(data.get("logs") or state.get("logs") or []),
            })
        return {"saves": items}

    async def _attach_from_payload(self, data: dict, game_id: Optional[str] = None) -> dict:
        world = data.get("world")
        if not world:
            raise ValueError("Save file is missing world snapshot")
        world_name = resolve_world_name(data.get("world_name") or world.get("world_name"))
        sim = DAGSmallvilleSimulation(world_name=world_name, resume=False)
        load_world_into_sim(sim, world)
        # 导入的存档里 game_id 不可信：非法时丢弃并重新生成，避免它被用作落盘路径。
        gid = game_id or data.get("game_id")
        if not is_valid_game_id(gid):
            gid = f"{world_name}-{uuid.uuid4().hex[:8]}"
        restore_memories(sim, gid)
        logs = data.get("logs") or (data.get("state") or {}).get("logs") or []
        session = GameSession(sim, gid, logs=logs)
        async with self._step_lock:
            self.current = session
            session.persist()
            state = session.snapshot()
        return {"game_id": gid, "state": state}

    async def continue_save(self, game_id: str) -> dict:
        path = _save_path(game_id)
        if not path.exists():
            raise KeyError(game_id)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return await self._attach_from_payload(data, game_id=game_id)

    async def import_save(self, payload: Any) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid save payload")
        data = payload
        if "world" not in data and "state" in payload and isinstance(payload["state"], dict) and "world" in payload["state"]:
            data = payload["state"]
        return await self._attach_from_payload(data)

    async def delete_save(self, game_id: str) -> dict:
        path = _save_path(game_id)
        mem = _save_path(game_id, ".memories.db")
        async with self._step_lock:
            deleted = False
            if path.exists():
                path.unlink()
                deleted = True
            if mem.exists():
                mem.unlink()
            if self.current and self.current.game_id == game_id:
                self.current = None
            if not deleted:
                raise KeyError(game_id)
        return {"success": True}

    async def clear_saves(self) -> dict:
        saves_deleted = 0
        memories_deleted = 0
        async with self._step_lock:
            for path in saves_dir().glob("*.json"):
                if path.name.startswith("_"):
                    continue
                path.unlink()
                saves_deleted += 1
            for path in saves_dir().glob("*.memories.db"):
                path.unlink()
                memories_deleted += 1
            self.current = None
        return {"success": True, "saves_deleted": saves_deleted, "memories_deleted": memories_deleted}

    def download_save(self, game_id: str) -> dict:
        if self.current and self.current.game_id == game_id:
            return self.current.to_save_payload()
        path = _save_path(game_id)
        if not path.exists():
            raise KeyError(game_id)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def agent_memories(self, agent_id: str) -> dict:
        if not self.current:
            return {"agent_id": agent_id, "short_term": [], "long_term": []}
        sim = self.current.sim
        agent = sim.world_agents.get(agent_id)
        short_term = _agent_short_term(sim, agent) if agent else []
        long_term = []
        try:
            episodes = sim.memory_manager.vector_store.get_agent_memories(agent_id)
            for mem in episodes[-20:]:
                long_term.append({
                    "memory_id": mem.memory_id,
                    "summary": mem.summary,
                    "content": mem.summary,
                    "timestamp": f"Tick {mem.tick_start}" if getattr(mem, "tick_start", None) is not None else "",
                    "tick_start": mem.tick_start,
                    "tick_end": mem.tick_end,
                    "location": mem.location,
                    "is_confabulated": mem.is_confabulated,
                    "importance": mem.importance,
                })
        except Exception:
            pass
        return {"agent_id": agent_id, "short_term": short_term, "long_term": long_term}

    def agent_prompts(self, game_id: str, agent_id: Optional[str] = None, frame: Optional[int] = None) -> dict:
        if not self.current or self.current.game_id != game_id:
            raise KeyError(game_id)
        stored = dict(get_gateway().agent_prompts)
        if agent_id:
            entry = stored.get(agent_id)
            prompts = {agent_id: entry} if entry else {}
        else:
            prompts = stored
        return {
            "frame": frame if frame is not None else int(self.current.sim.tick_count),
            "prompts": prompts,
        }


_manager: Optional[SessionManager] = None


def get_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


def reset_manager() -> SessionManager:
    global _manager
    try:
        from core.gateway import reset_gateway
    except ImportError:
        from gateway import reset_gateway
    reset_gateway()
    _manager = SessionManager()
    return _manager
