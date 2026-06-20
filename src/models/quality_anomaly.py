"""
PharmaFlow AI - Quality Anomaly Detection Model
=================================================
Detects quality degradation in supplier batches using:
1. Statistical Process Control (SPC) - baseline ± 2σ monitoring
2. Isolation Forest - unsupervised anomaly detection
3. Trend detection - identifies suppliers with declining quality over time

Usage:
    python src/models/quality_anomaly.py

Outputs:
    - Anomaly detection results in data/processed/
    - Trained model in models/quality_anomaly/
    - Supplier quality alerts
"""

import os
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from scipy import stats

warnings.filterwarnings("ignore")

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "synthetic")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "quality_anomaly")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "processed")


def load_data():
    """Load quality test results."""
    quality = pd.read_csv(os.path.join(DATA_DIR, "quality_results.csv"))
    quality["test_date"] = pd.to_datetime(quality["test_date"])
    return quality


def compute_spc_baselines(quality_df):
    """
    Compute Statistical Process Control baselines for each supplier.
    Uses the first 6 months of data as the baseline period.
    
    Returns a dict: {supplier_id: {metric: (mean, std, ucl, lcl)}}
    """
    baseline_end = quality_df["test_date"].min() + pd.Timedelta(days=180)
    baselines = {}

    metrics = ["purity_pct", "contamination_ppm", "dissolution_min", "moisture_pct"]

    for supplier_id in quality_df["supplier_id"].unique():
        sup_data = quality_df[
            (quality_df["supplier_id"] == supplier_id) &
            (quality_df["test_date"] <= baseline_end)
        ]

        if len(sup_data) < 5:
            continue

        baselines[supplier_id] = {}
        for metric in metrics:
            vals = sup_data[metric].values
            mean = np.mean(vals)
            std = max(np.std(vals), 0.01)  # prevent zero std
            ucl = mean + 2 * std  # upper control limit
            lcl = mean - 2 * std  # lower control limit
            baselines[supplier_id][metric] = {
                "mean": mean, "std": std, "ucl": ucl, "lcl": lcl
            }

    return baselines


def detect_spc_violations(quality_df, baselines):
    """
    Flag batches that violate SPC control limits.
    A violation means a metric is outside mean ± 2σ of baseline.
    """
    metrics = ["purity_pct", "contamination_ppm", "dissolution_min", "moisture_pct"]

    violations = []
    for _, row in quality_df.iterrows():
        sup_id = row["supplier_id"]
        if sup_id not in baselines:
            continue

        batch_violations = []
        for metric in metrics:
            baseline = baselines[sup_id][metric]
            val = row[metric]

            # For purity: below LCL is bad
            # For contamination, dissolution, moisture: above UCL is bad
            if metric == "purity_pct":
                if val < baseline["lcl"]:
                    batch_violations.append(f"{metric}_low")
            else:
                if val > baseline["ucl"]:
                    batch_violations.append(f"{metric}_high")

        violations.append({
            "batch_id": row["batch_id"],
            "supplier_id": sup_id,
            "test_date": row["test_date"],
            "num_violations": len(batch_violations),
            "violated_metrics": "|".join(batch_violations) if batch_violations else "",
            "is_spc_anomaly": len(batch_violations) > 0,
        })

    return pd.DataFrame(violations)


def train_isolation_forest(quality_df):
    """
    Train Isolation Forest on quality metrics for unsupervised anomaly detection.
    Returns the model and anomaly scores for each batch.
    """
    features = ["purity_pct", "contamination_ppm", "dissolution_min", "moisture_pct"]
    X = quality_df[features].values

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train Isolation Forest
    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.08,  # expect ~8% anomalies
        random_state=42,
        max_samples="auto",
    )
    iso_forest.fit(X_scaled)

    # Get scores (-1 = anomaly, 1 = normal)
    predictions = iso_forest.predict(X_scaled)
    scores = iso_forest.decision_function(X_scaled)

    return iso_forest, scaler, predictions, scores


def detect_quality_trends(quality_df):
    """
    Detect suppliers with statistically significant declining quality trends.
    Uses Spearman correlation between time and quality metrics.
    """
    metrics = ["purity_pct", "contamination_ppm", "dissolution_min", "moisture_pct"]
    # For purity: negative trend is bad
    # For contamination/dissolution/moisture: positive trend is bad
    bad_direction = {
        "purity_pct": "negative",
        "contamination_ppm": "positive",
        "dissolution_min": "positive",
        "moisture_pct": "positive",
    }

    trend_results = []
    for supplier_id in quality_df["supplier_id"].unique():
        sup_data = quality_df[quality_df["supplier_id"] == supplier_id].sort_values("test_date")
        if len(sup_data) < 10:
            continue

        supplier_name = sup_data["supplier_name"].iloc[0]
        time_ordinal = (sup_data["test_date"] - sup_data["test_date"].min()).dt.days.values

        for metric in metrics:
            values = sup_data[metric].values
            # Spearman correlation (robust to outliers)
            corr, p_value = stats.spearmanr(time_ordinal, values)

            # Check if trend is in the "bad" direction
            is_bad_trend = False
            if p_value < 0.05:  # statistically significant
                if bad_direction[metric] == "negative" and corr < -0.3:
                    is_bad_trend = True
                elif bad_direction[metric] == "positive" and corr > 0.3:
                    is_bad_trend = True

            trend_results.append({
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "metric": metric,
                "correlation": round(corr, 3),
                "p_value": round(p_value, 4),
                "significant": p_value < 0.05,
                "bad_trend": is_bad_trend,
                "direction": "declining" if corr < 0 else "increasing",
                "num_batches": len(sup_data),
            })

    return pd.DataFrame(trend_results)


