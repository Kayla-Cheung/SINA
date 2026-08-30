import { useMemo, useRef, useEffect, useState } from 'react'
import type { MapConfig, AgentState, GameObjectConfig } from '../types'

interface Props {
  map: MapConfig
  agents: AgentState[]
  objects: GameObjectConfig[]
  currentFrame: number
  width?: number
  height?: number
}

/** Fixed layout positions for known sandbox locations (normalized 0-1). */
const LAYOUT: Record<string, { x: number; y: number }> = {
  // SINA Sandbox (Vampire v3)
  loc_square: { x: 0.50, y: 0.42 },
  loc_park: { x: 0.28, y: 0.28 },
  loc_canteen: { x: 0.72, y: 0.28 },
  loc_market: { x: 0.28, y: 0.58 },
  loc_library: { x: 0.72, y: 0.58 },
  loc_kitchen: { x: 0.88, y: 0.38 },
  loc_sports: { x: 0.12, y: 0.18 },
  loc_theatre: { x: 0.18, y: 0.78 },
  loc_bedroom: { x: 0.88, y: 0.72 },
  loc_alley: { x: 0.50, y: 0.78 },
  // Legacy campus layout (kept for old saves)
  dormitory: { x: 0.18, y: 0.28 },
  classroom: { x: 0.55, y: 0.22 },
  library: { x: 0.82, y: 0.35 },
  cafeteria: { x: 0.35, y: 0.55 },
  garden: { x: 0.22, y: 0.78 },
  gym: { x: 0.72, y: 0.75 },
}

function edgeFrom(edge: any): string {
  return edge.from ?? edge.from_ ?? ''
}

export function MapView({ map, agents, objects }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 500, h: 420 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const update = () => {
      const rect = el.getBoundingClientRect()
      setSize({ w: Math.max(320, rect.width), h: Math.max(280, rect.height) })
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const positions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {}
    map.locations.forEach((loc, i) => {
      if (LAYOUT[loc.id]) {
        pos[loc.id] = LAYOUT[loc.id]
      } else {
        // Fallback circle layout for unknown locations
        const angle = (2 * Math.PI * i) / map.locations.length - Math.PI / 2
        pos[loc.id] = {
          x: 0.5 + 0.35 * Math.cos(angle),
          y: 0.5 + 0.35 * Math.sin(angle),
        }
      }
    })
    return pos
  }, [map.locations])

  const pad = 40
  const toPx = (id: string) => {
    const p = positions[id] || { x: 0.5, y: 0.5 }
    return {
      x: pad + p.x * (size.w - 2 * pad),
      y: pad + p.y * (size.h - 2 * pad),
    }
  }

  return (
    <div
      ref={containerRef}
      className="bg-panel border border-border rounded-lg overflow-hidden h-full w-full flex flex-col"
    >
      <div className="px-3 py-2 border-b border-border flex items-center justify-between bg-panel">
        <div>
          <span className="text-xs text-stone-400 uppercase tracking-wide">World Map</span>
          <h3 className="text-sm font-semibold text-stone-900">{map.name}</h3>
        </div>
        <span className="text-xs text-stone-500">
          {map.locations.length} locations · {map.edges.length} paths
        </span>
      </div>

      <div className="flex-1 min-h-0 relative">
        <svg width="100%" height="100%" viewBox={`0 0 ${size.w} ${size.h}`} className="block">
          {/* Edges */}
          {map.edges.map((edge, i) => {
            const a = toPx(edgeFrom(edge))
            const b = toPx(edge.to)
            const mx = (a.x + b.x) / 2
            const my = (a.y + b.y) / 2
            return (
              <g key={i}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke="#99f6e4"
                  strokeWidth={2}
                />
                <rect
                  x={mx - 22}
                  y={my - 9}
                  width={44}
                  height={16}
                  rx={4}
                  fill="#f0fdfa"
                  stroke="#ccfbf1"
                  opacity={0.95}
                />
                <text
                  x={mx}
                  y={my + 3}
                  textAnchor="middle"
                  fill="#0f766e"
                  fontSize={10}
                >
                  {edge.distance}m
                </text>
              </g>
            )
          })}

          {/* Nodes */}
          {map.locations.map(loc => {
            const p = toPx(loc.id)
            const here = agents.filter(a => a.current_location === loc.id)
            const objs = objects.filter(
              o => o.location === loc.id && !o.current_owner
            )
            return (
              <g key={loc.id}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={22}
                  fill="#ccfbf1"
                  stroke="#0d9488"
                  strokeWidth={2}
                />
                <text
                  x={p.x}
                  y={p.y + 4}
                  textAnchor="middle"
                  fill="#115e59"
                  fontSize={10}
                  fontWeight={600}
                >
                  {loc.name.length > 10 ? loc.name.slice(0, 9) + '…' : loc.name}
                </text>
                <text
                  x={p.x}
                  y={p.y + 36}
                  textAnchor="middle"
                  fill="#0f766e"
                  fontSize={11}
                  fontWeight={600}
                >
                  {loc.name}
                </text>
                {here.length > 0 && (
                  <>
                    <circle cx={p.x + 18} cy={p.y - 16} r={10} fill="#d97706" />
                    <text
                      x={p.x + 18}
                      y={p.y - 12}
                      textAnchor="middle"
                      fill="#fff"
                      fontSize={11}
                      fontWeight={700}
                    >
                      {here.length}
                    </text>
                    <text
                      x={p.x}
                      y={p.y + 50}
                      textAnchor="middle"
                      fill="#b45309"
                      fontSize={10}
                    >
                      {here.map(a => a.name).join(', ')}
                    </text>
                  </>
                )}
                {objs.length > 0 && here.length === 0 && (
                  <text
                    x={p.x}
                    y={p.y + 50}
                    textAnchor="middle"
                    fill="#a8a29e"
                    fontSize={9}
                  >
                    {objs.length} object{objs.length > 1 ? 's' : ''}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
    </div>
  )
}