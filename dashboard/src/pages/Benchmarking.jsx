import { useState, useEffect } from 'react'
import { api } from '../api'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine, ComposedChart, Line } from 'recharts'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const POS_COLORS = {
  SIGNIFICANTLY_ABOVE: '#ef4444',
  ABOVE_MARKET:        '#f59e0b',
  AT_MARKET:           '#22c55e',
  BELOW_MARKET:        '#60a5fa',
}
const POS_LABELS = {
  SIGNIFICANTLY_ABOVE: 'Significantly above',
  ABOVE_MARKET:        'Above market',
  AT_MARKET:           'At market',
  BELOW_MARKET:        'Below market',
}
const QUALITY_COLORS = {
  ABOVE_BENCHMARK: '#22c55e',
  AT_BENCHMARK:    '#f59e0b',
  BELOW_BENCHMARK: '#ef4444',
}

function PositionBadge({ position }) {
  const color = POS_COLORS[position] || '#9a9a9a'
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4,
      background: `${color}18`, color, border: `1px solid ${color}30`,
    }}>
      {POS_LABELS[position] || position}
    </span>
  )
}
function QualityBadge({ rating }) {
  const color = QUALITY_COLORS[rating] || '#9a9a9a'
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4,
      background: `${color}18`, color, border: `1px solid ${color}30`,
    }}>
      {rating?.replace('_', ' ')}
    </span>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#111', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <p style={{ color: '#9a9a9a', marginBottom: 6 }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || '#fff', fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? `$${p.value.toFixed(2)}` : p.value}
        </p>
      ))}
    </div>
  )
}

