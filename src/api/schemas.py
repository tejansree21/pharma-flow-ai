"""
PharmaFlow AI — Pydantic Schemas (Phase 2 + 3)
===============================================
Request / Response models for all FastAPI endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ═════════════════════════════════════════════════════════════════════════════
# Shared / Generic
# ═════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "3.0.0"
    phase: str = "Phase 3 — Shortage Prediction + Geopolitical Intelligence"


# ═════════════════════════════════════════════════════════════════════════════
# Drugs
# ═════════════════════════════════════════════════════════════════════════════

class DrugOut(BaseModel):
    id: str
    name: str
    category: str
    base_price_per_kg: float
    criticality: str
    demand_seasonality: str
    num_approved_suppliers: int


# ═════════════════════════════════════════════════════════════════════════════
# Suppliers
# ═════════════════════════════════════════════════════════════════════════════

class SupplierOut(BaseModel):
    id: str
    name: str
    country: str
    region: str
    price_tier: str
    fda_approved: bool
    risk_score: Optional[float] = None
    risk_tier: Optional[str] = None


# ═════════════════════════════════════════════════════════════════════════════
# Price Forecast
# ═════════════════════════════════════════════════════════════════════════════

class ForecastRequest(BaseModel):
    drug_id: str = Field(..., example="DRG001")
    weeks_ahead: int = Field(default=12, ge=1, le=52)


class ForecastPoint(BaseModel):
    date: str
    predicted_price: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None


class ForecastResponse(BaseModel):
    drug_id: str
    drug_name: str
    mape_pct: Optional[float] = None
    forecast: List[ForecastPoint]


# ═════════════════════════════════════════════════════════════════════════════
# Supplier Risk
# ═════════════════════════════════════════════════════════════════════════════

class RiskRequest(BaseModel):
    supplier_id: str = Field(..., example="SUP001")


class RiskResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    risk_score: float
    risk_tier: str
    delivery_risk: float
    quality_risk: float
    incident_risk: float
    geo_regulatory_risk: float
    recommendation: str


# ═════════════════════════════════════════════════════════════════════════════
# Quality Anomaly
# ═════════════════════════════════════════════════════════════════════════════

class QualityCheckRequest(BaseModel):
    supplier_id: str = Field(..., example="SUP001")
    drug_id: str = Field(..., example="DRG001")
    purity_pct: float = Field(..., ge=0, le=100, example=96.5)
    contamination_ppm: float = Field(..., ge=0, example=1.8)
    moisture_pct: float = Field(..., ge=0, le=100, example=0.5)
    particle_size_d90: float = Field(..., ge=0, example=120.0)


class QualityCheckResponse(BaseModel):
    supplier_id: str
    drug_id: str
    is_anomaly: bool
    anomaly_methods: List[str]
    anomaly_score: float
    spc_violations: List[str]
    risk_level: str
    recommendation: str


# ═════════════════════════════════════════════════════════════════════════════
# Purchase Optimisation
# ═════════════════════════════════════════════════════════════════════════════

class DrugDemand(BaseModel):
    drug_id: str
    quantity_kg: float = Field(..., gt=0)


class OptimizeRequest(BaseModel):
    demand: List[DrugDemand] = Field(
        default=[],
        description="List of drug demands. If empty, uses default monthly averages.",
    )
    risk_penalty_weight: float = Field(default=0.8, ge=0, le=5)
    concentration_limit: float = Field(default=0.60, ge=0.1, le=1.0)


class AllocationLine(BaseModel):
    drug_id: str
    drug_name: str
    supplier_id: str
    supplier_name: str
    supplier_country: str
    quantity_kg: float
    price_per_kg: float
    raw_cost_usd: float
    risk_score: float
    risk_penalty_usd: float
    total_effective_cost: float
    pct_of_demand: float


class OptimizeResponse(BaseModel):
    solver: str
    num_drugs: int
    num_suppliers_used: int
    total_raw_cost_usd: float
    total_risk_penalty_usd: float
    total_effective_cost_usd: float
    allocation: List[AllocationLine]


# ═════════════════════════════════════════════════════════════════════════════
# Inventory
# ═════════════════════════════════════════════════════════════════════════════

class InventoryRequest(BaseModel):
    current_stock: Optional[dict] = Field(
        default=None,
        description="Optional {drug_id: qty_kg}. If omitted, uses simulated stock.",
    )
    service_level: float = Field(default=0.95, ge=0.5, le=0.999)


class InventoryLine(BaseModel):
    drug_id: str
    drug_name: str
    category: str
    criticality: str
    avg_daily_demand_kg: float
    avg_lead_time_days: float
    safety_stock_kg: float
    reorder_point_kg: float
    eoq_kg: float
    current_stock_kg: float
    days_cover: float
    action: str
    urgency_score: float
    stock_value_usd: float


class InventoryResponse(BaseModel):
    total_drugs: int
    reorder_now: int
    reorder_soon: int
    adequate: int
    excess: int
    total_stock_value_usd: float
    avg_days_cover: float
    critical_reorders: List[str]
    recommendations: List[InventoryLine]


# ═════════════════════════════════════════════════════════════════════════════
# Dashboard Summary
# ═════════════════════════════════════════════════════════════════════════════

class DashboardSummary(BaseModel):
    total_drugs: int
    total_suppliers: int
    critical_suppliers: int
    high_risk_suppliers: int
    drugs_needing_reorder: int
    avg_price_forecast_mape_pct: float
    total_anomalies_detected: int
    top_risk_suppliers: List[dict]
    price_alerts: List[dict]
    inventory_alerts: List[dict]
    shortage_alerts: List[dict]
    geo_alerts: List[dict]


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3: Shortage Prediction
# ═════════════════════════════════════════════════════════════════════════════

class ShortageRequest(BaseModel):
    drug_id: Optional[str] = Field(
        default=None,
        description="Specific drug ID. If omitted, returns predictions for all drugs.",
    )
    lookback_weeks: int = Field(default=26, ge=4, le=52)
    recent_weeks: int = Field(default=4, ge=1, le=12)


class ShortageAlert(BaseModel):
    drug_id: str
    drug_name: str
    category: str
    criticality: str
    shortage_risk_score: float
    risk_tier: str
    demand_spike_score: float
    supply_concentration_score: float
    lead_time_stress_score: float
    inventory_runway_score: float
    supplier_risk_overlay_score: float
    recommended_action: str


class ShortageResponse(BaseModel):
    total_drugs: int
    critical: int
    warning: int
    watch: int
    stable: int
    avg_risk_score: float
    highest_risk_drug: str
    alerts: List[ShortageAlert]


# ═════════════════════════════════════════════════════════════════════════════
# Phase 3: Geopolitical Intelligence
# ═════════════════════════════════════════════════════════════════════════════

class GeoEventOut(BaseModel):
    event_id: str
    event_type: str
    country: str
    event_date: str
    days_ago: int
    description: str
    severity: float
    active: bool
    effective_score: float


class GeoSupplierAlert(BaseModel):
    supplier_id: str
    supplier_name: str
    country: str
    base_risk_score: float
    geo_intelligence_score: float
    adjusted_risk_score: float
    risk_delta: float
    active_geo_events: int
    top_event: str
    alert_level: str


class CountryRisk(BaseModel):
    country: str
    combined_risk: float
    num_events: int
    top_event_type: str
    baseline_risk: float


class GeoIntelligenceResponse(BaseModel):
    total_events: int
    active_events: int
    countries_affected: int
    suppliers_on_high_alert: int
    suppliers_on_medium_alert: int
    most_dangerous_country: str
    top_events: List[GeoEventOut]
    supplier_alerts: List[GeoSupplierAlert]
    country_risk_index: List[CountryRisk]
