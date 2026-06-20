import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'

// ── Helpers ──────────────────────────────────────────────────────────────────

function ScorePill({ score }) {
  const color = score >= 70 ? '#f43f5e' : score >= 45 ? '#f59e0b' : score >= 25 ? '#8b5cf6' : '#10b981'
  return (
    <span className="score-pill" style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>
      {score.toFixed(0)}
    </span>
  )
}

function Badge({ tier }) {
  const cls = {
    CRITICAL: 'badge-critical', WARNING: 'badge-warning',
    WATCH: 'badge-watch', STABLE: 'badge-stable',
    High: 'badge-critical', Moderate: 'badge-warning',
    Low: 'badge-stable', Critical: 'badge-critical',
  }[tier] || 'badge-info'
  return <span className={`badge ${cls}`}>{tier}</span>
}

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const TIER_COLOR = { CRITICAL: '#f43f5e', WARNING: '#f59e0b', WATCH: '#8b5cf6', STABLE: '#10b981' }

// ── KPI Card ─────────────────────────────────────────────────────────────────

function KPICard({ label, value, sub, accent, icon }) {
  return (
    <div className="kpi-card fade-in" style={{ '--accent': accent }}>
      <div className="kpi-label">{icon} {label}</div>
      <div className="kpi-value" style={{ color: accent ? undefined : 'var(--cyan-400)' }}>{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  )
}

// ── Overview Page ─────────────────────────────────────────────────────────────

export default function Overview() {
  const [summary, setSummary] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, a] = await Promise.all([api.dashboardSummary(), api.alerts()])
      setSummary(s)
      setAlerts(a)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return (
    <div className="fade-in">
      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        {Array(6).fill(0).map((_, i) => <div key={i} className="kpi-card"><Skeleton h={60} /></div>)}
      </div>
    </div>
  )

  const s = summary || {}
  const alertList = (alerts?.alerts || []).slice(0, 8)

  // Build shortage tier data
  const shortage = s.shortage_alerts || []
  const tierCounts = { CRITICAL: 0, WARNING: 0, WATCH: 0, STABLE: 0 }
  shortage.forEach(a => tierCounts[a.risk_tier] = (tierCounts[a.risk_tier] || 0) + 1)

  const tierData = Object.entries(tierCounts).map(([name, value]) => ({ name, value, fill: TIER_COLOR[name] }))

  return (
    <div className="fade-in">
      {/* KPIs */}
      <div className="kpi-grid">
        <KPICard label="Total Drugs" value={s.total_drugs || 0} sub="Active formulary" icon="💊" accent="linear-gradient(90deg,#2563eb,#06b6d4)" />
        <KPICard label="Suppliers" value={s.total_suppliers || 0} sub={`${s.critical_suppliers || 0} critical`} icon="🏭" accent="linear-gradient(90deg,#8b5cf6,#3b82f6)" />
        <KPICard label="Avg Forecast MAPE" value={`${s.avg_price_forecast_mape_pct || 0}%`} sub="Price accuracy" icon="📈" accent="linear-gradient(90deg,#06b6d4,#10b981)" />
        <KPICard label="Anomalies Detected" value={s.total_anomalies_detected || 0} sub="Quality flags" icon="🔬" accent="linear-gradient(90deg,#f43f5e,#f59e0b)" />
        <KPICard label="Reorder Alerts" value={s.drugs_needing_reorder || 0} sub="Inventory actions" icon="📦" accent="linear-gradient(90deg,#f59e0b,#f97316)" />
        <KPICard label="High Risk Suppliers" value={(s.high_risk_suppliers || 0) + (s.critical_suppliers || 0)} sub="Require attention" icon="⚠️" accent="linear-gradient(90deg,#f43f5e,#8b5cf6)" />
      </div>

      <div className="dashboard-grid">
        {/* Alert Feed */}
        <div className="card col-span-1">
          <div className="card-header">
            <div className="card-title"><span className="icon">🚨</span> Live Alert Feed</div>
            <span className="badge badge-info">{alerts?.total_alerts || 0} alerts</span>
          </div>
          <div className="card-body">
            <div className="alert-list">
              {alertList.length === 0 && <div className="empty-state"><div className="icon">✅</div><p>No active alerts</p></div>}
              {alertList.map((a, i) => (
                <div key={i} className={`alert-item ${a.severity?.toLowerCase()}`}>
                  <span className="alert-icon">{a.type === 'shortage' ? '💊' : a.type === 'geopolitical' ? '🌍' : '📈'}</span>
                  <div className="alert-content">
                    <div className="alert-title">{a.title}</div>
                    <div className="alert-body">{a.body}</div>
                  </div>
                  <span className="alert-score">{a.score?.toFixed(0)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Top Risk Suppliers */}
        <div className="card col-span-1">
          <div className="card-header">
            <div className="card-title"><span className="icon">🏭</span> Top Risk Suppliers</div>
          </div>
          <div className="card-body">
            {(s.top_risk_suppliers || []).map((sup, i) => (
              <div key={i} className="supplier-risk-row">
                <div className="supplier-risk-name">{sup.supplier_name}</div>
                <div className="supplier-risk-bar">
                  <div className="progress-bar">
                    <div className="progress-fill" style={{
                      width: `${sup.risk_score}%`,
                      background: sup.risk_score >= 65 ? '#f43f5e' : sup.risk_score >= 45 ? '#f59e0b' : '#10b981'
                    }} />
                  </div>
                </div>
                <div className="supplier-risk-score">{sup.risk_score?.toFixed(0)}</div>
                <Badge tier={sup.risk_tier} />
              </div>
            ))}
          </div>
        </div>

        {/* Price Alerts */}
        <div className="card col-span-1">
          <div className="card-header">
            <div className="card-title"><span className="icon">📈</span> Price Spike Alerts</div>
          </div>
          <div className="card-body">
            {(s.price_alerts || []).length === 0 && <div className="empty-state"><div className="icon">✅</div><p>All prices stable</p></div>}
            <table className="data-table">
              {(s.price_alerts || []).length > 0 && (
                <thead><tr><th>Drug</th><th>Base</th><th>Forecast</th><th>Change</th></tr></thead>
              )}
              <tbody>
                {(s.price_alerts || []).map((a, i) => (
                  <tr key={i}>
                    <td>{a.drug_name}</td>
                    <td>${a.base_price}</td>
                    <td>${a.forecast_price}</td>
                    <td><span className="badge badge-critical">+{a.pct_increase}%</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Shortage tier distribution */}
        <div className="card col-span-1">
          <div className="card-header">
            <div className="card-title"><span className="icon">⚡</span> Shortage Risk Distribution</div>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={tierData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="name" tick={{ fill: '#8ba4c8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#8ba4c8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {tierData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

export { Badge, ScorePill, Skeleton, KPICard }
