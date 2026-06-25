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
import os
import httpx
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

# ═════════════════════════════════════════════════════════════════════════════
# Phase 7: Ask PharmaFlow — Conversational AI Chat Endpoint
# ═════════════════════════════════════════════════════════════════════════════
#
# Add this block at the BOTTOM of main.py, after all existing routes.
# Also add to your imports at the top of main.py:
#   import os
#   import httpx
#   from .schemas import ChatRequest, ChatResponse, ChatMessage
#
# Add ANTHROPIC_API_KEY to your .env and Render environment variables.
# ═════════════════════════════════════════════════════════════════════════════

import os
import httpx

from .schemas import ChatRequest, ChatResponse, ChatMessage

# ── Intent keyword classifier ─────────────────────────────────────────────────

_INTENT_MAP = {
    "risk": [
        "risk", "risky", "dangerous", "unsafe", "critical",
        "high risk", "vendor", "supplier score", "audit",
        "reliable", "worst supplier", "best supplier",
    ],
    "forecast": [
        "price", "forecast", "cost", "cheap", "expensive",
        "forward buy", "predict", "trend", "going up", "going down",
        "next week", "next month", "buy now", "wait",
    ],
    "shortage": [
        "shortage", "stockout", "short", "running out",
        "supply disruption", "unavailable", "critical drug",
        "at risk", "shortage prediction",
    ],
    "inventory": [
        "inventory", "stock", "reorder", "safety stock",
        "eoq", "days cover", "how much stock", "order quantity",
        "running low", "excess", "overstock",
    ],
    "geo": [
        "geopolitical", "country", "region", "political",
        "trade", "sanctions", "disruption", "port", "china",
        "india", "brazil", "factory fire", "war", "unrest",
    ],
    "optimization": [
        "optimize", "allocation", "split", "how much to buy",
        "purchase plan", "order from", "supplier split",
        "concentration", "diversify",
    ],
    "quality": [
        "quality", "purity", "contamination", "batch",
        "anomaly", "drift", "recall", "gmp", "fda warning",
    ],
    "alerts": [
        "alert", "warning", "urgent", "attention", "critical",
        "top risks", "what should i know", "summary",
    ],
}


def _classify_intent(question: str) -> list[str]:
    """Return up to 3 matching intent categories for the question."""
    lower = question.lower()
    scores: dict[str, int] = {}
    for intent, keywords in _INTENT_MAP.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            scores[intent] = hits
    if not scores:
        return ["alerts"]  # default to summary
    # Return top 3 by hit count
    return sorted(scores, key=scores.get, reverse=True)[:3]


# ── Context builder ───────────────────────────────────────────────────────────

