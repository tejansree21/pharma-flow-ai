"""
PharmaFlow AI — Phase 8: Demand Forecasting (Epidemiology Layer)
================================================================
Pulls real disease surveillance data and maps outbreaks to drug demand signals.

Sources (all free, no API key required):
  1. WHO Disease Outbreak News (DONS) RSS — live outbreak alerts
  2. CDC ILI Surveillance — influenza-like illness weekly data (open data API)
  3. Synthetic seasonal baseline — for drugs with no live signal

Drug-to-disease mapping lets procurement teams anticipate demand spikes
weeks before they show up in purchase orders.
"""

import json
import logging
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.demand")

_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"

# ── External data sources ──────────────────────────────────────────────────────

WHO_DONS_RSS = "https://www.who.int/feeds/entity/csr/don/en/rss.xml"
CDC_ILI_API  = (
    "https://data.cdc.gov/resource/kvib-3txy.json"
    "?$limit=52&$order=week_start%20DESC"
)

# ── Disease → drug demand mapping ─────────────────────────────────────────────
# Keys match WHO/CDC outbreak categories; values are drug name fragments
# that appear in the synthetic formulary

DISEASE_DRUG_MAP = {
    # Viral respiratory
    "influenza":          ["oseltamivir", "amantadine", "zanamivir", "tamiflu"],
    "influenza-like":     ["oseltamivir", "ibuprofen", "acetaminophen"],
    "covid":              ["dexamethasone", "remdesivir", "baricitinib", "azithromycin"],
    "coronavirus":        ["dexamethasone", "azithromycin"],
    "respiratory":        ["azithromycin", "amoxicillin", "doxycycline"],
    # Bacterial
    "pneumonia":          ["amoxicillin", "azithromycin", "ceftriaxone"],
    "cholera":            ["doxycycline", "azithromycin", "ciprofloxacin"],
    "typhoid":            ["ciprofloxacin", "azithromycin", "ceftriaxone"],
    "tuberculosis":       ["rifampicin", "isoniazid", "ethambutol"],
    "meningitis":         ["ceftriaxone", "dexamethasone", "penicillin"],
    # Fever / pain
    "fever":              ["acetaminophen", "ibuprofen", "aspirin"],
    "dengue":             ["acetaminophen", "paracetamol"],
    "malaria":            ["chloroquine", "artemisinin", "mefloquine"],
    "ebola":              ["dexamethasone", "methylprednisolone"],
    # Allergy / seasonal
    "allerg":             ["cetirizine", "loratadine", "fexofenadine", "diphenhydramine"],
    "asthma":             ["salbutamol", "budesonide", "prednisone"],
    # Metabolic
    "diabetes":           ["metformin", "insulin", "glipizide"],
    "hypertension":       ["lisinopril", "amlodipine", "losartan"],
    # GI
    "gastrointestinal":   ["omeprazole", "metronidazole", "loperamide"],
    "diarrhea":           ["metronidazole", "oral rehydration", "loperamide"],
}

