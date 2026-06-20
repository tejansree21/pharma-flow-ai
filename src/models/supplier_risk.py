"""
PharmaFlow AI - Supplier Risk Scoring Model
=============================================
Generates composite risk scores for each supplier by combining:
1. Delivery reliability (on-time %)
2. Quality consistency (anomaly rate, trend)
3. Geographic risk (geopolitical, natural disaster)
4. Regulatory status (FDA approval, warnings)
5. Incident history (severity-weighted)
6. Financial proxies (capacity utilization, years active)

Uses XGBoost to learn the relationship between features and risk,
trained on engineered risk labels.

Usage:
    python src/models/supplier_risk.py

Outputs:
    - Supplier risk scores in data/processed/
    - Trained model in models/supplier_risk/
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "synthetic")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "supplier_risk")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "processed")


def load_all_data():
    """Load all datasets needed for risk scoring."""
    suppliers = pd.read_csv(os.path.join(DATA_DIR, "suppliers.csv"))
    purchases = pd.read_csv(os.path.join(DATA_DIR, "purchase_history.csv"))
    purchases["order_date"] = pd.to_datetime(purchases["order_date"])
    quality = pd.read_csv(os.path.join(DATA_DIR, "quality_results.csv"))
    quality["test_date"] = pd.to_datetime(quality["test_date"])
    incidents = pd.read_csv(os.path.join(DATA_DIR, "incidents.csv"))
    incidents["date"] = pd.to_datetime(incidents["date"])

    return suppliers, purchases, quality, incidents


def engineer_risk_features(suppliers, purchases, quality, incidents):
    """
    Engineer risk features for each supplier from all data sources.
    Returns a DataFrame with one row per supplier and computed risk features.
    """
    features = []

    for _, sup in suppliers.iterrows():
        sid = sup["id"]

        # --- Delivery Features ---
        sup_orders = purchases[purchases["supplier_id"] == sid]
        if len(sup_orders) > 0:
            on_time_rate = sup_orders["on_time"].mean()
            avg_lead_time = sup_orders["lead_time_days"].mean()
            lead_time_std = sup_orders["lead_time_days"].std()
            total_orders = len(sup_orders)
            total_volume = sup_orders["quantity_kg"].sum()
            avg_order_value = sup_orders["total_cost_usd"].mean()
        else:
            on_time_rate = 0.5
            avg_lead_time = sup["avg_lead_time_days"]
            lead_time_std = 10
            total_orders = 0
            total_volume = 0
            avg_order_value = 0

        # --- Quality Features ---
        sup_quality = quality[quality["supplier_id"] == sid]
        if len(sup_quality) > 0:
            avg_purity = sup_quality["purity_pct"].mean()
            purity_std = sup_quality["purity_pct"].std()
            avg_contamination = sup_quality["contamination_ppm"].mean()
            pass_rate = sup_quality["overall_pass"].mean()
            sterility_fail_rate = 1 - sup_quality["sterility_pass"].mean()
            num_batches = len(sup_quality)

            # Quality trend: slope of purity over time
            if len(sup_quality) >= 5:
                time_days = (sup_quality["test_date"] - sup_quality["test_date"].min()).dt.days.values
                purity_vals = sup_quality["purity_pct"].values
                if np.std(time_days) > 0:
                    slope = np.polyfit(time_days, purity_vals, 1)[0]
                    quality_trend_slope = slope * 365  # annualized
                else:
                    quality_trend_slope = 0
            else:
                quality_trend_slope = 0
        else:
            avg_purity = 90
            purity_std = 2
            avg_contamination = 3
            pass_rate = 0.8
            sterility_fail_rate = 0.05
            num_batches = 0
            quality_trend_slope = 0

        # --- Incident Features ---
        sup_incidents = incidents[incidents["supplier_id"] == sid]
        total_incidents = len(sup_incidents)
        severe_incidents = len(sup_incidents[sup_incidents["severity"] == "severe"])
        moderate_incidents = len(sup_incidents[sup_incidents["severity"] == "moderate"])
        fda_warnings = len(sup_incidents[sup_incidents["incident_type"] == "fda_warning_letter"])
        fda_inspections_failed = len(sup_incidents[sup_incidents["incident_type"] == "fda_inspection_failure"])
        avg_resolution_days = sup_incidents["resolution_days"].mean() if len(sup_incidents) > 0 else 0
        unresolved = len(sup_incidents[~sup_incidents["resolved"]]) if len(sup_incidents) > 0 else 0

        # Severity-weighted incident score
        incident_score = (severe_incidents * 3 + moderate_incidents * 2 +
                          (total_incidents - severe_incidents - moderate_incidents) * 1)

        # --- Geographic & Regulatory Features ---
        geo_risk = sup["geo_risk_score"]
        fda_approved = 1 if sup["fda_approved"] else 0
        years_active = sup["years_active"]
        capacity = sup["capacity_tons_year"]

        features.append({
            "supplier_id": sid,
            "supplier_name": sup["name"],
            "country": sup["country"],
            "region": sup["region"],
            # Delivery
            "on_time_rate": round(on_time_rate, 3),
            "avg_lead_time_days": round(avg_lead_time, 1),
            "lead_time_variability": round(lead_time_std if not np.isnan(lead_time_std) else 0, 1),
            "total_orders": total_orders,
            "total_volume_kg": total_volume,
            # Quality
            "avg_purity": round(avg_purity, 2),
            "purity_std": round(purity_std if not np.isnan(purity_std) else 0, 2),
            "avg_contamination_ppm": round(avg_contamination, 2),
            "batch_pass_rate": round(pass_rate, 3),
            "sterility_fail_rate": round(sterility_fail_rate, 3),
            "quality_trend_slope": round(quality_trend_slope, 4),
            "num_batches": num_batches,
            # Incidents
            "total_incidents": total_incidents,
            "severe_incidents": severe_incidents,
            "fda_warnings": fda_warnings,
            "fda_inspections_failed": fda_inspections_failed,
            "incident_score": incident_score,
            "avg_resolution_days": round(avg_resolution_days, 1),
            "unresolved_incidents": unresolved,
            # Geographic & regulatory
            "geo_risk_score": geo_risk,
            "fda_approved": fda_approved,
            "years_active": years_active,
            "capacity_tons_year": capacity,
        })

    return pd.DataFrame(features)


def compute_composite_risk_score(features_df):
    """
    Compute a composite risk score (0-100) for each supplier using
    weighted combination of normalized risk factors.
    
    Higher score = higher risk = worse supplier.
    """
    df = features_df.copy()

    # Normalize each factor to 0-1 (handling edge cases)
    def normalize(series, higher_is_riskier=True):
        s = series.fillna(0)
        if s.max() == s.min():
            return pd.Series(0.5, index=s.index)
        normed = (s - s.min()) / (s.max() - s.min())
        return normed if higher_is_riskier else (1 - normed)

    # Delivery risk (lower on_time = higher risk)
    delivery_risk = normalize(df["on_time_rate"], higher_is_riskier=False) * 0.5 + \
                    normalize(df["lead_time_variability"], higher_is_riskier=True) * 0.5

    # Quality risk (lower purity, higher contamination = higher risk)
    quality_risk = normalize(df["avg_purity"], higher_is_riskier=False) * 0.3 + \
                   normalize(df["avg_contamination_ppm"], higher_is_riskier=True) * 0.2 + \
                   normalize(df["batch_pass_rate"], higher_is_riskier=False) * 0.2 + \
                   normalize(df["quality_trend_slope"], higher_is_riskier=False) * 0.3  # negative slope = declining

    # Incident risk
    incident_risk = normalize(df["incident_score"], higher_is_riskier=True) * 0.4 + \
                    normalize(df["severe_incidents"], higher_is_riskier=True) * 0.3 + \
                    normalize(df["fda_warnings"], higher_is_riskier=True) * 0.3

    # Geographic & regulatory risk
    geo_reg_risk = normalize(df["geo_risk_score"], higher_is_riskier=True) * 0.4 + \
                   normalize(df["fda_approved"], higher_is_riskier=False) * 0.3 + \
                   normalize(df["years_active"], higher_is_riskier=False) * 0.3

    # Weighted composite
    weights = {
        "delivery": 0.20,
        "quality": 0.30,
        "incidents": 0.25,
        "geo_regulatory": 0.25,
    }

    composite = (delivery_risk * weights["delivery"] +
                 quality_risk * weights["quality"] +
                 incident_risk * weights["incidents"] +
                 geo_reg_risk * weights["geo_regulatory"])

    df["risk_score"] = (composite * 100).round(1)

    # Assign risk tier
    df["risk_tier"] = pd.cut(df["risk_score"],
                              bins=[0, 25, 45, 65, 100],
                              labels=["Low", "Moderate", "High", "Critical"])

    # Component scores for transparency
    df["delivery_risk"] = (delivery_risk * 100).round(1)
    df["quality_risk"] = (quality_risk * 100).round(1)
    df["incident_risk"] = (incident_risk * 100).round(1)
    df["geo_regulatory_risk"] = (geo_reg_risk * 100).round(1)

    return df


def train_xgboost_risk_model(features_df):
    """
    Train XGBoost to predict the composite risk score from raw features.
    This allows the model to learn non-linear relationships and be used
    for scoring new suppliers without recalculating the composite.
    """
    try:
        from xgboost import XGBRegressor
    except ImportError:
        print("⚠️  XGBoost not installed. Using GradientBoosting fallback.")
        from sklearn.ensemble import GradientBoostingRegressor as XGBRegressor

    feature_cols = [
        "on_time_rate", "avg_lead_time_days", "lead_time_variability",
        "avg_purity", "purity_std", "avg_contamination_ppm",
        "batch_pass_rate", "sterility_fail_rate", "quality_trend_slope",
        "total_incidents", "severe_incidents", "incident_score",
        "fda_warnings", "avg_resolution_days",
        "geo_risk_score", "fda_approved", "years_active", "capacity_tons_year",
    ]

    X = features_df[feature_cols].fillna(0).values
    y = features_df["risk_score"].values

    # Train model
    try:
        model = XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
            verbosity=0,
        )
    except TypeError:
        # GradientBoosting fallback doesn't have 'verbosity'
        model = XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )

    model.fit(X, y)

    # Cross-validation
    cv_scores = cross_val_score(model, X, y, cv=min(5, len(X)), scoring="r2")

    return model, feature_cols, cv_scores


def run_supplier_risk_scoring():
    """Run the full supplier risk scoring pipeline."""
    print("=" * 60)
    print("PharmaFlow AI — Supplier Risk Scoring")
    print("=" * 60)

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data
    suppliers, purchases, quality, incidents = load_all_data()
    print(f"\nSuppliers: {len(suppliers)}")
    print(f"Orders: {len(purchases)}")
    print(f"Quality records: {len(quality)}")
    print(f"Incidents: {len(incidents)}")

    # Engineer features
    print("\n--- Engineering Risk Features ---")
    features = engineer_risk_features(suppliers, purchases, quality, incidents)
    print(f"Computed {len(features.columns)} features for {len(features)} suppliers")

    # Compute composite scores
    print("\n--- Computing Composite Risk Scores ---")
    scored = compute_composite_risk_score(features)

    # Train XGBoost
    print("\n--- Training XGBoost Model ---")
    model, feature_cols, cv_scores = train_xgboost_risk_model(scored)
    print(f"Cross-validation R²: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    # Save model
    joblib.dump({
        "model": model,
        "feature_cols": feature_cols,
    }, os.path.join(MODEL_DIR, "xgb_risk_model.pkl"))

    # Display results
    print("\n--- Supplier Risk Rankings ---")
    display_cols = ["supplier_name", "country", "risk_score", "risk_tier",
                    "delivery_risk", "quality_risk", "incident_risk", "geo_regulatory_risk"]
    ranked = scored[display_cols].sort_values("risk_score", ascending=False)

    print(f"\n{'Supplier':<30} {'Country':<15} {'Risk':>6} {'Tier':<10} "
          f"{'Deliv':>6} {'Qual':>6} {'Incid':>6} {'Geo':>6}")
    print("-" * 100)
    for _, row in ranked.iterrows():
        tier_icon = {"Low": "🟢", "Moderate": "🟡", "High": "🟠", "Critical": "🔴"}.get(row["risk_tier"], "⚪")
        print(f"{row['supplier_name']:<30} {row['country']:<15} {row['risk_score']:>5.1f} "
              f"{tier_icon} {row['risk_tier']:<8} "
              f"{row['delivery_risk']:>5.1f} {row['quality_risk']:>5.1f} "
              f"{row['incident_risk']:>5.1f} {row['geo_regulatory_risk']:>5.1f}")

    # Save results
    scored.to_csv(os.path.join(OUTPUT_DIR, "supplier_risk_scores.csv"), index=False)
    features.to_csv(os.path.join(OUTPUT_DIR, "supplier_risk_features.csv"), index=False)

    print()
    print("-" * 60)
    tier_counts = scored["risk_tier"].value_counts()
    for tier in ["Low", "Moderate", "High", "Critical"]:
        count = tier_counts.get(tier, 0)
        print(f"  {tier}: {count} suppliers")
    print(f"\nModels saved: {MODEL_DIR}")
    print(f"Results saved: {OUTPUT_DIR}")
    print("=" * 60)

    return scored


if __name__ == "__main__":
    run_supplier_risk_scoring()
