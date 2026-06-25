import { useState, useEffect, useCallback } from 'react'
import { api } from './api'
import { AuthProvider, useAuth, ROLE_PERMISSIONS } from './useAuth.jsx'
import Login from './pages/Login'
import Overview from './pages/Overview'
import PriceForecast from './pages/PriceForecast'
import SupplierRisk from './pages/SupplierRisk'
import ShortagePredictor from './pages/ShortagePredictor'
import GeopoliticalIntel from './pages/GeopoliticalIntel'
import Inventory from './pages/Inventory'
import Scenarios from './pages/Scenarios'
import DemandForecast from './pages/DemandForecast'
import Benchmarking from './pages/Benchmarking'
import CounterfeitRisk from './pages/CounterfeitRisk'
import SupplyChainMap from './pages/SupplyChainMap'
import Compliance from './pages/Compliance'
import ESGScoring from './pages/ESGScoring'
import AskPharmaFlow from './components/AskPharmaFlow'

const ALL_NAV = [
  { section: 'Overview', items: [
    { id: 'overview',      label: 'Dashboard',           icon: '🏠' },
  ]},
  { section: 'Intelligence', items: [
    { id: 'forecast',      label: 'Price Forecast',      icon: '📈' },
    { id: 'shortage',      label: 'Shortage Predictor',  icon: '💊' },
    { id: 'geo',           label: 'Geopolitical Intel',  icon: '🌍' },
    { id: 'demand',        label: 'Demand Forecast',     icon: '🦠' },
    { id: 'benchmark',     label: 'Benchmarking',        icon: '📊' },
    { id: 'counterfeit',   label: 'Counterfeit Risk',    icon: '🔍' },
  ]},
  { section: 'Operations', items: [
    { id: 'suppliers',     label: 'Supplier Risk',       icon: '🏭' },
    { id: 'inventory',     label: 'Inventory',           icon: '📦' },
    { id: 'scenarios',     label: 'Scenarios',           icon: '⚗️' },
  ]},
  { section: 'Phase 10', items: [
    { id: 'supplychain',   label: 'Supply Chain Map',    icon: '🗺️' },
    { id: 'compliance',    label: 'Compliance',          icon: '📋' },
    { id: 'esg',           label: 'ESG Scoring',         icon: '🌱' },
  ]},
]

const PAGE_TITLES = {
  overview:    { title: 'Supply Chain Dashboard',      sub: 'Real-time intelligence across all modules' },
  forecast:    { title: 'Price Forecast',              sub: 'Prophet model · 16-week horizon · External regressors' },
  shortage:    { title: 'Shortage Predictor',          sub: 'Multi-signal composite risk scoring · 5 intelligence factors' },
  geo:         { title: 'Geopolitical Intelligence',   sub: 'Live event feed · Country risk index · Supplier geo overlay' },
  demand:      { title: 'Demand Forecast',             sub: 'WHO DONS · CDC ILI surveillance · Seasonal drug demand signals' },
  benchmark:   { title: 'Industry Benchmarking',       sub: 'Price percentile ranking · Quality vs benchmark · Savings opportunities' },
  counterfeit: { title: 'Counterfeit Risk Detection',  sub: 'Price anomaly · Quality drift · Regulatory posture · Incident signals' },
  suppliers:   { title: 'Supplier Risk Registry',      sub: 'XGBoost composite scoring · 4 risk dimensions' },
  inventory:   { title: 'Inventory Management',        sub: 'Safety stock · EOQ · Reorder point analysis' },
  scenarios:   { title: 'Scenario Simulation',         sub: 'Supplier offline · Demand shock · Price spike · What-if analysis' },
  supplychain: { title: 'Supply Chain Map',            sub: 'Tier 1 / Tier 2 / Tier 3 network · Hidden concentration risk detection' },
  compliance:  { title: 'Regulatory Compliance',       sub: 'FDA CGMP · EMA GMP · WHO PQ · Audit schedules · Warning letters' },
  esg:         { title: 'ESG Scoring',                 sub: 'Environmental · Social · Governance · Scope 3 carbon emissions' },
}

function RefreshIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
      <path d="M21 3v5h-5"/>
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
      <path d="M3 21v-5h5"/>
    </svg>
  )
}