export default function Benchmarking() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab]         = useState('price')
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    api.benchmarkOverview()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const s = data?.summary || {}

  // Chart: top 10 drugs by savings opportunity
  const savingsChart = (data?.price_benchmarks || [])
    .slice(0, 10)
    .map(d => ({
      name:     d.drug_name?.split(' ')[0],
      savings:  d.monthly_savings_opportunity,
      our:      d.our_price,
      median:   d.market_median,
      position: d.position,
    }))

  // Chart: quality comparison top 12 suppliers
  const qualityChart = (data?.quality_benchmarks || [])
    .slice(0, 12)
    .map(s => ({
      name:    s.supplier_name?.split(' ')[0],
      rate:    s.our_quality_rate,
      delta:   s.quality_delta,
      rating:  s.quality_rating,
    }))

  return (
    <div className="fade-in">
      {/* KPI strip */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
          <div className="kpi-card" style={{ '--accent': '#ef4444' }}>
            <div className="kpi-label">Monthly Savings Opp.</div>
            <div className="kpi-value" style={{ fontSize: 20, color: '#ef4444' }}>
              ${(s.total_monthly_savings_opportunity / 1000).toFixed(0)}K
            </div>
            <div className="kpi-sub">If priced at market median</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#f59e0b' }}>
            <div className="kpi-label">Drugs Above Market</div>
            <div className="kpi-value" style={{ color: '#f59e0b' }}>{s.drugs_above_market}</div>
            <div className="kpi-sub">of {s.total_drugs_benchmarked} benchmarked</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#22c55e' }}>
            <div className="kpi-label">Drugs At/Below Market</div>
            <div className="kpi-value" style={{ color: '#22c55e' }}>
              {(s.drugs_at_market || 0) + (s.drugs_below_market || 0)}
            </div>
            <div className="kpi-sub">Competitively priced</div>
          </div>
          <div className="kpi-card" style={{ '--accent': '#ef4444' }}>
            <div className="kpi-label">Below Quality Benchmark</div>
            <div className="kpi-value" style={{ color: '#ef4444' }}>{s.suppliers_below_quality_benchmark}</div>
            <div className="kpi-sub">Suppliers &lt; {s.industry_avg_quality_pct}% pass rate</div>
          </div>
        </div>
      )}

      <div className="page-tabs">
        <button className={`tab-btn ${tab === 'price' ? 'active' : ''}`} onClick={() => setTab('price')}>
          💰 Price Benchmarking
        </button>
        <button className={`tab-btn ${tab === 'quality' ? 'active' : ''}`} onClick={() => setTab('quality')}>
          🔬 Quality Benchmarking
        </button>
      </div>

      {/* ── Price tab ── */}
      {tab === 'price' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Savings bar chart */}
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">💰</span> Monthly Savings Opportunity by Drug</div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Difference from market median × monthly demand</span>
            </div>
            <div className="card-body">
              {loading ? <Skeleton h={220} /> : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={savingsChart} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}`} />
                    <Tooltip content={<CustomTooltip />} formatter={(v) => [`$${v.toFixed(0)}`, 'Savings opp.']} />
                    <Bar dataKey="savings" name="Savings opportunity" radius={[4, 4, 0, 0]}>
                      {savingsChart.map((entry, i) => (
                        <Cell key={i} fill={POS_COLORS[entry.position] || '#9a9a9a'} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
              <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
                {Object.entries(POS_COLORS).map(([k, c]) => (
                  <span key={k} style={{ fontSize: 11, color: c, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: c, display: 'inline-block' }} />
                    {POS_LABELS[k]}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Full table + detail panel */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 18 }}>
            <div className="card">
              <div className="card-header">
                <div className="card-title">All drugs — price vs market</div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  Avg percentile rank: <strong style={{ color: 'var(--text-primary)' }}>{s.avg_price_percentile?.toFixed(0)}th</strong>
                </span>
              </div>
              <div style={{ maxHeight: 440, overflowY: 'auto' }}>
                {loading ? <div style={{ padding: 20 }}><Skeleton h={300} /></div> : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Drug</th><th>Our Price</th><th>Market Median</th>
                        <th>Savings/kg</th><th>Monthly Opp.</th><th>Position</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(data?.price_benchmarks || []).map((d, i) => (
                        <tr key={i} onClick={() => setSelected({ type: 'price', data: d })} style={{ cursor: 'pointer', background: selected?.data?.drug_id === d.drug_id ? 'rgba(239,68,68,0.06)' : undefined }}>
                          <td>{d.drug_name}</td>
                          <td style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>${d.our_price?.toFixed(2)}</td>
                          <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>${d.market_median?.toFixed(2)}</td>
                          <td style={{ fontFamily: 'var(--mono)', color: d.savings_per_kg > 0 ? '#ef4444' : '#22c55e' }}>
                            {d.savings_per_kg > 0 ? `+$${d.savings_per_kg.toFixed(2)}` : '—'}
                          </td>
                          <td style={{ fontFamily: 'var(--mono)', color: d.monthly_savings_opportunity > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
                            {d.monthly_savings_opportunity > 0 ? `$${d.monthly_savings_opportunity.toFixed(0)}` : '—'}
                          </td>
                          <td><PositionBadge position={d.position} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* Detail panel */}
            <div>
              {!selected || selected.type !== 'price' ? (
                <div className="card">
                  <div className="card-body">
                    <div className="empty-state"><div className="icon">💰</div><p>Click a drug to see market range detail</p></div>
                  </div>
                </div>
              ) : (
                <div className="card fade-in">
                  <div className="card-header">
                    <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                      <span>{selected.data.drug_name}</span>
                      <PositionBadge position={selected.data.position} />
                    </div>
                  </div>
                  <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {/* Price range visual */}
                    <div style={{ position: 'relative', padding: '16px 0', marginBottom: 8 }}>
                      <div style={{ height: 8, background: `linear-gradient(90deg, #22c55e, #f59e0b, #ef4444)`, borderRadius: 4 }} />
                      {/* Our price marker */}
                      {(() => {
                        const d = selected.data
                        const range = d.market_p90 - d.market_p10
                        const pct = range > 0 ? ((d.our_price - d.market_p10) / range) * 100 : 50
                        const clampedPct = Math.max(2, Math.min(98, pct))
                        return (
                          <div style={{ position: 'absolute', left: `${clampedPct}%`, top: 8, transform: 'translateX(-50%)' }}>
                            <div style={{ width: 2, height: 16, background: '#fff', margin: '0 auto' }} />
                            <div style={{ fontSize: 10, color: '#fff', fontWeight: 700, whiteSpace: 'nowrap', textAlign: 'center', marginTop: 2 }}>
                              Our price<br />${d.our_price.toFixed(2)}
                            </div>
                          </div>
                        )
                      })()}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginBottom: 12 }}>
                      <span>P10 ${selected.data.market_p10?.toFixed(2)}</span>
                      <span>P25 ${selected.data.market_p25?.toFixed(2)}</span>
                      <span style={{ color: '#22c55e', fontWeight: 700 }}>Median ${selected.data.market_median?.toFixed(2)}</span>
                      <span>P75 ${selected.data.market_p75?.toFixed(2)}</span>
                      <span>P90 ${selected.data.market_p90?.toFixed(2)}</span>
                    </div>
                    {[
                      ['Our price', `$${selected.data.our_price?.toFixed(2)}/kg`],
                      ['Market median', `$${selected.data.market_median?.toFixed(2)}/kg`],
                      ['Percentile rank', `${selected.data.percentile_rank?.toFixed(0)}th`],
                      ['Savings per kg', `$${selected.data.savings_per_kg?.toFixed(2)}`],
                      ['Monthly savings opp.', `$${selected.data.monthly_savings_opportunity?.toFixed(0)}`],
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
      )}

      {/* ── Quality tab ── */}
      {tab === 'quality' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title"><span className="icon">🔬</span> Supplier Quality Pass Rate vs Industry Benchmark</div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Industry standard: <strong style={{ color: '#22c55e' }}>94.0%</strong>
              </span>
            </div>
            <div className="card-body">
              {loading ? <Skeleton h={220} /> : (
                <ResponsiveContainer width="100%" height={220}>
                  <ComposedChart data={qualityChart} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="name" tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis domain={[70, 100]} tick={{ fill: '#4a4a4a', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
                    <Tooltip content={<CustomTooltip />} formatter={(v) => [`${v.toFixed(1)}%`, 'Pass rate']} />
                    <ReferenceLine y={94} stroke="#22c55e" strokeDasharray="4 4" label={{ value: '94% benchmark', fill: '#22c55e', fontSize: 10 }} />
                    <Bar dataKey="rate" name="Quality pass rate" radius={[4, 4, 0, 0]}>
                      {qualityChart.map((entry, i) => (
                        <Cell key={i} fill={QUALITY_COLORS[entry.rating] || '#9a9a9a'} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </ComposedChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          <div className="card">
            <div style={{ maxHeight: 440, overflowY: 'auto' }}>
              {loading ? <div style={{ padding: 20 }}><Skeleton h={300} /></div> : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Supplier</th><th>Country</th><th>Our Rate</th>
                      <th>Benchmark</th><th>Delta</th><th>Batches</th><th>Rating</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.quality_benchmarks || []).map((s, i) => (
                      <tr key={i}>
                        <td>{s.supplier_name}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{s.country}</td>
                        <td style={{ fontFamily: 'var(--mono)', fontWeight: 600 }}>{s.our_quality_rate?.toFixed(1)}%</td>
                        <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{s.industry_benchmark?.toFixed(1)}%</td>
                        <td style={{ fontFamily: 'var(--mono)', color: s.quality_delta >= 0 ? '#22c55e' : '#ef4444', fontWeight: 700 }}>
                          {s.quality_delta >= 0 ? '+' : ''}{s.quality_delta?.toFixed(1)}%
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', color: 'var(--text-muted)' }}>{s.batches_analyzed}</td>
                        <td><QualityBadge rating={s.quality_rating} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
