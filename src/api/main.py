"""
PharmaFlow AI — FastAPI Main Application (Phase 2 + 3 + 5)
===========================================================
Development:
    python -m uvicorn src.api.main:app --reload --port 8000 --reload-exclude ".venv/*"

Production (Docker):
    uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 2

Interactive docs:
    http://localhost:8000/docs   (Swagger UI)
    http://localhost:8000/redoc  (ReDoc)
"""

import json
import logging
import uuid
import warnings
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import configure_logging, get_settings, verify_api_key

from .schemas import (
    AllocationLine,
    CountryRisk,
    DashboardSummary,
    DrugDemand,
    DrugOut,
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    GeoEventOut,
    GeoIntelligenceResponse,
    GeoSupplierAlert,
    HealthResponse,
    InventoryLine,
    InventoryRequest,
    InventoryResponse,
    OptimizeRequest,
    OptimizeResponse,
    QualityCheckRequest,
    QualityCheckResponse,
    RiskRequest,
    RiskResponse,
    ShortageAlert,
    ShortageRequest,
    ShortageResponse,
    SupplierOut,
)

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.api")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"
MODELS = _ROOT / "models"

# ── Boot config ──────────────────────────────────────────────────────────────
configure_logging()
settings = get_settings()

# ═════════════════════════════════════════════════════════════════════════════
# App factory
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="PharmaFlow AI",
    description=(
        "AI-powered pharmaceutical supply chain intelligence platform. "
        "Provides price forecasting, supplier risk scoring, quality anomaly detection, "
        "shortage prediction, geopolitical intelligence, and purchase optimisation as REST endpoints."
    ),
    version="4.0.0",
    contact={"name": "PharmaFlow AI"},
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "System", "description": "Health checks and metadata"},
        {"name": "Data", "description": "Drug and supplier catalogues"},
        {"name": "Intelligence", "description": "AI/ML forecasting, risk, and alert endpoints"},
        {"name": "Optimization", "description": "Purchase and inventory optimisation"},
        {"name": "Dashboard", "description": "Aggregated KPIs for the React dashboard"},
        {"name": "Auth", "description": "Authentication utilities"},
    ],
)

# ── Middleware stack ──────────────────────────────────────────────────────────

# 1. CORS (env-driven origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Request ID middleware (adds X-Request-ID to every response)
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

app.add_middleware(RequestIDMiddleware)

# 3. Rate limiting (slowapi)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    RATE_LIMIT = f"{settings.rate_limit_per_minute}/minute"
    log.info(f"Rate limiting enabled: {RATE_LIMIT}")
except ImportError:
    limiter = None
    RATE_LIMIT = "1000/minute"
    log.warning("slowapi not installed — rate limiting disabled")

# 4. Prometheus metrics
if settings.prometheus_enabled:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator().instrument(app).expose(app, endpoint=settings.metrics_path)
        log.info(f"Prometheus metrics at {settings.metrics_path}")
    except ImportError:
        log.warning("prometheus-fastapi-instrumentator not installed — metrics disabled")


# ═════════════════════════════════════════════════════════════════════════════
# Startup: load data + models into memory
# ═════════════════════════════════════════════════════════════════════════════

_cache = {}


