"""
PharmaFlow AI — Bulk Purchase Optimizer (Phase 2)
=================================================
Uses PuLP linear programming to determine optimal order allocations
across suppliers, minimising cost while penalising risk.

Decision variables:
    x[drug_id][supplier_id] = quantity (kg) to order

Objective (minimise):
    Σ price_per_kg × qty + risk_penalty_weight × risk_score × qty

Constraints:
    1. Demand coverage     — Σ_s x[d][s] >= demand[d]  for every drug d
    2. Supplier capacity   — Σ_d x[d][s] <= capacity[s] for every supplier s
    3. Concentration limit — x[d][s] <= conc_limit × demand[d]  (default 60%)
    4. Approved only       — x[d][s] = 0 if supplier not approved for drug
    5. Non-negativity      — x[d][s] >= 0
"""

import os
import json
import logging
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("pharma.optimizer")

# ── PuLP (fallback to greedy if not installed) ────────────────────────────────
try:
    import pulp  # type: ignore

    PULP_AVAILABLE = True
except ImportError:
    PULP_AVAILABLE = False
    log.warning("PuLP not installed – falling back to greedy heuristic optimizer.")

# ── Project paths ─────────────────────────────────────────────────────────────
_SRC = Path(__file__).resolve().parents[2]
SYNTHETIC_DIR = _SRC / "data" / "synthetic"
PROCESSED_DIR = _SRC / "data" / "processed"
RESULTS_DIR = _SRC / "data" / "processed"

RISK_PENALTY_WEIGHT = 0.8   # $ cost equivalent per risk-point per kg
DEFAULT_CONCENTRATION_LIMIT = 0.60  # max fraction from a single supplier


# ═════════════════════════════════════════════════════════════════════════════
# Data loaders
# ═════════════════════════════════════════════════════════════════════════════

def _load_data():
    """Load all required dataframes."""
    drugs = pd.read_csv(SYNTHETIC_DIR / "drugs.csv")
    suppliers = pd.read_csv(SYNTHETIC_DIR / "suppliers.csv")
    risk_scores = pd.read_csv(PROCESSED_DIR / "supplier_risk_scores.csv")
    forecasts = pd.read_csv(PROCESSED_DIR / "price_forecasts.csv")
    forecasts["ds"] = pd.to_datetime(forecasts["ds"])
    return drugs, suppliers, risk_scores, forecasts


def _get_current_prices(forecasts: pd.DataFrame) -> dict:
    """Return latest forecast price per kg for each drug."""
    latest = (
        forecasts.sort_values("ds")
        .groupby("drug_id")
        .last()
        .reset_index()[["drug_id", "yhat"]]
    )
    return dict(zip(latest["drug_id"], latest["yhat"].clip(lower=1)))


def _get_approved_suppliers(drugs: pd.DataFrame) -> dict:
    """Return {drug_id: [supplier_id, ...]} from drugs.csv approved_suppliers column."""
    approved = {}
    for _, row in drugs.iterrows():
        try:
            approved[row["id"]] = json.loads(row["approved_suppliers"])
        except (json.JSONDecodeError, KeyError):
            approved[row["id"]] = []
    return approved


# ═════════════════════════════════════════════════════════════════════════════
# Core optimizer
# ═════════════════════════════════════════════════════════════════════════════

