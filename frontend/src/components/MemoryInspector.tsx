import { useEffect, useState } from 'react'
import type { GameState, MemoryEntry } from '../types'

interface Props {
  gameState: GameState
  getAgentMemories: (agentId: string) => Promise<{
    agent_id: string
    short_term: MemoryEntry[]
    long_term: any[]
  }>
  getAgentPrompt: (agentId: string, frame?: number) => Promise<{
    frame: number | null
    prompts: Record<string, {
      system: string
      user: string
      raw_response: string
      character_response?: string
      god_kind?: string
      god_reason?: string
      god_raw?: string
      god_tool?: { tool: string; args: Record<string, unknown> } | null
    }>
  } | null>
}

type Tab = 'memory' | 'prompt'

function memoryTextClass(content: string, isReflection?: boolean): string {
  if (isReflection || content.startsWith('Reflection:')) return 'text-violet-800'
  if (content.startsWith("[Today's Plan]")) return 'text-emerald-800'
  if (content.startsWith('[Recalled]')) return 'text-amber-800'
  return 'text-stone-700'
}

function memoryBoxClass(content: string, isReflection?: boolean): string {
  if (isReflection || content.startsWith('Reflection:')) {
    return 'bg-violet-50 border border-violet-200'
  }
  if (content.startsWith("[Today's Plan]")) {
    return 'bg-emerald-50 border border-emerald-200'
  }
  if (content.startsWith('[Recalled]')) {
    return 'bg-amber-50 border border-amber-200'
  }
  return 'bg-stone-50 border border-stone-200'
}

