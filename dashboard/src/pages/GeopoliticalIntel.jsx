import { useState, useEffect } from 'react'
import { api } from '../api'
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const ALERT_COLORS = { HIGH: '#f43f5e', MEDIUM: '#f59e0b', LOW: '#8b5cf6', CLEAR: '#10b981' }

function AlertBadge({ level }) {
  const cls = { HIGH: 'badge-critical', MEDIUM: 'badge-warning', LOW: 'badge-watch', CLEAR: 'badge-stable' }[level] || 'badge-info'
  return <span className={`badge ${cls}`}>{level}</span>
}

export default function GeopoliticalIntel() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedEvent, setSelectedEvent] = useState(null)

  useEffect(() => {
    api.geopolitical().then(d => {
      setData(d)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const scatterData = (data?.supplier_alerts || []).map(s => ({
    x: s.base_risk_score,
    y: s.geo_intelligence_score,
    adj: s.adjusted_risk_score,
    name: s.supplier_name,
    country: s.country,
    level: s.alert_level,
  }))

  const CustomDot = (props) => {
    const { cx, cy, payload } = props
    const color = ALERT_COLORS[payload.level] || '#3b82f6'
    return <circle cx={cx} cy={cy} r={5} fill={color} fillOpacity={0.8} stroke={color} strokeWidth={1} />
  }

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.[0]) return null
    const d = payload[0].payload
    return (
      <div style={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
        <p style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{d.name}</p>
        <p style={{ color: '#8ba4c8' }}>{d.country}</p>
        <p style={{ color: '#8ba4c8' }}>Base: {d.x?.toFixed(0)} → Adjusted: {d.adj?.toFixed(0)}</p>
      </div>
    )
  }

  return (
    <div className="fade-in">
      {/* Summary KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14, marginBottom: 20 }}>
          <div className="kpi-card" style={{ '--accent': '#3b82f6' }}>
            <div className="kpi-label">Active Events</div>
            <div className="kpi-value" style={{ color: '#3b82f6' }}>{data.active_events}</div>
            <div className="kpi-sub">of {data.total_events} total</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#f43f5e' }}>
            <div className="kpi-label">Countries Affected</div>
            <div className="kpi-value" style={{ color: '#f43f5e' }}>{data.countries_affected}</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#f59e0b' }}>
            <div className="kpi-label">Suppliers on HIGH Alert</div>
            <div className="kpi-value" style={{ color: '#f59e0b' }}>{data.suppliers_on_high_alert}</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#8b5cf6' }}>
            <div className="kpi-label">Most Dangerous Country</div>
            <div className="kpi-value" style={{ fontSize: 16, color: '#8b5cf6' }}>{data.most_dangerous_country}</div>
          </div>
        </div>
      )}

      <div className="dashboard-grid">
        {/* Active Events */}
        <div className="card col-span-1">
          <div className="card-header">
            <div className="card-title"><span className="icon">📡</span> Active Geopolitical Events</div>
          </div>
          <div className="card-body" style={{ padding: 0, maxHeight: 380, overflowY: 'auto' }}>
            {loading ? <div style={{ padding: 20 }}><Skeleton h={280} /></div> : (
              <table className="data-table">
                <thead>
                  <tr><th>Event</th><th>Country</th><th>Days Ago</th><th>Score</th></tr>
                </thead>
                <tbody>
                  {(data?.top_events || []).map((ev, i) => (
                    <tr key={i} onClick={() => setSelectedEvent(ev)} style={{ cursor: 'pointer' }}>
                      <td style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 11 }}>
                        {ev.event_type.replace(/_/g, ' ').toUpperCase()}
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>{ev.country}</td>
                      <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>{ev.days_ago}d</td>
                      <td>
                        <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 11, color: ev.effective_score >= 50 ? '#f43f5e' : '#f59e0b' }}>
                          {ev.effective_score?.toFixed(1)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Country Risk Index */}
        <div className="card col-span-1">
          <div className="card-header">
            <div className="card-title"><span className="icon">🌍</span> Country Risk Index</div>
          </div>
          <div className="card-body">
            {loading ? <Skeleton h={260} /> : (
              <div className="country-list">
                {(data?.country_risk_index || []).slice(0, 8).map((c, i) => {
                  const pct = c.combined_risk / 100
                  const color = c.combined_risk >= 65 ? '#f43f5e' : c.combined_risk >= 45 ? '#f59e0b' : c.combined_risk >= 30 ? '#8b5cf6' : '#10b981'
                  return (
                    <div key={i} className="country-row">
                      <span className="country-name">🌐 {c.country}</span>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${c.combined_risk}%`, background: color }} />
                      </div>
                      <span className="country-score" style={{ color }}>{c.combined_risk?.toFixed(0)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Supplier Risk Scatter */}
        <div className="card col-span-2">
          <div className="card-header">
            <div className="card-title"><span className="icon">📊</span> Supplier Risk Map — Base vs Geo-Adjusted</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {Object.entries(ALERT_COLORS).map(([level, color]) => (
                <span key={level} className="badge" style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>{level}</span>
              ))}
            </div>
          </div>
          <div className="card-body">
            {loading ? <Skeleton h={220} /> : (
              <ResponsiveContainer width="100%" height={220}>
                <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="x" name="Base Risk" type="number" domain={[0, 100]} tick={{ fill: '#8ba4c8', fontSize: 10 }} label={{ value: 'Base Risk', fill: '#8ba4c8', fontSize: 10, dy: 14 }} />
                  <YAxis dataKey="y" name="Geo Score" type="number" domain={[0, 80]} tick={{ fill: '#8ba4c8', fontSize: 10 }} label={{ value: 'Geo Score', fill: '#8ba4c8', fontSize: 10, angle: -90, dx: -16 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Scatter data={scatterData} shape={<CustomDot />} />
                </ScatterChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Supplier Alert Table */}
        <div className="card col-span-2">
          <div className="card-header">
            <div className="card-title"><span className="icon">🏭</span> Supplier Geo Alerts</div>
          </div>
          <div className="card-body" style={{ padding: 0, maxHeight: 320, overflowY: 'auto' }}>
            {loading ? <div style={{ padding: 20 }}><Skeleton h={200} /></div> : (
              <table className="data-table">
                <thead>
                  <tr><th>Supplier</th><th>Country</th><th>Base</th><th>→ Adjusted</th><th>Δ</th><th>Alert</th><th>Top Event</th></tr>
                </thead>
                <tbody>
                  {(data?.supplier_alerts || []).filter(s => s.alert_level !== 'CLEAR').map((s, i) => (
                    <tr key={i}>
                      <td>{s.supplier_name}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{s.country}</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{s.base_risk_score?.toFixed(0)}</td>
                      <td style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: s.adjusted_risk_score >= 65 ? '#f43f5e' : '#f59e0b' }}>
                        {s.adjusted_risk_score?.toFixed(0)}
                      </td>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: s.risk_delta > 0 ? '#f59e0b' : '#10b981' }}>
                        {s.risk_delta > 0 ? '+' : ''}{s.risk_delta?.toFixed(1)}
                      </td>
                      <td><AlertBadge level={s.alert_level} /></td>
                      <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {s.top_event}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Event detail modal */}
      {selectedEvent && (
        <div
          onClick={() => setSelectedEvent(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}
        >
          <div onClick={e => e.stopPropagation()} className="card fade-in" style={{ width: 480, maxWidth: '90vw' }}>
            <div className="card-header">
              <div className="card-title">📡 {selectedEvent.event_type.replace(/_/g, ' ').toUpperCase()}</div>
              <button onClick={() => setSelectedEvent(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}>×</button>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Country</span><div style={{ fontWeight: 600 }}>{selectedEvent.country}</div></div>
                <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Date</span><div style={{ fontWeight: 600, fontFamily: 'var(--mono)' }}>{selectedEvent.event_date}</div></div>
                <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Severity</span><div style={{ fontWeight: 700, color: '#f59e0b' }}>{selectedEvent.severity?.toFixed(1)}</div></div>
                <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Effective Score</span><div style={{ fontWeight: 700, color: '#f43f5e' }}>{selectedEvent.effective_score?.toFixed(1)}</div></div>
              </div>
              <div style={{ padding: '10px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                {selectedEvent.description}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