def run_quality_anomaly_detection():
    """Run the full quality anomaly detection pipeline."""
    print("=" * 60)
    print("PharmaFlow AI — Quality Anomaly Detection")
    print("=" * 60)

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    quality = load_data()
    print(f"\nLoaded {len(quality)} quality test records")
    print(f"Suppliers: {quality['supplier_id'].nunique()}")
    print(f"Date range: {quality['test_date'].min()} to {quality['test_date'].max()}")

    # === 1. SPC Analysis ===
    print("\n--- Statistical Process Control ---")
    baselines = compute_spc_baselines(quality)
    spc_results = detect_spc_violations(quality, baselines)
    num_spc_anomalies = spc_results["is_spc_anomaly"].sum()
    print(f"SPC violations: {num_spc_anomalies} / {len(spc_results)} batches "
          f"({num_spc_anomalies / len(spc_results) * 100:.1f}%)")

    # === 2. Isolation Forest ===
    print("\n--- Isolation Forest ---")
    iso_model, scaler, predictions, scores = train_isolation_forest(quality)
    num_iso_anomalies = (predictions == -1).sum()
    print(f"Isolation Forest anomalies: {num_iso_anomalies} / {len(quality)} batches "
          f"({num_iso_anomalies / len(quality) * 100:.1f}%)")

    # Save model
    joblib.dump({"model": iso_model, "scaler": scaler}, os.path.join(MODEL_DIR, "isolation_forest.pkl"))

    # === 3. Trend Detection ===
    print("\n--- Quality Trend Detection ---")
    trends = detect_quality_trends(quality)
    bad_trends = trends[trends["bad_trend"]]

    if len(bad_trends) > 0:
        print(f"\n⚠️  SUPPLIERS WITH DECLINING QUALITY:")
        for _, row in bad_trends.iterrows():
            print(f"  🔴 {row['supplier_name']}: {row['metric']} "
                  f"({row['direction']}, r={row['correlation']}, p={row['p_value']})")
    else:
        print("  ✅ No significant quality declines detected")

    # === 4. Combine Results ===
    quality["iso_prediction"] = predictions
    quality["iso_score"] = scores
    quality["is_iso_anomaly"] = predictions == -1

    # Merge SPC results
    merged = pd.merge(quality, spc_results[["batch_id", "is_spc_anomaly", "num_violations", "violated_metrics"]],
                       on="batch_id", how="left")

    # Combined anomaly flag: either SPC or Isolation Forest flags it
    merged["is_anomaly"] = merged["is_spc_anomaly"] | merged["is_iso_anomaly"]
    total_anomalies = merged["is_anomaly"].sum()

    # Save outputs
    merged.to_csv(os.path.join(OUTPUT_DIR, "quality_anomaly_results.csv"), index=False)
    trends.to_csv(os.path.join(OUTPUT_DIR, "quality_trends.csv"), index=False)

    # Save baselines
    joblib.dump(baselines, os.path.join(MODEL_DIR, "spc_baselines.pkl"))

    # === Evaluation ===
    print("\n--- Evaluation ---")
    # Check if we correctly flagged the "declining" suppliers
    declining_suppliers = quality[quality["quality_trend"] == "declining"]["supplier_id"].unique()
    flagged_by_trends = bad_trends["supplier_id"].unique()

    true_positives = len(set(declining_suppliers) & set(flagged_by_trends))
    recall = true_positives / len(declining_suppliers) * 100 if len(declining_suppliers) > 0 else 0

    print(f"Known declining suppliers: {list(declining_suppliers)}")
    print(f"Detected by trend analysis: {list(flagged_by_trends)}")
    print(f"Recall on declining suppliers: {recall:.0f}%")

    print()
    print("-" * 60)
    print(f"Total anomalous batches: {total_anomalies} / {len(merged)} "
          f"({total_anomalies / len(merged) * 100:.1f}%)")
    print(f"Models saved: {MODEL_DIR}")
    print(f"Results saved: {OUTPUT_DIR}")
    print("=" * 60)

    return merged, trends


if __name__ == "__main__":
    run_quality_anomaly_detection()
