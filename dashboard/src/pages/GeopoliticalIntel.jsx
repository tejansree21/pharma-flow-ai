import { useState, useEffect } from 'react'
import { api } from '../api'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const ALERT_COLORS = {
  HIGH:   '#ef4444',
  MEDIUM: '#f59e0b',
  LOW:    '#f87171',
  CLEAR:  '#22c55e',
}

function AlertBadge({ level }) {
  const cls = {
    HIGH:   'badge-critical',
    MEDIUM: 'badge-warning',
    LOW:    'badge-watch',
    CLEAR:  'badge-stable',
  }[level] || 'badge-info'
  return <span className={`badge ${cls}`}>{level}</span>
}

function DataSourceBadge({ source }) {
  if (!source) return null
  const config = {
    live:      { label: '● Live data', color: '#22c55e', bg: 'rgba(34,197,94,0.1)',  border: 'rgba(34,197,94,0.25)' },
    mixed:     { label: '◐ Live + synthetic', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)', border: 'rgba(245,158,11,0.25)' },
    synthetic: { label: '○ Synthetic', color: '#9a9a9a', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)' },
  }[source] || { label: source, color: '#9a9a9a', bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.1)' }

  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: '2px 8px',
      borderRadius: 99, border: `1px solid ${config.border}`,
      background: config.bg, color: config.color,
    }}>
      {config.label}
    </span>
  )
}

function SourceTag({ source }) {
  const colors = {
    gdelt:      { label: 'GDELT',   color: '#ef4444' },
    fda_shortage:{ label: 'FDA',    color: '#f59e0b' },
    fda_warning: { label: 'FDA WL', color: '#f59e0b' },
    newsapi:    { label: 'NEWS',    color: '#60a5fa' },
    synthetic:  { label: 'SIM',    color: '#4a4a4a' },
  }[source] || { label: source?.toUpperCase()?.slice(0,6) || '?', color: '#4a4a4a' }

  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '1px 5px',
      borderRadius: 4, background: `${colors.color}22`,
      color: colors.color, border: `1px solid ${colors.color}44`,
      fontFamily: 'var(--mono)', flexShrink: 0,
    }}>
      {colors.label}
    </span>
  )
}