@app.on_event("startup")
async def startup():
    log.info("Loading PharmaFlow AI data + models…")
    _cache["drugs"] = pd.read_csv(SYNTHETIC / "drugs.csv")
    _cache["suppliers"] = pd.read_csv(SYNTHETIC / "suppliers.csv")
    _cache["risk_scores"] = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")
    _cache["forecasts"] = pd.read_csv(PROCESSED / "price_forecasts.csv")
    _cache["forecasts"]["ds"] = pd.to_datetime(_cache["forecasts"]["ds"])
    _cache["forecast_metrics"] = pd.read_csv(PROCESSED / "price_forecast_metrics.csv")
    _cache["quality_results"] = pd.read_csv(PROCESSED / "quality_anomaly_results.csv")
    _cache["quality_trends"] = pd.read_csv(PROCESSED / "quality_trends.csv")

    # Load quality anomaly models
    iso_path = MODELS / "quality_anomaly" / "isolation_forest.pkl"
    spc_path = MODELS / "quality_anomaly" / "spc_baselines.pkl"
    if iso_path.exists():
        _cache["iso_forest"] = joblib.load(iso_path)
    if spc_path.exists():
        _cache["spc_baselines"] = joblib.load(spc_path)

    # Load supplier risk model
    risk_model_path = MODELS / "supplier_risk" / "xgb_risk_model.pkl"
    if risk_model_path.exists():
        _cache["risk_model"] = joblib.load(risk_model_path)

    log.info("✅ PharmaFlow AI API ready")


# ═════════════════════════════════════════════════════════════════════════════
# Routes
# ═════════════════════════════════════════════════════════════════════════════

from fastapi.responses import RedirectResponse, Response

# ── Root redirect → /docs ─────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root URL to the Swagger interactive docs."""
    return RedirectResponse(url="/docs")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Suppress favicon 404 errors in browser."""
    return Response(status_code=204)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Health check endpoint."""
    return HealthResponse()


# ── Drugs ─────────────────────────────────────────────────────────────────────

@app.get("/drugs", response_model=List[DrugOut], tags=["Data"])
async def list_drugs():
    """Return all drugs in the formulary."""
    drugs = _cache["drugs"]

    def parse_suppliers(x):
        try:
            return len(json.loads(x))
        except Exception:
            return 0

    result = []
    for _, row in drugs.iterrows():
        result.append(
            DrugOut(
                id=row["id"],
                name=row["name"],
                category=row.get("category", ""),
                base_price_per_kg=float(row.get("base_price_per_kg", 0)),
                criticality=row.get("criticality", "medium"),
                demand_seasonality=row.get("demand_seasonality", "flat"),
                num_approved_suppliers=parse_suppliers(row.get("approved_suppliers", "[]")),
            )
        )
    return result


# ── Suppliers ─────────────────────────────────────────────────────────────────

@app.get("/suppliers", response_model=List[SupplierOut], tags=["Data"])
async def list_suppliers():
    """Return all suppliers with latest risk scores."""
    suppliers = _cache["suppliers"]
    risk = _cache["risk_scores"][["supplier_id", "risk_score", "risk_tier"]]
    merged = suppliers.merge(risk, left_on="id", right_on="supplier_id", how="left")

    result = []
    for _, row in merged.iterrows():
        result.append(
            SupplierOut(
                id=row["id"],
                name=row["name"],
                country=row.get("country", ""),
                region=row.get("region", ""),
                price_tier=row.get("price_tier", ""),
                fda_approved=bool(row.get("fda_approved", False)),
                risk_score=round(float(row["risk_score"]), 1)
                if pd.notna(row.get("risk_score"))
                else None,
                risk_tier=row.get("risk_tier") if pd.notna(row.get("risk_tier")) else None,
            )
        )
    return result


# ── Price Forecast ─────────────────────────────────────────────────────────────

