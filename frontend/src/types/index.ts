// Type definitions matching backend Pydantic models

export interface Location {
  id: string
  name: string
  description: string
}

export interface Edge {
  from: string
  to: string
  distance: number
}

export interface MapConfig {
  name: string
  locations: Location[]
  edges: Edge[]
}

export interface AgentConfig {
  id: string
  name: string
  persona: string
  initial_location: string
  inventory: string[]
  initial_memories: string[]
}

export interface GameObjectConfig {
  id: string
  name: string
  description: string
  location: string
  type: 'state' | 'portable'
  current_state: string
  current_owner?: string | null
}

export interface MemoryEntry {
  timestamp: string
  content: string
  is_reflection: boolean
  frame: number
}

export interface AgentState {
  id: string
  name: string
  persona: string
  current_location: string
  inventory: string[]
  status: string
  short_term_memory: MemoryEntry[]
  moving: boolean
  next_location: string | null
  daily_plan?: string | null
  daily_plan_day?: number | null
}

export interface FrameLog {
  frame: number
  game_time: string
  events: string[]
}

export interface GameState {
  game_id: string
  frame: number
  game_time: string
  day: number
  time_of_day: string
  map: MapConfig
  agents: AgentState[]
  objects: GameObjectConfig[]
  logs: FrameLog[]
}

export interface LLMConfig {
  base_url: string
  api_key: string
  model: string
  embedding_base_url?: string
  embedding_api_key?: string
  embedding_model: string
  embedding_provider?: 'openai' | 'google'
  thinking_enabled?: boolean
}

export interface StepResult {
  frames_executed: number
  results: Array<{
    frame: number
    game_time: string
    events: string[]
  }>
}