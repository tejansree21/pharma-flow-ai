"""
PharmaFlow AI - Comprehensive Synthetic Data Generator
======================================================
Generates realistic pharmaceutical supply chain data including:
- Suppliers with geographic and capability attributes
- Drugs/APIs with therapeutic categories
- 3 years of purchase history with realistic price patterns
- Quality test results with injected anomalies
- Supplier incidents (delays, warnings, inspections)

All data is designed to have discoverable patterns for ML models.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
import json

# Reproducibility
np.random.seed(42)

# ============================================================
# OUTPUT DIRECTORY
# ============================================================
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "synthetic")


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")


# ============================================================
# 1. SUPPLIER DATA
# ============================================================
def generate_suppliers():
    """
    Generate 25 pharmaceutical suppliers with realistic attributes.
    Key patterns baked in:
    - Suppliers in India/China are cheaper but have higher risk
    - US/EU suppliers are expensive but reliable
    - Some suppliers have declining quality (for anomaly detection)
    - Geographic clustering creates concentration risk
    """
    suppliers = [
        # Indian suppliers (cheap, moderate risk)
        {"id": "SUP001", "name": "Aurobindo API Ltd", "country": "India", "city": "Hyderabad",
         "region": "Asia", "base_reliability": 0.82, "base_quality": 0.88, "price_tier": "low",
         "capacity_tons_year": 5000, "fda_approved": True, "years_active": 15,
         "specialization": "generics", "quality_trend": "stable"},
        {"id": "SUP002", "name": "Cipla Chemical Works", "country": "India", "city": "Mumbai",
         "region": "Asia", "base_reliability": 0.85, "base_quality": 0.90, "price_tier": "low",
         "capacity_tons_year": 8000, "fda_approved": True, "years_active": 22,
         "specialization": "generics", "quality_trend": "stable"},
        {"id": "SUP003", "name": "Dr Reddy's API Division", "country": "India", "city": "Hyderabad",
         "region": "Asia", "base_reliability": 0.88, "base_quality": 0.91, "price_tier": "low",
         "capacity_tons_year": 6000, "fda_approved": True, "years_active": 18,
         "specialization": "generics", "quality_trend": "stable"},
        {"id": "SUP004", "name": "Laurus Labs Synthesis", "country": "India", "city": "Visakhapatnam",
         "region": "Asia", "base_reliability": 0.78, "base_quality": 0.85, "price_tier": "low",
         "capacity_tons_year": 3000, "fda_approved": True, "years_active": 10,
         "specialization": "generics", "quality_trend": "declining"},  # <-- anomaly target
        {"id": "SUP005", "name": "Divi's Laboratories API", "country": "India", "city": "Hyderabad",
         "region": "Asia", "base_reliability": 0.90, "base_quality": 0.93, "price_tier": "medium",
         "capacity_tons_year": 7000, "fda_approved": True, "years_active": 25,
         "specialization": "custom_synthesis", "quality_trend": "stable"},

        # Chinese suppliers (cheapest, higher risk)
        {"id": "SUP006", "name": "Zhejiang Pharma Chemical", "country": "China", "city": "Taizhou",
         "region": "Asia", "base_reliability": 0.75, "base_quality": 0.83, "price_tier": "lowest",
         "capacity_tons_year": 12000, "fda_approved": True, "years_active": 12,
         "specialization": "bulk_api", "quality_trend": "stable"},
        {"id": "SUP007", "name": "Huahai Pharmaceutical API", "country": "China", "city": "Linhai",
         "region": "Asia", "base_reliability": 0.72, "base_quality": 0.80, "price_tier": "lowest",
         "capacity_tons_year": 15000, "fda_approved": False, "years_active": 8,
         "specialization": "bulk_api", "quality_trend": "declining"},  # <-- anomaly target
        {"id": "SUP008", "name": "CSPC Pharma Intermediates", "country": "China", "city": "Shijiazhuang",
         "region": "Asia", "base_reliability": 0.77, "base_quality": 0.84, "price_tier": "lowest",
         "capacity_tons_year": 10000, "fda_approved": True, "years_active": 14,
         "specialization": "bulk_api", "quality_trend": "stable"},
        {"id": "SUP009", "name": "Shandong Xinhua API", "country": "China", "city": "Zibo",
         "region": "Asia", "base_reliability": 0.70, "base_quality": 0.81, "price_tier": "lowest",
         "capacity_tons_year": 8000, "fda_approved": False, "years_active": 6,
         "specialization": "bulk_api", "quality_trend": "stable"},

        # European suppliers (expensive, very reliable)
        {"id": "SUP010", "name": "Novartis API GmbH", "country": "Switzerland", "city": "Basel",
         "region": "Europe", "base_reliability": 0.96, "base_quality": 0.97, "price_tier": "high",
         "capacity_tons_year": 4000, "fda_approved": True, "years_active": 30,
         "specialization": "branded", "quality_trend": "stable"},
        {"id": "SUP011", "name": "BASF Pharma Solutions", "country": "Germany", "city": "Ludwigshafen",
         "region": "Europe", "base_reliability": 0.95, "base_quality": 0.96, "price_tier": "high",
         "capacity_tons_year": 6000, "fda_approved": True, "years_active": 35,
         "specialization": "excipients", "quality_trend": "stable"},
        {"id": "SUP012", "name": "Siegfried AG Pharma", "country": "Switzerland", "city": "Zofingen",
         "region": "Europe", "base_reliability": 0.94, "base_quality": 0.95, "price_tier": "high",
         "capacity_tons_year": 3000, "fda_approved": True, "years_active": 28,
         "specialization": "custom_synthesis", "quality_trend": "stable"},
        {"id": "SUP013", "name": "Lonza Pharma Ingredients", "country": "Switzerland", "city": "Visp",
         "region": "Europe", "base_reliability": 0.97, "base_quality": 0.98, "price_tier": "highest",
         "capacity_tons_year": 2500, "fda_approved": True, "years_active": 40,
         "specialization": "biologics", "quality_trend": "stable"},
        {"id": "SUP014", "name": "Euroapi France", "country": "France", "city": "Paris",
         "region": "Europe", "base_reliability": 0.92, "base_quality": 0.94, "price_tier": "high",
         "capacity_tons_year": 3500, "fda_approved": True, "years_active": 20,
         "specialization": "branded", "quality_trend": "stable"},
        {"id": "SUP015", "name": "Polpharma API Poland", "country": "Poland", "city": "Starogard",
         "region": "Europe", "base_reliability": 0.88, "base_quality": 0.91, "price_tier": "medium",
         "capacity_tons_year": 4000, "fda_approved": True, "years_active": 16,
         "specialization": "generics", "quality_trend": "stable"},

        # US suppliers (expensive, most reliable, fastest delivery)
        {"id": "SUP016", "name": "Pfizer CentreOne API", "country": "USA", "city": "Kalamazoo",
         "region": "North America", "base_reliability": 0.97, "base_quality": 0.98, "price_tier": "highest",
         "capacity_tons_year": 5000, "fda_approved": True, "years_active": 45,
         "specialization": "branded", "quality_trend": "stable"},
        {"id": "SUP017", "name": "Thermo Fisher Pharma", "country": "USA", "city": "Greenville",
         "region": "North America", "base_reliability": 0.96, "base_quality": 0.97, "price_tier": "highest",
         "capacity_tons_year": 3000, "fda_approved": True, "years_active": 30,
         "specialization": "custom_synthesis", "quality_trend": "stable"},
        {"id": "SUP018", "name": "Cambrex API Corp", "country": "USA", "city": "East Rutherford",
         "region": "North America", "base_reliability": 0.93, "base_quality": 0.95, "price_tier": "high",
         "capacity_tons_year": 2000, "fda_approved": True, "years_active": 25,
         "specialization": "custom_synthesis", "quality_trend": "stable"},
        {"id": "SUP019", "name": "Curia Global API", "country": "USA", "city": "Albany",
         "region": "North America", "base_reliability": 0.91, "base_quality": 0.94, "price_tier": "high",
         "capacity_tons_year": 2500, "fda_approved": True, "years_active": 18,
         "specialization": "generics", "quality_trend": "stable"},

        # Other regions
        {"id": "SUP020", "name": "Teva API Israel", "country": "Israel", "city": "Petah Tikva",
         "region": "Middle East", "base_reliability": 0.90, "base_quality": 0.93, "price_tier": "medium",
         "capacity_tons_year": 6000, "fda_approved": True, "years_active": 35,
         "specialization": "generics", "quality_trend": "stable"},
        {"id": "SUP021", "name": "Aspen Pharmacare API", "country": "South Africa", "city": "Durban",
         "region": "Africa", "base_reliability": 0.83, "base_quality": 0.87, "price_tier": "medium",
         "capacity_tons_year": 2000, "fda_approved": True, "years_active": 12,
         "specialization": "generics", "quality_trend": "stable"},
        {"id": "SUP022", "name": "Cristalia Brazil API", "country": "Brazil", "city": "Itapira",
         "region": "South America", "base_reliability": 0.80, "base_quality": 0.86, "price_tier": "medium",
         "capacity_tons_year": 1500, "fda_approved": False, "years_active": 10,
         "specialization": "generics", "quality_trend": "declining"},  # <-- anomaly target
        {"id": "SUP023", "name": "Mylan API Japan", "country": "Japan", "city": "Osaka",
         "region": "Asia", "base_reliability": 0.94, "base_quality": 0.96, "price_tier": "high",
         "capacity_tons_year": 3000, "fda_approved": True, "years_active": 20,
         "specialization": "branded", "quality_trend": "stable"},
        {"id": "SUP024", "name": "Fermion Oy Finland", "country": "Finland", "city": "Espoo",
         "region": "Europe", "base_reliability": 0.93, "base_quality": 0.95, "price_tier": "high",
         "capacity_tons_year": 1500, "fda_approved": True, "years_active": 22,
         "specialization": "custom_synthesis", "quality_trend": "stable"},
        {"id": "SUP025", "name": "Lupin API Division", "country": "India", "city": "Pune",
         "region": "Asia", "base_reliability": 0.84, "base_quality": 0.89, "price_tier": "low",
         "capacity_tons_year": 4000, "fda_approved": True, "years_active": 13,
         "specialization": "generics", "quality_trend": "stable"},
    ]

    # Add computed fields
    price_multiplier = {"lowest": 0.6, "low": 0.75, "medium": 1.0, "high": 1.4, "highest": 1.8}
    geo_risk = {
        "Asia": 0.35, "Europe": 0.10, "North America": 0.08,
        "Middle East": 0.25, "Africa": 0.30, "South America": 0.28
    }
    lead_time_days = {
        "Asia": (45, 90), "Europe": (20, 45), "North America": (7, 21),
        "Middle East": (30, 60), "Africa": (40, 75), "South America": (35, 65)
    }

    for s in suppliers:
        s["price_multiplier"] = price_multiplier[s["price_tier"]]
        s["geo_risk_score"] = geo_risk.get(s["region"], 0.2)
        lt = lead_time_days.get(s["region"], (30, 60))
        s["avg_lead_time_days"] = int(np.mean(lt))
        s["min_order_kg"] = int(np.random.choice([100, 250, 500, 1000, 2000]))

    df = pd.DataFrame(suppliers)
    filepath = os.path.join(OUTPUT_DIR, "suppliers.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Generated {len(df)} suppliers → {filepath}")
    return df


# ============================================================
# 2. DRUG / API DATA
# ============================================================
def generate_drugs():
    """
    Generate 18 common pharmaceutical drugs/APIs with realistic attributes.
    Includes therapeutic category, base price, demand patterns, and
    which suppliers can produce each drug.
    """
    drugs = [
        # Cardiovascular
        {"id": "DRG001", "name": "Lisinopril", "category": "Cardiovascular",
         "base_price_per_kg": 120, "demand_seasonality": "flat", "criticality": "high",
         "approved_suppliers": ["SUP001", "SUP002", "SUP004", "SUP006", "SUP008", "SUP015", "SUP020", "SUP025"]},
        {"id": "DRG002", "name": "Amlodipine Besylate", "category": "Cardiovascular",
         "base_price_per_kg": 180, "demand_seasonality": "flat", "criticality": "high",
         "approved_suppliers": ["SUP001", "SUP003", "SUP005", "SUP010", "SUP015", "SUP020"]},
        {"id": "DRG003", "name": "Atorvastatin Calcium", "category": "Cardiovascular",
         "base_price_per_kg": 250, "demand_seasonality": "flat", "criticality": "high",
         "approved_suppliers": ["SUP002", "SUP005", "SUP006", "SUP010", "SUP016", "SUP023"]},

        # Diabetes
        {"id": "DRG004", "name": "Metformin HCl", "category": "Diabetes",
         "base_price_per_kg": 45, "demand_seasonality": "flat", "criticality": "critical",
         "approved_suppliers": ["SUP001", "SUP004", "SUP006", "SUP007", "SUP008", "SUP009", "SUP015", "SUP022", "SUP025"]},
        {"id": "DRG005", "name": "Glimepiride", "category": "Diabetes",
         "base_price_per_kg": 320, "demand_seasonality": "flat", "criticality": "medium",
         "approved_suppliers": ["SUP002", "SUP003", "SUP010", "SUP014", "SUP020"]},

        # Pain/Inflammation
        {"id": "DRG006", "name": "Ibuprofen", "category": "Pain",
         "base_price_per_kg": 35, "demand_seasonality": "winter_peak", "criticality": "high",
         "approved_suppliers": ["SUP001", "SUP006", "SUP007", "SUP008", "SUP009", "SUP011", "SUP015", "SUP021", "SUP025"]},
        {"id": "DRG007", "name": "Acetaminophen (Paracetamol)", "category": "Pain",
         "base_price_per_kg": 28, "demand_seasonality": "winter_peak", "criticality": "critical",
         "approved_suppliers": ["SUP004", "SUP006", "SUP007", "SUP008", "SUP009", "SUP011", "SUP022"]},

        # Antibiotics
        {"id": "DRG008", "name": "Amoxicillin Trihydrate", "category": "Antibiotics",
         "base_price_per_kg": 85, "demand_seasonality": "winter_peak", "criticality": "critical",
         "approved_suppliers": ["SUP001", "SUP002", "SUP006", "SUP008", "SUP014", "SUP021", "SUP025"]},
        {"id": "DRG009", "name": "Azithromycin", "category": "Antibiotics",
         "base_price_per_kg": 150, "demand_seasonality": "winter_peak", "criticality": "high",
         "approved_suppliers": ["SUP002", "SUP003", "SUP005", "SUP010", "SUP020"]},
        {"id": "DRG010", "name": "Ciprofloxacin HCl", "category": "Antibiotics",
         "base_price_per_kg": 95, "demand_seasonality": "slight_winter", "criticality": "medium",
         "approved_suppliers": ["SUP001", "SUP004", "SUP006", "SUP009", "SUP015"]},

        # Respiratory
        {"id": "DRG011", "name": "Salbutamol Sulfate", "category": "Respiratory",
         "base_price_per_kg": 420, "demand_seasonality": "spring_peak", "criticality": "high",
         "approved_suppliers": ["SUP003", "SUP005", "SUP010", "SUP012", "SUP016"]},
        {"id": "DRG012", "name": "Montelukast Sodium", "category": "Respiratory",
         "base_price_per_kg": 550, "demand_seasonality": "spring_peak", "criticality": "medium",
         "approved_suppliers": ["SUP002", "SUP005", "SUP013", "SUP017", "SUP023"]},

        # GI
        {"id": "DRG013", "name": "Omeprazole", "category": "Gastrointestinal",
         "base_price_per_kg": 110, "demand_seasonality": "flat", "criticality": "high",
         "approved_suppliers": ["SUP001", "SUP003", "SUP006", "SUP008", "SUP014", "SUP020", "SUP025"]},
        {"id": "DRG014", "name": "Pantoprazole Sodium", "category": "Gastrointestinal",
         "base_price_per_kg": 140, "demand_seasonality": "flat", "criticality": "medium",
         "approved_suppliers": ["SUP002", "SUP004", "SUP007", "SUP015", "SUP021"]},

        # CNS
        {"id": "DRG015", "name": "Sertraline HCl", "category": "CNS",
         "base_price_per_kg": 280, "demand_seasonality": "slight_winter", "criticality": "high",
         "approved_suppliers": ["SUP003", "SUP005", "SUP010", "SUP016", "SUP018", "SUP024"]},
        {"id": "DRG016", "name": "Escitalopram Oxalate", "category": "CNS",
         "base_price_per_kg": 350, "demand_seasonality": "slight_winter", "criticality": "medium",
         "approved_suppliers": ["SUP002", "SUP005", "SUP012", "SUP017", "SUP023"]},

        # Anti-infective (antiviral)
        {"id": "DRG017", "name": "Oseltamivir Phosphate", "category": "Antiviral",
         "base_price_per_kg": 1200, "demand_seasonality": "strong_winter", "criticality": "high",
         "approved_suppliers": ["SUP005", "SUP010", "SUP013", "SUP016", "SUP017"]},

        # Allergy
        {"id": "DRG018", "name": "Cetirizine HCl", "category": "Allergy",
         "base_price_per_kg": 65, "demand_seasonality": "spring_peak", "criticality": "medium",
         "approved_suppliers": ["SUP001", "SUP004", "SUP006", "SUP008", "SUP015", "SUP020", "SUP025"]},
    ]

    df = pd.DataFrame(drugs)
    # Store approved_suppliers as JSON string for CSV
    df["approved_suppliers"] = df["approved_suppliers"].apply(json.dumps)
    filepath = os.path.join(OUTPUT_DIR, "drugs.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Generated {len(df)} drugs → {filepath}")
    return df


# ============================================================
# 3. PURCHASE HISTORY (3 years, ~5000 orders)
# ============================================================
def generate_purchase_history(suppliers_df, drugs_df):
    """
    Generate 3 years of realistic purchase orders.
    
    Key patterns baked in for ML to discover:
    - Seasonal price fluctuations (Q4 prices rise)
    - Cheaper suppliers have more variable prices
    - Overall inflation trend of ~3%/year
    - Price spikes during supply disruptions
    - Bulk discount for larger orders
    """
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2023, 12, 31)
    num_days = (end_date - start_date).days

    # Load drug data with parsed supplier lists
    drugs_raw = drugs_df.copy()
    drugs_raw["approved_suppliers"] = drugs_raw["approved_suppliers"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else x
    )

    orders = []
    order_id = 1

    # Generate ~5000 orders across 3 years
    for _ in range(5200):
        # Random date
        day_offset = np.random.randint(0, num_days)
        order_date = start_date + timedelta(days=day_offset)
        month = order_date.month
        year = order_date.year

        # Pick a random drug
        drug_row = drugs_raw.iloc[np.random.randint(0, len(drugs_raw))]
        drug_id = drug_row["id"]
        base_price = drug_row["base_price_per_kg"]
        seasonality = drug_row["demand_seasonality"]

        # Pick a random approved supplier for this drug
        approved = drug_row["approved_suppliers"]
        supplier_id = np.random.choice(approved)
        sup_row = suppliers_df[suppliers_df["id"] == supplier_id].iloc[0]

        # --- PRICE CALCULATION (with realistic patterns) ---
        price = base_price * sup_row["price_multiplier"]

        # Inflation: ~3% per year
        years_from_start = (order_date - start_date).days / 365.25
        price *= (1 + 0.03 * years_from_start)

        # Seasonality
        seasonal_factor = 1.0
        if seasonality == "winter_peak" and month in [11, 12, 1, 2]:
            seasonal_factor = 1.08 + np.random.uniform(0, 0.07)
        elif seasonality == "strong_winter" and month in [11, 12, 1, 2]:
            seasonal_factor = 1.15 + np.random.uniform(0, 0.12)
        elif seasonality == "spring_peak" and month in [3, 4, 5]:
            seasonal_factor = 1.06 + np.random.uniform(0, 0.05)
        elif seasonality == "slight_winter" and month in [11, 12, 1]:
            seasonal_factor = 1.03 + np.random.uniform(0, 0.03)
        price *= seasonal_factor

        # Q4 general price pressure (end-of-year budget rush)
        if month in [10, 11, 12]:
            price *= 1.03

        # Supplier price variability (cheaper suppliers are less stable)
        if sup_row["price_tier"] in ["lowest", "low"]:
            price *= np.random.uniform(0.92, 1.12)
        else:
            price *= np.random.uniform(0.97, 1.04)

        # Random supply disruption events (rare price spikes)
        if np.random.random() < 0.03:  # 3% chance
            price *= np.random.uniform(1.15, 1.40)

        # Quantity with bulk discount
        quantity_kg = int(np.random.choice([50, 100, 250, 500, 1000, 2000, 5000],
                                           p=[0.05, 0.15, 0.25, 0.25, 0.15, 0.10, 0.05]))
        # Bulk discount
        if quantity_kg >= 2000:
            price *= 0.92
        elif quantity_kg >= 1000:
            price *= 0.95
        elif quantity_kg >= 500:
            price *= 0.97

        price = round(price, 2)
        total_cost = round(price * quantity_kg, 2)

        # Delivery simulation
        base_lead = int(sup_row["avg_lead_time_days"])
        actual_lead = max(3, int(base_lead + np.random.normal(0, base_lead * 0.15)))
        promised_date = order_date + timedelta(days=int(base_lead))
        actual_delivery = order_date + timedelta(days=int(actual_lead))
        on_time = actual_lead <= base_lead * 1.1

        orders.append({
            "order_id": f"ORD{order_id:05d}",
            "order_date": order_date.strftime("%Y-%m-%d"),
            "drug_id": drug_id,
            "drug_name": drug_row["name"],
            "supplier_id": supplier_id,
            "supplier_name": sup_row["name"],
            "quantity_kg": quantity_kg,
            "price_per_kg": price,
            "total_cost_usd": total_cost,
            "promised_delivery": promised_date.strftime("%Y-%m-%d"),
            "actual_delivery": actual_delivery.strftime("%Y-%m-%d"),
            "lead_time_days": actual_lead,
            "on_time": on_time,
            "year": year,
            "month": month,
            "quarter": f"Q{(month - 1) // 3 + 1}",
        })
        order_id += 1

    df = pd.DataFrame(orders)
    df = df.sort_values("order_date").reset_index(drop=True)
    filepath = os.path.join(OUTPUT_DIR, "purchase_history.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Generated {len(df)} purchase orders → {filepath}")
    return df


# ============================================================
# 4. QUALITY TEST RESULTS (~3000 batch records)
# ============================================================
def generate_quality_results(suppliers_df, drugs_df):
    """
    Generate quality test results for drug batches from each supplier.

    Key patterns:
    - Suppliers marked 'declining' quality_trend have gradually worsening metrics
    - Most suppliers are stable with normal variation
    - Some batches fail outright (rare)
    - Purity, contamination, dissolution, moisture content, sterility
    """
    drugs_raw = drugs_df.copy()
    drugs_raw["approved_suppliers"] = drugs_raw["approved_suppliers"].apply(
        lambda x: json.loads(x) if isinstance(x, str) else x
    )

    start_date = datetime(2021, 1, 1)
    records = []
    batch_id = 1

    # For each supplier-drug pair, generate batch results over time
    for _, sup_row in suppliers_df.iterrows():
        supplier_id = sup_row["id"]
        base_quality = sup_row["base_quality"]
        trend = sup_row["quality_trend"]

        # Find drugs this supplier makes
        for _, drug_row in drugs_raw.iterrows():
            approved = drug_row["approved_suppliers"]
            if supplier_id not in approved:
                continue

            # Generate 10-25 batches over 3 years
            num_batches = np.random.randint(10, 26)
            batch_dates = sorted([
                start_date + timedelta(days=np.random.randint(0, 1095))
                for _ in range(num_batches)
            ])

            for i, batch_date in enumerate(batch_dates):
                # Time progression factor (0 to 1 over 3 years)
                time_factor = (batch_date - start_date).days / 1095.0

                # Base metrics
                purity = base_quality * 100  # e.g., 0.90 -> 90%
                contamination = (1 - base_quality) * 100 * 0.5  # lower is better

                # Apply declining trend for flagged suppliers
                if trend == "declining":
                    # Quality degrades gradually — subtle at first, obvious later
                    degradation = time_factor ** 1.5 * 8  # up to 8% purity drop
                    purity -= degradation
                    contamination += degradation * 0.6

                # Normal variation
                purity += np.random.normal(0, 0.8)
                contamination += np.random.normal(0, 0.3)

                # Dissolution rate (85-100 minutes, lower is better for most drugs)
                dissolution_min = 30 + (1 - base_quality) * 40 + np.random.normal(0, 3)
                if trend == "declining":
                    dissolution_min += time_factor * 12

                # Moisture content (should be < 5%)
                moisture_pct = 1.5 + (1 - base_quality) * 2 + np.random.normal(0, 0.3)
                if trend == "declining":
                    moisture_pct += time_factor * 1.5

                # Sterility pass/fail
                sterility_pass = np.random.random() > (0.02 if trend == "stable" else 0.02 + time_factor * 0.08)

                # Overall pass/fail
                passed = (purity >= 95.0 and contamination <= 3.0 and
                          dissolution_min <= 55 and moisture_pct <= 5.0 and sterility_pass)

                records.append({
                    "batch_id": f"BAT{batch_id:05d}",
                    "test_date": batch_date.strftime("%Y-%m-%d"),
                    "drug_id": drug_row["id"],
                    "drug_name": drug_row["name"],
                    "supplier_id": supplier_id,
                    "supplier_name": sup_row["name"],
                    "purity_pct": round(max(80, min(100, purity)), 2),
                    "contamination_ppm": round(max(0, contamination), 2),
                    "dissolution_min": round(max(15, dissolution_min), 1),
                    "moisture_pct": round(max(0.1, moisture_pct), 2),
                    "sterility_pass": sterility_pass,
                    "overall_pass": passed,
                    "quality_trend": trend,
                })
                batch_id += 1

    df = pd.DataFrame(records)
    df = df.sort_values("test_date").reset_index(drop=True)
    filepath = os.path.join(OUTPUT_DIR, "quality_results.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Generated {len(df)} quality test records → {filepath}")
    return df


# ============================================================
# 5. SUPPLIER INCIDENTS (~200 events)
# ============================================================
def generate_incidents(suppliers_df):
    """
    Generate supplier incident records: late deliveries, FDA warnings,
    inspection failures, capacity issues, geopolitical disruptions.
    """
    incident_types = [
        ("late_delivery", 0.40, "minor"),
        ("quality_complaint", 0.20, "moderate"),
        ("fda_warning_letter", 0.08, "severe"),
        ("fda_inspection_failure", 0.05, "severe"),
        ("capacity_shortage", 0.10, "moderate"),
        ("geopolitical_disruption", 0.07, "severe"),
        ("natural_disaster", 0.03, "severe"),
        ("price_dispute", 0.07, "minor"),
    ]

    start_date = datetime(2021, 1, 1)
    incidents = []
    inc_id = 1

    for _, sup_row in suppliers_df.iterrows():
        # Riskier suppliers have more incidents
        risk_factor = 1 - sup_row["base_reliability"]
        num_incidents = int(np.random.poisson(risk_factor * 30))
        num_incidents = max(1, min(num_incidents, 25))

        for _ in range(num_incidents):
            # Weighted random incident type
            types, weights, severities = zip(*incident_types)
            weights = np.array(weights)
            weights /= weights.sum()
            idx = np.random.choice(len(types), p=weights)

            inc_date = start_date + timedelta(days=np.random.randint(0, 1095))

            # Resolution time depends on severity
            if severities[idx] == "minor":
                resolution_days = np.random.randint(1, 14)
            elif severities[idx] == "moderate":
                resolution_days = np.random.randint(7, 45)
            else:
                resolution_days = np.random.randint(30, 180)

            incidents.append({
                "incident_id": f"INC{inc_id:04d}",
                "date": inc_date.strftime("%Y-%m-%d"),
                "supplier_id": sup_row["id"],
                "supplier_name": sup_row["name"],
                "incident_type": types[idx],
                "severity": severities[idx],
                "resolution_days": resolution_days,
                "resolved": np.random.random() > 0.05,
                "description": f"{types[idx].replace('_', ' ').title()} at {sup_row['name']}",
            })
            inc_id += 1

    df = pd.DataFrame(incidents)
    df = df.sort_values("date").reset_index(drop=True)
    filepath = os.path.join(OUTPUT_DIR, "incidents.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Generated {len(df)} incidents → {filepath}")
    return df


# ============================================================
# 6. COMMODITY PRICE INDEX (external signal for price model)
# ============================================================
def generate_commodity_index():
    """
    Generate a synthetic commodity price index (similar to chemical price indices).
    This serves as an external regressor for the price forecasting model.
    """
    dates = pd.date_range("2021-01-01", "2023-12-31", freq="W")
    n = len(dates)

    # Base trend: gradual increase with some volatility
    trend = np.linspace(100, 125, n)
    seasonal = 5 * np.sin(2 * np.pi * np.arange(n) / 52)  # yearly cycle
    noise = np.cumsum(np.random.normal(0, 0.8, n))  # random walk component

    # Add a supply shock in mid-2022 (mimicking real-world events)
    shock_center = n // 2 + 10
    shock = 15 * np.exp(-0.5 * ((np.arange(n) - shock_center) / 8) ** 2)

    index_values = trend + seasonal + noise + shock
    index_values = np.maximum(index_values, 80)  # floor

    df = pd.DataFrame({
        "date": dates,
        "commodity_index": np.round(index_values, 2),
        "usd_inr_rate": np.round(np.linspace(74, 83, n) + np.random.normal(0, 0.5, n), 2),
        "usd_cny_rate": np.round(np.linspace(6.4, 7.2, n) + np.random.normal(0, 0.05, n), 2),
        "usd_eur_rate": np.round(np.linspace(0.85, 0.92, n) + np.random.normal(0, 0.01, n), 2),
    })
    filepath = os.path.join(OUTPUT_DIR, "commodity_index.csv")
    df.to_csv(filepath, index=False)
    print(f"✅ Generated {len(df)} weeks of commodity data → {filepath}")
    return df


# ============================================================
# MASTER GENERATOR
# ============================================================
def generate_all():
    """Generate all synthetic datasets."""
    print("=" * 60)
    print("PharmaFlow AI — Synthetic Data Generator")
    print("=" * 60)
    print()

    ensure_output_dir()

    # Generate in dependency order
    suppliers_df = generate_suppliers()
    drugs_df = generate_drugs()
    purchase_df = generate_purchase_history(suppliers_df, drugs_df)
    quality_df = generate_quality_results(suppliers_df, drugs_df)
    incidents_df = generate_incidents(suppliers_df)
    commodity_df = generate_commodity_index()

    print()
    print("=" * 60)
    print("DATA GENERATION COMPLETE")
    print("=" * 60)
    print(f"  Suppliers:        {len(suppliers_df):>6}")
    print(f"  Drugs:            {len(drugs_df):>6}")
    print(f"  Purchase Orders:  {len(purchase_df):>6}")
    print(f"  Quality Records:  {len(quality_df):>6}")
    print(f"  Incidents:        {len(incidents_df):>6}")
    print(f"  Commodity Weeks:  {len(commodity_df):>6}")
    print(f"\n  Output: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    generate_all()