@app.post("/forecast/price", response_model=ForecastResponse, tags=["Intelligence"])
async def forecast_price(req: ForecastRequest):
    """
    Return price forecast for a given drug.
    Uses pre-computed Prophet forecasts from Phase 1.
    """
    forecasts = _cache["forecasts"]
    drug_fc = forecasts[forecasts["drug_id"] == req.drug_id].sort_values("ds")

    if drug_fc.empty:
        raise HTTPException(status_code=404, detail=f"No forecast found for drug {req.drug_id}")

    # Filter to future dates only, up to weeks_ahead
    future = drug_fc[drug_fc["ds"] >= pd.Timestamp.now()].head(req.weeks_ahead)
    if future.empty:
        # Fall back to last N rows (all forecast data)
        future = drug_fc.tail(req.weeks_ahead)

    drugs = _cache["drugs"]
    drug_row = drugs[drugs["id"] == req.drug_id]
    drug_name = drug_row["name"].iloc[0] if not drug_row.empty else req.drug_id

    metrics = _cache["forecast_metrics"]
    mape_row = metrics[metrics["drug_id"] == req.drug_id]
    mape = float(mape_row["mape"].iloc[0]) if not mape_row.empty else None

    forecast_points = []
    for _, row in future.iterrows():
        forecast_points.append(
            ForecastPoint(
                date=row["ds"].strftime("%Y-%m-%d"),
                predicted_price=round(float(row["yhat"]), 2),
                lower_bound=round(float(row["yhat_lower"]), 2)
                if "yhat_lower" in row
                else None,
                upper_bound=round(float(row["yhat_upper"]), 2)
                if "yhat_upper" in row
                else None,
            )
        )

    return ForecastResponse(
        drug_id=req.drug_id,
        drug_name=drug_name,
        mape_pct=round(mape, 1) if mape else None,
        forecast=forecast_points,
    )


# ── Supplier Risk ──────────────────────────────────────────────────────────────

