// Central API client
// In production (Vercel), VITE_API_URL is set to the Render backend URL.
// In development, requests go through the Vite /api proxy → localhost:8000.

const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`   // production: full Render URL
  : '/api'                                // dev: Vite proxy

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
  health:            () => get('/health'),
  drugs:             () => get('/drugs'),
  suppliers:         () => get('/suppliers'),
  dashboardSummary:  () => get('/dashboard/summary'),
  alerts:            () => get('/intelligence/alerts'),
  geopolitical:      () => get('/intelligence/geopolitical'),
  forecastPrice:     (drug_id, weeks_ahead = 12) => post('/forecast/price', { drug_id, weeks_ahead }),
  supplierRisk:      (supplier_id) => post('/risk/supplier', { supplier_id }),
  qualityCheck:      (payload) => post('/anomaly/quality', payload),
  predictShortage:   (opts = {}) => post('/predict/shortage', opts),
  optimizePurchase:  (payload = {}) => post('/optimize/purchase', payload),
  optimizeInventory: (payload = {}) => post('/optimize/inventory', payload),
}