# Seasonal demand multipliers by month (1.0 = baseline)
SEASONAL_PATTERNS = {
    "antiviral":      [1.0, 1.2, 1.4, 1.6, 1.4, 1.1, 0.9, 0.8, 0.9, 1.0, 1.2, 1.3],
    "antibiotic":     [1.1, 1.2, 1.2, 1.1, 1.0, 0.9, 0.9, 0.9, 1.0, 1.0, 1.1, 1.2],
    "antihistamine":  [0.8, 0.8, 0.9, 1.3, 1.8, 1.7, 1.5, 1.4, 1.2, 0.9, 0.8, 0.8],
    "analgesic":      [1.1, 1.0, 1.0, 1.0, 1.0, 1.0, 0.9, 0.9, 1.0, 1.0, 1.0, 1.1],
    "antidiabetic":   [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "cardiovascular": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "other":          [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
}

CATEGORY_PATTERN_MAP = {
    "antiviral":      "antiviral",
    "antibiotic":     "antibiotic",
    "antihistamine":  "antihistamine",
    "analgesic":      "analgesic",
    "antidiabetic":   "antidiabetic",
    "cardiovascular": "cardiovascular",
    "steroid":        "antiviral",   # steroids spike with respiratory outbreaks
    "proton pump":    "other",
    "nsaid":          "analgesic",
    "opioid":         "other",
}


# ═════════════════════════════════════════════════════════════════════════════
# Data fetchers
# ═════════════════════════════════════════════════════════════════════════════

def _fetch(url: str, timeout: int = 8):
    try:
        req = Request(url, headers={"User-Agent": "PharmaFlowAI/8.0"})
        with urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:
        log.warning(f"Fetch failed [{url[:60]}]: {e}")
        return None


def fetch_who_dons() -> list[dict]:
    """Pull WHO Disease Outbreak News RSS feed."""
    raw = _fetch(WHO_DONS_RSS)
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            desc  = item.findtext("description") or ""
            pub   = item.findtext("pubDate") or ""
            link  = item.findtext("link") or ""
            # Parse date
            try:
                dt = datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S")
            except Exception:
                dt = datetime.now() - timedelta(days=7)
            days_ago = max(0, (datetime.now() - dt).days)
            items.append({
                "title": title,
                "description": desc[:300],
                "published": dt.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "link": link,
                "source": "who_dons",
            })
        log.info(f"WHO DONS: {len(items)} outbreak alerts fetched")
        return items[:20]
    except Exception as e:
        log.warning(f"WHO DONS parse error: {e}")
        return []


def fetch_cdc_ili() -> list[dict]:
    """Pull CDC ILI (influenza-like illness) surveillance weekly data."""
    raw = _fetch(CDC_ILI_API)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        rows = []
        for record in data[:52]:
            try:
                rows.append({
                    "week_start": record.get("week_start", "")[:10],
                    "region": record.get("region", "National"),
                    "ili_pct": float(record.get("total_ili", 0) or 0),
                    "total_patients": int(record.get("total_patients", 0) or 0),
                    "source": "cdc_ili",
                })
            except Exception:
                continue
        # Sort by week descending
        rows.sort(key=lambda x: x["week_start"], reverse=True)
        log.info(f"CDC ILI: {len(rows)} weekly records fetched")
        return rows
    except Exception as e:
        log.warning(f"CDC ILI parse error: {e}")
        return []


# ═════════════════════════════════════════════════════════════════════════════
# Drug demand signal engine
# ═════════════════════════════════════════════════════════════════════════════

class DemandForecaster:
    """
    Maps disease surveillance signals to drug demand forecasts.

    Parameters
    ----------
    lookback_weeks : int — how many weeks of history to include
    """

    def __init__(self, lookback_weeks: int = 12):
        self.lookback_weeks = lookback_weeks
        self.drugs = pd.read_csv(SYNTHETIC / "drugs.csv")

    # ── Signal extraction ─────────────────────────────────────────────────────

    def _classify_outbreak(self, text: str) -> list[str]:
        """Return matching disease categories from WHO/CDC text."""
        lower = text.lower()
        return [disease for disease in DISEASE_DRUG_MAP if disease in lower]

    def _drugs_affected_by_outbreak(self, outbreak_text: str) -> list[str]:
        """Return drug names from formulary likely affected by an outbreak."""
        categories = self._classify_outbreak(outbreak_text)
        affected = []
        for cat in categories:
            keywords = DISEASE_DRUG_MAP.get(cat, [])
            for _, drug in self.drugs.iterrows():
                name_lower = drug["name"].lower()
                if any(kw.lower() in name_lower for kw in keywords):
                    if drug["name"] not in affected:
                        affected.append(drug["name"])
        return affected

    def _demand_signal_strength(self, days_ago: int) -> float:
        """Decay signal strength with time. 0-1 scale."""
        return max(0, 1.0 - days_ago / 30.0)

    # ── Seasonal baseline ─────────────────────────────────────────────────────

    def _seasonal_demand_curve(self, drug: pd.Series, weeks: int = 52) -> list[dict]:
        """Generate weekly demand curve with seasonal multiplier."""
        category = str(drug.get("category", "other")).lower()
        pattern_key = "other"
        for key in CATEGORY_PATTERN_MAP:
            if key in category:
                pattern_key = CATEGORY_PATTERN_MAP[key]
                break

        pattern = SEASONAL_PATTERNS.get(pattern_key, SEASONAL_PATTERNS["other"])
        now = datetime.now()
        rows = []
        for i in range(weeks):
            week_date = now - timedelta(weeks=weeks - i - 1)
            month_idx = week_date.month - 1
            multiplier = pattern[month_idx]
            base_demand = float(drug.get("base_price_per_kg", 50)) * 10  # proxy
            rows.append({
                "week": week_date.strftime("%Y-%m-%d"),
                "demand_index": round(multiplier * 100, 1),
                "seasonal_multiplier": round(multiplier, 3),
                "pattern": pattern_key,
            })
        return rows

    # ── ILI → antiviral demand signal ────────────────────────────────────────

    def _ili_to_demand_signal(self, ili_data: list[dict]) -> list[dict]:
        """Convert CDC ILI % into antiviral demand signals."""
        if not ili_data:
            return []
        # Normalize ILI pct to a 0-100 demand signal
        max_ili = max((r["ili_pct"] for r in ili_data), default=1)
        signals = []
        for row in ili_data[:self.lookback_weeks]:
            norm = round(row["ili_pct"] / max(max_ili, 0.01) * 100, 1)
            signals.append({
                "week": row["week_start"],
                "ili_pct": row["ili_pct"],
                "demand_signal": norm,
                "region": row["region"],
                "interpretation": (
                    "High antiviral demand expected" if norm > 60
                    else "Moderate antiviral demand" if norm > 30
                    else "Low antiviral demand"
                ),
            })
        return signals

    # ── WHO outbreaks → drug alerts ───────────────────────────────────────────

    def _outbreaks_to_drug_alerts(self, outbreaks: list[dict]) -> list[dict]:
        """Map WHO outbreak news to formulary drug demand alerts."""
        alerts = []
        for ob in outbreaks:
            text = f"{ob['title']} {ob['description']}"
            affected_drugs = self._drugs_affected_by_outbreak(text)
            if not affected_drugs:
                continue
            signal = self._demand_signal_strength(ob["days_ago"])
            if signal < 0.1:
                continue
            alerts.append({
                "outbreak": ob["title"][:120],
                "published": ob["published"],
                "days_ago": ob["days_ago"],
                "affected_drugs": affected_drugs,
                "signal_strength": round(signal, 2),
                "severity": "HIGH" if signal > 0.7 else "MEDIUM" if signal > 0.4 else "LOW",
                "source": "who_dons",
                "link": ob.get("link", ""),
            })
        alerts.sort(key=lambda x: x["signal_strength"], reverse=True)
        return alerts

    # ── Per-drug demand forecast ──────────────────────────────────────────────

    def _per_drug_forecast(self, who_alerts: list[dict], ili_signals: list[dict]) -> list[dict]:
        """Compute a demand forecast score per drug combining all signals."""
        # Base scores from seasonal curve
        drug_scores = {}
        now = datetime.now()
        month_idx = now.month - 1

        for _, drug in self.drugs.iterrows():
            category = str(drug.get("category", "other")).lower()
            pattern_key = "other"
            for key in CATEGORY_PATTERN_MAP:
                if key in category:
                    pattern_key = CATEGORY_PATTERN_MAP[key]
                    break
            pattern = SEASONAL_PATTERNS.get(pattern_key, SEASONAL_PATTERNS["other"])
            seasonal_score = pattern[month_idx] * 100

            drug_scores[drug["name"]] = {
                "drug_id": drug["id"],
                "drug_name": drug["name"],
                "category": drug.get("category", "unknown"),
                "base_demand_score": round(seasonal_score, 1),
                "outbreak_boost": 0.0,
                "ili_boost": 0.0,
                "total_demand_score": 0.0,
                "signal_sources": [],
                "trend": "STABLE",
            }

        # Add WHO outbreak boosts
        for alert in who_alerts:
            for drug_name in alert["affected_drugs"]:
                if drug_name in drug_scores:
                    boost = alert["signal_strength"] * 40  # max +40 from outbreak
                    drug_scores[drug_name]["outbreak_boost"] += boost
                    drug_scores[drug_name]["signal_sources"].append(
                        f"WHO: {alert['outbreak'][:60]}"
                    )

        # Add ILI boost for antivirals
        antiviral_drugs = [
            d["name"] for _, d in self.drugs.iterrows()
            if "antiviral" in str(d.get("category", "")).lower()
            or any(kw in d["name"].lower() for kw in ["tamiflu", "oseltamivir", "amantadine"])
        ]
        if ili_signals:
            latest_ili = ili_signals[0]["demand_signal"] if ili_signals else 0
            ili_boost = latest_ili * 0.3  # max +30 from flu season
            for name in antiviral_drugs:
                if name in drug_scores:
                    drug_scores[name]["ili_boost"] = round(ili_boost, 1)
                    drug_scores[name]["signal_sources"].append(
                        f"CDC ILI: {latest_ili:.0f}% demand signal"
                    )

        # Compute totals and trend
        for name, info in drug_scores.items():
            total = min(
                100,
                info["base_demand_score"] + info["outbreak_boost"] + info["ili_boost"]
            )
            info["total_demand_score"] = round(total, 1)
            info["outbreak_boost"] = round(info["outbreak_boost"], 1)
            info["signal_sources"] = info["signal_sources"][:3]
            if total > info["base_demand_score"] * 1.3:
                info["trend"] = "SPIKE"
            elif total > info["base_demand_score"] * 1.1:
                info["trend"] = "RISING"
            elif total < info["base_demand_score"] * 0.9:
                info["trend"] = "FALLING"
            else:
                info["trend"] = "STABLE"

        result = sorted(
            drug_scores.values(),
            key=lambda x: x["total_demand_score"],
            reverse=True,
        )
        return result

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Fetch all demand signals and return a comprehensive demand forecast.

        Returns
        -------
        dict with keys:
            who_alerts       : list — outbreak → drug mapping alerts
            ili_signals      : list — CDC flu surveillance weekly data
            drug_forecasts   : list — per-drug demand score with trend
            seasonal_curves  : dict — {drug_id: weekly curve}
            summary          : dict — KPI summary
            data_sources     : list — which sources responded
        """
        log.info("Running demand forecasting pipeline (Phase 8)…")
        data_sources = []

        # Fetch live data
        who_outbreaks = fetch_who_dons()
        if who_outbreaks:
            data_sources.append("who_dons")

        ili_raw = fetch_cdc_ili()
        if ili_raw:
            data_sources.append("cdc_ili")

        # Process signals
        who_alerts  = self._outbreaks_to_drug_alerts(who_outbreaks)
        ili_signals = self._ili_to_demand_signal(ili_raw)
        drug_forecasts = self._per_drug_forecast(who_alerts, ili_signals)

        # Seasonal curves for top 5 drugs
        top_drugs = [d for d in self.drugs.itertuples()][:5]
        seasonal_curves = {
            d.id: self._seasonal_demand_curve(self.drugs[self.drugs["id"] == d.id].iloc[0])
            for d in top_drugs
        }

        spike_count = sum(1 for d in drug_forecasts if d["trend"] == "SPIKE")
        rising_count = sum(1 for d in drug_forecasts if d["trend"] == "RISING")

        summary = {
            "total_drugs_tracked": len(drug_forecasts),
            "demand_spikes_detected": spike_count,
            "rising_demand": rising_count,
            "active_who_alerts": len(who_alerts),
            "latest_ili_signal": ili_signals[0]["demand_signal"] if ili_signals else None,
            "highest_demand_drug": drug_forecasts[0]["drug_name"] if drug_forecasts else "N/A",
            "data_sources": data_sources or ["seasonal_model"],
        }

        log.info(
            f"Demand forecast complete — "
            f"{spike_count} spikes | {rising_count} rising | "
            f"sources: {data_sources or ['seasonal_model']}"
        )

        return {
            "who_alerts":      who_alerts,
            "ili_signals":     ili_signals,
            "drug_forecasts":  drug_forecasts,
            "seasonal_curves": seasonal_curves,
            "summary":         summary,
            "data_sources":    data_sources or ["seasonal_model"],
        }


if __name__ == "__main__":
    df = DemandForecaster()
    result = df.run()
    s = result["summary"]
    print("\n" + "=" * 60)
    print("DEMAND FORECAST REPORT")
    print("=" * 60)
    print(f"Drugs tracked          : {s['total_drugs_tracked']}")
    print(f"Demand spikes detected : {s['demand_spikes_detected']}")
    print(f"Rising demand          : {s['rising_demand']}")
    print(f"Active WHO alerts      : {s['active_who_alerts']}")
    print(f"Data sources           : {s['data_sources']}")
    print(f"\nTop drug by demand     : {s['highest_demand_drug']}")
    if result["who_alerts"]:
        print(f"\nWHO Outbreak → Drug alerts:")
        for a in result["who_alerts"][:5]:
            print(f"  [{a['severity']:6s}] {a['outbreak'][:60]}")
            print(f"         → drugs: {', '.join(a['affected_drugs'][:3])}")
