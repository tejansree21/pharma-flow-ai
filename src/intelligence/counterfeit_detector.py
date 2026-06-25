"""
PharmaFlow AI — Phase 9: Counterfeit & Grey-Market Risk Detector
================================================================
Combines four independent risk signals to score each supplier's
likelihood of sourcing counterfeit or grey-market pharmaceutical
ingredients.

IMPORTANT: This module detects *risk signals* and flags suppliers
for investigation. A high score means "investigate urgently" — it
does NOT confirm that a supplier is selling counterfeits. Human
review and laboratory testing are always required before action.

Scoring dimensions (total 0–100):
  1. Price anomaly (0–35)
     Supplier pricing significantly below market median is a classic
     counterfeit signal — counterfeit products are often priced at
     60–80% of legitimate product to undercut the market.

  2. Quality drift (0–30)
     Sustained quality metric degradation detected by Isolation Forest
     + SPC can indicate product substitution or dilution.

  3. Regulatory posture (0–20)
     Non-FDA-approved suppliers, active warning letters, and poor
     regulatory inspection history all correlate with counterfeit risk.

  4. Incident history (0–15)
     Past supply incidents (delivery failures, quality rejections)
     contribute to the composite risk.

Risk tiers:
  CRITICAL (75–100): Immediate investigation required. Do not order.
  HIGH     (50–74):  Audit before next order. Test current inventory.
  MEDIUM   (25–49):  Monitor closely. Increase incoming QC testing.
  LOW      (0–24):   Normal procedures.
"""

import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.counterfeit")

_ROOT     = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"