export default function GeopoliticalIntel() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [activeTab, setActiveTab] = useState('events')

  useEffect(() => {
    api.geopolitical().then(d => {
      setData(d)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const scatterData = (data?.supplier_alerts || []).map(s => ({
    x:       s.base_risk_score,
    y:       s.geo_intelligence_score,
    adj:     s.adjusted_risk_score,
    name:    s.supplier_name,
    country: s.country,
    level:   s.alert_level,
  }))

  const CustomDot = ({ cx, cy, payload }) => {
    const color = ALERT_COLORS[payload.level] || '#ef4444'
    return <circle cx={cx} cy={cy} r={5} fill={color} fillOpacity={0.85} stroke={color} strokeWidth={1} />
  }

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.[0]) return null
    const d = payload[0].payload
    return (
      <div style={{
        background: '#111', border: '1px solid rgba(239,68,68,0.2)',
        borderRadius: 8, padding: '10px 14px', fontSize: 12,
      }}>
        <p style={{ color: '#fff', fontWeight: 600 }}>{d.name}</p>
        <p style={{ color: '#9a9a9a' }}>{d.country}</p>
        <p style={{ color: '#9a9a9a' }}>Base: {d.x?.toFixed(0)} → Adjusted: {d.adj?.toFixed(0)}</p>
      </div>
    )
  }

  const dataSource = data?.data_source || 'synthetic'

  return (
    <div className="fade-in">

      {/* KPI strip */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
          <div className="kpi-card" style={{ '--accent': 'var(--red-600)' }}>
            <div className="kpi-label">Active Events</div>
            <div className="kpi-value" style={{ color: 'var(--red-400)' }}>{data.active_events}</div>
            <div className="kpi-sub">of {data.total_events} total</div>
          </div>
          <div className="kpi-card" style={{ '--accent': 'var(--red-700)' }}>
            <div className="kpi-label">Countries Affected</div>
            <div className="kpi-value" style={{ color: 'var(--red-400)' }}>{data.countries_affected}</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#f59e0b' }}>
            <div className="kpi-label">Suppliers on HIGH Alert</div>
            <div className="kpi-value" style={{ color: '#f59e0b' }}>{data.suppliers_on_high_alert}</div>
          </div>
          <div className="kpi-card" style={{ '--accent': 'var(--red-600)' }}>
            <div className="kpi-label">Most Dangerous Country</div>
            <div className="kpi-value" style={{ fontSize: 16, color: 'var(--red-400)' }}>
              {data.most_dangerous_country}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="page-tabs">
        {['events', 'countries', 'suppliers', 'map'].map(tab => (
          <button
            key={tab}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {{ events: '📡 Events', countries: '🌍 Country Risk', suppliers: '🏭 Supplier Alerts', map: '📊 Risk Map' }[tab]}
          </button>
        ))}
      </div>

      {/* Events tab */}
      {activeTab === 'events' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="icon">📡</span> Active Geopolitical Events
            </div>
            <DataSourceBadge source={dataSource} />
          </div>
          <div className="card-body" style={{ padding: 0, maxHeight: 480, overflowY: 'auto' }}>
            {loading ? (
              <div style={{ padding: 20 }}><Skeleton h={320} /></div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Event</th>
                    <th>Country</th>
                    <th>Days Ago</th>
                    <th>Score</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.top_events || []).map((ev, i) => (
                    <tr
                      key={i}
                      onClick={() => setSelectedEvent(ev)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td><SourceTag source={ev.source || 'synthetic'} /></td>
                      <td style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                        {ev.event_type?.replace(/_/g, ' ').toUpperCase()}
                      </td>
                      <td style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {ev.country}
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                        {ev.days_ago}d
                      </td>
                      <td>
                        <span style={{
                          fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 11,
                          color: ev.effective_score >= 50 ? '#ef4444' : '#f59e0b',
                        }}>
                          {ev.effective_score?.toFixed(1)}
                        </span>
                      </td>
                      <td style={{
                        fontSize: 11, color: 'var(--text-secondary)',
                        maxWidth: 280, overflow: 'hidden',
                        textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {ev.description}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Country risk tab */}
      {activeTab === 'countries' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">🌍</span> Country Risk Index</div>
            <DataSourceBadge source={dataSource} />
          </div>
          <div className="card-body">
            {loading ? <Skeleton h={320} /> : (
              <div className="country-list">
                {(data?.country_risk_index || []).slice(0, 12).map((c, i) => {
                  const color = c.combined_risk >= 65 ? '#ef4444'
                    : c.combined_risk >= 45 ? '#f59e0b'
                    : c.combined_risk >= 30 ? '#f87171'
                    : '#22c55e'
                  return (
                    <div key={i} className="country-row">
                      <span className="country-name">🌐 {c.country}</span>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${c.combined_risk}%`, background: color }} />
                      </div>
                      <span className="country-score" style={{ color }}>
                        {c.combined_risk?.toFixed(0)}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Suppliers tab */}
      {activeTab === 'suppliers' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">🏭</span> Supplier Geo Alerts</div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <DataSourceBadge source={dataSource} />
              {Object.entries(ALERT_COLORS).map(([level, color]) => (
                <span key={level} className="badge" style={{
                  background: `${color}22`, color,
                  border: `1px solid ${color}44`,
                }}>
                  {level}
                </span>
              ))}
            </div>
          </div>
          <div className="card-body" style={{ padding: 0, maxHeight: 480, overflowY: 'auto' }}>
            {loading ? (
              <div style={{ padding: 20 }}><Skeleton h={280} /></div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Supplier</th><th>Country</th>
                    <th>Base</th><th>→ Adjusted</th><th>Δ</th>
                    <th>Alert</th><th>Top Event</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.supplier_alerts || [])
                    .filter(s => s.alert_level !== 'CLEAR')
                    .map((s, i) => (
                      <tr key={i}>
                        <td>{s.supplier_name}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{s.country}</td>
                        <td style={{ fontFamily: 'var(--mono)' }}>{s.base_risk_score?.toFixed(0)}</td>
                        <td style={{
                          fontFamily: 'var(--mono)', fontWeight: 700,
                          color: s.adjusted_risk_score >= 65 ? '#ef4444' : '#f59e0b',
                        }}>
                          {s.adjusted_risk_score?.toFixed(0)}
                        </td>
                        <td style={{
                          fontFamily: 'var(--mono)', fontSize: 11,
                          color: s.risk_delta > 0 ? '#f59e0b' : '#22c55e',
                        }}>
                          {s.risk_delta > 0 ? '+' : ''}{s.risk_delta?.toFixed(1)}
                        </td>
                        <td><AlertBadge level={s.alert_level} /></td>
                        <td style={{
                          fontSize: 11, color: 'var(--text-muted)',
                          maxWidth: 200, overflow: 'hidden',
                          textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {s.top_event}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Scatter map tab */}
      {activeTab === 'map' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <span className="icon">📊</span> Supplier Risk Map — Base vs Geo-Adjusted
            </div>
            <DataSourceBadge source={dataSource} />
          </div>
          <div className="card-body">
            {loading ? <Skeleton h={280} /> : (
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis
                    dataKey="x" name="Base Risk" type="number" domain={[0, 100]}
                    tick={{ fill: '#4a4a4a', fontSize: 10 }}
                    label={{ value: 'Base Risk', fill: '#4a4a4a', fontSize: 10, dy: 14 }}
                  />
                  <YAxis
                    dataKey="y" name="Geo Score" type="number" domain={[0, 80]}
                    tick={{ fill: '#4a4a4a', fontSize: 10 }}
                    label={{ value: 'Geo Score', fill: '#4a4a4a', fontSize: 10, angle: -90, dx: -16 }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Scatter data={scatterData} shape={<CustomDot />} />
                </ScatterChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* Event detail modal */}
      {selectedEvent && (
        <div
          onClick={() => setSelectedEvent(null)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
            zIndex: 200, display: 'flex', alignItems: 'center',
            justifyContent: 'center', backdropFilter: 'blur(4px)',
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            className="card fade-in"
            style={{ width: 500, maxWidth: '90vw', border: '1px solid rgba(239,68,68,0.2)' }}
          >
            <div className="card-header">
              <div className="card-title">
                <SourceTag source={selectedEvent.source || 'synthetic'} />
                &nbsp;{selectedEvent.event_type?.replace(/_/g, ' ').toUpperCase()}
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}
              >
                ×
              </button>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Country</span>
                  <div style={{ fontWeight: 600 }}>{selectedEvent.country}</div>
                </div>
                <div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Date</span>
                  <div style={{ fontWeight: 600, fontFamily: 'var(--mono)' }}>{selectedEvent.event_date}</div>
                </div>
                <div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Severity</span>
                  <div style={{ fontWeight: 700, color: '#f59e0b' }}>{selectedEvent.severity?.toFixed(1)}</div>
                </div>
                <div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Effective Score</span>
                  <div style={{ fontWeight: 700, color: '#ef4444' }}>{selectedEvent.effective_score?.toFixed(1)}</div>
                </div>
              </div>
              <div style={{
                padding: '10px 12px',
                background: 'rgba(239,68,68,0.04)',
                borderRadius: 8,
                border: '1px solid rgba(239,68,68,0.12)',
                fontSize: 13, lineHeight: 1.6,
                color: 'var(--text-secondary)',
              }}>
                {selectedEvent.description}
              </div>
              {selectedEvent.source && selectedEvent.source !== 'synthetic' && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'right' }}>
                  Source: <span style={{ color: 'var(--text-secondary)' }}>{selectedEvent.source}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
