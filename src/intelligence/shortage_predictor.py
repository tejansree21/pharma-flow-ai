"""
PharmaFlow AI — Phase 3: Shortage Predictor
============================================
Predicts which drugs are at risk of supply shortage over the next 4–12 weeks.

Shortage risk is scored 0–100 from a weighted combination of:

  1. Demand Spike Score    (25%) — recent demand vs historical average (z-score)
  2. Supply Concentration  (20%) — Herfindahl-Hirschman Index across approved suppliers
  3. Lead Time Stress      (20%) — recent lead time vs historical baseline
  4. Inventory Runway      (20%) — days of stock cover vs reorder point
  5. Supplier Risk Overlay (15%) — avg risk score of approved suppliers

Outputs per-drug shortage alerts with 3 risk tiers:
  CRITICAL   — shortage likely within 4 weeks
  WARNING    — shortage possible within 8 weeks
  WATCH      — monitor closely
  STABLE     — no immediate concern
"""

import logging
import warnings
from pathlib import Path

import json
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("pharma.shortage")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"

# ── Weights ────────────────────────────────────────────────────────────────────
WEIGHTS = {
    "demand_spike": 0.25,
    "supply_concentration": 0.20,
    "lead_time_stress": 0.20,
    "inventory_runway": 0.20,
    "supplier_risk_overlay": 0.15,
}

TIER_THRESHOLDS = {
    "CRITICAL": 70,
    "WARNING": 45,
    "WATCH": 25,
}


# ═════════════════════════════════════════════════════════════════════════════
# Shortage Predictor
# ═════════════════════════════════════════════════════════════════════════════