function AppInner() {
  const { user, ready, logout, hasAccess } = useAuth()
  const [page, setPage]             = useState('overview')
  const [apiStatus, setApiStatus]   = useState('checking')
  const [refreshKey, setRefreshKey] = useState(0)
  const [spinning, setSpinning]     = useState(false)

  useEffect(() => {
    api.health()
      .then(h => setApiStatus(h.status === 'ok' ? 'online' : 'offline'))
      .catch(() => setApiStatus('offline'))
  }, [])

  useEffect(() => {
    if (user && !hasAccess(page)) {
      const allowed = ROLE_PERMISSIONS[user.role] || []
      if (allowed.length) setPage(allowed[0])
    }
  }, [user, page, hasAccess])

  const handleRefresh = useCallback(() => {
    setSpinning(true); setRefreshKey(k => k + 1)
    setTimeout(() => setSpinning(false), 1200)
  }, [])

  if (!ready) return null
  if (!user)  return <Login />

  const nav = ALL_NAV
    .map(s => ({ ...s, items: s.items.filter(i => hasAccess(i.id)) }))
    .filter(s => s.items.length > 0)

  const renderPage = () => {
    const p = { key: refreshKey }
    switch (page) {
      case 'overview':    return <Overview {...p} />
      case 'forecast':    return <PriceForecast {...p} />
      case 'shortage':    return <ShortagePredictor {...p} />
      case 'geo':         return <GeopoliticalIntel {...p} />
      case 'demand':      return <DemandForecast {...p} />
      case 'benchmark':   return <Benchmarking {...p} />
      case 'counterfeit': return <CounterfeitRisk {...p} />
      case 'suppliers':   return <SupplierRisk {...p} />
      case 'inventory':   return <Inventory {...p} />
      case 'scenarios':   return <Scenarios {...p} />
      case 'supplychain': return <SupplyChainMap {...p} />
      case 'compliance':  return <Compliance {...p} />
      case 'esg':         return <ESGScoring {...p} />
      default:            return <Overview {...p} />
    }
  }

  const info = PAGE_TITLES[page] || PAGE_TITLES.overview

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">
            <div className="logo-icon">⚕️</div>
            <span className="logo-name">PharmaFlow AI</span>
          </div>
          <div className="logo-sub">Supply Chain Intelligence</div>
        </div>

        <nav className="sidebar-nav">
          {nav.map(({ section, items }) => (
            <div key={section}>
              <div className="nav-section-label">{section}</div>
              {items.map(({ id, label, icon }) => (
                <div key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => setPage(id)}>
                  <span className="nav-icon">{icon}</span>{label}
                </div>
              ))}
            </div>
          ))}
        </nav>

        <div style={{ padding: '0 12px 12px' }}>
          <div
            style={{ display:'flex',alignItems:'center',gap:8,padding:'10px 12px',borderRadius:8,background:'rgba(220,38,38,0.08)',border:'1px solid rgba(239,68,68,0.18)',cursor:'pointer',fontSize:12,fontWeight:500,color:'#f87171',transition:'all 0.2s' }}
            onClick={() => document.getElementById('ask-pharmaflow-fab')?.click()}
            onMouseEnter={e=>e.currentTarget.style.background='rgba(220,38,38,0.14)'}
            onMouseLeave={e=>e.currentTarget.style.background='rgba(220,38,38,0.08)'}
          >
            <span style={{fontSize:14}}>✦</span> Ask PharmaFlow AI
          </div>
        </div>

        <div className="sidebar-footer">
          <div style={{ display:'flex',alignItems:'center',gap:8,padding:'8px 10px',borderRadius:8,background:'rgba(255,255,255,0.03)',border:'1px solid rgba(255,255,255,0.07)',marginBottom:8 }}>
            <div style={{ width:28,height:28,borderRadius:'50%',flexShrink:0,background:'linear-gradient(135deg,#dc2626,#ef4444)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:10,fontWeight:700,color:'#fff' }}>
              {user.initials}
            </div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontSize:11,fontWeight:600,color:'var(--text-primary)',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{user.name}</div>
              <div style={{fontSize:10,color:'var(--text-muted)'}}>{user.role}</div>
            </div>
            <button onClick={logout} title="Sign out" style={{background:'none',border:'none',color:'var(--text-muted)',cursor:'pointer',fontSize:14,padding:'2px 4px',borderRadius:4}} onMouseEnter={e=>e.target.style.color='#ef4444'} onMouseLeave={e=>e.target.style.color='var(--text-muted)'}>⏻</button>
          </div>
          <div className="api-status">
            <div className={`status-dot ${apiStatus!=='online'?'offline':''}`} />
            <span>API {apiStatus==='online'?'· v5.0.0':apiStatus==='checking'?'· checking…':'· offline'}</span>
          </div>
          <div style={{marginTop:8,fontSize:10,color:'var(--text-muted)',textAlign:'center'}}>Phase 10 — Supply Chain · Compliance · ESG</div>
        </div>
      </aside>

      <main className="main-content">
        <div className="topbar">
          <div className="topbar-title"><h1>{info.title}</h1><p>{info.sub}</p></div>
          <div className="topbar-right">
            <button
              onClick={() => document.getElementById('ask-pharmaflow-fab')?.click()}
              style={{display:'flex',alignItems:'center',gap:6,padding:'7px 14px',background:'rgba(220,38,38,0.1)',border:'1px solid rgba(239,68,68,0.25)',borderRadius:8,color:'#f87171',fontSize:12,fontWeight:600,cursor:'pointer',fontFamily:'var(--font)',transition:'all 0.2s'}}
              onMouseEnter={e=>{e.currentTarget.style.background='rgba(220,38,38,0.18)';e.currentTarget.style.color='#fff'}}
              onMouseLeave={e=>{e.currentTarget.style.background='rgba(220,38,38,0.1)';e.currentTarget.style.color='#f87171'}}
            >
              ✦ Ask AI
            </button>
            <button className={`refresh-btn ${spinning?'spinning':''}`} onClick={handleRefresh}><RefreshIcon /> Refresh</button>
          </div>
        </div>
        <div className="page-content">{renderPage()}</div>
      </main>

      <AskPharmaFlow fabId="ask-pharmaflow-fab" />
    </div>
  )
}

export default function App() {
  return <AuthProvider><AppInner /></AuthProvider>
}
