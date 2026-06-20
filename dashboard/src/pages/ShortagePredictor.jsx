import { useState, useEffect } from 'react'
import { api } from '../api'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

function Badge({ tier }) {
  const cls = { CRITICAL: 'badge-critical', WARNING: 'badge-warning', WATCH: 'badge-watch', STABLE: 'badge-stable' }[tier] || 'badge-info'
  return <span className={`badge ${cls}`}>{tier}</span>
}

function ScorePill({ score }) {
  const color = score >= 70 ? '#f43f5e' : score >= 45 ? '#f59e0b' : score >= 25 ? '#8b5cf6' : '#10b981'
  return <span className="score-pill" style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>{score?.toFixed(0)}</span>
}

function MiniBar({ value, label }) {
  const color = value >= 70 ? '#f43f5e' : value >= 45 ? '#f59e0b' : value >= 25 ? '#8b5cf6' : '#10b981'
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>
        <span>{label}</span><span style={{ color, fontWeight: 700 }}>{value?.toFixed(0)}</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${value}%`, background: color }} />
      </div>
    </div>
  )
}

export default function ShortagePredictor() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('ALL')

  const load = () => {
    setLoading(true)
    api.predictShortage().then(d => {
      setData(d)
      setLoading(false)
    }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const tiers = ['ALL', 'CRITICAL', 'WARNING', 'WATCH', 'STABLE']
  const filtered = (data?.alerts || []).filter(a => filter === 'ALL' || a.risk_tier === filter)

  const summary = data ? {
    CRITICAL: data.critical,
    WARNING: data.warning,
    WATCH: data.watch,
    STABLE: data.stable,
  } : {}

  return (
    <div className="fade-in">
      {/* Summary KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'All Drugs', count: data.total_drugs, color: '#3b82f6' },
            { label: 'Critical', count: data.critical, color: '#f43f5e' },
            { label: 'Warning', count: data.warning, color: '#f59e0b' },
            { label: 'Watch', count: data.watch, color: '#8b5cf6' },
            { label: 'Stable', count: data.stable, color: '#10b981' },
          ].map(({ label, count, color }) => (
            <div key={label} className="kpi-card" style={{ '--accent': color }}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value" style={{ color, fontSize: 28 }}>{count}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="page-tabs" style={{ marginBottom: 16 }}>
        {tiers.map(t => (
          <button key={t} id={`tab-${t.toLowerCase()}`} className={`tab-btn ${filter === t ? 'active' : ''}`} onClick={() => setFilter(t)}>
            {t === 'ALL' ? '🔍 All' : t === 'CRITICAL' ? '🚨' : t === 'WARNING' ? '⚠️' : t === 'WATCH' ? '👁️' : '✅'} {t}
            {t !== 'ALL' && ` (${summary[t] || 0})`}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 18 }}>
        {/* Drug list */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">💊</span> Drug Shortage Predictions</div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Avg risk: <b style={{ color: 'var(--text-primary)' }}>{data?.avg_risk_score?.toFixed(1) || '—'}</b></span>
          </div>
          <div className="card-body" style={{ padding: 0, maxHeight: 520, overflowY: 'auto' }}>
            {loading ? <div style={{ padding: 20 }}><Skeleton h={300} /></div> : (
              <table className="data-table">
                <thead>
                  <tr><th>Drug</th><th>Category</th><th>Score</th><th>Tier</th><th>Action</th></tr>
                </thead>
                <tbody>
                  {filtered.map((a, i) => (
                    <tr key={i} onClick={() => setSelected(a)} style={{ cursor: 'pointer', background: selected?.drug_id === a.drug_id ? 'rgba(59,130,246,0.08)' : undefined }}>
                      <td>{a.drug_name}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{a.category}</td>
                      <td><ScorePill score={a.shortage_risk_score} /></td>
                      <td><Badge tier={a.risk_tier} /></td>
                      <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {a.recommended_action.replace(/^[^\w]+/, '')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div>
          {!selected ? (
            <div className="card">
              <div className="card-body">
                <div className="empty-state">
                  <div className="icon">💊</div>
                  <p>Click a drug to see signal breakdown</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="card fade-in">
              <div className="card-header">
                <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
                  <span style={{ fontSize: 14 }}>{selected.drug_name}</span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <Badge tier={selected.risk_tier} />
                    <span className="badge badge-info">{selected.criticality}</span>
                  </div>
                </div>
                <ScorePill score={selected.shortage_risk_score} />
              </div>
              <div className="card-body">
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>Signal breakdown (0 = safe, 100 = critical)</p>
                <MiniBar value={selected.demand_spike_score} label="Demand Spike (25%)" />
                <MiniBar value={selected.supply_concentration_score} label="Supply Concentration HHI (20%)" />
                <MiniBar value={selected.lead_time_stress_score} label="Lead Time Stress (20%)" />
                <MiniBar value={selected.inventory_runway_score} label="Inventory Runway (20%)" />
                <MiniBar value={selected.supplier_risk_overlay_score} label="Supplier Risk Overlay (15%)" />

                <div style={{
                  marginTop: 14, padding: '10px 12px',
                  background: 'rgba(255,255,255,0.03)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border)',
                  fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5
                }}>
                  {selected.recommended_action}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