def _build_context(intents: list[str], question: str) -> tuple[str, list[str]]:
    """
    Pull relevant pre-computed data from _cache based on detected intents.
    Returns (context_text, sources_used).
    Fast: reads from in-memory cache only — no ML recomputation.
    """
    parts: list[str] = []
    sources: list[str] = []

    if "risk" in intents or "alerts" in intents:
        risk = _cache.get("risk_scores")
        if risk is not None:
            top = risk.nlargest(8, "risk_score")[
                ["supplier_name", "risk_score", "risk_tier"]
            ].to_dict(orient="records")
            lines = [f"  - {r['supplier_name']}: {r['risk_score']:.1f}/100 ({r['risk_tier']})" for r in top]
            parts.append("SUPPLIER RISK SCORES (top 8 by risk):\n" + "\n".join(lines))
            sources.append("supplier_risk")

    if "forecast" in intents or "alerts" in intents:
        metrics = _cache.get("forecast_metrics")
        forecasts = _cache.get("forecasts")
        drugs = _cache.get("drugs")
        if metrics is not None and forecasts is not None and drugs is not None:
            avg_mape = float(metrics["mape"].mean())
            # Find drugs with price forecast > base price * 1.15
            spikes = []
            for _, drug in drugs.iterrows():
                fc = forecasts[forecasts["drug_id"] == drug["id"]].sort_values("ds")
                if fc.empty:
                    continue
                latest = float(fc["yhat"].iloc[-1])
                base = float(drug.get("base_price_per_kg", 50))
                pct = (latest / base - 1) * 100
                if pct > 10:
                    spikes.append(f"  - {drug['name']}: ${base:.2f}/kg → ${latest:.2f}/kg forecast (+{pct:.1f}%)")
            parts.append(
                f"PRICE FORECAST SUMMARY (avg MAPE: {avg_mape:.1f}%):\n" +
                ("  No significant price spikes detected." if not spikes else "\n".join(spikes[:8]))
            )
            sources.append("price_forecast")

    if "shortage" in intents or "alerts" in intents:
        try:
            from ..intelligence.shortage_predictor import ShortagePredictor
            sp = ShortagePredictor()
            df = sp.predict_all()
            at_risk = df[df["risk_tier"].isin(["CRITICAL", "WARNING"])][
                ["drug_name", "shortage_risk_score", "risk_tier", "recommended_action"]
            ].head(8)
            if at_risk.empty:
                parts.append("SHORTAGE PREDICTION:\n  All drugs currently stable.")
            else:
                lines = [
                    f"  - {r['drug_name']}: score={r['shortage_risk_score']:.0f}/100 "
                    f"({r['risk_tier']}) → {r['recommended_action']}"
                    for _, r in at_risk.iterrows()
                ]
                parts.append("SHORTAGE PREDICTION (Critical/Warning drugs):\n" + "\n".join(lines))
            sources.append("shortage_prediction")
        except Exception as e:
            log.warning(f"Chat: shortage predictor failed: {e}")

    if "inventory" in intents:
        try:
            from ..optimization.inventory_manager import InventoryManager
            mgr = InventoryManager()
            inv_df = mgr.compute_recommendations()
            reorder = inv_df[inv_df["action"].isin(["REORDER_NOW", "REORDER_SOON"])][
                ["drug_name", "action", "days_cover", "urgency_score"]
            ].head(8)
            s = mgr.summary(inv_df)
            summary_line = (
                f"Total drugs: {s['total_drugs']} | "
                f"Reorder now: {s['reorder_now']} | "
                f"Reorder soon: {s['reorder_soon']} | "
                f"Avg days cover: {s['avg_days_cover']:.0f} days"
            )
            lines = [
                f"  - {r['drug_name']}: {r['action']} "
                f"({r['days_cover']:.0f} days cover, urgency {r['urgency_score']:.1f})"
                for _, r in reorder.iterrows()
            ]
            parts.append(
                f"INVENTORY STATUS:\n  {summary_line}\n" +
                ("  All inventory adequate." if not lines else "\n".join(lines))
            )
            sources.append("inventory_optimization")
        except Exception as e:
            log.warning(f"Chat: inventory manager failed: {e}")

    if "geo" in intents:
        try:
            from ..intelligence.geopolitical_intelligence import GeopoliticalIntelligence
            geo = GeopoliticalIntelligence()
            result = geo.run()
            s = result["summary"]
            high_alert = result["supplier_alerts"][
                result["supplier_alerts"]["alert_level"] == "HIGH"
            ][["supplier_name", "country", "adjusted_risk_score", "top_event"]].head(6)
            lines = [
                f"  - {r['supplier_name']} ({r['country']}): "
                f"adj risk={r['adjusted_risk_score']:.0f} | {r['top_event'][:80]}"
                for _, r in high_alert.iterrows()
            ]
            parts.append(
                f"GEOPOLITICAL INTELLIGENCE:\n"
                f"  Active events: {s['active_events']} | "
                f"Countries affected: {s['countries_affected']} | "
                f"Most dangerous: {s['most_dangerous_country']}\n"
                f"  Suppliers on HIGH alert:\n" +
                ("\n".join(lines) if lines else "  None currently.")
            )
            sources.append("geopolitical_intelligence")
        except Exception as e:
            log.warning(f"Chat: geo intelligence failed: {e}")

    if "quality" in intents:
        quality = _cache.get("quality_results")
        if quality is not None and "is_anomaly" in quality.columns:
            total = len(quality)
            anomalies = int(quality["is_anomaly"].sum())
            pct = anomalies / total * 100 if total > 0 else 0
            parts.append(
                f"QUALITY ANOMALY DETECTION:\n"
                f"  Total batches checked: {total} | "
                f"Anomalies flagged: {anomalies} ({pct:.1f}%)\n"
                f"  Dual-method detection: Isolation Forest + SPC (2-sigma) must both agree for HIGH escalation."
            )
            sources.append("quality_anomaly")

    if "optimization" in intents:
        # Give context about what the optimizer can do without running it
        risk = _cache.get("risk_scores")
        drugs = _cache.get("drugs")
        suppliers = _cache.get("suppliers")
        if risk is not None and drugs is not None and suppliers is not None:
            parts.append(
                f"PURCHASE OPTIMIZATION CONTEXT:\n"
                f"  Formulary: {len(drugs)} drugs | Approved suppliers: {len(suppliers)}\n"
                f"  Optimizer: Linear programming (PuLP) — minimizes cost + risk penalty,\n"
                f"  enforces concentration limit (default: no supplier >60% of any drug's volume).\n"
                f"  Call POST /optimize/purchase to run a live allocation."
            )
            sources.append("purchase_optimization")

    # Always add platform summary
    drugs = _cache.get("drugs")
    suppliers = _cache.get("suppliers")
    risk = _cache.get("risk_scores")
    if drugs is not None and suppliers is not None:
        critical = int((risk["risk_tier"] == "Critical").sum()) if risk is not None else "?"
        high = int((risk["risk_tier"] == "High").sum()) if risk is not None else "?"
        parts.insert(0,
            f"PLATFORM OVERVIEW:\n"
            f"  Formulary: {len(drugs)} drugs | Suppliers: {len(suppliers)} "
            f"| Critical risk: {critical} | High risk: {high}"
        )

    context = "\n\n".join(parts) if parts else "No platform data available."
    return context, list(set(sources))


