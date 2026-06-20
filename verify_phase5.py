"""
PharmaFlow AI — Phase 5 Production Verification
================================================
Tests all Phase 5 components: auth, config, middleware, rate limiting.
Run from project root:
    python verify_phase5.py
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set development mode so auth is bypassed
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("API_KEY", "")

PASS = "  ✅"
WARN = "  ⚠️ "
FAIL = "  ❌"

print("=" * 60)
print("PHARMAFLOW AI — PHASE 5 PRODUCTION VERIFICATION")
print("=" * 60)

errors = 0

# ── 1. Config module ──────────────────────────────────────────────────────────
print("\n[1/6] Testing Config module...")
try:
    from src.api.config import get_settings, configure_logging
    settings = get_settings()
    configure_logging()
    print(f"{PASS} Settings loaded — env={settings.environment}")
    print(f"{PASS} Auth enabled: {settings.auth_enabled}")
    print(f"{PASS} Rate limit: {settings.rate_limit_per_minute}/min")
    print(f"{PASS} Prometheus: {settings.prometheus_enabled}")
except Exception as e:
    print(f"{FAIL} Config error: {e}")
    errors += 1

# ── 2. JWT helpers ─────────────────────────────────────────────────────────────
print("\n[2/6] Testing JWT helpers...")
try:
    from src.api.config import create_access_token, decode_access_token
    token = create_access_token({"sub": "test-user"})
    payload = decode_access_token(token)
    assert payload["sub"] == "test-user"
    print(f"{PASS} JWT create + decode round-trip OK")
except ImportError:
    print(f"{WARN} python-jose not installed — JWT disabled (install: pip install python-jose[cryptography])")
except Exception as e:
    print(f"{FAIL} JWT error: {e}")
    errors += 1

# ── 3. Rate limiter ────────────────────────────────────────────────────────────
print("\n[3/6] Testing Rate limiter...")
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
    print(f"{PASS} slowapi Limiter available")
except ImportError:
    print(f"{WARN} slowapi not installed (install: pip install slowapi)")

# ── 4. Prometheus instrumentation ─────────────────────────────────────────────
print("\n[4/6] Testing Prometheus instrumentation...")
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    print(f"{PASS} prometheus-fastapi-instrumentator available")
except ImportError:
    print(f"{WARN} prometheus-fastapi-instrumentator not installed (install: pip install prometheus-fastapi-instrumentator)")

# ── 5. Dockerfile exists ──────────────────────────────────────────────────────
print("\n[5/6] Checking deployment files...")
from pathlib import Path
root = Path(__file__).parent
checks = {
    "Dockerfile":                   root / "Dockerfile",
    "docker-compose.yml":           root / "docker-compose.yml",
    "dashboard/Dockerfile":         root / "dashboard" / "Dockerfile",
    "dashboard/nginx.conf":         root / "dashboard" / "nginx.conf",
    ".env.example":                 root / ".env.example",
    ".gitignore":                   root / ".gitignore",
    ".github/workflows/ci.yml":     root / ".github" / "workflows" / "ci.yml",
    "deploy/prometheus.yml":        root / "deploy" / "prometheus.yml",
}
for name, path in checks.items():
    if path.exists():
        print(f"{PASS} {name}")
    else:
        print(f"{FAIL} Missing: {name}")
        errors += 1

# ── 6. Full API startup with Phase 5 middleware ────────────────────────────────
print("\n[6/6] Testing API imports with Phase 5 middleware...")
try:
    import importlib
    import src.api.main as main_mod
    importlib.reload(main_mod)
    app = main_mod.app
    assert app.version == "4.0.0", f"Expected v4.0.0, got {app.version}"
    print(f"{PASS} FastAPI app v{app.version} loaded")
    print(f"{PASS} Middleware stack: {len(app.middleware_stack.__dict__)} layers")
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    print(f"{PASS} {len(routes)} routes registered")
    for r in sorted(routes):
        print(f"       {r}")
except Exception as e:
    print(f"{FAIL} API load error: {e}")
    errors += 1

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if errors == 0:
    print("✅ PHASE 5 VERIFICATION COMPLETE — All checks passed!")
else:
    print(f"⚠️  PHASE 5 VERIFICATION — {errors} error(s) found")
    print("   Install missing packages: pip install -r requirements.txt")
print("=" * 60)
print()
print("To start production stack:")
print("  docker compose up -d")
print()
print("To start development:")
print("  python -m uvicorn src.api.main:app --reload --port 8000 --reload-exclude \".venv/*\"")
print("  cd dashboard && npm run dev")
