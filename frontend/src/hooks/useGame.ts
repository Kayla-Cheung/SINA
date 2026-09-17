import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  GameState, MapConfig, AgentConfig, GameObjectConfig,
  LLMConfig, MemoryEntry
} from '../types'

const API_BASE = '/api'
const LAST_GAME_KEY = 'graph-world-last-game-id'

export interface SaveInfo {
  game_id: string
  saved_at?: string
  frame: number
  game_time?: string
  day?: number
  time_of_day?: string
  map_name?: string
  agent_count?: number
  frame_count?: number
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    let detail = resp.statusText
    try {
      const body = await resp.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      // ignore
    }
    throw new Error(`API ${path} failed: ${detail}`)
  }
  return resp.json()
}

export function useGame() {
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [gameId, setGameId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const steppingRef = useRef(false)

  const activateGame = useCallback((id: string, state: GameState) => {
    try {
      sessionStorage.removeItem('graph-world-skip-resume')
    } catch {
      // ignore
    }
    setGameId(id)
    setGameState(state)
    try {
      localStorage.setItem(LAST_GAME_KEY, id)
    } catch {
      // ignore
    }
  }, [])

  const abandonGame = useCallback(async () => {
    try {
      await api('/games/abandon', { method: 'POST' })
    } catch {
      // Backend may be down; still clear local UI state
    }
    setGameId(null)
    setGameState(null)
    try {
      localStorage.removeItem(LAST_GAME_KEY)
      sessionStorage.setItem('graph-world-skip-resume', '1')
    } catch {
      // ignore
    }
  }, [])

  const setLLMConfig = useCallback(async (config: LLMConfig) => {
    return api('/config/llm', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }, [])

  const getLLMConfig = useCallback(async () => {
    return api<{ success: boolean; config: LLMConfig }>('/config/llm')
  }, [])

  const getTemplate = useCallback(async () => {
    return api<{ map: MapConfig; agents: AgentConfig[]; objects: GameObjectConfig[] }>(
      '/templates/initial'
    )
  }, [])

  const listSaves = useCallback(async () => {
    return api<{ saves: SaveInfo[] }>('/saves')
  }, [])

  const createGame = useCallback(async (
    mapConfig: MapConfig,
    agentConfigs: AgentConfig[],
    objectConfigs: GameObjectConfig[],
    startTime: string = '08:00',
  ) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api<{ game_id: string; state: GameState }>('/games', {
        method: 'POST',
        body: JSON.stringify({
          map_config: mapConfig,
          agent_configs: agentConfigs,
          object_configs: objectConfigs,
          start_time: startTime,
        }),
      })
      activateGame(resp.game_id, resp.state)
      return resp.game_id
    } catch (e: any) {
      setError(e.message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [activateGame])

  const continueSave = useCallback(async (id: string) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api<{ game_id: string; state: GameState }>(
        `/saves/${id}/continue`,
        { method: 'POST' },
      )
      activateGame(resp.game_id, resp.state)
      return resp.game_id
    } catch (e: any) {
      setError(e.message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [activateGame])

  const importSave = useCallback(async (payload: unknown) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await api<{ game_id: string; state: GameState }>('/saves/import', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      activateGame(resp.game_id, resp.state)
      return resp.game_id
    } catch (e: any) {
      setError(e.message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [activateGame])

  const deleteSave = useCallback(async (id: string) => {
    return api<{ success: boolean }>(`/saves/${id}`, { method: 'DELETE' })
  }, [])

  const clearAllSaves = useCallback(async () => {
    return api<{ success: boolean; saves_deleted: number; memories_deleted: number }>(
      '/saves/clear',
      { method: 'POST' },
    )
  }, [])

  const step = useCallback(async (steps: number = 1) => {
    if (!gameId || steppingRef.current) return
    steppingRef.current = true
    setLoading(true)
    setError(null)
    try {
      await api(`/games/${gameId}/step`, {
        method: 'POST',
        body: JSON.stringify({ steps }),
      })
      const state = await api<GameState>(`/games/${gameId}`)
      setGameState(state)
      return state
    } catch (e: any) {
      setError(e.message)
      // 必须重新抛出：auto-step 的 runLoop 依赖这个 rejection 来终止循环，
      // 否则后端持续失败时前端会以 3 秒为周期无限重试。
      throw e
    } finally {
      steppingRef.current = false
      setLoading(false)
    }
  }, [gameId])

  const refresh = useCallback(async () => {
    if (!gameId) return
    const state = await api<GameState>(`/games/${gameId}`)
    setGameState(state)
  }, [gameId])

  const exportState = useCallback(async () => {
    if (!gameId) return
    const resp = await fetch(`${API_BASE}/saves/${gameId}/download`)
    if (!resp.ok) throw new Error('Download failed')
    const data = await resp.json()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `graph-world-${gameId}-frame-${data?.state?.frame ?? 'save'}.json`
    link.click()
  }, [gameId])

  const getAgentMemories = useCallback(async (agentId: string) => {
    return api<{ agent_id: string; short_term: MemoryEntry[]; long_term: any[] }>(
      `/agents/${agentId}/memories`
    )
  }, [])

  const getAgentPrompt = useCallback(async (agentId: string, frame?: number) => {
    if (!gameId) return null
    const q = new URLSearchParams({ agent_id: agentId })
    if (frame !== undefined) q.set('frame', String(frame))
    return api<{
      frame: number | null
      prompts: Record<string, {
        system: string
        user: string
        raw_response: string
        character_response?: string
      }>
    }>(`/games/${gameId}/prompts?${q.toString()}`)
  }, [gameId])

  // Try resume: in-memory current game, else last localStorage save id.
  // Keep skip-resume until the user explicitly starts/continues a game
  // (React Strict Mode remounts must not clear the flag early).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        try {
          if (sessionStorage.getItem('graph-world-skip-resume') === '1') {
            return
          }
        } catch {
          // ignore
        }
        const cur = await api<{ game_id: string | null; state: GameState | null }>('/games/current')
        if (cancelled) return
        if (cur.game_id && cur.state) {
          activateGame(cur.game_id, cur.state)
          return
        }
        const last = localStorage.getItem(LAST_GAME_KEY)
        if (last) {
          const resp = await api<{ game_id: string; state: GameState }>(
            `/saves/${last}/continue`,
            { method: 'POST' },
          )
          if (!cancelled) activateGame(resp.game_id, resp.state)
        }
      } catch {
        // stay on setup screen
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activateGame])

  // WebSocket connection: 订阅本局帧更新，断开后指数退避重连。
  useEffect(() => {
    if (!gameId) return
    let disposed = false
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let ws: WebSocket | null = null

    const connect = () => {
      if (disposed) return
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/games/${gameId}`
      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          // 后端已在 frame_update 里带完整 state，直接采用即可，避免再发一次
          // GET，消除「旧 GET 晚到覆盖新帧」的乱序覆盖。
          if (msg.type === 'frame_update' && msg.data) {
            setGameState(msg.data)
          }
        } catch {
          // 忽略无法解析的消息
        }
      }

      ws.onclose = () => {
        if (disposed) return
        wsRef.current = null
        if (retryTimer) clearTimeout(retryTimer)
        retryTimer = setTimeout(connect, 2000)
      }
    }

    connect()

    return () => {
      disposed = true
      if (retryTimer) clearTimeout(retryTimer)
      if (ws) {
        ws.onclose = null
        ws.onmessage = null
        ws.close()
      }
      wsRef.current = null
    }
  }, [gameId])

  return {
    gameState,
    gameId,
    loading,
    error,
    setLLMConfig,
    getLLMConfig,
    getTemplate,
    listSaves,
    createGame,
    continueSave,
    importSave,
    deleteSave,
    clearAllSaves,
    abandonGame,
    step,
    refresh,
    exportState,
    getAgentMemories,
    getAgentPrompt,
  }
}