class ShortagePredictor:
    """
    Multi-signal shortage risk scorer.

    Parameters
    ----------
    lookback_weeks : int
        Historical window for baseline statistics (default 26 = 6 months).
    recent_weeks : int
        'Recent' window to compare against baseline (default 4).
    """

    def __init__(self, lookback_weeks: int = 26, recent_weeks: int = 4):
        self.lookback_weeks = lookback_weeks
        self.recent_weeks = recent_weeks

        # Load data
        self.drugs = pd.read_csv(SYNTHETIC / "drugs.csv")
        self.suppliers = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.purchases = pd.read_csv(SYNTHETIC / "purchase_history.csv")
        self.purchases["order_date"] = pd.to_datetime(self.purchases["order_date"])
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")

        # Inventory recommendations (from Phase 2) if available
        inv_path = PROCESSED / "inventory_recommendations.csv"
        self.inventory = pd.read_csv(inv_path) if inv_path.exists() else pd.DataFrame()

        self._cutoff = self.purchases["order_date"].max()
        self._recent_start = self._cutoff - pd.Timedelta(weeks=recent_weeks)
        self._lookback_start = self._cutoff - pd.Timedelta(weeks=lookback_weeks)

        self.result_ = None

    # ── Signal calculators ────────────────────────────────────────────────────

    def _demand_spike_score(self, drug_id: str) -> float:
        """
        Z-score of recent weekly demand vs historical.
        Clipped to [0, 100] where 100 = demand 3+ std devs above normal.
        """
        hist = self.purchases[
            (self.purchases["drug_id"] == drug_id) &
            (self.purchases["order_date"] >= self._lookback_start) &
            (self.purchases["order_date"] < self._recent_start)
        ]
        recent = self.purchases[
            (self.purchases["drug_id"] == drug_id) &
            (self.purchases["order_date"] >= self._recent_start)
        ]

        if hist.empty or recent.empty:
            return 50.0

        # Weekly aggregate
        hist_weekly = hist.groupby(hist["order_date"].dt.to_period("W"))["quantity_kg"].sum()
        recent_weekly = recent.groupby(recent["order_date"].dt.to_period("W"))["quantity_kg"].sum()

        mu = hist_weekly.mean()
        sigma = hist_weekly.std()
        if sigma < 1e-6:
            return 0.0

        recent_avg = recent_weekly.mean()
        z = (recent_avg - mu) / sigma

        # Convert z-score to 0-100 score (positive z = demand higher than usual)
        score = float(np.clip(z * 20 + 50, 0, 100))
        return score

    def _supply_concentration_score(self, drug_id: str) -> float:
        """
        Herfindahl-Hirschman Index (HHI) over last 6 months by supplier.
        HHI = Σ(market_share²) → 0=perfectly diversified, 10000=monopoly.
        Normalised to 0-100.
        """
        hist = self.purchases[
            (self.purchases["drug_id"] == drug_id) &
            (self.purchases["order_date"] >= self._lookback_start)
        ]
        if hist.empty:
            return 50.0

        by_supplier = hist.groupby("supplier_id")["quantity_kg"].sum()
        total = by_supplier.sum()
        if total < 1e-6:
            return 50.0

        shares = (by_supplier / total * 100) ** 2
        hhi = shares.sum()  # max 10000 (monopoly)
        return float(np.clip(hhi / 100, 0, 100))  # normalise to 0-100

    def _lead_time_stress_score(self, drug_id: str) -> float:
        """
        Recent lead time vs historical baseline.
        Rising lead times = early warning of supply stress.
        """
        if "lead_time_days" not in self.purchases.columns:
            return 30.0  # neutral default

        hist = self.purchases[
            (self.purchases["drug_id"] == drug_id) &
            (self.purchases["order_date"] >= self._lookback_start) &
            (self.purchases["order_date"] < self._recent_start)
        ]["lead_time_days"].dropna()

        recent = self.purchases[
            (self.purchases["drug_id"] == drug_id) &
            (self.purchases["order_date"] >= self._recent_start)
        ]["lead_time_days"].dropna()

        if hist.empty or recent.empty:
            return 30.0

        mu = hist.mean()
        sigma = hist.std()
        if sigma < 1e-6:
            return 0.0

        z = (recent.mean() - mu) / sigma
        return float(np.clip(z * 25 + 30, 0, 100))

    def _inventory_runway_score(self, drug_id: str) -> float:
        """
        Urgency score from Phase 2 inventory manager (0-100).
        If inventory data not available, estimate from purchase frequency.
        """
        if not self.inventory.empty:
            row = self.inventory[self.inventory["drug_id"] == drug_id]
            if not row.empty:
                return float(row["urgency_score"].iloc[0])

        # Fallback: estimate days cover from recent purchase volume
        recent = self.purchases[
            (self.purchases["drug_id"] == drug_id) &
            (self.purchases["order_date"] >= self._recent_start)
        ]
        if recent.empty:
            return 50.0

        avg_weekly = recent.groupby(recent["order_date"].dt.to_period("W"))["quantity_kg"].sum().mean()
        # Assume 4-week stock on hand → days cover = 28
        days_cover = 28
        score = max(0, 100 - days_cover * 2)
        return float(score)

    def _supplier_risk_overlay_score(self, drug_id: str) -> float:
        """
        Weighted average risk score of approved suppliers for this drug.
        """
        drug_row = self.drugs[self.drugs["id"] == drug_id]
        if drug_row.empty:
            return 50.0

        try:
            approved = json.loads(drug_row.iloc[0].get("approved_suppliers", "[]"))
        except (json.JSONDecodeError, AttributeError):
            return 50.0

        if not approved:
            return 100.0  # no approved suppliers = maximum risk

        risk_rows = self.risk_scores[self.risk_scores["supplier_id"].isin(approved)]
        if risk_rows.empty:
            return 50.0

        return float(risk_rows["risk_score"].mean())

    # ── Composite scorer ──────────────────────────────────────────────────────

    def _composite_score(self, drug_id: str) -> dict:
        demand = self._demand_spike_score(drug_id)
        concentration = self._supply_concentration_score(drug_id)
        lead_time = self._lead_time_stress_score(drug_id)
        inventory = self._inventory_runway_score(drug_id)
        supplier_risk = self._supplier_risk_overlay_score(drug_id)

        composite = (
            demand * WEIGHTS["demand_spike"] +
            concentration * WEIGHTS["supply_concentration"] +
            lead_time * WEIGHTS["lead_time_stress"] +
            inventory * WEIGHTS["inventory_runway"] +
            supplier_risk * WEIGHTS["supplier_risk_overlay"]
        )

        return {
            "demand_spike_score": round(demand, 1),
            "supply_concentration_score": round(concentration, 1),
            "lead_time_stress_score": round(lead_time, 1),
            "inventory_runway_score": round(inventory, 1),
            "supplier_risk_overlay_score": round(supplier_risk, 1),
            "shortage_risk_score": round(composite, 1),
        }

    @staticmethod
    def _risk_tier(score: float) -> str:
        if score >= TIER_THRESHOLDS["CRITICAL"]:
            return "CRITICAL"
        if score >= TIER_THRESHOLDS["WARNING"]:
            return "WARNING"
        if score >= TIER_THRESHOLDS["WATCH"]:
            return "WATCH"
        return "STABLE"

    @staticmethod
    def _recommended_action(tier: str, drug_name: str) -> str:
        actions = {
            "CRITICAL": f"🚨 Trigger emergency procurement for {drug_name}. Activate backup suppliers. Notify clinical teams.",
            "WARNING":  f"⚠️  Accelerate reorder for {drug_name}. Increase safety stock by 50%. Audit top 2 suppliers.",
            "WATCH":    f"👁️  Monitor {drug_name} weekly. Pre-qualify additional supplier. Review demand forecast.",
            "STABLE":   f"✅ {drug_name} supply stable. Maintain standard monitoring schedule.",
        }
        return actions[tier]

    # ── Public API ─────────────────────────────────────────────────────────────

    def predict_all(self) -> pd.DataFrame:
        """
        Run shortage prediction for all drugs.

        Returns
        -------
        pd.DataFrame sorted by shortage_risk_score descending.
        """
        rows = []
        for _, drug in self.drugs.iterrows():
            d = drug["id"]
            scores = self._composite_score(d)
            tier = self._risk_tier(scores["shortage_risk_score"])
            rows.append({
                "drug_id": d,
                "drug_name": drug["name"],
                "category": drug.get("category", ""),
                "criticality": drug.get("criticality", "medium"),
                **scores,
                "risk_tier": tier,
                "recommended_action": self._recommended_action(tier, drug["name"]),
            })

        df = pd.DataFrame(rows).sort_values("shortage_risk_score", ascending=False)
        df.to_csv(PROCESSED / "shortage_predictions.csv", index=False)
        self.result_ = df
        return df

    def summary(self, df: pd.DataFrame = None) -> dict:
        if df is None:
            df = self.result_ or self.predict_all()
        return {
            "total_drugs": len(df),
            "critical": int((df["risk_tier"] == "CRITICAL").sum()),
            "warning": int((df["risk_tier"] == "WARNING").sum()),
            "watch": int((df["risk_tier"] == "WATCH").sum()),
            "stable": int((df["risk_tier"] == "STABLE").sum()),
            "avg_risk_score": round(float(df["shortage_risk_score"].mean()), 1),
            "highest_risk_drug": df.iloc[0]["drug_name"] if not df.empty else "N/A",
            "highest_risk_score": float(df.iloc[0]["shortage_risk_score"]) if not df.empty else 0,
        }


