import { useState, useEffect } from 'react'
import { api } from '../api'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const TIER_CONFIG = {
  CRITICAL: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',  border: 'rgba(239,68,68,0.25)' },
  HIGH:     { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)' },
  MEDIUM:   { color: '#f87171', bg: 'rgba(248,113,113,0.06)', border: 'rgba(248,113,113,0.15)' },
  LOW:      { color: '#22c55e', bg: 'rgba(34,197,94,0.06)', border: 'rgba(34,197,94,0.15)' },
}

function TierBadge({ tier }) {
  const cfg = TIER_CONFIG[tier] || TIER_CONFIG.LOW
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`,
    }}>
      {tier}
    </span>
  )
}

function SignalBar({ label, score, max, color, detail }) {
  const pct = (score / max) * 100
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'var(--mono)', color }}>{score?.toFixed(1)}/{max}</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, lineHeight: 1.4 }}>{detail}</div>
    </div>
  )
}

export default function CounterfeitRisk() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter]   = useState('ALL')
  const [search, setSearch]   = useState('')

  useEffect(() => {
    api.counterfeitRisk()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const s = data?.summary || {}

  const filtered = (data?.supplier_risks || []).filter(r => {
    const matchesTier   = filter === 'ALL' || r.risk_tier === filter
    const matchesSearch = !search || r.supplier_name?.toLowerCase().includes(search.toLowerCase()) || r.country?.toLowerCase().includes(search.toLowerCase())
    return matchesTier && matchesSearch
  })

  return (
    <div className="fade-in">
      {/* Disclaimer */}
      <div style={{
        padding: '10px 16px', borderRadius: 8, marginBottom: 20,
        background: 'rgba(245,158,11,0.06)',
        border: '1px solid rgba(245,158,11,0.2)',
        fontSize: 12, color: '#f59e0b', lineHeight: 1.6,
      }}>
        <strong>⚠️ Important:</strong> Risk scores indicate signals warranting investigation — not confirmed counterfeit activity. Always verify via laboratory testing before taking action.
      </div>

      {/* KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Total Suppliers', val: s.total_suppliers, color: 'var(--text-primary)' },
            { label: 'Critical Risk',   val: s.critical_risk,  color: '#ef4444' },
            { label: 'High Risk',       val: s.high_risk,      color: '#f59e0b' },
            { label: 'Medium Risk',     val: s.medium_risk,    color: '#f87171' },
            { label: 'Low Risk',        val: s.low_risk,       color: '#22c55e' },
          ].map(({ label, val, color }) => (
            <div key={label} className="kpi-card" style={{ '--accent': color }}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value" style={{ color, fontSize: 26 }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <div className="page-tabs" style={{ flex: 'none', marginBottom: 0 }}>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(t => (
            <button key={t} className={`tab-btn ${filter === t ? 'active' : ''}`} onClick={() => setFilter(t)}>
              {t}
            </button>
          ))}
        </div>
        <input
          type="text"
          placeholder="Search suppliers…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 8, color: 'var(--text-primary)', fontFamily: 'var(--font)',
            fontSize: 12, padding: '7px 12px', outline: 'none',
          }}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 18, alignItems: 'start' }}>
        {/* Supplier table */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">🔍</span> Counterfeit Risk by Supplier</div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Click a supplier for signal breakdown</span>
          </div>
          <div style={{ maxHeight: 560, overflowY: 'auto' }}>
            {loading ? <div style={{ padding: 20 }}><Skeleton h={350} /></div> : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Supplier</th><th>Country</th>
                    <th>Risk Score</th><th>Tier</th>
                    <th>Price Anom.</th><th>Quality Drift</th>
                    <th>Regulatory</th><th>FDA</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => {
                    const tc = TIER_CONFIG[r.risk_tier] || TIER_CONFIG.LOW
                    return (
                      <tr
                        key={i}
                        onClick={() => setSelected(r)}
                        style={{
                          cursor: 'pointer',
                          background: selected?.supplier_id === r.supplier_id
                            ? `${tc.color}08` : undefined,
                        }}
                      >
                        <td>{r.supplier_name}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{r.country}</td>
                        <td>
                          <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: tc.color }}>
                            {r.counterfeit_risk_score?.toFixed(0)}
                          </span>
                        </td>
                        <td><TierBadge tier={r.risk_tier} /></td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: r.price_anomaly_score > 15 ? '#ef4444' : 'var(--text-muted)' }}>
                          {r.price_anomaly_score?.toFixed(0)}/35
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: r.quality_drift_score > 15 ? '#ef4444' : 'var(--text-muted)' }}>
                          {r.quality_drift_score?.toFixed(0)}/30
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: r.regulatory_risk_score > 10 ? '#f59e0b' : 'var(--text-muted)' }}>
                          {r.regulatory_risk_score?.toFixed(0)}/20
                        </td>
                        <td>
                          <span style={{ color: r.fda_approved ? '#22c55e' : '#ef4444', fontSize: 13, fontWeight: 700 }}>
                            {r.fda_approved ? '✓' : '✗'}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
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
                  <div className="icon">🔍</div>
                  <p>Click a supplier to see risk signal breakdown</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="card fade-in" style={{ border: `1px solid ${TIER_CONFIG[selected.risk_tier]?.border || 'rgba(255,255,255,0.07)'}` }}>
              <div className="card-header">
                <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                  <span>{selected.supplier_name}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{selected.country}</span>
                  <TierBadge tier={selected.risk_tier} />
                </div>
                <span style={{
                  fontSize: 28, fontWeight: 800, fontFamily: 'var(--mono)',
                  color: TIER_CONFIG[selected.risk_tier]?.color || '#9a9a9a',
                }}>
                  {selected.counterfeit_risk_score?.toFixed(0)}
                </span>
              </div>
              <div className="card-body">
                <SignalBar
                  label="Price anomaly"
                  score={selected.price_anomaly_score}
                  max={35} color="#ef4444"
                  detail={selected.price_anomaly_detail}
                />
                <SignalBar
                  label="Quality drift"
                  score={selected.quality_drift_score}
                  max={30} color="#f59e0b"
                  detail={selected.quality_drift_detail}
                />
                <SignalBar
                  label="Regulatory posture"
                  score={selected.regulatory_risk_score}
                  max={20} color="#f87171"
                  detail={selected.regulatory_detail}
                />
                <SignalBar
                  label="Incident history"
                  score={selected.incident_risk_score}
                  max={15} color="#a78bfa"
                  detail={selected.incident_detail}
                />

                <div style={{
                  marginTop: 14, padding: '10px 12px',
                  borderRadius: 8,
                  background: `${TIER_CONFIG[selected.risk_tier]?.color || '#9a9a9a'}0a`,
                  border: `1px solid ${TIER_CONFIG[selected.risk_tier]?.border || 'rgba(255,255,255,0.07)'}`,
                  fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
                }}>
                  <strong style={{ color: TIER_CONFIG[selected.risk_tier]?.color }}>Recommendation: </strong>
                  {selected.recommendation}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