# ── Claude API call ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are PharmaFlow AI's procurement intelligence assistant — an expert in pharmaceutical supply chain management, bulk drug ingredient sourcing, supplier risk, and regulatory compliance.

You help procurement teams make fast, data-driven decisions. You have access to real-time platform data shown below. Your job is to answer questions by referencing specific numbers, supplier names, and drug names from the data provided.

Rules:
- Always cite specific data points (scores, percentages, drug names, supplier names)
- Supplier risk scores are out of 100 (higher = riskier)
- Shortage risk scores are out of 100 (higher = more likely to run short)
- Give concrete, actionable recommendations, not generic advice
- If the question is outside the data provided, say so clearly and suggest what to check
- Keep answers focused and professional — this is a procurement command center, not a chatbot
- Never fabricate data points. Only cite what is in the platform data below.

Platform data (current):
{context}"""

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = 800


async def _call_claude(
    question: str,
    context: str,
    history: list[ChatMessage],
) -> str:
    """Call the Anthropic Messages API asynchronously via httpx."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "ANTHROPIC_API_KEY is not set on this server. "
            "Add it to your Render environment variables to enable the AI chat feature."
        )

    system = _SYSTEM_PROMPT.format(context=context)

    # Build message list: history + current question
    messages = []
    for msg in history[-6:]:  # keep last 6 turns for context window efficiency
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})

    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
        "system": system,
        "messages": messages,
    }

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
    except httpx.TimeoutException:
        return "The AI took too long to respond. Please try again in a moment."
    except httpx.HTTPStatusError as e:
        log.error(f"Anthropic API HTTP error: {e.response.status_code} {e.response.text}")
        return f"AI service error ({e.response.status_code}). Please try again."
    except Exception as e:
        log.error(f"Anthropic API call failed: {e}")
        return "Failed to reach the AI service. Please check server logs."


# ── /chat endpoint ────────────────────────────────────────────────────────────

@app.post("/chat", tags=["Intelligence"])
async def chat(req: ChatRequest):
    """
    Ask PharmaFlow AI a natural language question about your supply chain.
    Returns an AI-generated answer grounded in live platform data.
    """
    intents = _classify_intent(req.question)
    log.info(f"Chat | intents={intents} | question={req.question[:60]!r}")

    context, sources = _build_context(intents, req.question)
    answer = await _call_claude(req.question, context, req.history)

    return ChatResponse(
        answer=answer,
        sources=sources,
        intents=intents,
        model=ANTHROPIC_MODEL,
    )
# ═════════════════════════════════════════════════════════════════════════════
# Phase 8: Simulation Endpoints + Demand Forecasting
# ═════════════════════════════════════════════════════════════════════════════
#
# Append this entire block to the bottom of src/api/main.py
# Also import these schemas at the top of main.py:
#   from .schemas import (
#       SupplierOfflineRequest, DemandShockRequest, PriceSpikeRequest,
#       SimulationResponse, SimulationDrugImpact,
#   )
# ═════════════════════════════════════════════════════════════════════════════

import json as _json

from .schemas import (
    SupplierOfflineRequest,
    DemandShockRequest,
    PriceSpikeRequest,
    SimulationResponse,
    SimulationDrugImpact,
)

