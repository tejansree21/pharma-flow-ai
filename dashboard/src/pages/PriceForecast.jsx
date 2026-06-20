import { useState, useEffect } from 'react'
import { api } from '../api'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine
} from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#0a1628', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <p style={{ color: '#8ba4c8', marginBottom: 4 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, fontWeight: 600 }}>{p.name}: ${p.value?.toFixed(2)}/kg</p>
      ))}
    </div>
  )
}

export default function PriceForecast() {
  const [drugs, setDrugs] = useState([])
  const [selectedDrug, setSelectedDrug] = useState('')
  const [forecast, setForecast] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadingDrugs, setLoadingDrugs] = useState(true)

  useEffect(() => {
    api.drugs().then(d => {
      setDrugs(d)
      if (d.length) setSelectedDrug(d[0].id)
      setLoadingDrugs(false)
    }).catch(() => setLoadingDrugs(false))
  }, [])

  useEffect(() => {
    if (!selectedDrug) return
    setLoading(true)
    setForecast(null)
    api.forecastPrice(selectedDrug, 16).then(f => {
      setForecast(f)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [selectedDrug])

  const drug = drugs.find(d => d.id === selectedDrug)
  const chartData = (forecast?.forecast || []).map(p => ({
    date: p.date.slice(0, 10),
    price: p.predicted_price,
    lower: p.lower_bound,
    upper: p.upper_bound,
  }))

  const mape = forecast?.mape_pct
  const mapeColor = mape < 15 ? '#10b981' : mape < 20 ? '#f59e0b' : '#f43f5e'

  return (
    <div className="fade-in">
      {/* Header controls */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-header">
          <div className="card-title"><span className="icon">📈</span> Price Forecast</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {mape && (
              <span className="badge" style={{ background: `${mapeColor}22`, color: mapeColor, border: `1px solid ${mapeColor}44` }}>
                MAPE {mape}%
              </span>
            )}
            {loadingDrugs
              ? <Skeleton h={30} w={180} />
              : (
                <select
                  id="drug-select"
                  className="drug-select"
                  value={selectedDrug}
                  onChange={e => setSelectedDrug(e.target.value)}
                >
                  {drugs.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              )
            }
          </div>
        </div>
        {drug && (
          <div className="card-body" style={{ paddingTop: 10, paddingBottom: 10, display: 'flex', gap: 24 }}>
            <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Category</span><div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>{drug.category}</div></div>
            <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Criticality</span><div style={{ fontSize: 12, fontWeight: 600, marginTop: 2, textTransform: 'capitalize' }}>{drug.criticality}</div></div>
            <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Base Price</span><div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>${drug.base_price_per_kg?.toFixed(2)}/kg</div></div>
            <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Approved Suppliers</span><div style={{ fontSize: 12, fontWeight: 600, marginTop: 2 }}>{drug.num_approved_suppliers}</div></div>
            <div><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Seasonality</span><div style={{ fontSize: 12, fontWeight: 600, marginTop: 2, textTransform: 'capitalize' }}>{drug.demand_seasonality}</div></div>
          </div>
        )}
      </div>

      {/* Main chart */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-header">
          <div className="card-title">16-Week Price Forecast with Confidence Interval</div>
        </div>
        <div className="card-body">
          {loading ? <Skeleton h={280} /> : (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="confGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.12} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fill: '#8ba4c8', fontSize: 10 }} axisLine={false} tickLine={false} interval={2} />
                <YAxis tick={{ fill: '#8ba4c8', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} />
                <Tooltip content={<CustomTooltip />} />
                {chartData[0]?.upper && (
                  <Area type="monotone" dataKey="upper" stroke="none" fill="url(#confGrad)" name="Upper bound" />
                )}
                {chartData[0]?.lower && (
                  <Area type="monotone" dataKey="lower" stroke="none" fill="white" fillOpacity={0} name="Lower bound" />
                )}
                <Area type="monotone" dataKey="price" stroke="#06b6d4" strokeWidth={2.5} fill="url(#priceGrad)" dot={false} name="Forecast Price" />
                {drug && <ReferenceLine y={drug.base_price_per_kg} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: 'Base', fill: '#f59e0b', fontSize: 10 }} />}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Forecast table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Weekly Forecast Data</div>
        </div>
        <div className="card-body" style={{ maxHeight: 280, overflowY: 'auto' }}>
          {loading ? <Skeleton h={200} /> : (
            <table className="data-table">
              <thead>
                <tr><th>Week</th><th>Forecast ($/kg)</th><th>Lower</th><th>Upper</th><th>vs Base</th></tr>
              </thead>
              <tbody>
                {chartData.map((row, i) => {
                  const base = drug?.base_price_per_kg || 0
                  const delta = base ? ((row.price - base) / base * 100) : 0
                  const color = delta > 10 ? '#f43f5e' : delta > 0 ? '#f59e0b' : '#10b981'
                  return (
                    <tr key={i}>
                      <td style={{ fontFamily: 'var(--mono)' }}>{row.date}</td>
                      <td style={{ fontWeight: 600 }}>${row.price?.toFixed(2)}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{row.lower ? `$${row.lower.toFixed(2)}` : '—'}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{row.upper ? `$${row.upper.toFixed(2)}` : '—'}</td>
                      <td><span style={{ color, fontSize: 11, fontWeight: 700 }}>{delta > 0 ? '+' : ''}{delta.toFixed(1)}%</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
