"""
PharmaFlow AI - Train All Phase 1 Models
==========================================
Runs the complete Phase 1 pipeline:
1. Generate synthetic data
2. Train price forecasting model
3. Train quality anomaly detection model
4. Train supplier risk scoring model

Usage:
    python src/models/train_all.py
"""

import sys
import os
import io
import time

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)


def main():
    start = time.time()

    print()
    print("+" + "=" * 58 + "+")
    print("|" + " PharmaFlow AI - Phase 1 Full Pipeline ".center(58) + "|")
    print("+" + "=" * 58 + "+")
    print()

    # Step 1: Generate data
    print(">> STEP 1/4: Generating Synthetic Data...")
    print()
    from src.data_generation.generate_all import generate_all
    generate_all()

    # Step 2: Price forecasting
    print()
    print(">> STEP 2/4: Training Price Forecasting Model...")
    print()
    from src.models.price_forecast import run_price_forecasting
    run_price_forecasting()

    # Step 3: Quality anomaly detection
    print()
    print(">> STEP 3/4: Training Quality Anomaly Detection...")
    print()
    from src.models.quality_anomaly import run_quality_anomaly_detection
    run_quality_anomaly_detection()

    # Step 4: Supplier risk scoring
    print()
    print(">> STEP 4/4: Training Supplier Risk Scoring Model...")
    print()
    from src.models.supplier_risk import run_supplier_risk_scoring
    run_supplier_risk_scoring()

    # Summary
    elapsed = time.time() - start
    print()
    print("+" + "=" * 58 + "+")
    print("|" + " PHASE 1 COMPLETE ".center(58) + "|")
    print("+" + "=" * 58 + "+")
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  Data:    data/synthetic/")
    print(f"  Models:  models/")
    print(f"  Results: data/processed/")
    print("+" + "=" * 58 + "+")


if __name__ == "__main__":
    main()
