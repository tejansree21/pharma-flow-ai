"""Quick verification script for Phase 2 components."""
import sys
import os

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

print("=" * 60)
print("PHARMAFLOW AI — PHASE 2 VERIFICATION")
print("=" * 60)

# ── Test 1: Purchase Optimizer ─────────────────────────────────────
print("\n[1/3] Testing Purchase Optimizer...")
try:
    from src.optimization.purchase_optimizer import PurchaseOptimizer
    opt = PurchaseOptimizer()
    result = opt.optimize()
    print(f"  ✅ Solver: {result['solver']}")
    print(f"  ✅ Drugs covered: {result['num_drugs']}")
    print(f"  ✅ Suppliers used: {result['num_suppliers_used']}")
    print(f"  ✅ Total raw cost: ${result['total_raw_cost']:,.2f}")
    print(f"  ✅ Risk penalty:   ${result['total_risk_penalty']:,.2f}")
    print(f"  ✅ Effective cost: ${result['total_effective_cost']:,.2f}")
    alloc = result['allocation_df']
    print(f"\n  Top 5 allocation lines:")
    for _, row in alloc.nlargest(5, 'quantity_kg').iterrows():
        print(f"    {row['drug_name']:<25} {row['supplier_name']:<20} {row['quantity_kg']:>8,.1f} kg  risk={row['risk_score']:.0f}")
except Exception as e:
    print(f"  ❌ FAILED: {e}")
    import traceback; traceback.print_exc()

# ── Test 2: Inventory Manager ──────────────────────────────────────
print("\n[2/3] Testing Inventory Manager...")
try:
    from src.optimization.inventory_manager import InventoryManager
    mgr = InventoryManager()
    df = mgr.compute_recommendations()
    s = mgr.summary(df)
    print(f"  ✅ Drugs tracked: {s['total_drugs']}")
    print(f"  ✅ REORDER NOW:   {s['reorder_now']}")
    print(f"  ✅ REORDER SOON:  {s['reorder_soon']}")
    print(f"  ✅ ADEQUATE:      {s['adequate']}")
    print(f"  ✅ EXCESS:        {s['excess']}")
    print(f"  ✅ Stock value:   ${s['total_stock_value_usd']:,.2f}")
    print(f"  ✅ Avg days cover: {s['avg_days_cover']}")
    if s['critical_reorders']:
        print(f"  ⚠️  Critical reorders: {s['critical_reorders']}")
except Exception as e:
    print(f"  ❌ FAILED: {e}")
    import traceback; traceback.print_exc()

# ── Test 3: API schemas can be imported ───────────────────────────
print("\n[3/3] Testing API schema imports...")
try:
    from src.api.schemas import (
        HealthResponse, DrugOut, SupplierOut, ForecastRequest, ForecastResponse,
        RiskRequest, RiskResponse, QualityCheckRequest, QualityCheckResponse,
        OptimizeRequest, OptimizeResponse, InventoryRequest, InventoryResponse,
        DashboardSummary,
    )
    h = HealthResponse()
    print(f"  ✅ HealthResponse: {h.status} | {h.version} | {h.phase}")
    print(f"  ✅ All {14} schema classes imported successfully")
except Exception as e:
    print(f"  ❌ FAILED: {e}")
    import traceback; traceback.print_exc()

print("\n" + "=" * 60)
print("PHASE 2 VERIFICATION COMPLETE")
print("=" * 60)
print("\nOutputs saved:")
print("  data/processed/purchase_allocation.csv")
print("  data/processed/purchase_summary.csv")
print("  data/processed/inventory_recommendations.csv")
print("\nTo start the API:")
print("  uvicorn src.api.main:app --reload --port 8000")