# ═════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("Running PharmaFlow Shortage Predictor…")
    predictor = ShortagePredictor()
    df = predictor.predict_all()
    s = predictor.summary(df)

    print("\n" + "=" * 65)
    print("SHORTAGE PREDICTION RESULTS")
    print("=" * 65)
    print(f"Total drugs monitored : {s['total_drugs']}")
    print(f"🚨 CRITICAL           : {s['critical']}")
    print(f"⚠️  WARNING            : {s['warning']}")
    print(f"👁️  WATCH              : {s['watch']}")
    print(f"✅ STABLE             : {s['stable']}")
    print(f"Avg risk score        : {s['avg_risk_score']}")
    print(f"Highest risk drug     : {s['highest_risk_drug']} ({s['highest_risk_score']:.1f})")
    print()
    print(f"{'Drug':<30} {'Score':>6}  {'Tier':<10}  {'Category'}")
    print("-" * 70)
    for _, row in df.iterrows():
        tier_icon = {"CRITICAL": "🚨", "WARNING": "⚠️ ", "WATCH": "👁️ ", "STABLE": "✅"}
        icon = tier_icon.get(row["risk_tier"], "  ")
        print(f"{row['drug_name']:<30} {row['shortage_risk_score']:>6.1f}  {icon} {row['risk_tier']:<10}  {row['category']}")
    print()
    print("Predictions saved to data/processed/shortage_predictions.csv")