@app.post("/risk/supplier", response_model=RiskResponse, tags=["Intelligence"])
async def supplier_risk(req: RiskRequest):
    """Return composite risk score and breakdown for a supplier."""
    risk = _cache["risk_scores"]
    row = risk[risk["supplier_id"] == req.supplier_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Supplier {req.supplier_id} not found")
    row = row.iloc[0]

    suppliers = _cache["suppliers"]
    sup = suppliers[suppliers["id"] == req.supplier_id]
    sup_name = sup["name"].iloc[0] if not sup.empty else req.supplier_id

    score = float(row["risk_score"])
    tier = str(row["risk_tier"])
    rec_map = {
        "Low": "✅ Preferred supplier — continue use and monitor quarterly.",
        "Moderate": "⚠️ Monitor closely — review quality and delivery KPIs monthly.",
        "High": "🔶 Use with caution — develop contingency suppliers urgently.",
        "Critical": "🚨 Avoid new orders — initiate supplier audit immediately.",
    }

    return RiskResponse(
        supplier_id=req.supplier_id,
        supplier_name=sup_name,
        risk_score=round(score, 1),
        risk_tier=tier,
        delivery_risk=round(float(row.get("delivery_risk", 0)), 1),
        quality_risk=round(float(row.get("quality_risk", 0)), 1),
        incident_risk=round(float(row.get("incident_risk", 0)), 1),
        geo_regulatory_risk=round(float(row.get("geo_regulatory_risk", 0)), 1),
        recommendation=rec_map.get(tier, "Monitor."),
    )


# ── Quality Anomaly ────────────────────────────────────────────────────────────

@app.post("/anomaly/quality", response_model=QualityCheckResponse, tags=["Intelligence"])
async def quality_anomaly(req: QualityCheckRequest):
    """
    Check if a batch quality reading is anomalous.
    Uses Isolation Forest + SPC baselines from Phase 1.
    """
    features = np.array(
        [[req.purity_pct, req.contamination_ppm, req.moisture_pct, req.particle_size_d90]]
    )

    anomaly_methods = []
    iso_score = 0.0

    # Isolation Forest
    if "iso_forest" in _cache:
        pred = _cache["iso_forest"].predict(features)
        iso_score = float(-_cache["iso_forest"].score_samples(features)[0])
        if pred[0] == -1:
            anomaly_methods.append("isolation_forest")

    # SPC check
    spc_violations = []
    if "spc_baselines" in _cache:
        baselines = _cache["spc_baselines"]
        key = f"{req.supplier_id}_{req.drug_id}"
        if key in baselines:
            bl = baselines[key]
            checks = {
                "purity_pct": req.purity_pct,
                "contamination_ppm": req.contamination_ppm,
                "moisture_pct": req.moisture_pct,
                "particle_size_d90": req.particle_size_d90,
            }
            for metric, val in checks.items():
                if metric in bl:
                    mean = bl[metric]["mean"]
                    std = bl[metric]["std"]
                    if std > 0 and abs(val - mean) > 2 * std:
                        spc_violations.append(metric)
        if spc_violations:
            anomaly_methods.append("spc")

    is_anomaly = len(anomaly_methods) > 0
    anomaly_score = round(iso_score, 4)

    # Risk level
    if len(anomaly_methods) >= 2:
        risk_level = "HIGH"
        recommendation = "🚨 Reject batch — multiple anomaly signals detected. Initiate supplier audit."
    elif len(anomaly_methods) == 1:
        risk_level = "MEDIUM"
        recommendation = "⚠️ Hold batch — single anomaly signal. Request re-test before release."
    else:
        risk_level = "LOW"
        recommendation = "✅ Batch within normal parameters — approve for use."

    return QualityCheckResponse(
        supplier_id=req.supplier_id,
        drug_id=req.drug_id,
        is_anomaly=is_anomaly,
        anomaly_methods=anomaly_methods,
        anomaly_score=anomaly_score,
        spc_violations=spc_violations,
        risk_level=risk_level,
        recommendation=recommendation,
    )


# ── Purchase Optimisation ──────────────────────────────────────────────────────

@app.post("/optimize/purchase", response_model=OptimizeResponse, tags=["Optimization"])
async def optimize_purchase(req: OptimizeRequest):
    """
    Run the LP bulk purchase optimizer.
    Returns optimal supplier allocation across all drugs.
    """
    from ..optimization.purchase_optimizer import PurchaseOptimizer

    demand_dict = {d.drug_id: d.quantity_kg for d in req.demand} if req.demand else None

    opt = PurchaseOptimizer(
        demand_kg=demand_dict,
        risk_penalty_weight=req.risk_penalty_weight,
        concentration_limit=req.concentration_limit,
    )
    result = opt.optimize()

    if "error" in result:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {result['error']}")

    alloc_df = result["allocation_df"]
    allocation = [
        AllocationLine(
            drug_id=r["drug_id"],
            drug_name=r["drug_name"],
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
            supplier_country=r["supplier_country"],
            quantity_kg=r["quantity_kg"],
            price_per_kg=r["price_per_kg"],
            raw_cost_usd=r["raw_cost_usd"],
            risk_score=r["risk_score"],
            risk_penalty_usd=r["risk_penalty_usd"],
            total_effective_cost=r["total_effective_cost"],
            pct_of_demand=r["pct_of_demand"],
        )
        for _, r in alloc_df.iterrows()
    ]

    return OptimizeResponse(
        solver=result["solver"],
        num_drugs=result["num_drugs"],
        num_suppliers_used=result["num_suppliers_used"],
        total_raw_cost_usd=result["total_raw_cost"],
        total_risk_penalty_usd=result["total_risk_penalty"],
        total_effective_cost_usd=result["total_effective_cost"],
        allocation=allocation,
    )


# ── Inventory Recommendations ──────────────────────────────────────────────────

@app.post("/optimize/inventory", response_model=InventoryResponse, tags=["Optimization"])
async def optimize_inventory(req: InventoryRequest):
    """
    Compute inventory recommendations (safety stock, reorder points, EOQ).
    """
    from ..optimization.inventory_manager import InventoryManager

    mgr = InventoryManager(
        current_stock_kg=req.current_stock,
        service_level=req.service_level,
    )
    df = mgr.compute_recommendations()
    s = mgr.summary(df)

    recs = [
        InventoryLine(
            drug_id=r["drug_id"],
            drug_name=r["drug_name"],
            category=r.get("category", ""),
            criticality=r.get("criticality", "medium"),
            avg_daily_demand_kg=r["avg_daily_demand_kg"],
            avg_lead_time_days=r["avg_lead_time_days"],
            safety_stock_kg=r["safety_stock_kg"],
            reorder_point_kg=r["reorder_point_kg"],
            eoq_kg=r["eoq_kg"],
            current_stock_kg=r["current_stock_kg"],
            days_cover=r["days_cover"],
            action=r["action"],
            urgency_score=r["urgency_score"],
            stock_value_usd=r["stock_value_usd"],
        )
        for _, r in df.iterrows()
    ]

    return InventoryResponse(
        total_drugs=s["total_drugs"],
        reorder_now=s["reorder_now"],
        reorder_soon=s["reorder_soon"],
        adequate=s["adequate"],
        excess=s["excess"],
        total_stock_value_usd=s["total_stock_value_usd"],
        avg_days_cover=s["avg_days_cover"],
        critical_reorders=s["critical_reorders"],
        recommendations=recs,
    )


# ── Dashboard Summary ──────────────────────────────────────────────────────────

@app.get("/dashboard/summary", response_model=DashboardSummary, tags=["Dashboard"])
async def dashboard_summary():
    """
    Comprehensive analytics summary powering the Phase 4 dashboard.
    Returns key KPIs, alerts, and top risk suppliers.
    """
    drugs = _cache["drugs"]
    suppliers = _cache["suppliers"]
    risk = _cache["risk_scores"]
    metrics = _cache["forecast_metrics"]
    quality = _cache["quality_results"]

    # Inventory quick check
    from ..optimization.inventory_manager import InventoryManager
    mgr = InventoryManager()
    inv_df = mgr.compute_recommendations()
    inv_summary = mgr.summary(inv_df)

    # Top 5 riskiest suppliers
    top_risk = risk.nlargest(5, "risk_score")[
        ["supplier_id", "supplier_name", "risk_score", "risk_tier"]
    ].to_dict(orient="records")

    # Price alerts: drugs where price forecast > base_price * 1.15
    price_alerts = []
    forecasts = _cache["forecasts"]
    for _, drug in drugs.iterrows():
        d = drug["id"]
        fc = forecasts[forecasts["drug_id"] == d].sort_values("ds")
        if fc.empty:
            continue
        latest_price = float(fc["yhat"].iloc[-1])
        base = float(drug.get("base_price_per_kg", 50))
        if latest_price > base * 1.15:
            price_alerts.append(
                {
                    "drug_id": d,
                    "drug_name": drug["name"],
                    "base_price": round(base, 2),
                    "forecast_price": round(latest_price, 2),
                    "pct_increase": round((latest_price / base - 1) * 100, 1),
                }
            )

    # Inventory alerts
    inv_alerts = inv_df[inv_df["action"].isin(["REORDER_NOW", "REORDER_SOON"])][
        ["drug_id", "drug_name", "action", "days_cover", "urgency_score"]
    ].to_dict(orient="records")

    # Shortage alerts (Phase 3)
    from ..intelligence.shortage_predictor import ShortagePredictor
    sp = ShortagePredictor()
    shortage_df = sp.predict_all()
    shortage_alerts = shortage_df[shortage_df["risk_tier"].isin(["CRITICAL", "WARNING"])][
        ["drug_id", "drug_name", "shortage_risk_score", "risk_tier", "recommended_action"]
    ].to_dict(orient="records")

    # Geo alerts (Phase 3)
    from ..intelligence.geopolitical_intelligence import GeopoliticalIntelligence
    geo = GeopoliticalIntelligence()
    geo_result = geo.run()
    geo_alerts = geo_result["supplier_alerts"][
        geo_result["supplier_alerts"]["alert_level"] == "HIGH"
    ][["supplier_id", "supplier_name", "country", "adjusted_risk_score", "top_event", "alert_level"]].to_dict(orient="records")

    return DashboardSummary(
        total_drugs=len(drugs),
        total_suppliers=len(suppliers),
        critical_suppliers=int((risk["risk_tier"] == "Critical").sum()),
        high_risk_suppliers=int((risk["risk_tier"] == "High").sum()),
        drugs_needing_reorder=inv_summary["reorder_now"] + inv_summary["reorder_soon"],
        avg_price_forecast_mape_pct=round(float(metrics["mape"].mean()), 1),
        total_anomalies_detected=int(quality["is_anomaly"].sum())
        if "is_anomaly" in quality.columns
        else 0,
        top_risk_suppliers=top_risk,
        price_alerts=price_alerts[:10],
        inventory_alerts=inv_alerts[:10],
        shortage_alerts=shortage_alerts[:10],
        geo_alerts=geo_alerts[:10],
    )


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3: Shortage Prediction
# ═════════════════════════════════════════════════════════════════════════════

@app.post("/predict/shortage", response_model=ShortageResponse, tags=["Intelligence"])
async def predict_shortage(req: ShortageRequest):
    """
    Predict supply shortage risk for all drugs (or a single drug).
    Combines demand spikes, supply concentration (HHI), lead time stress,
    inventory runway, and supplier risk overlay into a composite 0–100 score.
    """
    from ..intelligence.shortage_predictor import ShortagePredictor

    sp = ShortagePredictor(
        lookback_weeks=req.lookback_weeks,
        recent_weeks=req.recent_weeks,
    )
    df = sp.predict_all()

    if req.drug_id:
        df = df[df["drug_id"] == req.drug_id]
        if df.empty:
            raise HTTPException(status_code=404, detail=f"Drug {req.drug_id} not found")

    s = sp.summary(df)

    alerts = [
        ShortageAlert(
            drug_id=r["drug_id"],
            drug_name=r["drug_name"],
            category=r.get("category", ""),
            criticality=r.get("criticality", "medium"),
            shortage_risk_score=r["shortage_risk_score"],
            risk_tier=r["risk_tier"],
            demand_spike_score=r["demand_spike_score"],
            supply_concentration_score=r["supply_concentration_score"],
            lead_time_stress_score=r["lead_time_stress_score"],
            inventory_runway_score=r["inventory_runway_score"],
            supplier_risk_overlay_score=r["supplier_risk_overlay_score"],
            recommended_action=r["recommended_action"],
        )
        for _, r in df.iterrows()
    ]

    return ShortageResponse(
        total_drugs=s["total_drugs"],
        critical=s["critical"],
        warning=s["warning"],
        watch=s["watch"],
        stable=s["stable"],
        avg_risk_score=s["avg_risk_score"],
        highest_risk_drug=s["highest_risk_drug"],
        alerts=alerts,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3: Geopolitical Intelligence
# ═════════════════════════════════════════════════════════════════════════════

@app.get("/intelligence/geopolitical", response_model=GeoIntelligenceResponse, tags=["Intelligence"])
async def geopolitical_intelligence():
    """
    Run the geopolitical intelligence engine.
    Returns active events, supplier alerts, and country risk index.
    """
    from ..intelligence.geopolitical_intelligence import GeopoliticalIntelligence

    engine = GeopoliticalIntelligence(n_events=25)
    result = engine.run()
    s = result["summary"]

    top_events = [
        GeoEventOut(
            event_id=r["event_id"],
            event_type=r["event_type"],
            country=r["country"],
            event_date=r["event_date"],
            days_ago=int(r["days_ago"]),
            description=r["description"],
            severity=r["severity"],
            active=bool(r["active"]),
            effective_score=r["effective_score"],
        )
        for _, r in result["events_df"][result["events_df"]["active"]].head(10).iterrows()
    ]

    sup_alerts = [
        GeoSupplierAlert(
            supplier_id=r["supplier_id"],
            supplier_name=r["supplier_name"],
            country=r["country"],
            base_risk_score=r["base_risk_score"],
            geo_intelligence_score=r["geo_intelligence_score"],
            adjusted_risk_score=r["adjusted_risk_score"],
            risk_delta=r["risk_delta"],
            active_geo_events=int(r["active_geo_events"]),
            top_event=r["top_event"],
            alert_level=r["alert_level"],
        )
        for _, r in result["supplier_alerts"].iterrows()
    ]

    country_risk = [
        CountryRisk(
            country=r["country"],
            combined_risk=r["combined_risk"],
            num_events=int(r["num_events"]),
            top_event_type=r["top_event_type"],
            baseline_risk=r["baseline_risk"],
        )
        for _, r in result["country_risk"].iterrows()
    ]

    return GeoIntelligenceResponse(
        total_events=s["total_events"],
        active_events=s["active_events"],
        countries_affected=s["countries_affected"],
        suppliers_on_high_alert=s["suppliers_on_high_alert"],
        suppliers_on_medium_alert=s["suppliers_on_medium_alert"],
        most_dangerous_country=s["most_dangerous_country"],
        top_events=top_events,
        supplier_alerts=sup_alerts,
        country_risk_index=country_risk,
    )


@app.get("/intelligence/alerts", tags=["Intelligence"])
async def intelligence_alerts():
    """
    Combined alert feed: shortage + geopolitical + price signals.
    Ordered by severity for use in a notification / alert dashboard panel.
    """
    from ..intelligence.shortage_predictor import ShortagePredictor
    from ..intelligence.geopolitical_intelligence import GeopoliticalIntelligence

    # Shortage alerts
    sp = ShortagePredictor()
    shortage_df = sp.predict_all()
    critical_drugs = shortage_df[shortage_df["risk_tier"] == "CRITICAL"]
    warning_drugs = shortage_df[shortage_df["risk_tier"] == "WARNING"]

    alerts = []

    for _, r in critical_drugs.iterrows():
        alerts.append({
            "type": "shortage",
            "severity": "CRITICAL",
            "title": f"🚨 Shortage Risk: {r['drug_name']}",
            "body": r["recommended_action"],
            "score": r["shortage_risk_score"],
            "entity_id": r["drug_id"],
        })

    for _, r in warning_drugs.iterrows():
        alerts.append({
            "type": "shortage",
            "severity": "WARNING",
            "title": f"⚠️ Shortage Warning: {r['drug_name']}",
            "body": r["recommended_action"],
            "score": r["shortage_risk_score"],
            "entity_id": r["drug_id"],
        })

    # Geo alerts
    geo = GeopoliticalIntelligence()
    geo_result = geo.run()
    high_geo = geo_result["supplier_alerts"][geo_result["supplier_alerts"]["alert_level"] == "HIGH"]
    for _, r in high_geo.iterrows():
        alerts.append({
            "type": "geopolitical",
            "severity": "HIGH",
            "title": f"🌍 Geo Alert: {r['supplier_name']} ({r['country']})",
            "body": r["top_event"],
            "score": r["adjusted_risk_score"],
            "entity_id": r["supplier_id"],
        })

    # Price alerts
    forecasts = _cache["forecasts"]
    drugs = _cache["drugs"]
    for _, drug in drugs.iterrows():
        fc = forecasts[forecasts["drug_id"] == drug["id"]].sort_values("ds")
        if fc.empty:
            continue
        latest = float(fc["yhat"].iloc[-1])
        base = float(drug.get("base_price_per_kg", 50))
        pct = (latest / base - 1) * 100
        if pct > 20:
            alerts.append({
                "type": "price",
                "severity": "HIGH" if pct > 30 else "MEDIUM",
                "title": f"📈 Price Spike: {drug['name']} (+{pct:.1f}%)",
                "body": f"Forecast price ${latest:.2f}/kg vs base ${base:.2f}/kg. Consider forward buying.",
                "score": min(pct, 100),
                "entity_id": drug["id"],
            })

    # Sort by score descending
    alerts.sort(key=lambda x: x["score"], reverse=True)
    return {"total_alerts": len(alerts), "alerts": alerts}
