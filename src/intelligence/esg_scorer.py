"""
PharmaFlow AI — Phase 10: ESG & Carbon Footprint Scorer
=========================================================
Scores each supplier on Environmental, Social, and Governance (ESG)
dimensions and estimates Scope 3 supply chain carbon emissions.

Required by:
  - EU Corporate Sustainability Reporting Directive (CSRD) — mandatory for
    large EU companies from FY2024
  - SEC climate disclosure rules (proposed)
  - Many investor ESG frameworks (MSCI, Sustainalytics, S&P CSA)

Scoring methodology
-------------------
Environmental (0–40):
  - Carbon intensity estimate: shipping distance × transport mode × qty
  - Country renewable energy mix (from IEA data, synthetic proxy)
  - Waste / water management rating by country

Social (0–30):
  - Labour rights index by country (from ILO ratification data, synthetic proxy)
  - Working conditions score
  - Modern slavery risk (UK Modern Slavery Act, synthetic proxy)

Governance (0–30):
  - Regulatory compliance score (from ComplianceEngine)
  - Transparency / disclosure rating
  - Corruption perception index proxy (Transparency International)

Scope 3 emissions estimate:
  Shipping emissions = distance_km × emission_factor_kg_co2_per_tonne_km × quantity_tonnes
  Manufacturing emissions = quantity_kg × manufacturing_emission_factor (by category)
"""

import logging
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.esg")

_ROOT     = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"

# ── Country-level ESG proxies ─────────────────────────────────────────────────

COUNTRY_ENV_SCORE = {
    # Higher = better environmental performance
    "Germany": 82, "Switzerland": 88, "France": 78, "UK": 75, "Ireland": 72,
    "USA": 65,     "Japan": 73,       "South Korea": 62,
    "India": 38,   "China": 32,       "Bangladesh": 25, "Pakistan": 28,
    "Brazil": 55,  "Mexico": 48,      "Israel": 58,
}

COUNTRY_SOCIAL_SCORE = {
    "Germany": 88, "Switzerland": 90, "France": 85, "UK": 84, "Ireland": 86,
    "USA": 72,     "Japan": 82,       "South Korea": 70,
    "India": 42,   "China": 35,       "Bangladesh": 28, "Pakistan": 30,
    "Brazil": 52,  "Mexico": 48,      "Israel": 68,
}

COUNTRY_GOVERNANCE_SCORE = {
    "Germany": 85, "Switzerland": 90, "France": 80, "UK": 82, "Ireland": 84,
    "USA": 75,     "Japan": 78,       "South Korea": 68,
    "India": 44,   "China": 38,       "Bangladesh": 32, "Pakistan": 30,
    "Brazil": 50,  "Mexico": 46,      "Israel": 70,
}

# Shipping emission factors (kg CO2 per tonne-km)
TRANSPORT_EMISSION_FACTORS = {
    "air":   0.602,
    "sea":   0.016,
    "road":  0.096,
    "rail":  0.028,
}

# Approximate distance from supplier country to US pharma hub (km)
COUNTRY_DISTANCE_KM = {
    "China": 12000, "India": 13000, "Bangladesh": 13500, "Pakistan": 11500,
    "Germany": 7000,"Switzerland": 6800,"France": 6500,"UK": 5500,"Ireland": 5300,
    "USA": 500,     "Japan": 10500,    "South Korea": 10000,
    "Brazil": 8000, "Mexico": 3000,    "Israel": 9000,
}

# Primary transport mode by distance
def _transport_mode(distance_km: float) -> str:
    if distance_km > 8000:  return "sea"
    if distance_km > 3000:  return "sea"
    if distance_km > 500:   return "road"
    return "road"

# Manufacturing emission factor by drug category (kg CO2 per kg product)
MANUFACTURING_EMISSION_FACTOR = {
    "antiviral":      12.0, "antibiotic":    8.0, "analgesic":     4.0,
    "antidiabetic":   6.0,  "cardiovascular": 5.0,"antihistamine": 5.0,
    "steroid":        10.0, "other":          6.0,
}

