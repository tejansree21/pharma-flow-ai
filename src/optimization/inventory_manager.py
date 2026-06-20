"""
PharmaFlow AI — Inventory Manager (Phase 2)
============================================
Implements classical pharmaceutical supply chain inventory formulas:

  Safety Stock  = Z_score × σ_demand × √(avg_lead_time)
  Reorder Point = (avg_demand_per_day × avg_lead_time) + safety_stock
  EOQ           = √(2 × annual_demand × ordering_cost / holding_cost_per_unit)
  Days Cover    = current_stock / avg_daily_demand

Outputs per-drug inventory recommendations including action codes:
  REORDER_NOW   — stock at or below reorder point
  REORDER_SOON  — stock within 2× safety stock of ROP
  ADEQUATE      — sufficient stock
  EXCESS        — stock exceeds 3× ROP (consider reducing)
"""

import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("pharma.inventory")

# ── Project paths ─────────────────────────────────────────────────────────────
_SRC = Path(__file__).resolve().parents[2]
SYNTHETIC_DIR = _SRC / "data" / "synthetic"
PROCESSED_DIR = _SRC / "data" / "processed"

# ── Constants ─────────────────────────────────────────────────────────────────
SERVICE_LEVEL = 0.95          # 95% service level → Z = 1.645
Z_SCORE = 1.645
ORDERING_COST_USD = 500.0     # fixed cost per purchase order
HOLDING_COST_RATE = 0.25      # 25% of item value per year


# ═════════════════════════════════════════════════════════════════════════════
# Inventory Manager
# ═════════════════════════════════════════════════════════════════════════════

