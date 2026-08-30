import type { AgentState, GameObjectConfig, MapConfig } from '../types'

interface Props {
  agents: AgentState[]
  map: MapConfig
  objects: GameObjectConfig[]
}

export function AgentPanel({ agents, map, objects }: Props) {
  return (
    <div className="bg-panel border border-border rounded-lg p-3 h-full overflow-auto scrollbar-thin shadow-sm">
      <h3 className="text-md font-semibold text-stone-900 mb-2 sticky top-0 bg-panel pb-2 border-b border-border">
        Agents ({agents.length})
      </h3>
      <div className="space-y-2">
        {agents.map(agent => {
          const loc = map.locations.find(l => l.id === agent.current_location)
          const carriedObjects = objects.filter(
            o => o.current_owner === agent.id
          )
          return (
            <div
              key={agent.id}
              className="bg-stone-50 border border-stone-200 rounded p-2 text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-stone-900">{agent.name}</span>
                <span className="text-xs text-stone-500">
                  {loc?.name || agent.current_location}
                </span>
              </div>
              {agent.status && (
                <p className="text-xs text-emerald-700 mt-1 italic">
                  "{agent.status}"
                </p>
              )}
              {agent.daily_plan && (
                <div className="mt-2 pt-2 border-t border-stone-200">
                  <p className="text-xs text-stone-500 mb-1">
                    Today&apos;s plan{agent.daily_plan_day != null ? ` (Day ${agent.daily_plan_day})` : ''}:
                  </p>
                  <p className="text-xs text-emerald-800 whitespace-pre-wrap">
                    {agent.daily_plan.slice(0, 160)}
                    {agent.daily_plan.length > 160 ? '...' : ''}
                  </p>
                </div>
              )}
              {agent.short_term_memory.length > 0 && (
                <div className="mt-2 pt-2 border-t border-stone-200">
                  <p className="text-xs text-stone-500 mb-1">Last memory:</p>
                  <p className="text-xs text-amber-900">
                    <span className="text-stone-400 font-mono">[{agent.short_term_memory[0].timestamp}]</span>{' '}
                    {agent.short_term_memory[0].content.slice(0, 80)}
                    {agent.short_term_memory[0].content.length > 80 ? '...' : ''}
                  </p>
                </div>
              )}
              {(agent.inventory.length > 0 || carriedObjects.length > 0) && (
                <div className="mt-2 pt-2 border-t border-stone-200">
                  <p className="text-xs text-stone-500 mb-1">Carrying:</p>
                  <div className="flex flex-wrap gap-1">
                    {agent.inventory.map(item => (
                      <span key={item} className="text-xs bg-stone-200 text-stone-700 px-2 py-0.5 rounded">
                        {item}
                      </span>
                    ))}
                    {carriedObjects.map(obj => (
                      <span key={obj.id} className="text-xs bg-violet-100 text-violet-800 px-2 py-0.5 rounded">
                        {obj.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