# ── Simulation helpers ────────────────────────────────────────────────────────

def _get_approved_map() -> dict:
    """Return {drug_id: [supplier_id, ...]} from drugs.csv."""
    drugs = _cache["drugs"]
    result = {}
    for _, row in drugs.iterrows():
        try:
            result[row["id"]] = _json.loads(row.get("approved_suppliers", "[]"))
        except Exception:
            result[row["id"]] = []
    return result


def _get_latest_prices() -> dict:
    """Return {drug_id: price_per_kg} from cached forecasts."""
    fc = _cache["forecasts"].sort_values("ds")
    return (
        fc.groupby("drug_id")["yhat"]
        .last()
        .clip(lower=1)
        .to_dict()
    )


def _get_risk_lookup() -> dict:
    """Return {supplier_id: risk_score} from cached risk scores."""
    risk = _cache["risk_scores"]
    return dict(zip(risk["supplier_id"], risk["risk_score"]))


def _supplier_name(supplier_id: str) -> str:
    sups = _cache["suppliers"]
    row = sups[sups["id"] == supplier_id]
    return str(row["name"].iloc[0]) if not row.empty else supplier_id


def _drug_name(drug_id: str) -> str:
    drugs = _cache["drugs"]
    row = drugs[drugs["id"] == drug_id]
    return str(row["name"].iloc[0]) if not row.empty else drug_id


def _impact_level(delta_pct: float) -> str:
    if abs(delta_pct) >= 30: return "CRITICAL"
    if abs(delta_pct) >= 15: return "HIGH"
    if abs(delta_pct) >= 5:  return "MEDIUM"
    return "LOW"


def _get_baseline_demand() -> dict:
    """Compute monthly demand per drug from purchase history."""
    try:
        ph = _cache.get("purchase_history")
        if ph is None:
            ph = pd.read_csv(SYNTHETIC / "purchase_history.csv")
            _cache["purchase_history"] = ph
        avg = ph.groupby("drug_id")["quantity_kg"].mean()
        return (avg * 4).round().to_dict()
    except Exception:
        # Fallback: use base price as proxy for relative demand
        drugs = _cache["drugs"]
        return {row["id"]: 500.0 for _, row in drugs.iterrows()}


def _cheapest_supplier(drug_id: str, excluded_ids: set, prices: dict, risk_lookup: dict) -> tuple:
    """Return (supplier_id, supplier_name, effective_price) for cheapest available supplier."""
    approved = _get_approved_map().get(drug_id, [])
    available = [s for s in approved if s not in excluded_ids]
    if not available:
        return None, "NONE", float("inf")
    price = prices.get(drug_id, 50.0)
    risk_weight = 0.8
    scored = [(s, price + risk_weight * risk_lookup.get(s, 50.0)) for s in available]
    best_id, best_price = min(scored, key=lambda x: x[1])
    return best_id, _supplier_name(best_id), best_price


# ── Simulation 1: Supplier Offline ────────────────────────────────────────────

