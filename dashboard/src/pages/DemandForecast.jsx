import { useState, useEffect } from 'react'
import { api } from '../api'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const TREND_CONFIG = {
  SPIKE:   { color: '#ef4444', label: 'Demand Spike',  icon: '🔴' },
  RISING:  { color: '#f59e0b', label: 'Rising',        icon: '🟡' },
  STABLE:  { color: '#22c55e', label: 'Stable',        icon: '🟢' },
  FALLING: { color: '#60a5fa', label: 'Falling',       icon: '🔵' },
}

const SEVERITY_CONFIG = {
  HIGH:   { color: '#ef4444', bg: 'rgba(239,68,68,0.08)',  border: 'rgba(239,68,68,0.2)' },
  MEDIUM: { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)' },
  LOW:    { color: '#9a9a9a', bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.08)' },
}

function DataSourceBadge({ sources }) {
  if (!sources?.length) return null
  const isLive = sources.some(s => s !== 'seasonal_model')
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {sources.map((s, i) => {
        const config = {
          who_dons:      { label: 'WHO DONS', color: '#ef4444' },
          cdc_ili:       { label: 'CDC ILI',  color: '#f59e0b' },
          seasonal_model:{ label: 'Seasonal model', color: '#9a9a9a' },
        }[s] || { label: s, color: '#9a9a9a' }
        return (
          <span key={i} style={{
            fontSize: 10, fontWeight: 600, padding: '2px 7px',
            borderRadius: 4, background: `${config.color}18`,
            color: config.color, border: `1px solid ${config.color}30`,
            fontFamily: 'var(--mono)',
          }}>
            {config.label}
          </span>
        )
      })}
    </div>
  )
}

