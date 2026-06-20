"""
PharmaFlow AI — Phase 3: Geopolitical Intelligence Engine
==========================================================
Maps geopolitical and regulatory risk signals to supplier risk overlays.

Simulates a news intelligence pipeline that would in production:
  - Ingest RSS feeds / news APIs (Reuters, Bloomberg, FDA MedWatch)
  - Run NLP classification on headlines
  - Map events to affected countries / suppliers
  - Produce time-decayed alert scores

In Phase 3 (offline/synthetic mode), this module:
  1. Generates realistic synthetic geo-political events (trade tensions,
     factory shutdowns, regulatory actions, sanctions, weather events)
  2. Maps each event to affected suppliers via country
  3. Scores each event by severity × recency decay
  4. Produces supplier-level geo alerts and a country risk index

Phase 4 integration: wire this to a live news API (e.g. NewsAPI, GDELT).
"""

import logging
import warnings
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("pharma.geopolitical")

_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"

# ── Event taxonomy ─────────────────────────────────────────────────────────────
EVENT_TYPES = {
    "trade_restriction": {
        "severity": 75,
        "description_template": "{country} imposes new export restrictions on pharmaceutical APIs",
        "duration_days": 90,
    },
    "factory_shutdown": {
        "severity": 90,
        "description_template": "Major API manufacturing facility in {country} halted due to safety inspection",
        "duration_days": 45,
    },
    "fda_import_alert": {
        "severity": 80,
        "description_template": "FDA issues import alert on {country}-sourced drug ingredients (cGMP violations)",
        "duration_days": 180,
    },
    "sanctions": {
        "severity": 95,
        "description_template": "New economic sanctions restrict pharmaceutical trade with {country}",
        "duration_days": 365,
    },
    "logistics_disruption": {
        "severity": 55,
        "description_template": "Port congestion and shipping delays from {country} affecting API delivery timelines",
        "duration_days": 30,
    },
    "currency_volatility": {
        "severity": 40,
        "description_template": "{country} currency depreciation causing API price instability",
        "duration_days": 60,
    },
    "regulatory_change": {
        "severity": 50,
        "description_template": "{country} updates pharmaceutical manufacturing regulations — compliance review required",
        "duration_days": 120,
    },
    "political_instability": {
        "severity": 65,
        "description_template": "Political unrest in {country} creates supply chain uncertainty for API manufacturers",
        "duration_days": 75,
    },
    "weather_disaster": {
        "severity": 70,
        "description_template": "Severe weather event in {country} disrupts pharmaceutical manufacturing and logistics",
        "duration_days": 21,
    },
    "quality_scandal": {
        "severity": 85,
        "description_template": "Widespread quality failures detected at {country} API manufacturers — industry-wide audit launched",
        "duration_days": 120,
    },
}

# Country risk baseline (0-100, higher = riskier geopolitically)
COUNTRY_RISK_BASELINE = {
    "China": 65,
    "India": 45,
    "Bangladesh": 55,
    "Pakistan": 70,
    "Mexico": 40,
    "Brazil": 42,
    "Germany": 12,
    "France": 14,
    "Switzerland": 8,
    "USA": 10,
    "UK": 11,
    "Ireland": 9,
    "Israel": 38,
    "South Korea": 22,
    "Japan": 15,
}


# ═════════════════════════════════════════════════════════════════════════════
# Geopolitical Intelligence Engine
# ═════════════════════════════════════════════════════════════════════════════

