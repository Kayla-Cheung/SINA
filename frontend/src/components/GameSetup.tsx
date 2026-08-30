import { useState, useEffect, useRef } from 'react'
import { Settings } from './Settings'
import type { LLMConfig, MapConfig, AgentConfig, GameObjectConfig } from '../types'
import type { SaveInfo } from '../hooks/useGame'

interface Props {
  getTemplate: () => Promise<{ map: MapConfig; agents: AgentConfig[]; objects: GameObjectConfig[] }>
  createGame: (
    map: MapConfig,
    agents: AgentConfig[],
    objects: GameObjectConfig[],
    startTime?: string,
  ) => Promise<string | undefined>
  listSaves: () => Promise<{ saves: SaveInfo[] }>
  continueSave: (gameId: string) => Promise<string | undefined>
  importSave: (payload: unknown) => Promise<string | undefined>
  deleteSave: (gameId: string) => Promise<unknown>
  clearAllSaves: () => Promise<unknown>
  setLLMConfig: (config: LLMConfig) => Promise<unknown>
  getLLMConfig: () => Promise<{ success: boolean; config: LLMConfig }>
}

export function GameSetup({
  getTemplate,
  createGame,
  listSaves,
  continueSave,
  importSave,
  deleteSave,
  clearAllSaves,
  setLLMConfig,
  getLLMConfig,
}: Props) {
  const [template, setTemplate] = useState<{
    map: MapConfig
    agents: AgentConfig[]
    objects: GameObjectConfig[]
  } | null>(null)
  const [saves, setSaves] = useState<SaveInfo[]>([])
  const [startTime, setStartTime] = useState('08:00')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const refreshSaves = async () => {
    try {
      const data = await listSaves()
      setSaves(data.saves || [])
    } catch (e: any) {
      setError(e.message)
    }
  }

  useEffect(() => {
    getTemplate().then(setTemplate).catch((e: any) => setError(e.message))
    refreshSaves()
  }, [getTemplate, listSaves])

  const handleCreate = async () => {
    if (!template) return
    setBusy(true)
    setError(null)
    try {
      await createGame(template.map, template.agents, template.objects, startTime)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleContinue = async (id: string) => {
    setBusy(true)
    setError(null)
    try {
      await continueSave(id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm(`Delete save ${id}? This also removes that game's long-term memories.`)) return
    setBusy(true)
    setError(null)
    try {
      await deleteSave(id)
      await refreshSaves()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleClearAll = async () => {
    if (!confirm('Clear ALL saves and ALL long-term memories? This cannot be undone.')) return
    setBusy(true)
    setError(null)
    try {
      await clearAllSaves()
      await refreshSaves()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const handleImportFile = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      const text = await file.text()
      const payload = JSON.parse(text)
      await importSave(payload)
    } catch (e: any) {
      setError(e.message || 'Invalid save file')
    } finally {
      setBusy(false)
    }
  }

  const handleSaveConfig = async (config: LLMConfig) => {
    await setLLMConfig(config)
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto p-6">
      <h1 className="text-3xl font-bold text-stone-900">Multi-Agent Graph World</h1>

      <Settings onSave={handleSaveConfig} getConfig={getLLMConfig} />

      <div className="bg-panel border border-border rounded-lg p-4 space-y-3 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-stone-900">Continue Saved Game</h2>
          <button
            onClick={handleClearAll}
            disabled={busy || saves.length === 0}
            className="text-xs text-red-600 hover:text-red-500 disabled:opacity-40"
          >
            Clear all saves
          </button>
        </div>

        {saves.length === 0 && (
          <p className="text-sm text-stone-500">No saves yet. Games autosave after each step.</p>
        )}

        <div className="space-y-2 max-h-64 overflow-auto">
          {saves.map((s) => (
            <div
              key={s.game_id}
              className="flex items-center justify-between gap-2 bg-stone-50 border border-stone-200 rounded px-3 py-2"
            >
              <div className="text-sm text-stone-800 min-w-0">
                <div className="font-mono text-stone-700">{s.game_id}</div>
                <div className="text-xs text-stone-500 truncate">
                  Frame {s.frame} · history {s.frame_count ?? 0} snapshots · {s.game_time} · Day {s.day}
                  {s.saved_at ? ` · saved ${s.saved_at}` : ''}
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleContinue(s.game_id)}
                  disabled={busy}
                  className="bg-accent hover:bg-stone-800 disabled:bg-stone-300 text-white px-3 py-1 rounded text-sm"
                >
                  Continue
                </button>
                <button
                  onClick={() => handleDelete(s.game_id)}
                  disabled={busy}
                  className="bg-stone-200 hover:bg-stone-300 text-stone-700 px-2 py-1 rounded text-sm"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="pt-2 border-t border-border">
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) handleImportFile(f)
              e.target.value = ''
            }}
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="w-full bg-stone-200 hover:bg-stone-300 disabled:bg-stone-100 text-stone-800 py-2 rounded text-sm"
          >
            Import save JSON…
          </button>
        </div>
      </div>

      <div className="bg-panel border border-border rounded-lg p-4 space-y-3 shadow-sm">
        <h2 className="text-lg font-semibold text-stone-900">Start New Game</h2>

        {template && (
          <div className="text-sm text-stone-700 space-y-1">
            <p><strong>Map:</strong> {template.map.name}</p>
            <p><strong>Locations:</strong> {template.map.locations.length}</p>
            <p><strong>Agents:</strong> {template.agents.map(a => a.name).join(', ')}</p>
            <p><strong>Objects:</strong> {template.objects.length}</p>
          </div>
        )}

        {!template && !error && (
          <p className="text-sm text-stone-500">Loading template...</p>
        )}

        <div>
          <label className="block text-sm text-stone-500 mb-1">Start Time (HH:MM)</label>
          <input
            type="text"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="w-full bg-white border border-border rounded px-3 py-2 text-stone-900 text-sm"
          />
        </div>

        <button
          onClick={handleCreate}
          disabled={!template || busy}
          className="w-full bg-emerald-700 hover:bg-emerald-800 disabled:bg-stone-300 text-white py-2 rounded font-medium transition"
        >
          {busy ? 'Working...' : 'Create Game'}
        </button>

        {error && <p className="text-red-600 text-sm">{error}</p>}
      </div>
    </div>
  )
}