@app.post("/simulate/supplier-offline", response_model=SimulationResponse, tags=["Intelligence"])
async def simulate_supplier_offline(req: SupplierOfflineRequest):
    """
    Simulate removing a supplier from the supply chain.
    Shows which drugs are affected, cost delta, and whether demand can be met.
    """
    prices     = _get_latest_prices()
    risk       = _get_risk_lookup()
    demand     = _get_baseline_demand()
    approved   = _get_approved_map()
    drugs_df   = _cache["drugs"]
    excluded   = {req.supplier_id}
    sup_name   = _supplier_name(req.supplier_id)

    # Find which drugs this supplier supplies
    affected_drug_ids = [
        d_id for d_id, sups in approved.items()
        if req.supplier_id in sups
    ]
    if req.drug_ids:
        affected_drug_ids = [d for d in affected_drug_ids if d in req.drug_ids]

    if not affected_drug_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Supplier {req.supplier_id} is not approved for any drugs in the formulary."
        )

    drug_impacts = []
    baseline_total = 0.0
    simulated_total = 0.0

    for d_id in affected_drug_ids:
        d_name = _drug_name(d_id)
        price = prices.get(d_id, 50.0)
        dem = demand.get(d_id, 500.0)

        # Baseline cost: assume we sourced 40% from this supplier (avg concentration)
        fraction_from_offline = 0.40
        qty_from_offline = dem * fraction_from_offline
        baseline_cost = dem * price
        baseline_total += baseline_cost

        # Simulate: find next best supplier
        alt_id, alt_name, alt_eff_price = _cheapest_supplier(d_id, excluded, prices, risk)
        can_fulfill = alt_id is not None
        sim_cost = (dem * price * (1 - fraction_from_offline)) + \
                   (qty_from_offline * (alt_eff_price if can_fulfill else price * 2.0))
        simulated_total += sim_cost

        delta_usd = sim_cost - baseline_cost
        delta_pct = (delta_usd / max(baseline_cost, 1)) * 100

        drug_impacts.append(SimulationDrugImpact(
            drug_id=d_id,
            drug_name=d_name,
            baseline_cost_usd=round(baseline_cost, 2),
            simulated_cost_usd=round(sim_cost, 2),
            cost_delta_usd=round(delta_usd, 2),
            cost_delta_pct=round(delta_pct, 1),
            baseline_supplier=sup_name,
            simulated_supplier=alt_name,
            can_fulfill=can_fulfill,
            impact_level=_impact_level(delta_pct) if can_fulfill else "CRITICAL",
        ))

    drug_impacts.sort(key=lambda x: abs(x.cost_delta_usd), reverse=True)
    total_delta = simulated_total - baseline_total
    total_delta_pct = (total_delta / max(baseline_total, 1)) * 100
    unfulfillable = sum(1 for d in drug_impacts if not d.can_fulfill)

    if unfulfillable > 0:
        rec = f"CRITICAL: {unfulfillable} drug(s) have NO alternative supplier if {sup_name} goes offline. Qualify backup suppliers immediately."
    elif total_delta_pct > 20:
        rec = f"HIGH RISK: Losing {sup_name} increases spend by {total_delta_pct:.1f}%. Develop 2nd-source suppliers for affected drugs."
    else:
        rec = f"Supply chain is resilient to {sup_name} going offline. Cost increases by {total_delta_pct:.1f}% — within acceptable range."

    return SimulationResponse(
        simulation_type="supplier_offline",
        scenario_description=f"Simulate {sup_name} ({req.supplier_id}) going offline",
        baseline_total_cost_usd=round(baseline_total, 2),
        simulated_total_cost_usd=round(simulated_total, 2),
        total_cost_delta_usd=round(total_delta, 2),
        total_cost_delta_pct=round(total_delta_pct, 1),
        drugs_affected=len(drug_impacts),
        drugs_unfulfillable=unfulfillable,
        impact_level=_impact_level(total_delta_pct) if unfulfillable == 0 else "CRITICAL",
        drug_impacts=drug_impacts,
        recommendation=rec,
    )


# ── Simulation 2: Demand Shock ────────────────────────────────────────────────

@app.post("/simulate/demand-shock", response_model=SimulationResponse, tags=["Intelligence"])
async def simulate_demand_shock(req: DemandShockRequest):
    """
    Simulate a sudden demand surge for a specific drug.
    Shows cost impact and whether current suppliers can fulfill increased demand.
    """
    prices   = _get_latest_prices()
    risk     = _get_risk_lookup()
    demand   = _get_baseline_demand()
    approved = _get_approved_map()

    d_id   = req.drug_id
    d_name = _drug_name(d_id)
    price  = prices.get(d_id, 50.0)
    base_demand = demand.get(d_id, 500.0)
    shocked_demand = base_demand * req.multiplier

    baseline_cost  = base_demand * price
    simulated_cost = shocked_demand * price  # same price initially
    delta_usd = simulated_cost - baseline_cost
    delta_pct = (delta_usd / max(baseline_cost, 1)) * 100

    # Check if approved suppliers can cover the surge
    approved_sups = approved.get(d_id, [])
    can_cover = len(approved_sups) >= 2  # need multiple sources for large surge

    if req.multiplier > 3 and not can_cover:
        impact = "CRITICAL"
        rec = f"CRITICAL: {req.multiplier:.1f}× demand surge for {d_name} cannot be met from current {len(approved_sups)} supplier(s). Qualify emergency backup suppliers and consider alternative therapeutics."
    elif req.multiplier > 2:
        impact = "HIGH"
        rec = f"HIGH: {req.multiplier:.1f}× demand surge for {d_name} increases cost by ${delta_usd:,.0f}. Activate all {len(approved_sups)} approved suppliers and negotiate expedited delivery."
    else:
        impact = "MEDIUM"
        rec = f"MEDIUM: {req.multiplier:.1f}× demand surge adds ${delta_usd:,.0f} to {d_name} spend. Increase safety stock by {int((req.multiplier - 1) * 100)}% as a precaution."

    return SimulationResponse(
        simulation_type="demand_shock",
        scenario_description=f"Demand for {d_name} increases {req.multiplier:.1f}× (from {base_demand:.0f}kg to {shocked_demand:.0f}kg)",
        baseline_total_cost_usd=round(baseline_cost, 2),
        simulated_total_cost_usd=round(simulated_cost, 2),
        total_cost_delta_usd=round(delta_usd, 2),
        total_cost_delta_pct=round(delta_pct, 1),
        drugs_affected=1,
        drugs_unfulfillable=0 if can_cover else 1,
        impact_level=impact,
        drug_impacts=[
            SimulationDrugImpact(
                drug_id=d_id,
                drug_name=d_name,
                baseline_cost_usd=round(baseline_cost, 2),
                simulated_cost_usd=round(simulated_cost, 2),
                cost_delta_usd=round(delta_usd, 2),
                cost_delta_pct=round(delta_pct, 1),
                baseline_supplier=f"{len(approved_sups)} approved suppliers",
                simulated_supplier=f"{len(approved_sups)} suppliers at {req.multiplier:.1f}× capacity",
                can_fulfill=can_cover,
                impact_level=impact,
            )
        ],
        recommendation=rec,
    )