export function MemoryInspector({ gameState, getAgentMemories, getAgentPrompt }: Props) {
  const [selectedAgent, setSelectedAgent] = useState<string>(gameState.agents[0]?.id || '')
  const [tab, setTab] = useState<Tab>('memory')
  const [memories, setMemories] = useState<{
    short_term: MemoryEntry[]
    long_term: any[]
  } | null>(null)
  const [promptData, setPromptData] = useState<{
    frame: number | null
    system: string
    user: string
    raw_response: string
    character_response?: string
    god_kind?: string
    god_reason?: string
    god_raw?: string
    god_tool?: { tool: string; args: Record<string, unknown> } | null
  } | null>(null)
  const [loading, setLoading] = useState(false)

  const loadMemories = async (agentId: string) => {
    setLoading(true)
    try {
      const m = await getAgentMemories(agentId)
      setMemories(m)
    } catch {
      setMemories(null)
    } finally {
      setLoading(false)
    }
  }

  const loadPrompt = async (agentId: string) => {
    setLoading(true)
    try {
      const data = await getAgentPrompt(agentId)
      const entry = data?.prompts?.[agentId]
      if (entry) {
        setPromptData({
          frame: data.frame,
          system: entry.system,
          user: entry.user,
          raw_response: entry.raw_response,
          character_response: entry.character_response,
          god_kind: entry.god_kind,
          god_reason: entry.god_reason,
          god_raw: entry.god_raw,
          god_tool: entry.god_tool,
        })
      } else {
        setPromptData(null)
      }
    } catch {
      setPromptData(null)
    } finally {
      setLoading(false)
    }
  }

  const selectAgent = async (agentId: string) => {
    setSelectedAgent(agentId)
    if (tab === 'memory') await loadMemories(agentId)
    else await loadPrompt(agentId)
  }

  const switchTab = async (next: Tab) => {
    setTab(next)
    if (!selectedAgent) return
    if (next === 'memory') await loadMemories(selectedAgent)
    else await loadPrompt(selectedAgent)
  }

  useEffect(() => {
    if (selectedAgent && tab === 'prompt') {
      loadPrompt(selectedAgent)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameState.frame])

  return (
    <div className="bg-panel border border-border rounded-lg p-3 h-full overflow-auto scrollbar-thin shadow-sm">
      <h3 className="text-md font-semibold text-stone-900 mb-2 sticky top-0 bg-panel pb-2 border-b border-border">
        Inspector
      </h3>

      <div className="mb-3 flex gap-2">
        <button
          onClick={() => switchTab('memory')}
          className={`px-2 py-1 rounded text-xs ${
            tab === 'memory' ? 'bg-accent text-white' : 'bg-stone-100 text-stone-600'
          }`}
        >
          Memory
        </button>
        <button
          onClick={() => switchTab('prompt')}
          className={`px-2 py-1 rounded text-xs ${
            tab === 'prompt' ? 'bg-accent text-white' : 'bg-stone-100 text-stone-600'
          }`}
        >
          Last Prompt
        </button>
      </div>

      <div className="mb-3">
        <label className="block text-xs text-stone-500 mb-1">Agent:</label>
        <select
          value={selectedAgent}
          onChange={(e) => selectAgent(e.target.value)}
          className="w-full bg-white border border-border rounded px-2 py-1 text-stone-900 text-sm"
        >
          {gameState.agents.map(a => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      {loading && <p className="text-stone-500 text-sm">Loading...</p>}

      {tab === 'memory' && memories && (
        <div className="space-y-3">
          <div>
            <h4 className="text-sm font-semibold text-amber-800 mb-1">
              Short-term ({memories.short_term.length})
            </h4>
            <div className="space-y-1">
              {memories.short_term.map((m, i) => (
                <div
                  key={i}
                  className={`text-xs p-2 rounded ${memoryBoxClass(m.content, m.is_reflection)}`}
                >
                  <span className="text-stone-400 font-mono">[{m.timestamp}]</span>{' '}
                  <span className={memoryTextClass(m.content, m.is_reflection)}>{m.content}</span>
                </div>
              ))}
              {memories.short_term.length === 0 && (
                <p className="text-xs text-stone-400 italic">No short-term memories</p>
              )}
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-stone-700 mb-1">
              Long-term / RAG ({memories.long_term.length})
            </h4>
            <div className="space-y-1">
              {memories.long_term.map((m, i) => (
                <div key={i} className="text-xs bg-stone-50 border border-stone-200 p-2 rounded">
                  <span className="text-stone-400 font-mono">[{m.timestamp}]</span>{' '}
                  <span className="text-stone-700">{m.content}</span>
                </div>
              ))}
              {memories.long_term.length === 0 && (
                <p className="text-xs text-stone-400 italic">
                  No long-term memories yet. Overflowed short-term memories are stored here automatically.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'prompt' && (
        <div className="space-y-3">
          {!promptData && !loading && (
            <p className="text-xs text-stone-400 italic">
              No stored prompt yet. Run Step once after restart to capture prompts.
            </p>
          )}
          {promptData && (
            <>
              <p className="text-xs text-stone-500">
                Frame {promptData.frame} — free-form intention + God mapping
              </p>
              <div>
                <h4 className="text-sm font-semibold text-emerald-800 mb-1">System</h4>
                <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-stone-50 border border-border rounded p-2 text-stone-700 max-h-64 overflow-auto">
                  {promptData.system}
                </pre>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-stone-700 mb-1">User</h4>
                <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-stone-50 border border-border rounded p-2 text-stone-700">
                  {promptData.user}
                </pre>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-emerald-700 mb-1">Character response</h4>
                <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-emerald-50 border border-emerald-200 rounded p-2 text-emerald-900 max-h-48 overflow-auto">
                  {promptData.character_response || promptData.raw_response}
                </pre>
              </div>
              <div>
                <h4 className="text-sm font-semibold text-sky-800 mb-1">
                  God decision{promptData.god_kind ? ` (${promptData.god_kind})` : ''}
                </h4>
                <pre className="text-[11px] leading-relaxed whitespace-pre-wrap bg-sky-50 border border-sky-200 rounded p-2 text-sky-900 max-h-48 overflow-auto">
                  {[
                    promptData.god_reason ? `Reason: ${promptData.god_reason}` : null,
                    promptData.god_tool
                      ? `Tool: ${promptData.god_tool.tool}(${JSON.stringify(promptData.god_tool.args)})`
                      : 'Tool: (none)',
                    promptData.god_raw ? `Raw:\n${promptData.god_raw}` : null,
                  ]
                    .filter(Boolean)
                    .join('\n\n') || '(no god data)'}
                </pre>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
