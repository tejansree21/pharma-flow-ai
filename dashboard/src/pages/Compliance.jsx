// ═════════════════════════════════════════════════════════════════════════════
// Compliance.jsx — save as dashboard/src/pages/Compliance.jsx
// ═════════════════════════════════════════════════════════════════════════════

import { useState, useEffect } from 'react'
import { api } from '../api'

function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />
}

const STATUS_CONFIG = {
  COMPLIANT:     { color: '#22c55e', label: 'Compliant' },
  AT_RISK:       { color: '#f59e0b', label: 'At Risk'   },
  NON_COMPLIANT: { color: '#ef4444', label: 'Non-Compliant' },
}
const AUDIT_STATUS = {
  CURRENT:   { color: '#22c55e', label: 'Current'   },
  DUE_SOON:  { color: '#f59e0b', label: 'Due Soon'  },
  OVERDUE:   { color: '#ef4444', label: 'Overdue'   },
}

export function Compliance() {
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState(null)
  const [auditReport, setAuditReport] = useState(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [filter, setFilter]     = useState('ALL')

  useEffect(() => {
    api.complianceOverview()
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const generateReport = async (supplierId) => {
    setReportLoading(true)
    try {
      const r = await api.auditReport(supplierId)
      setAuditReport(r)
    } catch (e) {
      console.error(e)
    } finally {
      setReportLoading(false)
    }
  }

  const downloadReport = () => {
    if (!auditReport) return
    const blob = new Blob([auditReport.report_text], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `compliance_report_${auditReport.supplier_name.replace(/\s+/g,'_')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const s = data?.summary || {}
  const filtered = (data?.suppliers || []).filter(r =>
    filter === 'ALL' || r.overall_status === filter
  )

  return (
    <div className="fade-in">
      {/* KPIs */}
      {!loading && data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14, marginBottom: 20 }}>
          {[
            { label: 'Compliant',        val: s.compliant,            color: '#22c55e' },
            { label: 'At Risk',          val: s.at_risk,              color: '#f59e0b' },
            { label: 'Non-Compliant',    val: s.non_compliant,        color: '#ef4444' },
            { label: 'Active Warnings',  val: s.total_active_warnings, color: '#ef4444' },
          ].map(({ label, val, color }) => (
            <div key={label} className="kpi-card" style={{ '--accent': color }}>
              <div className="kpi-label">{label}</div>
              <div className="kpi-value" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      <div className="page-tabs">
        {['ALL', 'COMPLIANT', 'AT_RISK', 'NON_COMPLIANT'].map(f => (
          <button key={f} className={`tab-btn ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
            {f.replace('_', ' ')}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 18 }}>
        {/* Supplier table */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><span className="icon">📋</span> Regulatory Compliance Status</div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Avg score: <strong style={{ color: 'var(--text-primary)' }}>{s.avg_compliance_score?.toFixed(0)}/100</strong></span>
          </div>
          <div style={{ maxHeight: 520, overflowY: 'auto' }}>
            {loading ? <div style={{ padding: 20 }}><Skeleton h={320} /></div> : (
              <table className="data-table">
                <thead>
                  <tr><th>Supplier</th><th>Country</th><th>Score</th><th>Status</th><th>Overdue</th><th>Warnings</th><th>Next Audit</th></tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => {
                    const sc = STATUS_CONFIG[r.overall_status] || STATUS_CONFIG.AT_RISK
                    return (
                      <tr key={i} onClick={() => { setSelected(r); setAuditReport(null) }} style={{ cursor: 'pointer', background: selected?.supplier_id === r.supplier_id ? 'rgba(239,68,68,0.06)' : undefined }}>
                        <td>{r.supplier_name}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{r.country}</td>
                        <td>
                          <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, color: r.compliance_score >= 80 ? '#22c55e' : r.compliance_score >= 60 ? '#f59e0b' : '#ef4444' }}>
                            {r.compliance_score?.toFixed(0)}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 4, background: `${sc.color}18`, color: sc.color, border: `1px solid ${sc.color}30` }}>
                            {sc.label}
                          </span>
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: r.overdue_frameworks.length > 0 ? '#ef4444' : 'var(--text-muted)' }}>
                          {r.overdue_frameworks.length || '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: r.active_warnings > 0 ? '#ef4444' : 'var(--text-muted)' }}>
                          {r.active_warnings > 0 ? `⚠ ${r.active_warnings}` : '—'}
                        </td>
                        <td style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                          {r.next_audit_due?.slice(0,7)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Detail + report */}
        <div>
          {!selected ? (
            <div className="card">
              <div className="card-body"><div className="empty-state"><div className="icon">📋</div><p>Click a supplier for details</p></div></div>
            </div>
          ) : (
            <div className="card fade-in">
              <div className="card-header">
                <div className="card-title" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                  <span style={{ fontSize: 13 }}>{selected.supplier_name}</span>
                  {(() => { const sc = STATUS_CONFIG[selected.overall_status]; return <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, background: `${sc.color}18`, color: sc.color, border: `1px solid ${sc.color}30` }}>{sc.label}</span> })()}
                </div>
                <span style={{ fontFamily: 'var(--mono)', fontWeight: 800, fontSize: 22, color: selected.compliance_score >= 80 ? '#22c55e' : selected.compliance_score >= 60 ? '#f59e0b' : '#ef4444' }}>
                  {selected.compliance_score?.toFixed(0)}
                </span>
              </div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {/* Framework status */}
                {(selected.frameworks || []).map((fw, i) => {
                  const as = AUDIT_STATUS[fw.status] || AUDIT_STATUS.CURRENT
                  return (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: 6 }}>
                      <span style={{ color: 'var(--text-muted)', flex: 1 }}>{fw.framework}</span>
                      <span style={{ fontSize: 9, padding: '1px 6px', borderRadius: 4, background: `${as.color}18`, color: as.color, border: `1px solid ${as.color}30`, marginLeft: 8 }}>
                        {as.label}
                      </span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-muted)', marginLeft: 8, minWidth: 60, textAlign: 'right' }}>
                        Due {fw.next_due?.slice(0,7)}
                      </span>
                    </div>
                  )
                })}

                {/* Warning letters */}
                {selected.active_warnings > 0 && (
                  <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', fontSize: 11, color: '#f87171' }}>
                    ⚠ {selected.active_warnings} active FDA warning letter{selected.active_warnings > 1 ? 's' : ''}
                  </div>
                )}

                {/* Generate report */}
                <button
                  onClick={() => generateReport(selected.supplier_id)}
                  disabled={reportLoading}
                  style={{ padding: '8px 14px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 8, color: '#f87171', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font)', marginTop: 4 }}
                >
                  {reportLoading ? 'Generating…' : '📄 Generate Audit Report'}
                </button>

                {auditReport && (
                  <>
                    <pre style={{ fontSize: 10, color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.02)', borderRadius: 6, padding: 10, border: '1px solid rgba(255,255,255,0.06)', maxHeight: 200, overflowY: 'auto', whiteSpace: 'pre-wrap', fontFamily: 'var(--mono)', lineHeight: 1.5 }}>
                      {auditReport.report_text}
                    </pre>
                    <button onClick={downloadReport} style={{ padding: '7px 14px', background: '#dc2626', border: 'none', borderRadius: 8, color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'var(--font)' }}>
                      ⬇ Download .txt
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default Compliance
