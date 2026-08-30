interface Props {
  frame: number
  maxFrame: number
  gameTime: string
  day: number
  timeOfDay: string
  loading: boolean
  onStep: (steps: number) => void
  onExport: () => void
}

export function Timeline({
  frame, maxFrame, gameTime, day, timeOfDay, loading, onStep, onExport,
}: Props) {
  return (
    <div className="bg-panel border border-border rounded-lg p-3 flex items-center gap-3 shadow-sm">
      <div className="flex flex-col">
        <span className="text-xs text-stone-500">Frame</span>
        <span className="text-lg font-bold text-stone-900">{frame}</span>
      </div>

      <div className="h-10 w-px bg-border"></div>

      <div className="flex flex-col">
        <span className="text-xs text-stone-500">Game Time</span>
        <span className="text-lg font-bold text-amber-800">
          {gameTime} <span className="text-xs text-stone-500">Day {day}</span>
        </span>
        <span className="text-xs text-stone-500">{timeOfDay}</span>
      </div>

      <div className="flex-1 mx-4">
        <input
          type="range"
          min={0}
          max={Math.max(maxFrame, frame)}
          value={frame}
          readOnly
          className="w-full accent-accent"
        />
        <div className="flex justify-between text-xs text-stone-400">
          <span>Frame 0</span>
          <span>Current: {frame} / {Math.max(maxFrame, frame)}</span>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onStep(1)}
          disabled={loading}
          className="bg-accent hover:bg-stone-800 disabled:bg-stone-300 text-white px-4 py-2 rounded font-medium transition"
        >
          {loading ? '...' : 'Step +1'}
        </button>
        <button
          onClick={() => onStep(5)}
          disabled={loading}
          className="bg-stone-200 hover:bg-stone-300 disabled:bg-stone-100 text-stone-800 px-4 py-2 rounded font-medium transition"
        >
          +5
        </button>
        <button
          onClick={onExport}
          className="bg-stone-700 hover:bg-stone-800 text-white px-4 py-2 rounded font-medium transition"
        >
          Export
        </button>
      </div>
    </div>
  )
}