class PurchaseOptimizer:
    """
    Bulk purchase LP optimizer.

    Parameters
    ----------
    demand_kg : dict
        {drug_id: required_kg}  — the demand to fulfil.
    risk_penalty_weight : float
        $ cost per risk-score-point per kg ordered (default 0.8).
    concentration_limit : float
        Max fraction of any drug's demand from a single supplier (default 0.60).
    horizon_weeks : int
        How many weeks ahead the forecast price is taken from (default 4).
    """

    def __init__(
        self,
        demand_kg: Optional[dict] = None,
        risk_penalty_weight: float = RISK_PENALTY_WEIGHT,
        concentration_limit: float = DEFAULT_CONCENTRATION_LIMIT,
        horizon_weeks: int = 4,
    ):
        self.risk_penalty_weight = risk_penalty_weight
        self.concentration_limit = concentration_limit
        self.horizon_weeks = horizon_weeks

        # Load data
        self.drugs, self.suppliers, self.risk_scores, self.forecasts = _load_data()
        self.prices = _get_current_prices(self.forecasts)
        self.approved = _get_approved_suppliers(self.drugs)

        # Build risk lookup  {supplier_id: risk_score 0-100}
        self.risk_lookup = dict(
            zip(self.risk_scores["supplier_id"], self.risk_scores["risk_score"])
        )

        # Default demand: 1 month of average weekly orders per drug
        if demand_kg is None:
            purchases = pd.read_csv(SYNTHETIC_DIR / "purchase_history.csv")
            avg_weekly = (
                purchases.groupby("drug_id")["quantity_kg"]
                .mean()
                .reset_index()
            )
            self.demand_kg = dict(
                zip(avg_weekly["drug_id"], (avg_weekly["quantity_kg"] * 4).round())
            )
        else:
            self.demand_kg = demand_kg

        self.result_ = None

    # ── LP Solver ─────────────────────────────────────────────────────────────

    def _solve_lp(self) -> pd.DataFrame:
        """Solve the purchase allocation LP with PuLP."""
        drug_ids = list(self.demand_kg.keys())
        sup_ids = self.suppliers["id"].tolist()

        # ── Variables ─────────────────────────────────────────────────────────
        prob = pulp.LpProblem("PharmaFlowPurchaseOptimizer", pulp.LpMinimize)
        x = {
            (d, s): pulp.LpVariable(f"x_{d}_{s}", lowBound=0)
            for d in drug_ids
            for s in self.approved.get(d, [])
        }

        # ── Objective ─────────────────────────────────────────────────────────
        cost_terms = []
        for (d, s), var in x.items():
            price = self.prices.get(d, 50.0)
            risk = self.risk_lookup.get(s, 50.0) / 100.0  # normalise to [0,1]
            effective_cost = price + self.risk_penalty_weight * risk * 100
            cost_terms.append(effective_cost * var)
        prob += pulp.lpSum(cost_terms), "TotalRiskAdjustedCost"

        # ── Constraints ───────────────────────────────────────────────────────
        for d in drug_ids:
            approved_s = self.approved.get(d, [])
            valid_vars = [x[(d, s)] for s in approved_s if (d, s) in x]
            if valid_vars:
                # 1. Demand coverage
                prob += pulp.lpSum(valid_vars) >= self.demand_kg.get(d, 0), f"demand_{d}"
                # 3. Concentration limit
                for s in approved_s:
                    if (d, s) in x:
                        prob += (
                            x[(d, s)] <= self.concentration_limit * self.demand_kg.get(d, 0),
                            f"conc_{d}_{s}",
                        )

        # 2. Supplier capacity (generous: 10× avg monthly volume)
        purchases = pd.read_csv(SYNTHETIC_DIR / "purchase_history.csv")
        sup_capacity = (
            purchases.groupby("supplier_id")["quantity_kg"]
            .mean()
            .mul(10)
            .round()
            .to_dict()
        )
        for s in sup_ids:
            cap_vars = [x[(d, s)] for d in drug_ids if (d, s) in x]
            if cap_vars:
                cap = sup_capacity.get(s, 999_999)
                prob += pulp.lpSum(cap_vars) <= cap, f"capacity_{s}"

        # ── Solve ─────────────────────────────────────────────────────────────
        solver = pulp.PULP_CBC_CMD(msg=0)
        prob.solve(solver)

        status = pulp.LpStatus[prob.status]
        log.info(f"LP solver status: {status}")

        # ── Extract solution ───────────────────────────────────────────────────
        rows = []
        for (d, s), var in x.items():
            qty = var.varValue or 0.0
            if qty > 0.01:
                drug_row = self.drugs[self.drugs["id"] == d].iloc[0]
                sup_row = self.suppliers[self.suppliers["id"] == s].iloc[0]
                price = self.prices.get(d, 50.0)
                risk = self.risk_lookup.get(s, 50.0)
                rows.append(
                    {
                        "drug_id": d,
                        "drug_name": drug_row["name"],
                        "supplier_id": s,
                        "supplier_name": sup_row["name"],
                        "supplier_country": sup_row["country"],
                        "quantity_kg": round(qty, 2),
                        "price_per_kg": round(price, 2),
                        "raw_cost_usd": round(qty * price, 2),
                        "risk_score": round(risk, 1),
                        "risk_penalty_usd": round(
                            qty * self.risk_penalty_weight * (risk / 100) * 100, 2
                        ),
                        "total_effective_cost": round(
                            qty * price
                            + qty * self.risk_penalty_weight * (risk / 100) * 100,
                            2,
                        ),
                        "pct_of_demand": round(
                            qty / max(self.demand_kg.get(d, 1), 1) * 100, 1
                        ),
                        "solver": "LP",
                    }
                )
        return pd.DataFrame(rows)

    # ── Greedy fallback ───────────────────────────────────────────────────────

    def _solve_greedy(self) -> pd.DataFrame:
        """Simple greedy: sort suppliers by risk-adjusted price, fill demand."""
        rows = []
        for d, demand in self.demand_kg.items():
            drug_row = self.drugs[self.drugs["id"] == d]
            if drug_row.empty:
                continue
            drug_row = drug_row.iloc[0]
            price = self.prices.get(d, 50.0)
            approved_s = self.approved.get(d, [])
            if not approved_s:
                continue

            # Score suppliers
            sup_scores = []
            for s in approved_s:
                risk = self.risk_lookup.get(s, 50.0)
                effective = price + self.risk_penalty_weight * risk
                sup_scores.append((s, effective, risk))
            sup_scores.sort(key=lambda x: x[1])

            remaining = demand
            max_per_sup = self.concentration_limit * demand
            for s, eff_price, risk in sup_scores:
                if remaining <= 0:
                    break
                qty = min(max_per_sup, remaining)
                sup_row = self.suppliers[self.suppliers["id"] == s].iloc[0]
                rows.append(
                    {
                        "drug_id": d,
                        "drug_name": drug_row["name"],
                        "supplier_id": s,
                        "supplier_name": sup_row["name"],
                        "supplier_country": sup_row["country"],
                        "quantity_kg": round(qty, 2),
                        "price_per_kg": round(price, 2),
                        "raw_cost_usd": round(qty * price, 2),
                        "risk_score": round(risk, 1),
                        "risk_penalty_usd": round(
                            qty * self.risk_penalty_weight * (risk / 100) * 100, 2
                        ),
                        "total_effective_cost": round(qty * eff_price, 2),
                        "pct_of_demand": round(qty / max(demand, 1) * 100, 1),
                        "solver": "Greedy",
                    }
                )
                remaining -= qty
        return pd.DataFrame(rows)

    # ── Public API ─────────────────────────────────────────────────────────────

    def optimize(self) -> dict:
        """
        Run the optimizer and return a results dict.

        Returns
        -------
        dict with keys:
            allocation_df   : pd.DataFrame  — detailed line-item orders
            summary_df      : pd.DataFrame  — per-drug summary
            total_raw_cost  : float
            total_risk_penalty : float
            total_effective_cost : float
            solver          : str
        """
        if PULP_AVAILABLE:
            allocation = self._solve_lp()
        else:
            allocation = self._solve_greedy()

        if allocation.empty:
            log.warning("Optimizer returned empty allocation – check data.")
            return {"allocation_df": allocation, "error": "empty_allocation"}

        # Per-drug summary
        summary = (
            allocation.groupby(["drug_id", "drug_name"])
            .agg(
                num_suppliers=("supplier_id", "nunique"),
                total_qty_kg=("quantity_kg", "sum"),
                total_raw_cost=("raw_cost_usd", "sum"),
                total_risk_penalty=("risk_penalty_usd", "sum"),
                avg_risk_score=("risk_score", "mean"),
            )
            .reset_index()
        )
        summary["demand_kg"] = summary["drug_id"].map(self.demand_kg)
        summary["coverage_pct"] = (
            summary["total_qty_kg"] / summary["demand_kg"].clip(lower=1) * 100
        ).round(1)
        summary["total_effective_cost"] = (
            summary["total_raw_cost"] + summary["total_risk_penalty"]
        ).round(2)

        result = {
            "allocation_df": allocation,
            "summary_df": summary,
            "total_raw_cost": round(allocation["raw_cost_usd"].sum(), 2),
            "total_risk_penalty": round(allocation["risk_penalty_usd"].sum(), 2),
            "total_effective_cost": round(allocation["total_effective_cost"].sum(), 2),
            "num_drugs": allocation["drug_id"].nunique(),
            "num_suppliers_used": allocation["supplier_id"].nunique(),
            "solver": allocation["solver"].iloc[0] if not allocation.empty else "none",
        }
        self.result_ = result

        # Persist
        allocation.to_csv(RESULTS_DIR / "purchase_allocation.csv", index=False)
        summary.to_csv(RESULTS_DIR / "purchase_summary.csv", index=False)
        log.info(
            f"Optimization complete — "
            f"Total effective cost: ${result['total_effective_cost']:,.2f} | "
            f"Drugs: {result['num_drugs']} | "
            f"Suppliers used: {result['num_suppliers_used']} | "
            f"Solver: {result['solver']}"
        )
        return result


# ═════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log.info("Running PharmaFlow Purchase Optimizer…")
    opt = PurchaseOptimizer()
    result = opt.optimize()

    print("\n" + "=" * 60)
    print("PURCHASE OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"Solver Used         : {result['solver']}")
    print(f"Drugs Covered       : {result['num_drugs']}")
    print(f"Suppliers Used      : {result['num_suppliers_used']}")
    print(f"Total Raw Cost      : ${result['total_raw_cost']:>12,.2f}")
    print(f"Total Risk Penalty  : ${result['total_risk_penalty']:>12,.2f}")
    print(f"Total Effective Cost: ${result['total_effective_cost']:>12,.2f}")
    print()
    print("TOP 10 LINE ITEMS:")
    alloc = result["allocation_df"]
    print(
        alloc.nlargest(10, "quantity_kg")[
            [
                "drug_name",
                "supplier_name",
                "supplier_country",
                "quantity_kg",
                "price_per_kg",
                "risk_score",
                "raw_cost_usd",
            ]
        ].to_string(index=False)
    )
    print("\nPer-drug summary saved to data/processed/purchase_summary.csv")