export default function DemandForecast() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    api.demandForecast()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const s = data?.summary || {}

  // Prepare bar chart data from drug forecasts
  const barData = (data?.drug_forecasts || [])
    .slice(0, 12)
    .map(d => ({
      name: d.drug_name?.split(' ')[0],
      score: d.total_demand_score,
      base: d.base_demand_score,
      trend: d.trend,
    }))

  // ILI chart data
  const iliData = (data?.ili_signals || [])
    .slice(0, 26)
    .reverse()
    .map(r => ({
      week: r.week?.slice(0, 7),
      signal: r.demand_signal,
      ili: r.ili_pct,
    }))

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div style={{
        background: '#111', border: '1px solid rgba(239,68,68,0.2)',
        borderRadius: 8, padding: '10px 14px', fontSize: 12,
      }}>
        <p style={{ color: '#9a9a9a', marginBottom: 4 }}>{label}</p>
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color, fontWeight: 600 }}>
            {p.name}: {p.value?.toFixed(1)}
          </p>
        ))}
      </div>
    )
  }

  return (
    <div className="fade-in">
      {/* KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
          <div className="kpi-card" style={{ '--accent': '#ef4444' }}>
            <div className="kpi-label">Demand Spikes</div>
            <div className="kpi-value" style={{ color: '#ef4444' }}>{s.demand_spikes_detected || 0}</div>
            <div className="kpi-sub">Drugs at spike level</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#f59e0b' }}>
            <div className="kpi-label">Rising Demand</div>
            <div className="kpi-value" style={{ color: '#f59e0b' }}>{s.rising_demand || 0}</div>
            <div className="kpi-sub">Drugs trending up</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#ef4444' }}>
            <div className="kpi-label">WHO Alerts</div>
            <div className="kpi-value" style={{ color: '#ef4444' }}>{s.active_who_alerts || 0}</div>
            <div className="kpi-sub">Active outbreaks mapped</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#f59e0b' }}>
            <div className="kpi-label">ILI Flu Signal</div>
            <div className="kpi-value" style={{
              fontSize: 20,
              color: (s.latest_ili_signal || 0) > 60 ? '#ef4444'
                : (s.latest_ili_signal || 0) > 30 ? '#f59e0b' : '#22c55e',
            }}>
              {s.latest_ili_signal != null ? `${s.latest_ili_signal?.toFixed(0)}%` : 'N/A'}
            </div>
            <div className="kpi-sub">Current CDC ILI index</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="page-tabs">
        <button className={`tab-btn ${tab === 'overview' ? 'active' : ''}`} onClick={() => setTab('overview')}>
          📊 Drug Demand Index
        </button>
        <button className={`tab-btn ${tab === 'flu' ? 'active' : ''}`} onClick={() => setTab('flu')}>
          🦠 Flu Surveillance
        </button>
        <button className={`tab-btn ${tab === 'outbreaks' ? 'active' : ''}`} onClick={() => setTab('outbreaks')}>
          🌍 WHO Outbreaks
        </button>
      </div>

      {/* Drug demand index */}
      {tab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">📊</span> Drug Demand Score by Drug</div>
              <DataSourceBadge sources={data?.data_sources} />
            </div>
            <div className="card-body">
              {loading ? <Skeleton h={220} /> : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="score" name="Demand score" radius={[4, 4, 0, 0]}>
                      {barData.map((entry, i) => (
                        <Cell key={i} fill={TREND_CONFIG[entry.trend]?.color || '#9a9a9a'} fillOpacity={0.8} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
              {!loading && (
                <div style={{ display: 'flex', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
                  {Object.entries(TREND_CONFIG).map(([k, v]) => (
                    <span key={k} style={{ fontSize: 11, color: v.color, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 10, height: 10, borderRadius: 2, background: v.color, display: 'inline-block' }} />
                      {v.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">💊</span> Per-drug demand breakdown</div>
            </div>
            <div style={{ maxHeight: 360, overflowY: 'auto' }}>
              {loading ? <div style={{ padding: 20 }}><Skeleton h={260} /></div> : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Drug</th>
                      <th>Category</th>
                      <th>Base Score</th>
                      <th>Outbreak Boost</th>
                      <th>Total Score</th>
                      <th>Trend</th>
                      <th>Signals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.drug_forecasts || []).map((d, i) => {
                      const tc = TREND_CONFIG[d.trend] || TREND_CONFIG.STABLE
                      return (
                        <tr key={i}>
                          <td>{d.drug_name}</td>
                          <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{d.category}</td>
                          <td style={{ fontFamily: 'var(--mono)' }}>{d.base_demand_score?.toFixed(0)}</td>
                          <td style={{ fontFamily: 'var(--mono)', color: d.outbreak_boost > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
                            {d.outbreak_boost > 0 ? `+${d.outbreak_boost?.toFixed(0)}` : '—'}
                          </td>
                          <td>
                            <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: tc.color }}>
                              {d.total_demand_score?.toFixed(0)}
                            </span>
                          </td>
                          <td>
                            <span style={{
                              fontSize: 10, fontWeight: 600, padding: '2px 6px',
                              borderRadius: 4, background: `${tc.color}18`, color: tc.color,
                              border: `1px solid ${tc.color}30`,
                            }}>
                              {tc.icon} {d.trend}
                            </span>
                          </td>
                          <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {d.signal_sources?.join('; ') || '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Flu surveillance */}
      {tab === 'flu' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">🦠</span> CDC Influenza-Like Illness Surveillance</div>
              <DataSourceBadge sources={['cdc_ili']} />
            </div>
            <div className="card-body">
              {loading ? <Skeleton h={240} /> : iliData.length === 0 ? (
                <div className="empty-state">
                  <div className="icon">📡</div>
                  <p>CDC ILI data unavailable — check network or CDC API status</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={iliData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="iliGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="week" tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} interval={4} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="signal" name="ILI demand signal" stroke="#ef4444" strokeWidth={2} fill="url(#iliGrad)" dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">💉</span> Flu Season → Antiviral Demand Mapping</div>
            </div>
            <div className="card-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, fontSize: 13 }}>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>When flu signal is HIGH</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {['Oseltamivir (Tamiflu)', 'Amantadine', 'Zanamivir', 'Ibuprofen', 'Acetaminophen'].map((d, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
                        <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>{d}</span>
                        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#ef4444', fontWeight: 600 }}>+40–80% demand</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 10 }}>Key flu season months</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 4 }}>
                    {['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((m, i) => {
                      const isFlu = [0,1,2,3,10,11].includes(i)
                      return (
                        <div key={m} style={{
                          padding: '6px 4px', textAlign: 'center', borderRadius: 6,
                          background: isFlu ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.03)',
                          border: `1px solid ${isFlu ? 'rgba(239,68,68,0.25)' : 'rgba(255,255,255,0.06)'}`,
                          fontSize: 10, fontWeight: isFlu ? 700 : 400,
                          color: isFlu ? '#ef4444' : 'var(--text-muted)',
                        }}>
                          {m}
                        </div>
                      )
                    })}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>
                    Red = peak flu season (Northern Hemisphere)
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* WHO Outbreaks */}
      {tab === 'outbreaks' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">🌍</span> WHO Disease Outbreak Alerts → Drug Demand</div>
            <DataSourceBadge sources={['who_dons']} />
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            {loading ? (
              <div style={{ padding: 20 }}><Skeleton h={320} /></div>
            ) : (data?.who_alerts || []).length === 0 ? (
              <div className="empty-state">
                <div className="icon">✅</div>
                <p>No active WHO outbreak alerts mapped to formulary drugs</p>
                <p style={{ fontSize: 11, marginTop: 4 }}>WHO DONS feed may be unavailable — check connectivity</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {(data?.who_alerts || []).map((alert, i) => {
                  const cfg = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.LOW
                  return (
                    <div key={i} style={{
                      padding: '14px 20px',
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      background: cfg.bg,
                      transition: 'background 0.15s',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                        <div style={{
                          padding: '3px 8px', borderRadius: 4, flexShrink: 0,
                          background: cfg.bg, border: `1px solid ${cfg.border}`,
                          fontSize: 10, fontWeight: 700, color: cfg.color,
                        }}>
                          {alert.severity}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                            {alert.outbreak}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
                            Published {alert.published} · {alert.days_ago}d ago · Signal strength: {(alert.signal_strength * 100).toFixed(0)}%
                          </div>
                          {alert.affected_drugs?.length > 0 && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>→ Affects:</span>
                              {alert.affected_drugs.map((d, j) => (
                                <span key={j} style={{
                                  fontSize: 10, padding: '1px 7px', borderRadius: 4,
                                  background: 'rgba(239,68,68,0.12)',
                                  border: '1px solid rgba(239,68,68,0.2)',
                                  color: '#f87171', fontWeight: 600,
                                }}>
                                  {d}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        {alert.link && (
                          <a
                            href={alert.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              fontSize: 10, color: 'var(--text-muted)',
                              textDecoration: 'none', flexShrink: 0,
                              padding: '4px 8px', borderRadius: 6,
                              border: '1px solid rgba(255,255,255,0.07)',
                            }}
                          >
                            WHO ↗
                          </a>
                        )}
                      </div>
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