# ── Simulation 3: Price Spike ─────────────────────────────────────────────────

@app.post("/simulate/price-spike", response_model=SimulationResponse, tags=["Intelligence"])
async def simulate_price_spike(req: PriceSpikeRequest):
    """
    Simulate a price increase from specific suppliers (or top-3 highest risk).
    Shows total spend impact across all affected drugs.
    """
    prices   = _get_latest_prices()
    risk     = _get_risk_lookup()
    demand   = _get_baseline_demand()
    approved = _get_approved_map()
    drugs_df = _cache["drugs"]
    risk_df  = _cache["risk_scores"]

    # Determine which suppliers get the price spike
    if req.supplier_ids:
        spiked = set(req.supplier_ids)
    else:
        top3 = risk_df.nlargest(3, "risk_score")["supplier_id"].tolist()
        spiked = set(top3)

    spiked_names = [_supplier_name(s) for s in spiked]

    drug_impacts = []
    baseline_total = 0.0
    simulated_total = 0.0

    for _, drug in drugs_df.iterrows():
        d_id   = drug["id"]
        d_name = drug["name"]
        price  = prices.get(d_id, 50.0)
        dem    = demand.get(d_id, 500.0)
        app_sups = approved.get(d_id, [])

        # What fraction of this drug comes from spiked suppliers
        spiked_for_drug = [s for s in app_sups if s in spiked]
        if not spiked_for_drug:
            continue  # drug not sourced from spiked suppliers

        frac_spiked = len(spiked_for_drug) / max(len(app_sups), 1)
        # Assume proportional allocation
        baseline_cost  = dem * price
        spiked_portion = dem * frac_spiked
        new_price = price * req.price_multiplier
        simulated_cost = (
            (dem - spiked_portion) * price +
            spiked_portion * new_price
        )

        baseline_total  += baseline_cost
        simulated_total += simulated_cost
        delta_usd = simulated_cost - baseline_cost
        delta_pct = (delta_usd / max(baseline_cost, 1)) * 100

        drug_impacts.append(SimulationDrugImpact(
            drug_id=d_id,
            drug_name=d_name,
            baseline_cost_usd=round(baseline_cost, 2),
            simulated_cost_usd=round(simulated_cost, 2),
            cost_delta_usd=round(delta_usd, 2),
            cost_delta_pct=round(delta_pct, 1),
            baseline_supplier=", ".join(spiked_names[:2]),
            simulated_supplier=f"+{int((req.price_multiplier - 1) * 100)}% price",
            can_fulfill=True,
            impact_level=_impact_level(delta_pct),
        ))

    drug_impacts.sort(key=lambda x: x.cost_delta_usd, reverse=True)

    total_delta = simulated_total - baseline_total
    total_delta_pct = (total_delta / max(baseline_total, 1)) * 100
    pct_increase = int((req.price_multiplier - 1) * 100)
    sup_names_str = ", ".join(spiked_names[:3])

    if total_delta_pct > 15:
        rec = f"HIGH IMPACT: A {pct_increase}% price spike from {sup_names_str} adds ${total_delta:,.0f} to spend. Consider forward buying before price increase takes effect and diversify away from these suppliers."
    else:
        rec = f"MANAGEABLE: A {pct_increase}% price spike from {sup_names_str} adds ${total_delta:,.0f} ({total_delta_pct:.1f}%) to total spend. Within acceptable variance — monitor supplier pricing monthly."

    return SimulationResponse(
        simulation_type="price_spike",
        scenario_description=f"Suppliers {sup_names_str} raise prices by {pct_increase}%",
        baseline_total_cost_usd=round(baseline_total, 2),
        simulated_total_cost_usd=round(simulated_total, 2),
        total_cost_delta_usd=round(total_delta, 2),
        total_cost_delta_pct=round(total_delta_pct, 1),
        drugs_affected=len(drug_impacts),
        drugs_unfulfillable=0,
        impact_level=_impact_level(total_delta_pct),
        drug_impacts=drug_impacts,
        recommendation=rec,
    )


