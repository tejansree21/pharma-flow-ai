import { useState, useEffect } from 'react'
import { api } from '../api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const ESG_TIER_CONFIG = {
  A: { color: '#22c55e', label: 'A — Leading'  },
  B: { color: '#60a5fa', label: 'B — Good'     },
  C: { color: '#f59e0b', label: 'C — Adequate' },
  D: { color: '#ef4444', label: 'D — Poor'     },
}

function ESGTierBadge({ tier }) {
  const cfg = ESG_TIER_CONFIG[tier] || ESG_TIER_CONFIG.D
  return (
    <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: `${cfg.color}18`, color: cfg.color, border: `1px solid ${cfg.color}30` }}>
      {cfg.label}
    </span>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#111', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <p style={{ color: '#9a9a9a', marginBottom: 4 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || '#fff', fontWeight: 600 }}>{p.name}: {typeof p.value === 'number' ? p.value.toFixed(1) : p.value}</p>
      ))}
    </div>
  )
}

export default function ESGScoring() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [tab, setTab]         = useState('overview')

  useEffect(() => {
    api.esgScores()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const s = data?.summary || {}

  const chartData = (data?.supplier_scores || [])
    .slice(0, 15)
    .map(s => ({
      name:  s.supplier_name?.split(' ')[0],
      env:   s.environmental_score,
      soc:   s.social_score,
      gov:   s.governance_score,
      total: s.esg_total_score,
      tier:  s.esg_tier,
    }))
    .reverse()

  const co2Chart = (data?.top_emitters || []).map(s => ({
    name:   s.supplier_name?.split(' ')[0],
    co2:    Math.round(s.scope3_kg_co2 / 1000),  // tonnes
    country: s.country,
  }))

  return (
    <div className="fade-in">
      {/* KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Avg ESG Score',    val: `${s.avg_esg_score?.toFixed(0)}/100`, color: '#22c55e' },
            { label: 'Tier A',           val: s.tier_a, color: '#22c55e' },
            { label: 'Tier B',           val: s.tier_b, color: '#60a5fa' },
            { label: 'Tier C/D',         val: (s.tier_c || 0) + (s.tier_d || 0), color: '#f59e0b' },
            { label: 'Scope 3 Emissions',val: `${s.total_scope3_tonnes_co2?.toFixed(0)}t CO₂`, color: '#ef4444' },
          ].map(({ label, val, color }) => (
            <div key={label} className="kpi-card" style={{ '--accent': color }}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value" style={{ color, fontSize: typeof val === 'string' ? 18 : 26 }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      <div className="page-tabs">
        <button className={`tab-btn ${tab === 'overview' ? 'active' : ''}`} onClick={() => setTab('overview')}>📊 ESG Scores</button>
        <button className={`tab-btn ${tab === 'carbon' ? 'active' : ''}`} onClick={() => setTab('carbon')}>🌱 Carbon / Scope 3</button>
      </div>

      {tab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 18 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {/* Stacked bar chart */}
            <div className="card">
              <div className="card-header">
                <div className="card-title"><span className="icon">📊</span> ESG Breakdown by Supplier (top 15)</div>
                <div style={{ display: 'flex', gap: 12 }}>
                  {[['#22c55e','Environmental'],['#60a5fa','Social'],['#a78bfa','Governance']].map(([c,l]) => (
                    <span key={l} style={{ fontSize: 10, color: c, display: 'flex', alignItems: 'center', gap: 4 }}>
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: c, display: 'inline-block' }} />
                      {l}
                    </span>
                  ))}
                </div>
              </div>
              <div className="card-body">
                {loading ? <Skeleton h={280} /> : (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                      <XAxis type="number" domain={[0,100]} tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="name" tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} width={60} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="env" stackId="a" name="Environmental (0-40)" fill="#22c55e" radius={[0,0,0,0]} />
                      <Bar dataKey="soc" stackId="a" name="Social (0-30)" fill="#60a5fa" />
                      <Bar dataKey="gov" stackId="a" name="Governance (0-30)" fill="#a78bfa" radius={[2,2,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            {/* Full table */}
            <div className="card">
              <div style={{ maxHeight: 360, overflowY: 'auto' }}>
                {loading ? <div style={{ padding: 20 }}><Skeleton h={260} /></div> : (
                  <table className="data-table">
                    <thead>
                      <tr><th>Supplier</th><th>Country</th><th>Total</th><th>Env</th><th>Social</th><th>Gov</th><th>ESG Tier</th></tr>
                    </thead>
                    <tbody>
                      {(data?.supplier_scores || []).map((s, i) => (
                        <tr key={i} onClick={() => setSelected(s)} style={{ cursor: 'pointer', background: selected?.supplier_id === s.supplier_id ? 'rgba(34,197,94,0.05)' : undefined }}>
                          <td>{s.supplier_name}</td>
                          <td style={{ color: 'var(--text-muted)', fontSize: 11 }}>{s.country}</td>
                          <td style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: s.esg_total_score >= 75 ? '#22c55e' : s.esg_total_score >= 60 ? '#60a5fa' : s.esg_total_score >= 45 ? '#f59e0b' : '#ef4444' }}>
                            {s.esg_total_score?.toFixed(0)}
                          </td>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#22c55e' }}>{s.environmental_score?.toFixed(0)}</td>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#60a5fa' }}>{s.social_score?.toFixed(0)}</td>
                          <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: '#a78bfa' }}>{s.governance_score?.toFixed(0)}</td>
                          <td><ESGTierBadge tier={s.esg_tier} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>

          {/* Detail panel */}
          <div>
            {!selected ? (
              <div className="card">
                <div className="card-body"><div className="empty-state"><div className="icon">🌱</div><p>Click a supplier for ESG details</p></div></div>
              </div>
            ) : (
              <div className="card fade-in">
                <div className="card-header">
                  <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                    <span style={{ fontSize: 13 }}>{selected.supplier_name}</span>
                    <ESGTierBadge tier={selected.esg_tier} />
                  </div>
                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 800, fontSize: 24, color: selected.esg_total_score >= 75 ? '#22c55e' : selected.esg_total_score >= 60 ? '#60a5fa' : '#f59e0b' }}>
                    {selected.esg_total_score?.toFixed(0)}
                  </span>
                </div>
                <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    ['Environmental (0–40)', selected.environmental_score, '#22c55e', 40],
                    ['Social (0–30)',         selected.social_score,        '#60a5fa', 30],
                    ['Governance (0–30)',     selected.governance_score,    '#a78bfa', 30],
                  ].map(([label, score, color, max]) => (
                    <div key={label} style={{ marginBottom: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                        <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, color }}>{score?.toFixed(1)}/{max}</span>
                      </div>
                      <div className="progress-bar">
                        <div className="progress-fill" style={{ width: `${(score/max)*100}%`, background: color }} />
                      </div>
                    </div>
                  ))}
                  <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '4px 0' }} />
                  {[
                    ['Country',         selected.country],
                    ['Transport',       `${selected.primary_transport} (${selected.distance_km?.toLocaleString()} km)`],
                    ['Annual volume',   `${selected.annual_volume_kg?.toLocaleString()} kg`],
                    ['Scope 3 CO₂',    `${(selected.scope3_kg_co2/1000).toFixed(1)} t`],
                  ].map(([label, val]) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 6 }}>
                      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{val}</span>
                    </div>
                  ))}
                  <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)', fontSize: 11, color: '#f59e0b', marginTop: 4 }}>
                    ⚠ {selected.key_esg_risk}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'carbon' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">🌱</span> Top 5 Scope 3 Emitters (tonnes CO₂)</div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Total: <strong style={{ color: '#ef4444' }}>{s.total_scope3_tonnes_co2?.toFixed(0)} t CO₂/yr</strong>
              </span>
            </div>
            <div className="card-body">
              {loading ? <Skeleton h={200} /> : (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={co2Chart} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}t`} />
                    <Tooltip content={<CustomTooltip />} formatter={(v) => [`${v}t CO₂`, 'Scope 3 emissions']} />
                    <Bar dataKey="co2" name="Scope 3 (t CO₂)" radius={[4,4,0,0]}>
                      {co2Chart.map((_, i) => <Cell key={i} fill={['#ef4444','#f59e0b','#f87171','#fca5a5','#fcd34d'][i] || '#ef4444'} fillOpacity={0.85} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div className="card">
              <div className="card-header"><div className="card-title"><span className="icon">📏</span> Scope 3 Methodology</div></div>
              <div className="card-body" style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div><strong style={{ color: 'var(--text-primary)' }}>Shipping emissions:</strong> volume (tonnes) × distance (km) × transport emission factor (kg CO₂/tonne-km)</div>
                <div><strong style={{ color: 'var(--text-primary)' }}>Manufacturing emissions:</strong> volume (kg) × category manufacturing intensity factor</div>
                <div><strong style={{ color: 'var(--text-primary)' }}>Transport factors:</strong> Air: 0.60 · Sea: 0.016 · Road: 0.10 · Rail: 0.03 (kg CO₂/tonne-km)</div>
                <div style={{ padding: '8px 10px', borderRadius: 6, background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.12)', fontSize: 11, color: '#f59e0b', marginTop: 4 }}>
                  Estimates based on synthetic volume and distance proxies. In production, connect to actual shipment data for GHG Protocol Scope 3 Category 1 compliance.
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-header"><div className="card-title"><span className="icon">📋</span> Regulatory Context</div></div>
              <div className="card-body" style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div><strong style={{ color: '#ef4444' }}>EU CSRD:</strong> Mandatory Scope 3 reporting for large EU companies from FY2024 onwards</div>
                <div><strong style={{ color: '#f59e0b' }}>SEC Climate Rules:</strong> Proposed Scope 3 disclosure for US public companies (pending final rule)</div>
                <div><strong style={{ color: '#60a5fa' }}>GHG Protocol:</strong> Category 1 (purchased goods) and Category 4 (upstream transport) most relevant for pharma procurement</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
