import { useState, useEffect } from 'react'
import { api } from '../api'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

function Badge({ tier }) {
  const cls = {
    High: 'badge-critical', Moderate: 'badge-warning',
    Low: 'badge-stable', Critical: 'badge-critical',
    'LOW': 'badge-stable', 'MODERATE': 'badge-warning', 'HIGH': 'badge-critical', 'CRITICAL': 'badge-critical'
  }[tier] || 'badge-info'
  return <span className={`badge ${cls}`}>{tier}</span>
}

function ScoreBar({ value, max = 100 }) {
  const color = value >= 65 ? '#f43f5e' : value >= 45 ? '#f59e0b' : value >= 25 ? '#8b5cf6' : '#10b981'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="progress-bar" style={{ flex: 1 }}>
        <div className="progress-fill" style={{ width: `${(value / max) * 100}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 700, color, fontFamily: 'var(--mono)', width: 24 }}>{value?.toFixed(0)}</span>
    </div>
  )
}

export default function SupplierRisk() {
  const [suppliers, setSuppliers] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.suppliers().then(s => {
      const sorted = [...s].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
      setSuppliers(sorted)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const selectSupplier = (sup) => {
    setSelected(sup)
    setDetailLoading(true)
    api.supplierRisk(sup.id).then(d => {
      setDetail(d)
      setDetailLoading(false)
    }).catch(() => setDetailLoading(false))
  }

  const filtered = suppliers.filter(s =>
    s.name?.toLowerCase().includes(search.toLowerCase()) ||
    s.country?.toLowerCase().includes(search.toLowerCase())
  )

  const radarData = detail ? [
    { metric: 'Delivery', value: detail.delivery_risk },
    { metric: 'Quality', value: detail.quality_risk },
    { metric: 'Incident', value: detail.incident_risk },
    { metric: 'Geo/Reg', value: detail.geo_regulatory_risk },
  ] : []

  return (
    <div className="fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 18, alignItems: 'start' }}>
      {/* Supplier table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span className="icon">🏭</span> Supplier Risk Registry</div>
          <input
            type="text"
            placeholder="Search suppliers…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
              fontFamily: 'var(--font)', fontSize: 12, padding: '5px 10px', outline: 'none'
            }}
          />
        </div>
        <div className="card-body" style={{ padding: 0, maxHeight: 560, overflowY: 'auto' }}>
          {loading ? <div style={{ padding: 20 }}><Skeleton h={300} /></div> : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th>Country</th>
                  <th>Region</th>
                  <th>Risk Score</th>
                  <th>Tier</th>
                  <th>FDA</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => (
                  <tr
                    key={i}
                    onClick={() => selectSupplier(s)}
                    style={{ cursor: 'pointer', background: selected?.id === s.id ? 'rgba(59,130,246,0.08)' : undefined }}
                  >
                    <td>{s.name}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{s.country}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{s.region}</td>
                    <td><ScoreBar value={s.risk_score || 0} /></td>
                    <td>{s.risk_tier ? <Badge tier={s.risk_tier} /> : '—'}</td>
                    <td>
                      <span style={{ color: s.fda_approved ? '#10b981' : '#f43f5e', fontSize: 13 }}>
                        {s.fda_approved ? '✓' : '✗'}
                      </span>
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
                <div className="icon">🏭</div>
                <p>Click a supplier to see detailed risk breakdown</p>
              </div>
            </div>
          </div>
        ) : detailLoading ? (
          <div className="card"><div className="card-body"><Skeleton h={300} /></div></div>
        ) : detail && (
          <div className="card fade-in">
            <div className="card-header">
              <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                <span style={{ fontSize: 14 }}>{detail.supplier_name}</span>
                <Badge tier={detail.risk_tier} />
              </div>
              <span style={{ fontSize: 24, fontWeight: 800, fontFamily: 'var(--mono)', color: detail.risk_score >= 65 ? '#f43f5e' : detail.risk_score >= 45 ? '#f59e0b' : '#10b981' }}>
                {detail.risk_score?.toFixed(0)}
              </span>
            </div>
            <div className="card-body">
              {/* Radar chart */}
              <ResponsiveContainer width="100%" height={180}>
                <RadarChart data={radarData}>
                  <PolarGrid stroke="rgba(255,255,255,0.08)" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: '#8ba4c8', fontSize: 11 }} />
                  <Radar dataKey="value" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.2} />
                  <Tooltip contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                </RadarChart>
              </ResponsiveContainer>

              {/* Subscores */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
                {[
                  { label: 'Delivery Risk', value: detail.delivery_risk },
                  { label: 'Quality Risk', value: detail.quality_risk },
                  { label: 'Incident Risk', value: detail.incident_risk },
                  { label: 'Geo/Regulatory', value: detail.geo_regulatory_risk },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
                    </div>
                    <ScoreBar value={value} />
                  </div>
                ))}
              </div>

              <div style={{
                marginTop: 14, padding: '10px 12px',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border)',
                fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5
              }}>
                {detail.recommendation}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
