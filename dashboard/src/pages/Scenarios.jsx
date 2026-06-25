import { useState, useEffect } from 'react'
import { api } from '../api'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const IMPACT_COLORS = {
  CRITICAL: '#ef4444',
  HIGH:     '#f59e0b',
  MEDIUM:   '#f87171',
  LOW:      '#22c55e',
}

function ImpactBadge({ level }) {
  const color = IMPACT_COLORS[level] || '#9a9a9a'
  return (
    <span className="badge" style={{
      background: `${color}18`, color,
      border: `1px solid ${color}30`,
    }}>
      {level}
    </span>
  )
}

function DeltaCell({ value, pct }) {
  const color = value > 0 ? '#ef4444' : value < 0 ? '#22c55e' : '#9a9a9a'
  return (
    <span style={{ color, fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 12 }}>
      {value > 0 ? '+' : ''}{value > 0 || value < 0 ? `$${Math.abs(value).toLocaleString()}` : '—'}
      {pct !== undefined && (
        <span style={{ fontSize: 10, marginLeft: 4, opacity: 0.8 }}>
          ({pct > 0 ? '+' : ''}{pct?.toFixed(1)}%)
        </span>
      )}
    </span>
  )
}

function ResultCard({ result }) {
  if (!result) return null
  const color = IMPACT_COLORS[result.impact_level] || '#9a9a9a'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Summary KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        <div className="kpi-card" style={{ '--accent': color }}>
          <div className="kpi-label">Impact Level</div>
          <div className="kpi-value" style={{ fontSize: 18, color }}>{result.impact_level}</div>
        </div>
        <div className="kpi-card" style={{ '--accent': '#ef4444' }}>
          <div className="kpi-label">Cost Delta</div>
          <div className="kpi-value" style={{ fontSize: 18, color: result.total_cost_delta_usd > 0 ? '#ef4444' : '#22c55e' }}>
            {result.total_cost_delta_usd > 0 ? '+' : ''}{result.total_cost_delta_pct?.toFixed(1)}%
          </div>
          <div className="kpi-sub">${Math.abs(result.total_cost_delta_usd).toLocaleString()}</div>
        </div>
        <div className="kpi-card" style={{ '--accent': '#f59e0b' }}>
          <div className="kpi-label">Drugs Affected</div>
          <div className="kpi-value" style={{ fontSize: 18, color: '#f59e0b' }}>{result.drugs_affected}</div>
        </div>
        <div className="kpi-card" style={{ '--accent': '#ef4444' }}>
          <div className="kpi-label">Can't Fulfill</div>
          <div className="kpi-value" style={{ fontSize: 18, color: result.drugs_unfulfillable > 0 ? '#ef4444' : '#22c55e' }}>
            {result.drugs_unfulfillable}
          </div>
        </div>
      </div>

      {/* Recommendation */}
      <div style={{
        padding: '12px 16px',
        borderRadius: 10,
        background: `${color}0d`,
        border: `1px solid ${color}25`,
        fontSize: 13, lineHeight: 1.6,
        color: 'var(--text-primary)',
      }}>
        <strong style={{ color }}>Recommendation: </strong>{result.recommendation}
      </div>

      {/* Drug impact table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Drug-level impact breakdown</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Baseline ${result.baseline_total_cost_usd?.toLocaleString()} → Simulated ${result.simulated_total_cost_usd?.toLocaleString()}
          </div>
        </div>
        <div style={{ maxHeight: 280, overflowY: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Drug</th>
                <th>Baseline</th>
                <th>Simulated</th>
                <th>Delta</th>
                <th>Can Fulfill</th>
                <th>Impact</th>
                <th>Alt. Supplier</th>
              </tr>
            </thead>
            <tbody>
              {(result.drug_impacts || []).map((d, i) => (
                <tr key={i}>
                  <td>{d.drug_name}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>${d.baseline_cost_usd?.toLocaleString()}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>${d.simulated_cost_usd?.toLocaleString()}</td>
                  <td><DeltaCell value={d.cost_delta_usd} pct={d.cost_delta_pct} /></td>
                  <td>
                    <span style={{ color: d.can_fulfill ? '#22c55e' : '#ef4444', fontSize: 12, fontWeight: 700 }}>
                      {d.can_fulfill ? '✓ Yes' : '✗ No'}
                    </span>
                  </td>
                  <td><ImpactBadge level={d.impact_level} /></td>
                  <td style={{ fontSize: 11, color: 'var(--text-muted)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {d.simulated_supplier}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function Scenarios() {
  const [tab, setTab] = useState('offline')
  const [suppliers, setSuppliers] = useState([])
  const [drugs, setDrugs] = useState([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  // Offline sim state
  const [offlineSupplier, setOfflineSupplier] = useState('')

  // Demand shock state
  const [shockDrug, setShockDrug] = useState('')
  const [shockMultiplier, setShockMultiplier] = useState(2.0)

  // Price spike state
  const [spikeSuppliers, setSpikeSuppliers] = useState([])
  const [spikeMultiplier, setSpikeMultiplier] = useState(1.2)

  useEffect(() => {
    Promise.all([api.suppliers(), api.drugs()]).then(([s, d]) => {
      setSuppliers(s)
      setDrugs(d)
      if (s.length) setOfflineSupplier(s[0].id)
      if (d.length) setShockDrug(d[0].id)
    })
  }, [])

  // Reset result on tab change
  useEffect(() => { setResult(null); setError(null) }, [tab])

  const runSim = async () => {
    setLoading(true)
    setResult(null)
    setError(null)
    try {
      let res
      if (tab === 'offline') {
        res = await api.simulateSupplierOffline(offlineSupplier)
      } else if (tab === 'demand') {
        res = await api.simulateDemandShock(shockDrug, shockMultiplier)
      } else {
        res = await api.simulatePriceSpike(
          spikeSuppliers.length ? spikeSuppliers : null,
          spikeMultiplier,
        )
      }
      setResult(res)
    } catch (e) {
      setError(e.message || 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }

  const supById = Object.fromEntries(suppliers.map(s => [s.id, s]))

  return (
    <div className="fade-in">
      {/* Scenario tabs */}
      <div className="page-tabs">
        <button className={`tab-btn ${tab === 'offline' ? 'active' : ''}`} onClick={() => setTab('offline')}>
          🔌 Supplier Offline
        </button>
        <button className={`tab-btn ${tab === 'demand' ? 'active' : ''}`} onClick={() => setTab('demand')}>
          📈 Demand Shock
        </button>
        <button className={`tab-btn ${tab === 'price' ? 'active' : ''}`} onClick={() => setTab('price')}>
          💰 Price Spike
        </button>
      </div>

      {/* Controls card */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="card-header">
          <div className="card-title">
            <span className="icon">⚙️</span>
            {tab === 'offline' ? 'Supplier Offline Simulation'
              : tab === 'demand' ? 'Demand Shock Simulation'
              : 'Price Spike Simulation'}
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Fast greedy solver — results in ~2 seconds
          </span>
        </div>
        <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

          {/* Supplier Offline */}
          {tab === 'offline' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                Remove a supplier from the supply chain and see which drugs are affected, what alternatives exist, and how much more it will cost.
              </p>
              <div>
                <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                  Supplier to take offline
                </label>
                <select
                  className="drug-select"
                  style={{ width: '100%' }}
                  value={offlineSupplier}
                  onChange={e => setOfflineSupplier(e.target.value)}
                >
                  {suppliers.map(s => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.country}) — Risk: {s.risk_score?.toFixed(0) ?? '?'}/100
                    </option>
                  ))}
                </select>
              </div>
              {offlineSupplier && supById[offlineSupplier] && (
                <div style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: 'rgba(239,68,68,0.06)',
                  border: '1px solid rgba(239,68,68,0.15)',
                  fontSize: 12, color: 'var(--text-secondary)',
                  display: 'flex', gap: 20,
                }}>
                  <span>Country: <strong style={{ color: 'var(--text-primary)' }}>{supById[offlineSupplier].country}</strong></span>
                  <span>Risk tier: <strong style={{ color: 'var(--text-primary)' }}>{supById[offlineSupplier].risk_tier || '—'}</strong></span>
                  <span>FDA approved: <strong style={{ color: supById[offlineSupplier].fda_approved ? '#22c55e' : '#ef4444' }}>{supById[offlineSupplier].fda_approved ? 'Yes' : 'No'}</strong></span>
                </div>
              )}
            </div>
          )}

          {/* Demand Shock */}
          {tab === 'demand' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                Simulate a sudden demand surge (e.g. from a disease outbreak or seasonal spike) and see the cost and supply capacity impact.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                    Drug experiencing demand surge
                  </label>
                  <select
                    className="drug-select"
                    style={{ width: '100%' }}
                    value={shockDrug}
                    onChange={e => setShockDrug(e.target.value)}
                  >
                    {drugs.map(d => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                    Demand multiplier: <strong style={{ color: '#ef4444' }}>{shockMultiplier.toFixed(1)}×</strong>
                  </label>
                  <input
                    type="range"
                    min="1.1" max="5" step="0.1"
                    value={shockMultiplier}
                    onChange={e => setShockMultiplier(parseFloat(e.target.value))}
                    style={{ width: '100%', accentColor: '#dc2626' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                    <span>1.1× (mild)</span><span>2.5× (moderate)</span><span>5× (severe)</span>
                  </div>
                </div>
              </div>
              <div style={{
                padding: '10px 14px', borderRadius: 8,
                background: 'rgba(239,68,68,0.06)',
                border: '1px solid rgba(239,68,68,0.15)',
                fontSize: 12, color: 'var(--text-secondary)',
              }}>
                Demand increases from baseline to <strong style={{ color: 'var(--text-primary)' }}>{shockMultiplier.toFixed(1)}× of normal</strong>
                {shockMultiplier >= 3 && <span style={{ color: '#ef4444', marginLeft: 8 }}>— SEVERE: may exceed supplier capacity</span>}
                {shockMultiplier >= 2 && shockMultiplier < 3 && <span style={{ color: '#f59e0b', marginLeft: 8 }}>— HIGH: will require all approved suppliers</span>}
              </div>
            </div>
          )}

          {/* Price Spike */}
          {tab === 'price' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                Simulate a price increase from specific suppliers (or top 3 highest-risk suppliers) and see the total spend impact across all affected drugs.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                    Suppliers raising prices (leave empty for top 3 risk suppliers)
                  </label>
                  <select
                    className="drug-select"
                    style={{ width: '100%', height: 80 }}
                    multiple
                    value={spikeSuppliers}
                    onChange={e => setSpikeSuppliers(
                      Array.from(e.target.selectedOptions, o => o.value)
                    )}
                  >
                    {suppliers.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.country})
                      </option>
                    ))}
                  </select>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>Hold Ctrl/Cmd to select multiple</div>
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 6 }}>
                    Price increase: <strong style={{ color: '#ef4444' }}>+{((spikeMultiplier - 1) * 100).toFixed(0)}%</strong>
                  </label>
                  <input
                    type="range"
                    min="1.0" max="3.0" step="0.05"
                    value={spikeMultiplier}
                    onChange={e => setSpikeMultiplier(parseFloat(e.target.value))}
                    style={{ width: '100%', accentColor: '#dc2626' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                    <span>+0% (baseline)</span><span>+50%</span><span>+100%</span><span>+200%</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Run button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={runSim}
              disabled={loading}
              style={{
                padding: '10px 24px',
                background: loading ? 'rgba(220,38,38,0.3)' : '#dc2626',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 8,
                color: 'white', fontWeight: 600, fontSize: 13,
                cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: 'var(--font)',
                boxShadow: loading ? 'none' : '0 0 16px rgba(220,38,38,0.25)',
                transition: 'all 0.2s ease',
              }}
            >
              {loading ? '⏳ Running simulation…' : '▶ Run Simulation'}
            </button>
            {result && (
              <span style={{ fontSize: 12, color: '#22c55e' }}>✓ Simulation complete</span>
            )}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '12px 16px', borderRadius: 8, marginBottom: 18,
          background: 'rgba(239,68,68,0.08)',
          border: '1px solid rgba(239,68,68,0.2)',
          fontSize: 13, color: '#ef4444',
        }}>
          ✗ {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Skeleton h={100} />
            <Skeleton h={40} />
            <Skeleton h={200} />
          </div>
        </div>
      )}

      {/* Results */}
      {!loading && result && <ResultCard result={result} />}

      {/* Empty state */}
      {!loading && !result && !error && (
        <div style={{
          padding: '48px 24px', textAlign: 'center',
          color: 'var(--text-muted)', fontSize: 13,
        }}>
          <div style={{ fontSize: 32, marginBottom: 12, opacity: 0.4 }}>⚗️</div>
          <div>Configure a scenario above and click Run Simulation</div>
          <div style={{ marginTop: 6, fontSize: 12 }}>
            Results show cost delta, affected drugs, and fulfillment capacity
          </div>
        </div>
      )}
    </div>
  )
}
