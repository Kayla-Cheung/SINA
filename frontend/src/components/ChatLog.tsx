import type { FrameLog } from '../types'

interface Props {
  logs: FrameLog[]
}

/** Color event lines: actions vs dialogue vs idle vs errors. */
function eventClass(event: string): string {
  const e = event.trim()
  if (
    e.startsWith('[WASTED]') ||
    e.startsWith('[REJECTED]') ||
    e.startsWith('[ERROR]') ||
    e.startsWith('[CHAT DECLINED]')
  ) {
    return 'text-red-600'
  }
  if (e.startsWith('[IDLE]')) {
    return 'text-stone-500 italic'
  }
  if (e.startsWith('Time advanced') || e.includes('Game initialized') || e.includes('Game restored')) {
    return 'text-stone-400'
  }
  // Dialogue / chat transcript lines
  if (e.startsWith('  ') || /^[A-Za-z][\w ]+: /.test(e)) {
    return 'text-violet-700'
  }
  if (
    e.includes(' walked ') ||
    e.includes(' talked ') ||
    e.includes(' interacted ')
  ) {
    return 'text-emerald-700 font-medium'
  }
  return 'text-stone-700'
}

export function ChatLog({ logs }: Props) {
  const allEvents = logs.flatMap(log =>
    log.events.map(e => ({ frame: log.frame, time: log.game_time, event: e }))
  ).reverse()

  return (
    <div className="bg-panel border border-border rounded-lg p-3 h-full overflow-auto scrollbar-thin shadow-sm">
      <h3 className="text-md font-semibold text-stone-900 mb-2 sticky top-0 bg-panel pb-2 border-b border-border">
        Event Log
      </h3>
      <div className="mb-2 flex flex-wrap gap-3 text-[10px] text-stone-500">
        <span><span className="text-emerald-700 font-medium">■</span> action</span>
        <span><span className="text-violet-700">■</span> chat</span>
        <span><span className="text-stone-500 italic">■</span> idle</span>
        <span><span className="text-red-600">■</span> wasted / declined</span>
      </div>
      <div className="space-y-1 text-xs">
        {allEvents.length === 0 ? (
          <p className="text-stone-400 italic">No events yet. Step the simulation to begin.</p>
        ) : (
          allEvents.map((entry, idx) => (
            <div key={idx} className="flex gap-2">
              <span className="text-stone-400 font-mono whitespace-nowrap">
                [{entry.time}]
              </span>
              <span className={eventClass(entry.event)}>{entry.event}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