# ── Demand Forecasting ────────────────────────────────────────────────────────

@app.get("/intelligence/demand-forecast", tags=["Intelligence"])
async def demand_forecast():
    """
    Epidemiology-driven demand forecasting.
    Pulls WHO DONS outbreak alerts + CDC ILI surveillance and maps to drug demand signals.
    """
    from ..intelligence.demand_forecasting import DemandForecaster
    df = DemandForecaster()
    return df.run()

# ═════════════════════════════════════════════════════════════════════════════
# Phase 9: Benchmarking + Counterfeit Detection Endpoints
# ═════════════════════════════════════════════════════════════════════════════
#
# Append this entire block to the bottom of src/api/main.py
# Also import these schemas at the top of main.py (add to the existing import):
#   from .schemas import (
#       BenchmarkResponse, DrugPriceBenchmark, SupplierQualityBenchmark,
#       BenchmarkSummary, CounterfeitRiskResponse, CounterfeitRiskEntry,
#       CounterfeitRiskSummary,
#   )
# ═════════════════════════════════════════════════════════════════════════════

from .schemas import (
    BenchmarkResponse,
    DrugPriceBenchmark,
    SupplierQualityBenchmark,
    BenchmarkSummary,
    CounterfeitRiskResponse,
    CounterfeitRiskEntry,
    CounterfeitRiskSummary,
)


@app.get("/benchmark/overview", response_model=BenchmarkResponse, tags=["Intelligence"])
async def benchmark_overview():
    """
    Compare our drug prices and supplier quality rates against market benchmarks.
    Returns per-drug price percentile rankings, savings opportunities,
    and per-supplier quality pass rate vs industry standard.
    """
    from ..intelligence.benchmarking import BenchmarkEngine
    eng = BenchmarkEngine()
    result = eng.run()

    price_bm = [DrugPriceBenchmark(**d) for d in result["price_benchmarks"]]
    quality_bm = [SupplierQualityBenchmark(**s) for s in result["quality_benchmarks"]]
    summary = BenchmarkSummary(**result["summary"])

    return BenchmarkResponse(
        price_benchmarks=price_bm,
        quality_benchmarks=quality_bm,
        summary=summary,
    )


@app.get("/intelligence/counterfeit-risk", response_model=CounterfeitRiskResponse, tags=["Intelligence"])
async def counterfeit_risk():
    """
    Score every supplier on counterfeit / grey-market risk using four signals:
    price anomaly, quality drift, regulatory posture, and incident history.

    IMPORTANT: High scores indicate risk signals warranting investigation —
    not confirmed counterfeit activity. Always verify via laboratory testing.
    """
    from ..intelligence.counterfeit_detector import CounterfeitDetector
    cd = CounterfeitDetector()
    result = cd.score_all()

    supplier_risks = [CounterfeitRiskEntry(**r) for r in result["supplier_risks"]]
    summary = CounterfeitRiskSummary(**result["summary"])

    return CounterfeitRiskResponse(
        supplier_risks=supplier_risks,
        summary=summary,
    )

# ═════════════════════════════════════════════════════════════════════════════
# Phase 10: Supply Chain Map + Compliance + ESG Endpoints
# Append to the bottom of src/api/main.py
# ═════════════════════════════════════════════════════════════════════════════