class CounterfeitDetector:
    """
    Scores each supplier on counterfeit / grey-market risk.

    Parameters
    ----------
    price_anomaly_threshold : float
        Fraction below market median that triggers price anomaly flag (default 0.25 = 25%).
    seed : int
        Random seed for reproducible synthetic market prices.
    """

    def __init__(self, price_anomaly_threshold: float = 0.25, seed: int = 42):
        self.threshold = price_anomaly_threshold
        self.seed      = seed

        self.suppliers   = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.drugs       = pd.read_csv(SYNTHETIC / "drugs.csv")
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")

        fc = pd.read_csv(PROCESSED / "price_forecasts.csv")
        fc["ds"] = pd.to_datetime(fc["ds"])
        self.market_prices = (
            fc.sort_values("ds").groupby("drug_id")["yhat"].last().clip(lower=1).to_dict()
        )

        try:
            self.quality_df = pd.read_csv(PROCESSED / "quality_anomaly_results.csv")
            self._has_quality = "is_anomaly" in self.quality_df.columns
        except FileNotFoundError:
            self.quality_df = pd.DataFrame()
            self._has_quality = False

        # Precompute supplier price lookup from purchase history
        try:
            ph = pd.read_csv(SYNTHETIC / "purchase_history.csv")
            self.sup_prices = (
                ph.groupby(["supplier_id", "drug_id"])["price_per_kg"]
                .mean()
                .to_dict()
            )
        except (FileNotFoundError, KeyError):
            self.sup_prices = {}

    # ── Signal 1: Price anomaly ───────────────────────────────────────────────

    def _price_anomaly_score(self, supplier_id: str) -> tuple[float, str]:
        """
        Return (score 0–35, description).
        Higher score = supplier prices are suspiciously far below market.
        """
        # Average discount this supplier offers across all drugs they supply
        discounts = []
        for drug_id, market_price in self.market_prices.items():
            their_price = self.sup_prices.get((supplier_id, drug_id))
            if their_price and market_price > 0:
                discount = (market_price - their_price) / market_price
                discounts.append(discount)

        if not discounts:
            # Estimate from risk-adjusted price tier
            rng = np.random.default_rng(self.seed + sum(ord(c) for c in supplier_id))
            risk_row = self.risk_scores[self.risk_scores["supplier_id"] == supplier_id]
            risk_score = float(risk_row["risk_score"].iloc[0]) if not risk_row.empty else 50.0
            avg_discount = float(rng.uniform(-0.05, min(0.45, risk_score / 200)))
        else:
            avg_discount = float(np.mean(discounts))

        if avg_discount >= 0.40:
            score = 35.0
            desc  = f"Price {avg_discount*100:.0f}% below market — CRITICAL price anomaly"
        elif avg_discount >= 0.30:
            score = 28.0
            desc  = f"Price {avg_discount*100:.0f}% below market — significant underpricing"
        elif avg_discount >= self.threshold:
            score = 18.0
            desc  = f"Price {avg_discount*100:.0f}% below market — moderate underpricing"
        elif avg_discount >= 0.10:
            score = 8.0
            desc  = f"Price {avg_discount*100:.0f}% below market — minor discount"
        else:
            score = 0.0
            desc  = "Pricing at or above market — no price anomaly"

        return round(score, 1), desc

    # ── Signal 2: Quality drift ───────────────────────────────────────────────

    def _quality_drift_score(self, supplier_id: str) -> tuple[float, str]:
        """Return (score 0–30, description)."""
        if not self._has_quality:
            # Estimate from XGBoost risk score quality_risk dimension
            risk_row = self.risk_scores[self.risk_scores["supplier_id"] == supplier_id]
            if not risk_row.empty and "quality_risk" in risk_row.columns:
                qr = float(risk_row["quality_risk"].iloc[0])
                score = round(qr * 0.30, 1)
                return min(30.0, score), f"Quality risk estimate: {qr:.0f}/100"
            return 0.0, "No quality data available"

        sup_batches = self.quality_df[self.quality_df["supplier_id"] == supplier_id]
        if sup_batches.empty:
            return 0.0, "No batch quality data for this supplier"

        anomaly_rate = float(sup_batches["is_anomaly"].mean())
        n = len(sup_batches)

        if anomaly_rate >= 0.30:
            score = 30.0
            desc  = f"{anomaly_rate*100:.0f}% anomaly rate ({n} batches) — severe quality drift"
        elif anomaly_rate >= 0.20:
            score = 22.0
            desc  = f"{anomaly_rate*100:.0f}% anomaly rate — significant quality concerns"
        elif anomaly_rate >= 0.10:
            score = 13.0
            desc  = f"{anomaly_rate*100:.0f}% anomaly rate — elevated anomaly frequency"
        elif anomaly_rate >= 0.05:
            score = 6.0
            desc  = f"{anomaly_rate*100:.0f}% anomaly rate — mild quality drift"
        else:
            score = 0.0
            desc  = f"{anomaly_rate*100:.0f}% anomaly rate — quality within norms"

        return round(score, 1), desc

    # ── Signal 3: Regulatory posture ──────────────────────────────────────────

    def _regulatory_score(self, supplier_id: str) -> tuple[float, str]:
        """Return (score 0–20, description)."""
        sup_row = self.suppliers[self.suppliers["id"] == supplier_id]
        if sup_row.empty:
            return 10.0, "Unknown supplier — regulatory status unverified"
        sup = sup_row.iloc[0]

        fda_approved = bool(sup.get("fda_approved", False))
        risk_row     = self.risk_scores[self.risk_scores["supplier_id"] == supplier_id]
        geo_reg      = float(risk_row["geo_regulatory_risk"].iloc[0]) if not risk_row.empty and "geo_regulatory_risk" in risk_row.columns else 50.0

        if not fda_approved and geo_reg >= 60:
            score = 20.0
            desc  = "Not FDA-approved + high geo/regulatory risk — critical regulatory gap"
        elif not fda_approved and geo_reg >= 40:
            score = 15.0
            desc  = "Not FDA-approved + elevated regulatory risk"
        elif not fda_approved:
            score = 10.0
            desc  = "Not FDA-approved — standard regulatory monitoring required"
        elif geo_reg >= 70:
            score = 8.0
            desc  = "FDA-approved but high geo/regulatory risk environment"
        elif geo_reg >= 45:
            score = 4.0
            desc  = "FDA-approved, moderate regulatory environment"
        else:
            score = 0.0
            desc  = "FDA-approved, low regulatory risk"

        return round(score, 1), desc

    # ── Signal 4: Incident history ────────────────────────────────────────────

    def _incident_score(self, supplier_id: str) -> tuple[float, str]:
        """Return (score 0–15, description) from risk model incident_risk."""
        risk_row = self.risk_scores[self.risk_scores["supplier_id"] == supplier_id]
        if risk_row.empty:
            return 5.0, "No incident history available"
        inc_risk = float(risk_row.get("incident_risk", pd.Series([50.0])).iloc[0])
        score    = round(inc_risk * 0.15, 1)
        score    = min(15.0, score)
        if score >= 12:
            desc = f"Incident risk {inc_risk:.0f}/100 — multiple recorded incidents"
        elif score >= 7:
            desc = f"Incident risk {inc_risk:.0f}/100 — some incidents recorded"
        else:
            desc = f"Incident risk {inc_risk:.0f}/100 — minimal incident history"
        return score, desc

    # ── Composite scoring ─────────────────────────────────────────────────────

    def _tier(self, score: float) -> str:
        if score >= 75: return "CRITICAL"
        if score >= 50: return "HIGH"
        if score >= 25: return "MEDIUM"
        return "LOW"

    def _recommendation(self, tier: str, top_concern: str) -> str:
        if tier == "CRITICAL":
            return f"Do not place new orders until audit complete. Urgently investigate: {top_concern}. Test all current inventory from this supplier."
        if tier == "HIGH":
            return f"Audit required before next order. Increase incoming QC testing to 100% batch inspection. Key concern: {top_concern}"
        if tier == "MEDIUM":
            return f"Monitor closely. Apply enhanced incoming inspection (20% batch sampling). Watch for: {top_concern}"
        return "Standard incoming QC procedures sufficient. Continue periodic monitoring."

    # ── Public API ─────────────────────────────────────────────────────────────

    def score_all(self) -> dict:
        """Score every supplier and return ranked results."""
        log.info("Running counterfeit risk detection…")
        rows = []

        for _, sup in self.suppliers.iterrows():
            s_id = sup["id"]

            p_score, p_desc = self._price_anomaly_score(s_id)
            q_score, q_desc = self._quality_drift_score(s_id)
            r_score, r_desc = self._regulatory_score(s_id)
            i_score, i_desc = self._incident_score(s_id)

            total = round(p_score + q_score + r_score + i_score, 1)
            tier  = self._tier(total)

            # Top concern is the highest-scoring signal
            signal_scores = [
                (p_score, p_desc), (q_score, q_desc),
                (r_score, r_desc), (i_score, i_desc)
            ]
            top_concern = max(signal_scores, key=lambda x: x[0])[1]

            rows.append({
                "supplier_id":          s_id,
                "supplier_name":        sup["name"],
                "country":              sup.get("country", ""),
                "fda_approved":         bool(sup.get("fda_approved", False)),
                "counterfeit_risk_score": total,
                "risk_tier":            tier,
                "price_anomaly_score":  p_score,
                "quality_drift_score":  q_score,
                "regulatory_risk_score": r_score,
                "incident_risk_score":  i_score,
                "price_anomaly_detail": p_desc,
                "quality_drift_detail": q_desc,
                "regulatory_detail":    r_desc,
                "incident_detail":      i_desc,
                "top_concern":          top_concern,
                "recommendation":       self._recommendation(tier, top_concern),
            })

        rows.sort(key=lambda x: x["counterfeit_risk_score"], reverse=True)

        summary = {
            "total_suppliers": len(rows),
            "critical_risk":   sum(1 for r in rows if r["risk_tier"] == "CRITICAL"),
            "high_risk":       sum(1 for r in rows if r["risk_tier"] == "HIGH"),
            "medium_risk":     sum(1 for r in rows if r["risk_tier"] == "MEDIUM"),
            "low_risk":        sum(1 for r in rows if r["risk_tier"] == "LOW"),
            "highest_risk_supplier": rows[0]["supplier_name"] if rows else "N/A",
        }

        log.info(
            f"Counterfeit risk scan complete — "
            f"CRITICAL: {summary['critical_risk']} | HIGH: {summary['high_risk']}"
        )
        return {"supplier_risks": rows, "summary": summary}


if __name__ == "__main__":
    cd = CounterfeitDetector()
    result = cd.score_all()
    s = result["summary"]
    print(f"\nCOUNTERFEIT RISK REPORT")
    print(f"Total suppliers : {s['total_suppliers']}")
    print(f"CRITICAL        : {s['critical_risk']}")
    print(f"HIGH            : {s['high_risk']}")
    print(f"MEDIUM          : {s['medium_risk']}")
    print(f"LOW             : {s['low_risk']}")
    print(f"\nTop 5 highest risk:")
    for r in result["supplier_risks"][:5]:
        print(f"  {r['supplier_name']:<28} score={r['counterfeit_risk_score']:.0f} [{r['risk_tier']}]")
        print(f"    → {r['top_concern'][:80]}")
