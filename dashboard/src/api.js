// Central API client — Phase 8 update
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`
  : '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  // Core
  health:            () => get('/health'),
  drugs:             () => get('/drugs'),
  suppliers:         () => get('/suppliers'),
  dashboardSummary:  () => get('/dashboard/summary'),
  alerts:            () => get('/intelligence/alerts'),
  geopolitical:      () => get('/intelligence/geopolitical'),

  // Intelligence
  forecastPrice:     (drug_id, weeks_ahead = 12) => post('/forecast/price', { drug_id, weeks_ahead }),
  supplierRisk:      (supplier_id) => post('/risk/supplier', { supplier_id }),
  qualityCheck:      (payload) => post('/anomaly/quality', payload),
  predictShortage:   (opts = {}) => post('/predict/shortage', opts),
  optimizePurchase:  (payload = {}) => post('/optimize/purchase', payload),
  optimizeInventory: (payload = {}) => post('/optimize/inventory', payload),

  // Phase 7 — Ask PharmaFlow
  chat: (question, history = []) => post('/chat', { question, history }),

  // Phase 8 — Demand Forecast + Simulations
  demandForecast: () => get('/intelligence/demand-forecast'),
  simulateSupplierOffline: (supplier_id, drug_ids = null) =>
    post('/simulate/supplier-offline', { supplier_id, ...(drug_ids ? { drug_ids } : {}) }),
  simulateDemandShock: (drug_id, multiplier = 2.0) =>
    post('/simulate/demand-shock', { drug_id, multiplier }),
  simulatePriceSpike: (supplier_ids = null, price_multiplier = 1.2) =>
    post('/simulate/price-spike', { price_multiplier, ...(supplier_ids ? { supplier_ids } : {}) }),
}