from .schemas import (
    SupplyChainMapResponse, SupplyChainNode, SupplyChainEdge,
    ConcentrationRisk, SupplyChainSummary,
    ComplianceResponse, SupplierComplianceRecord, ComplianceFramework,
    WarningLetter, ComplianceSummary, AuditReportResponse,
    ESGResponse, ESGSupplierScore, ESGSummary,
)


@app.get("/intelligence/supply-chain-map", response_model=SupplyChainMapResponse, tags=["Intelligence"])
async def supply_chain_map():
    """
    Build a 3-tier supply chain network map.
    Returns nodes + edges for Tier 1 (direct suppliers), Tier 2 (chemical
    manufacturers), and Tier 3 (feedstock sources), plus detected hidden
    concentration risks where multiple Tier 1 suppliers share upstream sources.
    """
    from ..intelligence.supply_chain_mapper import SupplyChainMapper
    mapper = SupplyChainMapper()
    result = mapper.run()

    nodes = [SupplyChainNode(**n) for n in result["network"]["nodes"]]
    edges = [SupplyChainEdge(**e) for e in result["network"]["edges"]]
    risks = [
        ConcentrationRisk(
            shared_node_id=r["shared_node_id"],
            shared_node_name=r["shared_node_name"],
            shared_node_country=r["shared_node_country"],
            shared_node_tier=r["shared_node_tier"],
            tier1_supplier_names=r["tier1_supplier_names"],
            num_affected=r["num_affected"],
            pct_of_portfolio=r["pct_of_portfolio"],
            risk_level=r["risk_level"],
            description=r["description"],
        )
        for r in result["concentration_risks"]
    ]

    return SupplyChainMapResponse(
        nodes=nodes,
        edges=edges,
        concentration_risks=risks,
        country_exposure=result["country_exposure"],
        summary=SupplyChainSummary(**result["summary"]),
    )


@app.get("/compliance/overview", response_model=ComplianceResponse, tags=["Intelligence"])
async def compliance_overview():
    """
    Regulatory compliance status for all suppliers.
    Tracks FDA CGMP, EMA GMP, WHO Prequalification, ISO 9001, and ICH Q7
    audit cycles, warning letter history, and overall compliance score.
    """
    from ..intelligence.regulatory_compliance import ComplianceEngine
    engine = ComplianceEngine()
    result = engine.run()

    supplier_records = []
    for s in result["suppliers"]:
        frameworks = [ComplianceFramework(**f) for f in s["frameworks"]]
        letters    = [WarningLetter(**wl) for wl in s["warning_letters"]]
        supplier_records.append(SupplierComplianceRecord(
            supplier_id=s["supplier_id"],
            supplier_name=s["supplier_name"],
            country=s["country"],
            fda_approved=s["fda_approved"],
            risk_tier=s["risk_tier"],
            compliance_score=s["compliance_score"],
            overall_status=s["overall_status"],
            frameworks=frameworks,
            warning_letters=letters,
            active_warnings=s["active_warnings"],
            total_warnings=s["total_warnings"],
            next_audit_due=s["next_audit_due"],
            overdue_frameworks=s["overdue_frameworks"],
        ))

    return ComplianceResponse(
        suppliers=supplier_records,
        summary=ComplianceSummary(**result["summary"]),
    )


@app.get("/compliance/audit-report/{supplier_id}", response_model=AuditReportResponse, tags=["Intelligence"])
async def audit_report(supplier_id: str):
    """
    Generate a plain-text audit compliance report for a specific supplier.
    Suitable for use in procurement audit documentation.
    """
    from ..intelligence.regulatory_compliance import ComplianceEngine
    engine = ComplianceEngine()
    result = engine.generate_audit_report(supplier_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return AuditReportResponse(**result)


@app.get("/intelligence/esg-scores", response_model=ESGResponse, tags=["Intelligence"])
async def esg_scores():
    """
    ESG scoring and Scope 3 carbon emissions estimation for all suppliers.
    Environmental (0–40) + Social (0–30) + Governance (0–30) = total 0–100.
    Scope 3 emissions estimate covers shipping + manufacturing per supplier.
    """
    from ..intelligence.esg_scorer import ESGScorer
    scorer = ESGScorer()
    result = scorer.run()

    supplier_scores = [ESGSupplierScore(**s) for s in result["supplier_scores"]]
    top_emitters    = [ESGSupplierScore(**s) for s in result["top_emitters"]]

    return ESGResponse(
        supplier_scores=supplier_scores,
        top_emitters=top_emitters,
        summary=ESGSummary(**result["summary"]),
    )
