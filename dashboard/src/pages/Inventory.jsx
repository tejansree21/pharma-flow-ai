import { useState, useEffect } from 'react'
import { api } from '../api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

function Badge({ action }) {
  const cls = {
    REORDER_NOW: 'badge-critical', REORDER_SOON: 'badge-warning',
    ADEQUATE: 'badge-stable', EXCESS: 'badge-info'
  }[action] || 'badge-info'
  return <span className={`badge ${cls}`}>{action?.replace('_', ' ')}</span>
}

export default function Inventory() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('ALL')

  useEffect(() => {
    api.optimizeInventory().then(d => {
      setData(d)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const actions = ['ALL', 'REORDER_NOW', 'REORDER_SOON', 'ADEQUATE', 'EXCESS']
  const recs = (data?.recommendations || []).filter(r => filter === 'ALL' || r.action === filter)

  // Chart data — top 10 by urgency
  const chartData = [...(data?.recommendations || [])]
    .sort((a, b) => b.urgency_score - a.urgency_score)
    .slice(0, 10)
    .map(r => ({
      name: r.drug_name.split(' ')[0],
      days: r.days_cover,
      rop: r.reorder_point_kg,
      stock: r.current_stock_kg,
      action: r.action,
    }))

  const ACTION_COLOR = { REORDER_NOW: '#f43f5e', REORDER_SOON: '#f59e0b', ADEQUATE: '#10b981', EXCESS: '#3b82f6' }

  return (
    <div className="fade-in">
      {/* KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Total Drugs', val: data.total_drugs, color: '#3b82f6' },
            { label: 'Reorder Now', val: data.reorder_now, color: '#f43f5e' },
            { label: 'Reorder Soon', val: data.reorder_soon, color: '#f59e0b' },
            { label: 'Adequate', val: data.adequate, color: '#10b981' },
            { label: 'Excess', val: data.excess, color: '#06b6d4' },
            { label: 'Stock Value', val: `$${(data.total_stock_value_usd / 1e6).toFixed(1)}M`, color: '#8b5cf6' },
          ].map(({ label, val, color }) => (
            <div key={label} className="kpi-card" style={{ '--accent': color }}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value" style={{ color, fontSize: typeof val === 'string' ? 20 : 28 }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* Days cover chart */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-header">
          <div className="card-title"><span className="icon">📊</span> Days Cover — Top 10 Urgent Drugs</div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Avg cover: <b style={{ color: 'var(--text-primary)' }}>{data?.avg_days_cover?.toFixed(1) || '—'} days</b></span>
        </div>
        <div className="card-body">
          {loading ? <Skeleton h={200} /> : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: '#8ba4c8', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#8ba4c8', fontSize: 10 }} axisLine={false} tickLine={false} label={{ value: 'Days', fill: '#8ba4c8', fontSize: 10, angle: -90, dx: -12 }} />
                <Tooltip
                  contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  formatter={(val) => [`${val?.toFixed(1)} days`, 'Days Cover']}
                />
                <Bar dataKey="days" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={ACTION_COLOR[entry.action] || '#3b82f6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Critical reorders */}
      {(data?.critical_reorders || []).length > 0 && (
        <div className="card" style={{ marginBottom: 18, borderColor: 'rgba(244,63,94,0.3)', background: 'rgba(244,63,94,0.05)' }}>
          <div className="card-header" style={{ borderColor: 'rgba(244,63,94,0.2)' }}>
            <div className="card-title"><span className="icon">🚨</span> Critical Reorders Required</div>
          </div>
          <div className="card-body" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.critical_reorders.map((drug, i) => (
              <span key={i} className="badge badge-critical">{drug}</span>
            ))}
          </div>
        </div>
      )}

      {/* Filter + full table */}
      <div className="page-tabs" style={{ marginBottom: 14 }}>
        {actions.map(a => (
          <button key={a} className={`tab-btn ${filter === a ? 'active' : ''}`} onClick={() => setFilter(a)}>
            {a === 'ALL' ? '🔍 All' : a === 'REORDER_NOW' ? '🚨' : a === 'REORDER_SOON' ? '⚠️' : a === 'ADEQUATE' ? '✅' : '📦'} {a.replace('_', ' ')}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 18 }}>
        <div className="card">
          <div className="card-body" style={{ padding: 0, maxHeight: 420, overflowY: 'auto' }}>
            {loading ? <div style={{ padding: 20 }}><Skeleton h={300} /></div> : (
              <table className="data-table">
                <thead>
                  <tr><th>Drug</th><th>Category</th><th>Days Cover</th><th>EOQ (kg)</th><th>Safety Stock</th><th>Action</th></tr>
                </thead>
                <tbody>
                  {recs.map((r, i) => (
                    <tr key={i} onClick={() => setSelected(r)} style={{ cursor: 'pointer', background: selected?.drug_id === r.drug_id ? 'rgba(59,130,246,0.08)' : undefined }}>
                      <td>{r.drug_name}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{r.category}</td>
                      <td style={{ fontFamily: 'var(--mono)', color: r.days_cover < 30 ? '#f43f5e' : 'var(--text-secondary)' }}>
                        {r.days_cover?.toFixed(1)}
                      </td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{r.eoq_kg?.toFixed(0)}</td>
                      <td style={{ fontFamily: 'var(--mono)' }}>{r.safety_stock_kg?.toFixed(0)}</td>
                      <td><Badge action={r.action} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Detail */}
        <div>
          {!selected ? (
            <div className="card">
              <div className="card-body">
                <div className="empty-state"><div className="icon">📦</div><p>Click a drug for details</p></div>
              </div>
            </div>
          ) : (
            <div className="card fade-in">
              <div className="card-header">
                <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                  <span style={{ fontSize: 13 }}>{selected.drug_name}</span>
                  <Badge action={selected.action} />
                </div>
              </div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  ['Avg Daily Demand', `${selected.avg_daily_demand_kg?.toFixed(2)} kg`],
                  ['Avg Lead Time', `${selected.avg_lead_time_days?.toFixed(0)} days`],
                  ['Safety Stock', `${selected.safety_stock_kg?.toFixed(1)} kg`],
                  ['Reorder Point', `${selected.reorder_point_kg?.toFixed(1)} kg`],
                  ['EOQ', `${selected.eoq_kg?.toFixed(1)} kg`],
                  ['Current Stock', `${selected.current_stock_kg?.toFixed(1)} kg`],
                  ['Days Cover', `${selected.days_cover?.toFixed(1)} days`],
                  ['Urgency Score', `${selected.urgency_score?.toFixed(0)} / 100`],
                  ['Stock Value', `$${selected.stock_value_usd?.toLocaleString('en-US', { maximumFractionDigits: 0 })}`],
                ].map(([label, val]) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--text-muted)' }}>{label}</span>
                    <span style={{ fontWeight: 600, fontFamily: 'var(--mono)' }}>{val}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
