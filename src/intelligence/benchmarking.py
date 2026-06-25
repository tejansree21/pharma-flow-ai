"""
PharmaFlow AI — Phase 9: Industry Benchmarking Engine
======================================================
Compares your drug procurement prices and supplier quality rates
against synthetic peer market benchmarks.

Since real competitor pricing data requires expensive subscriptions
(IQVIA, Evaluate Pharma), this module generates a statistically
realistic market distribution around each drug's known base price —
the same approach used by consultant benchmarking tools before live
market data is connected.

Outputs:
  - Per-drug: our price vs market p25/median/p75, percentile rank, savings opportunity
  - Per-supplier: quality pass rate vs industry standard (94%)
  - Summary: total monthly savings opportunity, % of formulary above market
"""

import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.benchmark")

_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC  = _ROOT / "data" / "synthetic"
PROCESSED  = _ROOT / "data" / "processed"

INDUSTRY_QUALITY_BENCHMARK = 94.0   # 94% pass rate — pharma industry standard
MARKET_PRICE_STD_RATIO     = 0.15   # ±15% std dev around market median
MARKET_SAMPLE_SIZE         = 80     # synthetic peer observations per drug


class BenchmarkEngine:
    """
    Compares PharmaFlow supply chain performance against market benchmarks.

    Parameters
    ----------
    seed : int — random seed for reproducible market distributions
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.drugs     = pd.read_csv(SYNTHETIC / "drugs.csv")
        self.suppliers = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")

        # Latest forecast prices as our "current" prices
        fc = pd.read_csv(PROCESSED / "price_forecasts.csv")
        fc["ds"] = pd.to_datetime(fc["ds"])
        self.our_prices = (
            fc.sort_values("ds").groupby("drug_id")["yhat"].last().clip(lower=1).to_dict()
        )

        # Quality results for quality benchmarking
        try:
            self.quality_df = pd.read_csv(PROCESSED / "quality_anomaly_results.csv")
        except FileNotFoundError:
            self.quality_df = pd.DataFrame()

    # ── Price benchmarking ────────────────────────────────────────────────────

    def _market_distribution(self, drug_id: str, base_price: float) -> dict:
        """
        Generate a synthetic market price distribution for one drug.
        Uses drug_id as seed offset for reproducibility + uniqueness per drug.
        """
        drug_seed = self.seed + sum(ord(c) for c in drug_id)
        rng = np.random.default_rng(drug_seed)
        prices = rng.normal(
            loc=base_price,
            scale=base_price * MARKET_PRICE_STD_RATIO,
            size=MARKET_SAMPLE_SIZE
        )
        prices = np.clip(prices, base_price * 0.55, base_price * 1.65)
        return {
            "p10":    float(np.percentile(prices, 10)),
            "p25":    float(np.percentile(prices, 25)),
            "median": float(np.percentile(prices, 50)),
            "p75":    float(np.percentile(prices, 75)),
            "p90":    float(np.percentile(prices, 90)),
        }

    def benchmark_prices(self) -> list[dict]:
        """Return per-drug price benchmark comparison."""
        # Estimate monthly demand from purchase history if available
        demand_lookup: dict = {}
        try:
            ph = pd.read_csv(SYNTHETIC / "purchase_history.csv")
            demand_lookup = (ph.groupby("drug_id")["quantity_kg"].mean() * 4).round().to_dict()
        except FileNotFoundError:
            pass

        rows = []
        for _, drug in self.drugs.iterrows():
            d_id      = drug["id"]
            base      = float(drug.get("base_price_per_kg", 50))
            our_price = float(self.our_prices.get(d_id, base))
            dist      = self._market_distribution(d_id, base)

            # Compute percentile rank — what % of the market is cheaper
            savings_per_kg        = max(0.0, our_price - dist["median"])
            monthly_demand        = float(demand_lookup.get(d_id, base * 10))
            monthly_savings_opp   = round(savings_per_kg * monthly_demand, 2)

            # Position category
            if our_price > dist["p75"]:
                position = "SIGNIFICANTLY_ABOVE"
            elif our_price > dist["median"]:
                position = "ABOVE_MARKET"
            elif our_price >= dist["p25"]:
                position = "AT_MARKET"
            else:
                position = "BELOW_MARKET"

            # Approximate percentile rank
            percentile = max(5.0, min(95.0, (our_price - dist["p10"]) / (dist["p90"] - dist["p10"]) * 100))

            rows.append({
                "drug_id":                   d_id,
                "drug_name":                 drug["name"],
                "category":                  drug.get("category", ""),
                "criticality":               drug.get("criticality", "medium"),
                "our_price":                 round(our_price, 2),
                "market_p25":                round(dist["p25"], 2),
                "market_median":             round(dist["median"], 2),
                "market_p75":                round(dist["p75"], 2),
                "market_p10":                round(dist["p10"], 2),
                "market_p90":                round(dist["p90"], 2),
                "percentile_rank":           round(percentile, 1),
                "savings_per_kg":            round(savings_per_kg, 2),
                "monthly_demand_kg":         round(monthly_demand, 1),
                "monthly_savings_opportunity": monthly_savings_opp,
                "position":                  position,
            })

        return sorted(rows, key=lambda x: x["monthly_savings_opportunity"], reverse=True)

    # ── Quality benchmarking ──────────────────────────────────────────────────

    def benchmark_quality(self) -> list[dict]:
        """Return per-supplier quality pass rate vs industry benchmark."""
        rows = []

        if not self.quality_df.empty and "is_anomaly" in self.quality_df.columns:
            for sup_id, group in self.quality_df.groupby("supplier_id"):
                total    = len(group)
                anomalies = int(group["is_anomaly"].sum())
                pass_rate = (total - anomalies) / max(total, 1) * 100

                sup_row = self.suppliers[self.suppliers["id"] == sup_id]
                if sup_row.empty:
                    continue
                sup = sup_row.iloc[0]
                delta = pass_rate - INDUSTRY_QUALITY_BENCHMARK

                rows.append({
                    "supplier_id":        sup_id,
                    "supplier_name":      sup["name"],
                    "country":            sup.get("country", ""),
                    "fda_approved":       bool(sup.get("fda_approved", False)),
                    "our_quality_rate":   round(pass_rate, 1),
                    "industry_benchmark": INDUSTRY_QUALITY_BENCHMARK,
                    "quality_delta":      round(delta, 1),
                    "quality_rating":     "ABOVE_BENCHMARK" if delta > 2 else "AT_BENCHMARK" if delta >= -2 else "BELOW_BENCHMARK",
                    "batches_analyzed":   total,
                    "anomalies_detected": anomalies,
                })

        # Synthetic fallback
        if not rows:
            rng = np.random.default_rng(self.seed)
            for _, sup in self.suppliers.iterrows():
                # Risk tier informs quality: Critical suppliers → lower quality
                risk_row = self.risk_scores[self.risk_scores["supplier_id"] == sup["id"]]
                risk_tier = str(risk_row["risk_tier"].iloc[0]) if not risk_row.empty else "Moderate"
                offset = {"Low": 2.5, "Moderate": 0.0, "High": -3.0, "Critical": -6.0}.get(risk_tier, 0.0)
                pass_rate = float(np.clip(rng.normal(93.5 + offset, 3.5), 72, 100))
                delta = pass_rate - INDUSTRY_QUALITY_BENCHMARK
                rows.append({
                    "supplier_id":        sup["id"],
                    "supplier_name":      sup["name"],
                    "country":            sup.get("country", ""),
                    "fda_approved":       bool(sup.get("fda_approved", False)),
                    "our_quality_rate":   round(pass_rate, 1),
                    "industry_benchmark": INDUSTRY_QUALITY_BENCHMARK,
                    "quality_delta":      round(delta, 1),
                    "quality_rating":     "ABOVE_BENCHMARK" if delta > 2 else "AT_BENCHMARK" if delta >= -2 else "BELOW_BENCHMARK",
                    "batches_analyzed":   int(rng.integers(25, 120)),
                    "anomalies_detected": int(rng.integers(0, max(1, int(25 * (1 - pass_rate / 100))))),
                })

        return sorted(rows, key=lambda x: x["quality_delta"])

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        log.info("Running benchmark engine…")
        price_bm   = self.benchmark_prices()
        quality_bm = self.benchmark_quality()

        above = sum(1 for d in price_bm if "ABOVE" in d["position"])
        at_   = sum(1 for d in price_bm if d["position"] == "AT_MARKET")
        below = sum(1 for d in price_bm if d["position"] == "BELOW_MARKET")
        total_savings = sum(d["monthly_savings_opportunity"] for d in price_bm)
        below_qual   = sum(1 for s in quality_bm if s["quality_rating"] == "BELOW_BENCHMARK")
        avg_pctile   = sum(d["percentile_rank"] for d in price_bm) / max(len(price_bm), 1)

        summary = {
            "total_drugs_benchmarked":        len(price_bm),
            "drugs_above_market":             above,
            "drugs_at_market":                at_,
            "drugs_below_market":             below,
            "total_monthly_savings_opportunity": round(total_savings, 2),
            "avg_price_percentile":           round(avg_pctile, 1),
            "suppliers_below_quality_benchmark": below_qual,
            "industry_avg_quality_pct":       INDUSTRY_QUALITY_BENCHMARK,
        }

        log.info(
            f"Benchmark complete — {above} drugs above market | "
            f"Monthly savings opp: ${total_savings:,.0f} | "
            f"{below_qual} suppliers below quality benchmark"
        )

        return {
            "price_benchmarks":   price_bm,
            "quality_benchmarks": quality_bm,
            "summary":            summary,
        }


if __name__ == "__main__":
    eng = BenchmarkEngine()
    res = eng.run()
    s = res["summary"]
    print(f"\nBENCHMARK REPORT")
    print(f"Drugs above market     : {s['drugs_above_market']}")
    print(f"Monthly savings opp    : ${s['total_monthly_savings_opportunity']:,.0f}")
    print(f"Avg price percentile   : {s['avg_price_percentile']:.1f}th")
    print(f"Below quality benchmark: {s['suppliers_below_quality_benchmark']}")
    print("\nTop 5 savings opportunities:")
    for d in res["price_benchmarks"][:5]:
        print(f"  {d['drug_name']:<30} our=${d['our_price']:.2f} market={d['market_median']:.2f} save=${d['savings_per_kg']:.2f}/kg [{d['position']}]")
