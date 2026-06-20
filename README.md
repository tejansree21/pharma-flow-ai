# ⚕️ PharmaFlow AI

> **AI-Powered Pharmaceutical Supply Chain Intelligence Platform**

[![CI](https://github.com/your-org/pharmaflow-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/pharmaflow-ai/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-4.0.0-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

PharmaFlow AI is a full-stack AI platform for pharmaceutical supply chain intelligence. It combines machine learning forecasting, multi-signal risk scoring, geopolitical event analysis, and LP-based procurement optimisation into a single production-ready system.

---

## 🗺️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Dashboard (Port 5173/80)            │
│   Overview · Forecast · Shortage · Geo Intel · Inventory    │
└─────────────────────┬───────────────────────────────────────┘
                      │  /api proxy
┌─────────────────────▼───────────────────────────────────────┐
│                FastAPI Backend (Port 8000)                   │
│   12 endpoints · Rate limiting · API Key auth · Prometheus  │
├──────────────┬──────────────┬─────────────────┬────────────┤
│  Phase 1 ML  │  Phase 2 Opt │  Phase 3 Intel  │  Phase 5   │
│  · Prophet   │  · PuLP LP   │  · Shortage     │  · Auth    │
│  · XGBoost   │  · EOQ/SS    │  · Geo Events   │  · Docker  │
│  · IsoForest │  · Reorder   │  · Alert Feed   │  · CI/CD   │
└──────────────┴──────────────┴─────────────────┴────────────┘
```

---

## ✅ Phase Completion Status

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Synthetic data generation (18 drugs, 15+ suppliers) | ✅ Complete |
| 1 | Prophet price forecasting with external regressors | ✅ Complete |
| 1 | Isolation Forest + SPC quality anomaly detection | ✅ Complete |
| 1 | XGBoost supplier risk scoring | ✅ Complete |
| 2 | PuLP LP bulk purchase optimizer | ✅ Complete |
| 2 | Safety stock / EOQ / reorder point inventory manager | ✅ Complete |
| 2 | FastAPI REST API (9 endpoints) | ✅ Complete |
| 3 | 5-signal shortage predictor (HHI, demand spike, lead time…) | ✅ Complete |
| 3 | Geopolitical intelligence engine (10 event types, decay scoring) | ✅ Complete |
| 3 | Unified alert feed (shortage + geo + price) | ✅ Complete |
| 4 | Dark glassmorphism React dashboard | ✅ Complete |
| 4 | 6 dashboard pages with Recharts visualisations | ✅ Complete |
| 5 | API key authentication + JWT | ✅ Complete |
| 5 | Rate limiting (slowapi) | ✅ Complete |
| 5 | Prometheus metrics instrumentation | ✅ Complete |
| 5 | Docker multi-stage builds (API + dashboard) | ✅ Complete |
| 5 | Docker Compose (API + Dashboard + Prometheus + Grafana) | ✅ Complete |
| 5 | GitHub Actions CI/CD (5-job pipeline) | ✅ Complete |
| 5 | Nginx production config (proxy + gzip + security headers) | ✅ Complete |

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone and set up Python environment
git clone https://github.com/your-org/pharmaflow-ai.git
cd pharmaflow-ai
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY and API_KEY if needed

# 4. Generate synthetic data + train models
python -m src.data_generation.synthetic_data
python src/models/price_forecast.py
python src/models/quality_anomaly.py
python src/models/supplier_risk.py

# 5. Start the API (Terminal 1)
python -m uvicorn src.api.main:app --reload --port 8000 --reload-exclude ".venv/*"
# → http://localhost:8000/docs

# 6. Start the dashboard (Terminal 2)
cd dashboard
npm install
npm run dev
# → http://localhost:5173
```

### Docker (Production)

```bash
# Copy and configure environment
cp .env.example .env
# Edit SECRET_KEY and API_KEY

# Start all services
docker compose up -d

# With monitoring stack
docker compose --profile monitoring up -d

# View logs
docker compose logs -f api
docker compose logs -f dashboard

# Stop
docker compose down
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

---

## 📡 API Reference

All endpoints available at `http://localhost:8000/docs`

### Authentication
Set `X-API-Key` header if `API_KEY` is configured in `.env`:
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/health
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/drugs` | List all drugs in formulary |
| GET | `/suppliers` | List suppliers with risk scores |
| POST | `/forecast/price` | Prophet price forecast (1–52 weeks) |
| POST | `/risk/supplier` | Supplier composite risk breakdown |
| POST | `/anomaly/quality` | Isolation Forest + SPC quality check |
| POST | `/predict/shortage` | Multi-signal shortage risk prediction |
| GET | `/intelligence/geopolitical` | Geo event feed + country risk index |
| GET | `/intelligence/alerts` | Unified sorted alert feed |
| POST | `/optimize/purchase` | LP bulk purchase optimizer |
| POST | `/optimize/inventory` | EOQ / safety stock recommendations |
| GET | `/dashboard/summary` | Aggregated KPIs for the dashboard |
| GET | `/metrics` | Prometheus metrics |

---

## 🗂️ Project Structure

```
PharmaFlowAI/
├── .github/workflows/ci.yml    # GitHub Actions CI/CD (5 jobs)
├── .env.example                # Environment template
├── .gitignore
├── Dockerfile                  # API multi-stage build
├── docker-compose.yml          # Full stack orchestration
├── requirements.txt
├── verify_phase2.py            # Quick sanity check script
│
├── deploy/
│   └── prometheus.yml          # Prometheus scrape config
│
├── src/
│   ├── api/
│   │   ├── config.py           # Settings, auth, rate limiting
│   │   ├── main.py             # FastAPI app (12 endpoints)
│   │   └── schemas.py          # Pydantic v2 models
│   ├── data_generation/        # Synthetic pharma data generator
│   ├── intelligence/
│   │   ├── shortage_predictor.py    # 5-signal shortage scorer
│   │   └── geopolitical_intelligence.py  # Geo event engine
│   ├── models/
│   │   ├── price_forecast.py   # Prophet forecasting
│   │   ├── quality_anomaly.py  # Isolation Forest + SPC
│   │   └── supplier_risk.py    # XGBoost risk scoring
│   └── optimization/
│       ├── purchase_optimizer.py   # PuLP LP optimizer
│       └── inventory_manager.py    # EOQ / safety stock
│
├── dashboard/                  # React + Vite frontend
│   ├── Dockerfile              # Node build → nginx serve
│   ├── nginx.conf              # Production nginx config
│   ├── vite.config.js          # Vite + /api proxy
│   └── src/
│       ├── App.jsx             # Sidebar shell + routing
│       ├── api.js              # API client
│       ├── index.css           # Glassmorphism design system
│       └── pages/
│           ├── Overview.jsx
│           ├── PriceForecast.jsx
│           ├── SupplierRisk.jsx
│           ├── ShortagePredictor.jsx
│           ├── GeopoliticalIntel.jsx
│           └── Inventory.jsx
│
├── data/
│   ├── synthetic/              # Generated CSV datasets
│   └── processed/              # Model output CSVs
├── models/                     # Saved .pkl model files
└── notebooks/
    ├── PF01_Phase1_Walkthrough.ipynb
    └── PF02_Phase2_Walkthrough.ipynb
```

---

## 🔒 Security

- **API Key auth**: Set `API_KEY` in `.env` → all endpoints require `X-API-Key` header
- **JWT**: Available for user-facing auth via `create_access_token()` in `config.py`
- **Rate limiting**: 60 req/min per IP (configurable via `RATE_LIMIT_PER_MINUTE`)
- **CORS**: Restricted to configured origins (not `*`) in production
- **Request IDs**: Every response gets `X-Request-ID` for tracing
- **Non-root Docker**: API container runs as `uid=1001`
- **Security headers**: Nginx enforces CSP, X-Frame-Options, XSS protection

---

## 📊 ML Models

| Model | Algorithm | Task | Output |
|-------|-----------|------|--------|
| Price Forecast | Facebook Prophet | Time-series regression | $/kg weekly forecast + CI |
| Quality Anomaly | Isolation Forest + SPC | Unsupervised anomaly detection | Binary flag + violation list |
| Supplier Risk | XGBoost + feature engineering | Composite risk scoring | 0–100 score + tier |
| Shortage Predictor | Multi-signal weighted composite | Supply disruption prediction | 0–100 score + CRITICAL/WARNING/WATCH/STABLE |
| Geo Intelligence | Event taxonomy + time-decay | Geopolitical risk overlay | Country risk index + supplier adjustments |

---

## 🧪 CI/CD Pipeline

5-job GitHub Actions pipeline on every push to `main`/`develop`:

1. **🧪 Test API** — verify_phase2.py + API health check
2. **🎨 Test Dashboard** — `npm run build`
3. **🔒 Security Scan** — `safety` CVE check + `bandit` static analysis
4. **🐳 Build & Push** — multi-arch Docker images to GitHub Container Registry
5. **🚀 Deploy** — configurable for Railway / Render / VPS

---

## 📈 Monitoring

When running with `--profile monitoring`:

- **Prometheus**: scrapes `/metrics` every 10s
- **Grafana**: pre-configured with API throughput, latency, error rate dashboards
- Tracked metrics: request count, latency histograms, in-flight requests, error rates

---

## 🤝 Contributing

1. Fork → feature branch → PR to `develop`
2. All PRs must pass the 5-job CI pipeline
3. Run `python verify_phase2.py` locally before pushing

---

## 📄 License

MIT © PharmaFlow AI