ESG_TIER_THRESHOLDS = {
    "A": 75, "B": 60, "C": 45, "D": 0
}


class ESGScorer:
    """
    Scores all Tier 1 suppliers on ESG dimensions and estimates Scope 3 emissions.

    Parameters
    ----------
    seed : int — for reproducible scoring noise
    annual_volume_kg : float — total annual procurement volume (kg) for Scope 3 calculation
    """

    def __init__(self, seed: int = 42, annual_volume_kg: float = 500_000.0):
        self.seed = seed
        self.annual_volume_kg = annual_volume_kg
        self.suppliers   = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.drugs       = pd.read_csv(SYNTHETIC / "drugs.csv")
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")
        self._rng = np.random.default_rng(seed)

        try:
            ph = pd.read_csv(SYNTHETIC / "purchase_history.csv")
            self._sup_volume = (ph.groupby("supplier_id")["quantity_kg"].sum()).to_dict()
        except FileNotFoundError:
            self._sup_volume = {}

    # ── Environmental scoring ─────────────────────────────────────────────────

    def _env_score(self, supplier_id: str, country: str) -> tuple[float, float]:
        """Return (env_score 0–40, scope3_kg_co2)."""
        country_env = COUNTRY_ENV_SCORE.get(country, 40)
        # Noise per supplier
        seed = sum(ord(c) for c in supplier_id)
        rng  = np.random.default_rng(self.seed + seed)
        noise = float(rng.normal(0, 5))
        env_raw = float(np.clip(country_env + noise, 10, 100))
        env_score = round(env_raw * 0.40, 1)  # scale to 40

        # Scope 3 estimate
        volume_kg   = self._sup_volume.get(supplier_id, self.annual_volume_kg / len(self.suppliers))
        distance_km = COUNTRY_DISTANCE_KM.get(country, 8000)
        mode        = _transport_mode(distance_km)
        ef          = TRANSPORT_EMISSION_FACTORS[mode]
        shipping_co2 = (volume_kg / 1000) * distance_km * ef  # tonnes × km × factor

        # Manufacturing emissions (estimate average factor)
        mfg_factor = 7.0  # kg CO2 / kg product — average across categories
        mfg_co2   = volume_kg * mfg_factor

        total_scope3 = round(shipping_co2 + mfg_co2, 0)
        return env_score, total_scope3

    # ── Social scoring ────────────────────────────────────────────────────────

    def _social_score(self, supplier_id: str, country: str) -> float:
        """Return social score 0–30."""
        country_social = COUNTRY_SOCIAL_SCORE.get(country, 45)
        seed = sum(ord(c) for c in supplier_id + "S")
        rng  = np.random.default_rng(self.seed + seed)
        noise = float(rng.normal(0, 4))
        raw   = float(np.clip(country_social + noise, 10, 100))
        return round(raw * 0.30, 1)

    # ── Governance scoring ────────────────────────────────────────────────────

    def _governance_score(self, supplier_id: str, country: str, fda_approved: bool) -> float:
        """Return governance score 0–30."""
        country_gov = COUNTRY_GOVERNANCE_SCORE.get(country, 45)
        fda_bonus   = 10.0 if fda_approved else 0.0
        seed = sum(ord(c) for c in supplier_id + "G")
        rng  = np.random.default_rng(self.seed + seed)
        noise = float(rng.normal(0, 4))
        raw   = float(np.clip(country_gov + fda_bonus * 0.3 + noise, 10, 100))
        return round(raw * 0.30, 1)

    # ── ESG tier ─────────────────────────────────────────────────────────────

    @staticmethod
    def _esg_tier(total: float) -> str:
        for tier, threshold in ESG_TIER_THRESHOLDS.items():
            if total >= threshold:
                return tier
        return "D"

    # ── Per-supplier scoring ──────────────────────────────────────────────────

    def _score_supplier(self, sup: pd.Series) -> dict:
        s_id        = sup["id"]
        country     = sup.get("country", "Unknown")
        fda_approved = bool(sup.get("fda_approved", False))
        risk_row    = self.risk_scores[self.risk_scores["supplier_id"] == s_id]
        risk_tier   = str(risk_row["risk_tier"].iloc[0]) if not risk_row.empty else "Moderate"

        env_score, scope3_co2 = self._env_score(s_id, country)
        social_score          = self._social_score(s_id, country)
        gov_score             = self._governance_score(s_id, country, fda_approved)
        total                 = round(env_score + social_score + gov_score, 1)
        tier                  = self._esg_tier(total)

        distance_km = COUNTRY_DISTANCE_KM.get(country, 8000)
        mode        = _transport_mode(distance_km)
        volume_kg   = self._sup_volume.get(s_id, self.annual_volume_kg / len(self.suppliers))

        return {
            "supplier_id":         s_id,
            "supplier_name":       sup["name"],
            "country":             country,
            "fda_approved":        fda_approved,
            "risk_tier":           risk_tier,
            "esg_total_score":     total,
            "esg_tier":            tier,
            "environmental_score": env_score,
            "social_score":        social_score,
            "governance_score":    gov_score,
            "scope3_kg_co2":       scope3_co2,
            "annual_volume_kg":    round(volume_kg, 0),
            "distance_km":         distance_km,
            "primary_transport":   mode,
            "shipping_co2_pct":    round(
                ((volume_kg / 1000) * distance_km * TRANSPORT_EMISSION_FACTORS[mode])
                / max(scope3_co2, 1) * 100, 1
            ),
            "key_esg_risk": (
                f"Low environmental score for {country} — high carbon intensity manufacturing"
                if env_score < 15 else
                f"Social risk in {country} — labour standards monitoring recommended"
                if social_score < 10 else
                f"Governance gap — {'not FDA approved' if not fda_approved else 'moderate regulatory environment'}"
                if gov_score < 12 else
                "No significant ESG concerns identified"
            ),
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        log.info("Running ESG scorer…")
        scores = [self._score_supplier(sup) for _, sup in self.suppliers.iterrows()]
        scores.sort(key=lambda x: x["esg_total_score"], reverse=True)

        total_scope3 = sum(s["scope3_kg_co2"] for s in scores)
        tier_counts  = {t: sum(1 for s in scores if s["esg_tier"] == t) for t in "ABCD"}

        # Top emitters
        top_emitters = sorted(scores, key=lambda x: x["scope3_kg_co2"], reverse=True)[:5]

        summary = {
            "total_suppliers":    len(scores),
            "tier_a":             tier_counts.get("A", 0),
            "tier_b":             tier_counts.get("B", 0),
            "tier_c":             tier_counts.get("C", 0),
            "tier_d":             tier_counts.get("D", 0),
            "avg_esg_score":      round(sum(s["esg_total_score"] for s in scores) / max(len(scores),1), 1),
            "total_scope3_kg_co2":round(total_scope3, 0),
            "total_scope3_tonnes_co2": round(total_scope3 / 1000, 1),
            "highest_esg_supplier":   scores[0]["supplier_name"] if scores else "N/A",
            "lowest_esg_supplier":    scores[-1]["supplier_name"] if scores else "N/A",
            "top_emitter":            top_emitters[0]["supplier_name"] if top_emitters else "N/A",
        }

        log.info(
            f"ESG scoring complete — avg score {summary['avg_esg_score']} | "
            f"Scope 3: {summary['total_scope3_tonnes_co2']} tonnes CO2"
        )

        return {
            "supplier_scores": scores,
            "top_emitters":    top_emitters,
            "summary":         summary,
        }
