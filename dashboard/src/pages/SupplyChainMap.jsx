import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const TIER_CONFIG = {
  0: { color: '#ef4444', bg: 'rgba(239,68,68,0.15)', label: 'Your Company',   size: 56 },
  1: { color: '#f87171', bg: 'rgba(248,113,113,0.1)', label: 'Tier 1 — Direct Suppliers',    size: 40 },
  2: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', label: 'Tier 2 — Chemical Manufacturers', size: 34 },
  3: { color: '#60a5fa', bg: 'rgba(96,165,250,0.1)', label: 'Tier 3 — Feedstock Sources',  size: 28 },
}

const RISK_COLORS = { CRITICAL: '#ef4444', HIGH: '#f59e0b', MEDIUM: '#f87171', LOW: '#22c55e' }

function RiskBadge({ level }) {
  const c = RISK_COLORS[level] || '#9a9a9a'
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
      background: `${c}18`, color: c, border: `1px solid ${c}30` }}>
      {level}
    </span>
  )
}

// Simple SVG tree renderer
function NetworkTree({ nodes, edges, onNodeClick, selectedNode }) {
  const TIER_X  = { 0: 50, 1: 25, 2: 50, 3: 75 }  // % x position per tier
  const CANVAS_W = 900
  const CANVAS_H = 600

  // Position nodes
  const tierGroups = [0,1,2,3].map(tier => nodes.filter(n => n.tier === tier))
  const positioned = []

  tierGroups.forEach((group, tier) => {
    const x = (TIER_X[tier] / 100) * CANVAS_W
    group.forEach((node, i) => {
      const y = ((i + 1) / (group.length + 1)) * CANVAS_H
      positioned.push({ ...node, x, y })
    })
  })

  const posMap = Object.fromEntries(positioned.map(n => [n.id, { x: n.x, y: n.y }]))

  // Only draw edges for visible nodes
  const visibleIds = new Set(positioned.map(n => n.id))
  const visEdges   = edges.filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))

  return (
    <svg width="100%" viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} style={{ overflow: 'visible' }}>
      <defs>
        {[1,2,3].map(tier => (
          <marker key={tier} id={`arrow${tier}`} markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill={TIER_CONFIG[tier]?.color || '#9a9a9a'} opacity={0.4} />
          </marker>
        ))}
      </defs>

      {/* Edges */}
      {visEdges.map((e, i) => {
        const s = posMap[e.source]
        const t = posMap[e.target]
        if (!s || !t) return null
        const color = TIER_CONFIG[e.tier]?.color || '#9a9a9a'
        return (
          <line key={i}
            x1={s.x} y1={s.y} x2={t.x} y2={t.y}
            stroke={color} strokeOpacity={0.25} strokeWidth={1}
            markerEnd={`url(#arrow${e.tier})`}
          />
        )
      })}

      {/* Nodes */}
      {positioned.map(node => {
        const cfg  = TIER_CONFIG[node.tier] || TIER_CONFIG[1]
        const r    = cfg.size / 2
        const sel  = selectedNode?.id === node.id
        const risk = node.risk_score
        const fill = node.type === 'root' ? '#dc2626'
          : risk >= 65 ? '#ef4444'
          : risk >= 45 ? '#f59e0b'
          : node.tier === 2 ? '#f59e0b'
          : node.tier === 3 ? '#60a5fa'
          : '#f87171'

        return (
          <g key={node.id} onClick={() => onNodeClick(node)} style={{ cursor: 'pointer' }}>
            <circle
              cx={node.x} cy={node.y} r={sel ? r + 4 : r}
              fill={fill} fillOpacity={0.85}
              stroke={sel ? '#fff' : 'rgba(255,255,255,0.2)'}
              strokeWidth={sel ? 2.5 : 1}
            />
            {node.tier <= 1 && (
              <text
                x={node.x} y={node.y - r - 4}
                textAnchor="middle" fontSize={9} fill="rgba(255,255,255,0.7)"
              >
                {node.label?.split(' ')[0]}
              </text>
            )}
            {node.type === 'root' && (
              <text x={node.x} y={node.y + 4} textAnchor="middle" fontSize={10} fill="#fff" fontWeight="700">
                You
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

export default function SupplyChainMap() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab]         = useState('map')
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    api.supplyChainMap()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const s = data?.summary || {}

  return (
    <div className="fade-in">
      {/* KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Tier 1 Suppliers',      val: s.tier1_suppliers,     color: '#f87171' },
            { label: 'Tier 2 Manufacturers',   val: s.tier2_manufacturers, color: '#f59e0b' },
            { label: 'Tier 3 Feedstock',       val: s.tier3_feedstock,     color: '#60a5fa' },
            { label: 'Concentration Risks',    val: s.concentration_risks, color: '#ef4444' },
            { label: 'Countries Exposed',      val: s.countries_exposed,   color: '#a78bfa' },
          ].map(({ label, val, color }) => (
            <div key={label} className="kpi-card" style={{ '--accent': color }}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value" style={{ color, fontSize: 22 }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        {[0,1,2,3].map(tier => {
          const cfg = TIER_CONFIG[tier]
          return (
            <div key={tier} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
              <div style={{ width: 12, height: 12, borderRadius: '50%', background: cfg.color }} />
              <span style={{ color: 'var(--text-secondary)' }}>{cfg.label}</span>
            </div>
          )
        })}
      </div>

      <div className="page-tabs">
        <button className={`tab-btn ${tab === 'map' ? 'active' : ''}`} onClick={() => setTab('map')}>🗺️ Network Map</button>
        <button className={`tab-btn ${tab === 'risks' ? 'active' : ''}`} onClick={() => setTab('risks')}>⚠️ Concentration Risks</button>
        <button className={`tab-btn ${tab === 'exposure' ? 'active' : ''}`} onClick={() => setTab('exposure')}>🌍 Country Exposure</button>
      </div>

      {/* Map tab */}
      {tab === 'map' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 18 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">
                <span className="icon">🗺️</span> 3-Tier Supply Chain Network
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Click any node for details</span>
            </div>
            <div className="card-body" style={{ padding: 12 }}>
              {loading ? <Skeleton h={400} /> : (
                <NetworkTree
                  nodes={data?.nodes || []}
                  edges={data?.edges || []}
                  onNodeClick={setSelected}
                  selectedNode={selected}
                />
              )}
            </div>
          </div>

          {/* Node detail */}
          <div>
            {!selected ? (
              <div className="card">
                <div className="card-body">
                  <div className="empty-state">
                    <div className="icon">🗺️</div>
                    <p>Click a node to see details</p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="card fade-in">
                <div className="card-header">
                  <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                    <span style={{ fontSize: 13 }}>{selected.label}</span>
                    <span style={{
                      fontSize: 10, padding: '2px 6px', borderRadius: 4,
                      background: `${TIER_CONFIG[selected.tier]?.color}20`,
                      color: TIER_CONFIG[selected.tier]?.color,
                      border: `1px solid ${TIER_CONFIG[selected.tier]?.color}30`,
                    }}>
                      Tier {selected.tier}
                    </span>
                  </div>
                </div>
                <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    ['Country',   selected.country],
                    ['Type',      selected.type],
                    ['Specialty', selected.specialty],
                    ['Material',  selected.material],
                    ['Risk Score', selected.risk_score != null ? `${selected.risk_score}/100` : null],
                    ['FDA Approved', selected.fda_approved != null ? (selected.fda_approved ? 'Yes ✓' : 'No ✗') : null],
                  ].filter(([_, v]) => v != null).map(([label, val]) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 6 }}>
                      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                      <span style={{ fontWeight: 600 }}>{val}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Concentration risks */}
      {tab === 'risks' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {loading ? <Skeleton h={300} /> : (data?.concentration_risks || []).length === 0 ? (
            <div className="card"><div className="card-body"><div className="empty-state"><div className="icon">✅</div><p>No concentration risks detected</p></div></div></div>
          ) : (
            (data?.concentration_risks || []).map((r, i) => {
              const color = RISK_COLORS[r.risk_level] || '#9a9a9a'
              return (
                <div key={i} className="card" style={{ borderColor: `${color}30` }}>
                  <div className="card-header">
                    <div className="card-title">
                      <RiskBadge level={r.risk_level} />
                      <span style={{ marginLeft: 8 }}>{r.shared_node_name}</span>
                    </div>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                      Tier {r.shared_node_tier} · {r.shared_node_country}
                    </span>
                  </div>
                  <div className="card-body">
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 12 }}>
                      {r.description}
                    </p>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {r.tier1_supplier_names.map((name, j) => (
                        <span key={j} style={{
                          fontSize: 10, padding: '2px 8px', borderRadius: 4,
                          background: 'rgba(239,68,68,0.08)',
                          border: '1px solid rgba(239,68,68,0.2)',
                          color: '#f87171',
                        }}>
                          {name}
                        </span>
                      ))}
                    </div>
                    <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
                      {r.num_affected} suppliers affected · {r.pct_of_portfolio}% of portfolio
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Country exposure */}
      {tab === 'exposure' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">🌍</span> Country Exposure (all tiers)</div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Highest: <strong style={{ color: 'var(--text-primary)' }}>{s.highest_exposure_country}</strong>
            </span>
          </div>
          <div className="card-body">
            {loading ? <Skeleton h={280} /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(data?.country_exposure || []).map((c, i) => {
                  const maxNodes = data.country_exposure[0]?.node_count || 1
                  const pct = (c.node_count / maxNodes) * 100
                  const color = c.node_count >= 4 ? '#ef4444' : c.node_count >= 2 ? '#f59e0b' : '#22c55e'
                  return (
                    <div key={i} className="country-row">
                      <span className="country-name">🌐 {c.country}</span>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
                      </div>
                      <span className="country-score" style={{ color }}>{c.node_count}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
