import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import Overview from './pages/Overview'
import PriceForecast from './pages/PriceForecast'
import SupplierRisk from './pages/SupplierRisk'
import ShortagePredictor from './pages/ShortagePredictor'
import GeopoliticalIntel from './pages/GeopoliticalIntel'
import Inventory from './pages/Inventory'
import AskPharmaFlow from './components/AskPharmaFlow'

// ── Sidebar nav config ────────────────────────────────────────────────────────
const NAV = [
  {
    section: 'Overview',
    items: [
      { id: 'overview', label: 'Dashboard', icon: '🏠' },
    ]
  },
  {
    section: 'Intelligence',
    items: [
      { id: 'forecast',  label: 'Price Forecast',      icon: '📈' },
      { id: 'shortage',  label: 'Shortage Predictor',  icon: '💊' },
      { id: 'geo',       label: 'Geopolitical Intel',  icon: '🌍' },
    ]
  },
  {
    section: 'Operations',
    items: [
      { id: 'suppliers', label: 'Supplier Risk', icon: '🏭' },
      { id: 'inventory', label: 'Inventory',     icon: '📦' },
    ]
  },
]

const PAGE_TITLES = {
  overview:  { title: 'Supply Chain Dashboard',    sub: 'Real-time intelligence across all modules' },
  forecast:  { title: 'Price Forecast',            sub: 'Prophet model · 16-week horizon · External regressors' },
  shortage:  { title: 'Shortage Predictor',        sub: 'Multi-signal composite risk scoring · 5 intelligence factors' },
  geo:       { title: 'Geopolitical Intelligence', sub: 'Event feed · Country risk index · Supplier geo overlay' },
  suppliers: { title: 'Supplier Risk Registry',    sub: 'XGBoost composite scoring · 4 risk dimensions' },
  inventory: { title: 'Inventory Management',      sub: 'Safety stock · EOQ · Reorder point analysis' },
}

function RefreshIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  )
}

export default function App() {
  const [page, setPage] = useState('overview')
  const [apiStatus, setApiStatus] = useState('checking')
  const [refreshKey, setRefreshKey] = useState(0)
  const [spinning, setSpinning] = useState(false)

  useEffect(() => {
    api.health()
      .then(h => setApiStatus(h.status === 'ok' ? 'online' : 'offline'))
      .catch(() => setApiStatus('offline'))
  }, [])

  const handleRefresh = useCallback(() => {
    setSpinning(true)
    setRefreshKey(k => k + 1)
    setTimeout(() => setSpinning(false), 1200)
  }, [])

  const pageInfo = PAGE_TITLES[page] || PAGE_TITLES.overview

  const renderPage = () => {
    const props = { key: refreshKey }
    switch (page) {
      case 'overview':  return <Overview {...props} />
      case 'forecast':  return <PriceForecast {...props} />
      case 'shortage':  return <ShortagePredictor {...props} />
      case 'geo':       return <GeopoliticalIntel {...props} />
      case 'suppliers': return <SupplierRisk {...props} />
      case 'inventory': return <Inventory {...props} />
      default:          return <Overview {...props} />
    }
  }

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">
            <div className="logo-icon">⚕️</div>
            <span className="logo-name">PharmaFlow AI</span>
          </div>
          <div className="logo-sub">Supply Chain Intelligence</div>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(({ section, items }) => (
            <div key={section}>
              <div className="nav-section-label">{section}</div>
              {items.map(({ id, label, icon }) => (
                <div
                  key={id}
                  id={`nav-${id}`}
                  className={`nav-item ${page === id ? 'active' : ''}`}
                  onClick={() => setPage(id)}
                >
                  <span className="nav-icon">{icon}</span>
                  {label}
                </div>
              ))}
            </div>
          ))}
        </nav>

        {/* Ask PharmaFlow sidebar shortcut */}
        <div style={{ padding: '0 12px 12px' }}>
          <div
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 12px',
              borderRadius: 8,
              background: 'rgba(220,38,38,0.08)',
              border: '1px solid rgba(239,68,68,0.18)',
              cursor: 'pointer',
              fontSize: 12, fontWeight: 500,
              color: '#f87171',
              transition: 'all 0.2s ease',
            }}
            onClick={() => {
              // Trigger the floating chat by programmatically clicking the button
              document.getElementById('ask-pharmaflow-trigger')?.click()
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(220,38,38,0.14)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(220,38,38,0.08)'}
          >
            <span style={{ fontSize: 14 }}>✦</span>
            Ask PharmaFlow AI
          </div>
        </div>

        <div className="sidebar-footer">
          <div className="api-status">
            <div className={`status-dot ${apiStatus !== 'online' ? 'offline' : ''}`} />
            <span>
              API{' '}
              {apiStatus === 'online' ? '· v4.0.0'
                : apiStatus === 'checking' ? '· checking…'
                : '· offline'}
            </span>
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: 'var(--text-muted)', textAlign: 'center' }}>
            Phase 7 — Ask PharmaFlow AI
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-content">
        <div className="topbar">
          <div className="topbar-title">
            <h1>{pageInfo.title}</h1>
            <p>{pageInfo.sub}</p>
          </div>
          <div className="topbar-right">
            {/* Ask PharmaFlow button in topbar */}
            <button
              id="ask-pharmaflow-trigger"
              onClick={() => document.getElementById('ask-pharmaflow-fab')?.click()}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '7px 14px',
                background: 'rgba(220,38,38,0.1)',
                border: '1px solid rgba(239,68,68,0.25)',
                borderRadius: 8,
                color: '#f87171',
                fontSize: 12, fontWeight: 600,
                cursor: 'pointer',
                fontFamily: 'var(--font)',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={e => {
                e.target.style.background = 'rgba(220,38,38,0.18)'
                e.target.style.color = '#fff'
              }}
              onMouseLeave={e => {
                e.target.style.background = 'rgba(220,38,38,0.1)'
                e.target.style.color = '#f87171'
              }}
            >
              ✦ Ask AI
            </button>

            <button
              id="refresh-btn"
              className={`refresh-btn ${spinning ? 'spinning' : ''}`}
              onClick={handleRefresh}
            >
              <RefreshIcon /> Refresh
            </button>
          </div>
        </div>

        <div className="page-content">
          {renderPage()}
        </div>
      </main>

      {/* ── Floating Ask PharmaFlow panel ── */}
      <AskPharmaFlow fabId="ask-pharmaflow-fab" />
    </div>
  )
}