class InventoryManager:
    """
    Computes per-drug inventory KPIs and reorder recommendations.

    Parameters
    ----------
    current_stock_kg : dict, optional
        {drug_id: current_on_hand_kg}  — if None, simulated from historical data.
    service_level : float
        Target service level (default 0.95).
    ordering_cost : float
        Fixed cost per purchase order in USD (default $500).
    holding_cost_rate : float
        Annual holding cost as fraction of item value (default 0.25).
    """

    def __init__(
        self,
        current_stock_kg: dict = None,
        service_level: float = SERVICE_LEVEL,
        ordering_cost: float = ORDERING_COST_USD,
        holding_cost_rate: float = HOLDING_COST_RATE,
    ):
        self.service_level = service_level
        self.z = self._z_from_service_level(service_level)
        self.ordering_cost = ordering_cost
        self.holding_cost_rate = holding_cost_rate

        # Load data
        self.drugs = pd.read_csv(SYNTHETIC_DIR / "drugs.csv")
        self.purchases = pd.read_csv(SYNTHETIC_DIR / "purchase_history.csv")
        self.purchases["order_date"] = pd.to_datetime(self.purchases["order_date"])

        # Price lookup
        try:
            forecasts = pd.read_csv(PROCESSED_DIR / "price_forecasts.csv")
            forecasts["ds"] = pd.to_datetime(forecasts["ds"])
            latest = forecasts.sort_values("ds").groupby("drug_id").last().reset_index()
            self.price_lookup = dict(zip(latest["drug_id"], latest["yhat"].clip(lower=1)))
        except Exception:
            self.price_lookup = {}

        # Compute demand statistics from purchase history
        self._compute_demand_stats()

        # Current stock — simulate as 3–8 weeks of avg demand if not provided
        if current_stock_kg is None:
            rng = np.random.default_rng(42)
            self.current_stock = {
                d: round(self.avg_weekly_demand.get(d, 100) * rng.uniform(3, 8))
                for d in self.drugs["id"]
            }
        else:
            self.current_stock = current_stock_kg

        self.result_ = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _z_from_service_level(sl: float) -> float:
        from scipy.stats import norm  # type: ignore
        return norm.ppf(sl)

    def _compute_demand_stats(self):
        """Compute weekly demand stats per drug from purchase history."""
        # Weekly aggregation
        self.purchases["week"] = self.purchases["order_date"].dt.to_period("W")
        weekly = (
            self.purchases.groupby(["drug_id", "week"])["quantity_kg"]
            .sum()
            .reset_index()
        )
        stats = weekly.groupby("drug_id")["quantity_kg"].agg(
            ["mean", "std"]
        ).reset_index()
        stats.columns = ["drug_id", "avg_weekly_demand_kg", "std_weekly_demand_kg"]
        stats["std_weekly_demand_kg"] = stats["std_weekly_demand_kg"].fillna(0)

        # Lead time stats from purchase history (days between order and expected delivery)
        if "lead_time_days" in self.purchases.columns:
            lt_stats = (
                self.purchases.groupby("drug_id")["lead_time_days"]
                .agg(["mean", "std"])
                .reset_index()
            )
            lt_stats.columns = ["drug_id", "avg_lead_time_days", "std_lead_time_days"]
            lt_stats["std_lead_time_days"] = lt_stats["std_lead_time_days"].fillna(0)
            stats = stats.merge(lt_stats, on="drug_id", how="left")
        else:
            stats["avg_lead_time_days"] = 21.0  # default 3 weeks
            stats["std_lead_time_days"] = 5.0

        stats["avg_daily_demand_kg"] = stats["avg_weekly_demand_kg"] / 7
        self.demand_stats = stats
        self.avg_weekly_demand = dict(
            zip(stats["drug_id"], stats["avg_weekly_demand_kg"])
        )

    # ── Core calculations ─────────────────────────────────────────────────────

    def _safety_stock(self, avg_lead_days: float, std_demand_weekly: float) -> float:
        """
        Safety stock with demand uncertainty:
        SS = Z × σ_demand_daily × √(lead_time_days)
        σ_demand_daily ≈ σ_demand_weekly / √7
        """
        sigma_daily = std_demand_weekly / np.sqrt(7)
        return self.z * sigma_daily * np.sqrt(avg_lead_days)

    def _reorder_point(
        self, avg_daily_demand: float, avg_lead_days: float, safety_stock: float
    ) -> float:
        """ROP = (avg_demand_per_day × avg_lead_time) + safety_stock"""
        return avg_daily_demand * avg_lead_days + safety_stock

    def _eoq(self, annual_demand_kg: float, unit_price: float) -> float:
        """EOQ = √(2 × D × S / H)  where H = h × p"""
        holding_cost = self.holding_cost_rate * unit_price
        if holding_cost <= 0 or annual_demand_kg <= 0:
            return annual_demand_kg / 12  # fallback: 1 month
        return np.sqrt(2 * annual_demand_kg * self.ordering_cost / holding_cost)

    def _action_code(self, current: float, rop: float, safety_stock: float) -> str:
        if current <= rop:
            return "REORDER_NOW"
        if current <= rop + 2 * safety_stock:
            return "REORDER_SOON"
        if current >= 3 * rop:
            return "EXCESS"
        return "ADEQUATE"

    # ── Public API ─────────────────────────────────────────────────────────────

    def compute_recommendations(self) -> pd.DataFrame:
        """
        Compute inventory recommendations for all drugs.

        Returns
        -------
        pd.DataFrame with columns:
            drug_id, drug_name, avg_daily_demand_kg, avg_lead_time_days,
            safety_stock_kg, reorder_point_kg, eoq_kg, current_stock_kg,
            days_cover, action, urgency_score
        """
        rows = []
        for _, drug in self.drugs.iterrows():
            d = drug["id"]
            stats = self.demand_stats[self.demand_stats["drug_id"] == d]
            if stats.empty:
                continue
            s = stats.iloc[0]

            avg_daily = s["avg_daily_demand_kg"]
            avg_lt = s["avg_lead_time_days"]
            std_wk = s["std_weekly_demand_kg"]

            ss = self._safety_stock(avg_lt, std_wk)
            rop = self._reorder_point(avg_daily, avg_lt, ss)

            annual_demand = avg_daily * 365
            price = self.price_lookup.get(d, drug.get("base_price_per_kg", 50))
            eoq = self._eoq(annual_demand, price)

            stock = self.current_stock.get(d, 0.0)
            days_cover = round(stock / max(avg_daily, 0.01), 1)
            action = self._action_code(stock, rop, ss)

            # Urgency score 0-100 (100 = stock out imminent)
            if action == "REORDER_NOW":
                urgency = min(100, 80 + max(0, (rop - stock) / max(rop, 1) * 20))
            elif action == "REORDER_SOON":
                urgency = 50 + max(0, (rop + 2 * ss - stock) / max(ss * 2, 1) * 30)
            elif action == "EXCESS":
                urgency = 5
            else:
                urgency = max(0, 30 - days_cover)

            rows.append(
                {
                    "drug_id": d,
                    "drug_name": drug["name"],
                    "category": drug.get("category", ""),
                    "criticality": drug.get("criticality", "medium"),
                    "avg_daily_demand_kg": round(avg_daily, 2),
                    "avg_lead_time_days": round(avg_lt, 1),
                    "std_weekly_demand_kg": round(std_wk, 2),
                    "safety_stock_kg": round(ss, 2),
                    "reorder_point_kg": round(rop, 2),
                    "eoq_kg": round(eoq, 2),
                    "current_stock_kg": round(stock, 2),
                    "days_cover": days_cover,
                    "action": action,
                    "urgency_score": round(urgency, 1),
                    "price_per_kg": round(price, 2),
                    "stock_value_usd": round(stock * price, 2),
                    "service_level_target": self.service_level,
                }
            )

        df = pd.DataFrame(rows).sort_values("urgency_score", ascending=False)
        df.to_csv(PROCESSED_DIR / "inventory_recommendations.csv", index=False)
        self.result_ = df
        return df

    def summary(self, df: pd.DataFrame = None) -> dict:
        """High-level summary statistics."""
        if df is None:
            df = self.result_ or self.compute_recommendations()
        return {
            "total_drugs": len(df),
            "reorder_now": int((df["action"] == "REORDER_NOW").sum()),
            "reorder_soon": int((df["action"] == "REORDER_SOON").sum()),
            "adequate": int((df["action"] == "ADEQUATE").sum()),
            "excess": int((df["action"] == "EXCESS").sum()),
            "total_stock_value_usd": round(df["stock_value_usd"].sum(), 2),
            "avg_days_cover": round(df["days_cover"].mean(), 1),
            "critical_reorders": df[
                (df["action"] == "REORDER_NOW") & (df["criticality"] == "high")
            ]["drug_name"].tolist(),
        }


