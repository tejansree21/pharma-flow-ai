"""
PharmaFlow AI - Price Forecasting Model
========================================
Predicts drug prices from each supplier 4-12 weeks ahead using
Facebook Prophet with external regressors (commodity index, exchange rates).

Usage:
    python src/models/price_forecast.py

Outputs:
    - Trained model files in models/price_forecast/
    - Forecast CSV in data/processed/
    - Evaluation metrics printed to console
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import joblib
from datetime import timedelta

warnings.filterwarnings("ignore")

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "synthetic")
MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "price_forecast")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "processed")


def load_data():
    """Load purchase history and commodity index data."""
    purchases = pd.read_csv(os.path.join(DATA_DIR, "purchase_history.csv"))
    purchases["order_date"] = pd.to_datetime(purchases["order_date"])

    commodity = pd.read_csv(os.path.join(DATA_DIR, "commodity_index.csv"))
    commodity["date"] = pd.to_datetime(commodity["date"])

    return purchases, commodity


def prepare_price_series(purchases, commodity, drug_id, supplier_id=None):
    """
    Prepare a weekly price time series for a drug (optionally from a specific supplier).
    Merges with commodity index as external regressors.
    """
    mask = purchases["drug_id"] == drug_id
    if supplier_id:
        mask &= purchases["supplier_id"] == supplier_id

    drug_data = purchases[mask].copy()
    if len(drug_data) < 20:
        return None

    # Aggregate to weekly average price
    drug_data["week"] = drug_data["order_date"].dt.to_period("W").dt.start_time
    weekly = drug_data.groupby("week").agg(
        price=("price_per_kg", "mean"),
        volume=("quantity_kg", "sum"),
        num_orders=("order_id", "count"),
    ).reset_index()

    # Merge commodity index (align to nearest week)
    commodity_weekly = commodity.copy()
    commodity_weekly["week"] = commodity_weekly["date"].dt.to_period("W").dt.start_time
    commodity_weekly = commodity_weekly.groupby("week").first().reset_index()

    merged = pd.merge(weekly, commodity_weekly[["week", "commodity_index", "usd_inr_rate"]],
                       on="week", how="left")

    # Forward-fill missing commodity data
    merged["commodity_index"] = merged["commodity_index"].ffill().bfill()
    merged["usd_inr_rate"] = merged["usd_inr_rate"].ffill().bfill()

    return merged


def train_prophet_model(series, forecast_weeks=12):
    """
    Train a Prophet model on the price series with commodity index as regressor.
    Returns the model, forecast, and evaluation metrics.
    """
    try:
        from prophet import Prophet
    except ImportError:
        print("⚠️  Prophet not installed. Using fallback ARIMA-like approach.")
        return train_fallback_model(series, forecast_weeks)

    # Prophet requires 'ds' and 'y' columns
    df = series.rename(columns={"week": "ds", "price": "y"})

    # Train/test split: hold out last `forecast_weeks` weeks
    cutoff = df["ds"].max() - timedelta(weeks=forecast_weeks)
    train = df[df["ds"] <= cutoff].copy()
    test = df[df["ds"] > cutoff].copy()

    if len(train) < 15:
        return train_fallback_model(series, forecast_weeks)

    # Build model
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10,
    )

    # Add external regressors
    if "commodity_index" in df.columns:
        model.add_regressor("commodity_index")
    if "usd_inr_rate" in df.columns:
        model.add_regressor("usd_inr_rate")

    model.fit(train)

    # Create future dataframe
    future = model.make_future_dataframe(periods=forecast_weeks, freq="W")

    # Add regressors to future
    for col in ["commodity_index", "usd_inr_rate"]:
        if col in df.columns:
            last_val = df[col].iloc[-1]
            col_vals = pd.merge(future, df[["ds", col]], on="ds", how="left")[col]
            col_vals = col_vals.ffill().fillna(last_val)
            future[col] = col_vals.values

    forecast = model.predict(future)

    # Evaluate on test set using nearest-date matching
    # (Prophet's weekly dates may not exactly align with pandas Period dates)
    mape, rmse = None, None
    if len(test) > 0:
        test_sorted = test[["ds", "y"]].sort_values("ds").reset_index(drop=True)
        forecast_sorted = forecast[["ds", "yhat"]].sort_values("ds").reset_index(drop=True)

        # Use merge_asof to match nearest dates within 3-day tolerance
        merged_eval = pd.merge_asof(
            test_sorted, forecast_sorted,
            on="ds", tolerance=pd.Timedelta("3D"), direction="nearest"
        ).dropna(subset=["yhat"])

        if len(merged_eval) > 0:
            mape = np.mean(np.abs((merged_eval["y"] - merged_eval["yhat"]) / merged_eval["y"])) * 100
            rmse = np.sqrt(np.mean((merged_eval["y"] - merged_eval["yhat"]) ** 2))

    return {
        "model": model,
        "forecast": forecast,
        "mape": mape,
        "rmse": rmse,
        "train_size": len(train),
        "test_size": len(test),
    }


def train_fallback_model(series, forecast_weeks=12):
    """
    Fallback model using simple exponential smoothing when Prophet isn't available.
    """
    from sklearn.linear_model import Ridge

    df = series.copy()
    df["week_num"] = np.arange(len(df))
    df["month"] = df["week"].dt.month
    df["quarter"] = df["week"].dt.quarter

    # Features
    feature_cols = ["week_num", "month", "quarter"]
    for col in ["commodity_index", "usd_inr_rate"]:
        if col in df.columns:
            feature_cols.append(col)

    # Train/test split
    split = max(10, len(df) - forecast_weeks)
    train = df.iloc[:split]
    test = df.iloc[split:]

    X_train = train[feature_cols].values
    y_train = train["price"].values
    X_test = test[feature_cols].values if len(test) > 0 else None
    y_test = test["price"].values if len(test) > 0 else None

    model = Ridge(alpha=1.0)
    model.fit(X_train, y_train)

    # Forecast
    mape, rmse = None, None
    if X_test is not None and len(X_test) > 0:
        y_pred = model.predict(X_test)
        mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
        rmse = np.sqrt(np.mean((y_test - y_pred) ** 2))

    # Generate future forecast
    last_week_num = df["week_num"].max()
    future_weeks = []
    for i in range(1, forecast_weeks + 1):
        future_date = df["week"].max() + timedelta(weeks=i)
        row = {
            "week_num": last_week_num + i,
            "month": future_date.month,
            "quarter": (future_date.month - 1) // 3 + 1,
        }
        for col in ["commodity_index", "usd_inr_rate"]:
            if col in df.columns:
                row[col] = df[col].iloc[-1]
        future_weeks.append(row)

    future_df = pd.DataFrame(future_weeks)
    future_pred = model.predict(future_df[feature_cols].values)

    forecast = pd.DataFrame({
        "ds": [df["week"].max() + timedelta(weeks=i) for i in range(1, forecast_weeks + 1)],
        "yhat": future_pred,
        "yhat_lower": future_pred * 0.93,
        "yhat_upper": future_pred * 1.07,
    })

    return {
        "model": model,
        "forecast": forecast,
        "mape": mape,
        "rmse": rmse,
        "train_size": len(train),
        "test_size": len(test),
    }


def run_price_forecasting():
    """Run price forecasting for all major drugs."""
    print("=" * 60)
    print("PharmaFlow AI — Price Forecasting Model")
    print("=" * 60)

    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    purchases, commodity = load_data()

    # Get unique drugs
    drugs = purchases["drug_id"].unique()
    results = []
    all_forecasts = []

    for drug_id in sorted(drugs):
        drug_name = purchases[purchases["drug_id"] == drug_id]["drug_name"].iloc[0]

        # Aggregate across all suppliers for this drug
        series = prepare_price_series(purchases, commodity, drug_id)
        if series is None or len(series) < 15:
            print(f"  ⏭️  {drug_name}: insufficient data ({0 if series is None else len(series)} weeks)")
            continue

        result = train_prophet_model(series, forecast_weeks=12)

        mape_str = f"{result['mape']:.1f}%" if result['mape'] is not None else "N/A"
        status = "✅" if result['mape'] is not None and result['mape'] < 15 else "⚠️"
        print(f"  {status} {drug_name}: MAPE={mape_str}, "
              f"Train={result['train_size']}, Test={result['test_size']}")

        # Save model
        model_path = os.path.join(MODEL_DIR, f"{drug_id}_model.pkl")
        joblib.dump(result["model"], model_path)

        # Collect forecast
        forecast = result["forecast"].copy()
        forecast["drug_id"] = drug_id
        forecast["drug_name"] = drug_name
        all_forecasts.append(forecast)

        results.append({
            "drug_id": drug_id,
            "drug_name": drug_name,
            "mape": result["mape"],
            "rmse": result["rmse"],
            "train_weeks": result["train_size"],
            "test_weeks": result["test_size"],
        })

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(OUTPUT_DIR, "price_forecast_metrics.csv"), index=False)

    if all_forecasts:
        forecasts_df = pd.concat(all_forecasts, ignore_index=True)
        # Keep only essential columns
        keep_cols = [c for c in ["ds", "yhat", "yhat_lower", "yhat_upper", "drug_id", "drug_name"]
                     if c in forecasts_df.columns]
        forecasts_df[keep_cols].to_csv(
            os.path.join(OUTPUT_DIR, "price_forecasts.csv"), index=False
        )

    print()
    print("-" * 60)
    avg_mape = results_df["mape"].dropna().mean()
    print(f"Average MAPE: {avg_mape:.1f}%")
    print(f"Models saved: {MODEL_DIR}")
    print(f"Forecasts saved: {OUTPUT_DIR}")
    print("=" * 60)

    return results_df


if __name__ == "__main__":
    run_price_forecasting()