class GeopoliticalIntelligence:
    """
    Simulates a geopolitical event feed and maps events to supplier risk overlays.

    Parameters
    ----------
    n_events : int
        Number of synthetic events to generate (default 25).
    decay_halflife_days : float
        How quickly event scores decay over time (default 30 days).
    seed : int
        Random seed for reproducibility.
    """

    def __init__(self, n_events: int = 25, decay_halflife_days: float = 30.0, seed: int = 42):
        self.n_events = n_events
        self.decay_halflife = decay_halflife_days
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

        self.suppliers = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")

        self.events_ = None
        self.supplier_alerts_ = None
        self.country_risk_index_ = None

    # ── Event generation ──────────────────────────────────────────────────────

    def _generate_events(self) -> pd.DataFrame:
        """Generate synthetic geopolitical events over the past 6 months."""
        now = datetime.now()
        countries = list(COUNTRY_RISK_BASELINE.keys())
        event_type_list = list(EVENT_TYPES.keys())

        # Countries with higher baseline risk are more likely to have events
        weights = [COUNTRY_RISK_BASELINE[c] for c in countries]
        total_w = sum(weights)
        probs = [w / total_w for w in weights]

        rows = []
        for i in range(self.n_events):
            country = random.choices(countries, weights=probs)[0]
            event_type = random.choice(event_type_list)
            meta = EVENT_TYPES[event_type]

            # Event date: randomly within last 180 days
            days_ago = random.randint(0, 180)
            event_date = now - timedelta(days=days_ago)

            # Add noise to severity ± 10
            severity = float(np.clip(meta["severity"] + random.gauss(0, 10), 10, 100))

            # Time-decay factor: e^(-ln2 / halflife * days_ago)
            decay = np.exp(-np.log(2) / self.decay_halflife * days_ago)
            effective_score = severity * decay

            rows.append({
                "event_id": f"EVT{i+1:03d}",
                "event_type": event_type,
                "country": country,
                "event_date": event_date.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "description": meta["description_template"].format(country=country),
                "severity": round(severity, 1),
                "duration_days": meta["duration_days"],
                "active": days_ago <= meta["duration_days"],
                "decay_factor": round(float(decay), 4),
                "effective_score": round(float(effective_score), 1),
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
            })

        df = pd.DataFrame(rows).sort_values("effective_score", ascending=False)
        return df

    # ── Supplier overlay ──────────────────────────────────────────────────────

    def _build_supplier_alerts(self, events: pd.DataFrame) -> pd.DataFrame:
        """Map events to affected suppliers via country."""
        active_events = events[events["active"]].copy()

        rows = []
        for _, sup in self.suppliers.iterrows():
            country = sup.get("country", "Unknown")

            # Events in this supplier's country
            country_events = active_events[active_events["country"] == country]

            if country_events.empty:
                geo_score = 0.0
                top_event = "No active events"
                top_event_type = "none"
                n_events = 0
            else:
                geo_score = float(country_events["effective_score"].sum())
                geo_score = min(geo_score, 100)  # cap at 100
                top_row = country_events.iloc[0]
                top_event = top_row["description"]
                top_event_type = top_row["event_type"]
                n_events = len(country_events)

            # Look up existing ML risk score
            risk_row = self.risk_scores[self.risk_scores["supplier_id"] == sup["id"]]
            base_risk = float(risk_row["risk_score"].iloc[0]) if not risk_row.empty else 50.0
            risk_tier = str(risk_row["risk_tier"].iloc[0]) if not risk_row.empty else "Unknown"

            # Adjusted risk: blend base risk (70%) + geo overlay (30%)
            adjusted_risk = round(base_risk * 0.70 + geo_score * 0.30, 1)
            adjusted_risk = min(adjusted_risk, 100)

            delta = round(adjusted_risk - base_risk, 1)

            rows.append({
                "supplier_id": sup["id"],
                "supplier_name": sup["name"],
                "country": country,
                "region": sup.get("region", ""),
                "base_risk_score": round(base_risk, 1),
                "geo_intelligence_score": round(geo_score, 1),
                "adjusted_risk_score": adjusted_risk,
                "risk_delta": delta,
                "original_risk_tier": risk_tier,
                "active_geo_events": n_events,
                "top_event": top_event,
                "top_event_type": top_event_type,
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
                "alert_level": self._alert_level(delta, geo_score),
            })

        df = pd.DataFrame(rows).sort_values("adjusted_risk_score", ascending=False)
        df.to_csv(PROCESSED / "geo_supplier_alerts.csv", index=False)
        return df

    @staticmethod
    def _alert_level(delta: float, geo_score: float) -> str:
        if geo_score >= 60 or delta >= 15:
            return "HIGH"
        if geo_score >= 30 or delta >= 7:
            return "MEDIUM"
        if geo_score >= 10:
            return "LOW"
        return "CLEAR"

    # ── Country risk index ────────────────────────────────────────────────────

    def _build_country_risk_index(self, events: pd.DataFrame) -> pd.DataFrame:
        """Aggregate geo scores per country."""
        active = events[events["active"]]
        country_agg = (
            active.groupby("country")
            .agg(
                total_geo_score=("effective_score", "sum"),
                num_events=("event_id", "count"),
                top_event_type=("event_type", "first"),
                max_severity=("severity", "max"),
            )
            .reset_index()
        )
        country_agg["baseline_risk"] = country_agg["country"].map(COUNTRY_RISK_BASELINE).fillna(50)
        country_agg["combined_risk"] = (
            country_agg["baseline_risk"] * 0.5 +
            country_agg["total_geo_score"].clip(upper=100) * 0.5
        ).round(1)
        country_agg = country_agg.sort_values("combined_risk", ascending=False)
        country_agg.to_csv(PROCESSED / "country_risk_index.csv", index=False)
        return country_agg

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Run the full geopolitical intelligence pipeline.

        Returns
        -------
        dict with:
            events_df        : pd.DataFrame — all generated events
            supplier_alerts  : pd.DataFrame — supplier-level alerts
            country_risk     : pd.DataFrame — country risk index
            summary          : dict
        """
        log.info("Generating geopolitical event feed…")
        events = self._generate_events()
        self.events_ = events

        log.info("Building supplier alerts…")
        supplier_alerts = self._build_supplier_alerts(events)
        self.supplier_alerts_ = supplier_alerts

        log.info("Building country risk index…")
        country_risk = self._build_country_risk_index(events)
        self.country_risk_index_ = country_risk

        events.to_csv(PROCESSED / "geo_events.csv", index=False)

        summary = {
            "total_events": len(events),
            "active_events": int(events["active"].sum()),
            "countries_affected": int(events[events["active"]]["country"].nunique()),
            "suppliers_on_high_alert": int((supplier_alerts["alert_level"] == "HIGH").sum()),
            "suppliers_on_medium_alert": int((supplier_alerts["alert_level"] == "MEDIUM").sum()),
            "most_dangerous_country": country_risk.iloc[0]["country"] if not country_risk.empty else "N/A",
            "highest_adjusted_risk_supplier": supplier_alerts.iloc[0]["supplier_name"] if not supplier_alerts.empty else "N/A",
        }

        log.info(
            f"Geo intelligence complete — {summary['active_events']} active events | "
            f"{summary['suppliers_on_high_alert']} suppliers on HIGH alert"
        )
        return {
            "events_df": events,
            "supplier_alerts": supplier_alerts,
            "country_risk": country_risk,
            "summary": summary,
        }


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    engine = GeopoliticalIntelligence(n_events=25)
    result = engine.run()

    s = result["summary"]
    print("\n" + "=" * 65)
    print("GEOPOLITICAL INTELLIGENCE REPORT")
    print("=" * 65)
    print(f"Total events generated    : {s['total_events']}")
    print(f"Currently active          : {s['active_events']}")
    print(f"Countries affected        : {s['countries_affected']}")
    print(f"Suppliers on HIGH alert   : {s['suppliers_on_high_alert']}")
    print(f"Suppliers on MEDIUM alert : {s['suppliers_on_medium_alert']}")
    print(f"Most dangerous country    : {s['most_dangerous_country']}")
    print(f"Highest adjusted risk sup : {s['highest_adjusted_risk_supplier']}")

    print("\nTOP 10 ACTIVE EVENTS:")
    top_events = result["events_df"][result["events_df"]["active"]].head(10)
    for _, ev in top_events.iterrows():
        print(f"  [{ev['event_type']:25s}] {ev['country']:12s} | score={ev['effective_score']:5.1f} | {ev['days_ago']}d ago")

    print("\nSUPPLIER ALERTS (HIGH):")
    high = result["supplier_alerts"][result["supplier_alerts"]["alert_level"] == "HIGH"]
    for _, sup in high.iterrows():
        print(f"  {sup['supplier_name']:<28} base={sup['base_risk_score']:.1f} → adj={sup['adjusted_risk_score']:.1f} (+{sup['risk_delta']:.1f})")
        print(f"    ↳ {sup['top_event'][:80]}")

    print("\nCOUNTRY RISK INDEX:")
    for _, c in result["country_risk"].head(8).iterrows():
        print(f"  {c['country']:<15} combined_risk={c['combined_risk']:5.1f}  events={int(c['num_events'])}")