# ═════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("Running PharmaFlow Inventory Manager…")
    mgr = InventoryManager()
    df = mgr.compute_recommendations()
    s = mgr.summary(df)

    print("\n" + "=" * 60)
    print("INVENTORY MANAGEMENT RESULTS")
    print("=" * 60)
    print(f"Total Drugs Tracked : {s['total_drugs']}")
    print(f"⛔ REORDER NOW       : {s['reorder_now']}")
    print(f"⚠️  REORDER SOON      : {s['reorder_soon']}")
    print(f"✅ ADEQUATE          : {s['adequate']}")
    print(f"📦 EXCESS            : {s['excess']}")
    print(f"Total Stock Value   : ${s['total_stock_value_usd']:>12,.2f}")
    print(f"Avg Days Cover      : {s['avg_days_cover']} days")
    if s["critical_reorders"]:
        print(f"\n🚨 Critical drugs needing immediate reorder:")
        for d in s["critical_reorders"]:
            print(f"   • {d}")
    print()
    print("Full recommendations saved to data/processed/inventory_recommendations.csv")
    print("\nTop 10 by Urgency:")
    print(
        df.head(10)[
            [
                "drug_name",
                "current_stock_kg",
                "reorder_point_kg",
                "days_cover",
                "action",
                "urgency_score",
            ]
        ].to_string(index=False)
    )
