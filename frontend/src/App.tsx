import { useState, useEffect } from 'react'
import { useGame } from './hooks/useGame'
import { GameSetup } from './components/GameSetup'
import { MapView } from './components/MapView'
import { AgentPanel } from './components/AgentPanel'
import { ChatLog } from './components/ChatLog'
import { MemoryInspector } from './components/MemoryInspector'
import { Timeline } from './components/Timeline'
import { Settings } from './components/Settings'

function App() {
  const game = useGame()
  const [stepCount, setStepCount] = useState(1)
  const [autoStep, setAutoStep] = useState(false)
  const [showSettings, setShowSettings] = useState(false)

  useEffect(() => {
    if (!autoStep || !game.gameState) return

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const runLoop = async () => {
      while (!cancelled) {
        await game.step(1)
        if (cancelled) break
        await new Promise<void>((resolve) => {
          timer = setTimeout(resolve, 3000)
        })
      }
    }

    runLoop()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [autoStep, game.gameId, game.step])

  if (!game.gameState) {
    return (
      <GameSetup
        getTemplate={game.getTemplate}
        createGame={game.createGame}
        listSaves={game.listSaves}
        continueSave={game.continueSave}
        importSave={game.importSave}
        deleteSave={game.deleteSave}
        clearAllSaves={game.clearAllSaves}
        setLLMConfig={game.setLLMConfig}
        getLLMConfig={game.getLLMConfig}
      />
    )
  }

  const handleStep = async (steps: number) => {
    setStepCount(steps)
    await game.step(steps)
  }

  const handleExport = () => {
    game.exportState()
  }

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* Header */}
      <header className="bg-white border-b border-border px-4 py-2 flex items-center justify-between">
        <h1 className="text-xl font-bold text-stone-900">
          Multi-Agent Graph World
        </h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-stone-600">
            <input
              type="checkbox"
              checked={autoStep}
              onChange={(e) => setAutoStep(e.target.checked)}
              className="accent-accent"
            />
            Auto-step (3s)
          </label>
          <button
            onClick={() => setShowSettings(true)}
            className="bg-stone-200 hover:bg-stone-300 text-stone-800 px-3 py-1 rounded text-sm"
          >
            API Config
          </button>
          <button
            onClick={async () => {
              setAutoStep(false)
              setShowSettings(false)
              await game.abandonGame()
            }}
            className="bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded text-sm"
          >
            New Game
          </button>
        </div>
      </header>

      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 overflow-auto">
          <div className="w-full max-w-2xl bg-white rounded-lg shadow-xl my-8">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h2 className="text-lg font-semibold text-stone-900">Model / API Configuration</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="text-stone-500 hover:text-stone-800 text-sm px-2 py-1"
              >
                Close
              </button>
            </div>
            <div className="p-4">
              <Settings
                onSave={async (config) => {
                  await game.setLLMConfig(config)
                }}
                getConfig={game.getLLMConfig}
              />
            </div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="p-3 pb-0">
        <Timeline
          frame={game.gameState.frame}
          maxFrame={game.gameState.frame}
          gameTime={game.gameState.game_time}
          day={game.gameState.day}
          timeOfDay={game.gameState.time_of_day}
          loading={game.loading}
          onStep={handleStep}
          onExport={handleExport}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 grid grid-cols-12 gap-3 p-3 overflow-hidden min-h-0">
        {/* Map View + Memory */}
        <div className="col-span-5 flex flex-col gap-3 min-h-0">
          <div className="flex-1 min-h-[280px]">
            <MapView
              map={game.gameState.map}
              agents={game.gameState.agents}
              objects={game.gameState.objects}
              currentFrame={game.gameState.frame}
            />
          </div>
          <div className="h-48 shrink-0">
            <MemoryInspector
              gameState={game.gameState}
              getAgentMemories={game.getAgentMemories}
              getAgentPrompt={game.getAgentPrompt}
            />
          </div>
        </div>

        {/* Agents Panel */}
        <div className="col-span-3 min-h-0">
          <AgentPanel
            agents={game.gameState.agents}
            map={game.gameState.map}
            objects={game.gameState.objects}
          />
        </div>

        {/* Chat Log */}
        <div className="col-span-4 min-h-0">
          <ChatLog logs={game.gameState.logs} />
        </div>
      </div>

      {/* Error display */}
      {game.error && (
        <div className="bg-red-50 border-t border-red-200 text-red-700 px-4 py-2 text-sm">
          Error: {game.error}
        </div>
      )}
    </div>
  )
}

export default App