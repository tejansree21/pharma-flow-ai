"""
PharmaFlow AI — Phase 6: Geopolitical Intelligence Engine (Live Data)
======================================================================
Replaces synthetic event generation with real data sources:

  Priority 1 — GDELT Project API (free, no key, updates every 15 min)
  Priority 2 — FDA Drug Shortage RSS + FDA Warning Letters RSS (free, authoritative)
  Priority 3 — NewsAPI (requires NEWS_API_KEY, falls back gracefully if missing)
  Fallback   — Synthetic event generation (original Phase 3 behaviour)

Each source feeds into the same NLP classification pipeline which extracts:
  - Affected country
  - Event type (mapped to existing taxonomy)
  - Severity score
  - Active/expired status

Output schema is IDENTICAL to the original module — no changes needed in
main.py, schemas.py, or any frontend component.

Usage
-----
  engine = GeopoliticalIntelligence()
  result = engine.run()   # returns dict: events_df, supplier_alerts, country_risk, summary
"""

import json
import logging
import random
import re
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.geopolitical")

_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"

# ── Data source URLs ──────────────────────────────────────────────────────────

GDELT_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc"
    "?query=pharmaceutical+supply+chain+disruption+OR+drug+shortage+OR"
    "+API+manufacturer+recall+OR+chemical+plant+explosion+pharma"
    "&mode=artlist&maxrecords=50&format=json&timespan=30d"
)

FDA_SHORTAGE_RSS = (
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/"
    "rss-feeds/drug-shortages/rss.xml"
)

FDA_WARNINGS_RSS = (
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/"
    "rss-feeds/warning-letters/rss.xml"
)

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# ── Event taxonomy (preserved from original) ─────────────────────────────────

EVENT_TYPES = {
    "trade_restriction":    {"severity": 75, "duration_days": 90},
    "factory_shutdown":     {"severity": 90, "duration_days": 45},
    "fda_import_alert":     {"severity": 80, "duration_days": 180},
    "sanctions":            {"severity": 95, "duration_days": 365},
    "logistics_disruption": {"severity": 55, "duration_days": 30},
    "currency_volatility":  {"severity": 40, "duration_days": 60},
    "regulatory_change":    {"severity": 50, "duration_days": 120},
    "political_instability":{"severity": 65, "duration_days": 75},
    "weather_disaster":     {"severity": 70, "duration_days": 21},
    "quality_scandal":      {"severity": 85, "duration_days": 120},
    "drug_shortage":        {"severity": 80, "duration_days": 90},
    "fda_warning_letter":   {"severity": 70, "duration_days": 180},
}

# Country risk baseline (preserved from original)
COUNTRY_RISK_BASELINE = {
    "China": 65, "India": 45, "Bangladesh": 55, "Pakistan": 70,
    "Mexico": 40, "Brazil": 42, "Germany": 12, "France": 14,
    "Switzerland": 8, "USA": 10, "UK": 11, "Ireland": 9,
    "Israel": 38, "South Korea": 22, "Japan": 15,
}

# ── NLP Keyword Classifier ────────────────────────────────────────────────────
# Keyword sets used to classify raw article text into event types + countries

_COUNTRY_PATTERNS = {
    "China":        ["china", "chinese", "beijing", "shanghai", "wuhan", "zhejiang", "guangdong"],
    "India":        ["india", "indian", "mumbai", "hyderabad", "ahmedabad", "gujarat", "andhra"],
    "Bangladesh":   ["bangladesh", "dhaka"],
    "Pakistan":     ["pakistan", "karachi", "lahore"],
    "Mexico":       ["mexico", "mexican", "guadalajara"],
    "Brazil":       ["brazil", "brazilian", "são paulo", "rio"],
    "Germany":      ["germany", "german", "berlin", "frankfurt", "bayer", "basf"],
    "France":       ["france", "french", "paris", "sanofi"],
    "Switzerland":  ["switzerland", "swiss", "zurich", "novartis", "roche"],
    "USA":          ["united states", "american", "fda", "us pharma", "new jersey", "new york"],
    "UK":           ["united kingdom", "britain", "british", "astrazeneca", "glaxo"],
    "Ireland":      ["ireland", "irish", "dublin"],
    "Israel":       ["israel", "israeli", "teva", "tel aviv"],
    "South Korea":  ["south korea", "korean", "seoul", "samsung bioepis"],
    "Japan":        ["japan", "japanese", "tokyo", "osaka", "takeda"],
}

_EVENT_PATTERNS = {
    "factory_shutdown":     ["shutdown", "halted", "closed", "explosion", "fire", "plant closure", "suspended"],
    "fda_import_alert":     ["import alert", "cgmp", "gmp violation", "483", "warning letter"],
    "fda_warning_letter":   ["warning letter", "fda warning", "form 483", "consent decree"],
    "drug_shortage":        ["shortage", "out of stock", "supply disruption", "supply shortage", "unavailable"],
    "trade_restriction":    ["tariff", "export ban", "trade restriction", "export control", "embargo"],
    "sanctions":            ["sanction", "sanctions", "restricted entity", "blacklist"],
    "logistics_disruption": ["port", "shipping delay", "congestion", "logistics", "freight", "supply chain delay"],
    "regulatory_change":    ["regulation", "compliance", "new guideline", "policy change", "requirement"],
    "political_instability":["protest", "unrest", "political", "instability", "strike", "coup"],
    "weather_disaster":     ["flood", "earthquake", "typhoon", "hurricane", "cyclone", "weather", "disaster"],
    "quality_scandal":      ["recall", "contamination", "impurity", "ndma", "nitrosamine", "quality failure"],
    "currency_volatility":  ["currency", "devaluation", "inflation", "exchange rate", "rupee", "yuan"],
}

_SEVERITY_KEYWORDS = {
    "critical": 20, "major": 15, "severe": 15, "halt": 15,
    "shutdown": 12, "ban": 12, "recall": 12, "shortage": 10,
    "warning": 8, "disruption": 8, "delay": 5, "concern": 3,
}


def _fetch_json(url: str, timeout: int = 8) -> Optional[dict]:
    """Fetch JSON from a URL with timeout. Returns None on failure."""
    try:
        req = Request(url, headers={"User-Agent": "PharmaFlowAI/6.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log.warning(f"JSON fetch failed [{url[:60]}…]: {exc}")
        return None


def _fetch_rss(url: str, timeout: int = 8) -> list[dict]:
    """Fetch and parse an RSS feed. Returns list of {title, description, pubDate} dicts."""
    try:
        req = Request(url, headers={"User-Agent": "PharmaFlowAI/6.0"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        items = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            desc  = item.findtext("description") or ""
            pub   = item.findtext("pubDate") or ""
            items.append({"title": title, "description": desc, "pubDate": pub})
        return items
    except Exception as exc:
        log.warning(f"RSS fetch failed [{url[:60]}…]: {exc}")
        return []


def _classify_text(text: str) -> tuple[str, str, float]:
    """
    Classify raw article text into (country, event_type, severity_bonus).
    Returns the best-matching country and event type based on keyword overlap.
    """
    lower = text.lower()

    # Country detection — most keyword hits wins
    country_scores: dict[str, int] = {}
    for country, keywords in _COUNTRY_PATTERNS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            country_scores[country] = hits
    country = max(country_scores, key=country_scores.get) if country_scores else "Unknown"

    # Event type detection
    event_scores: dict[str, int] = {}
    for event_type, keywords in _EVENT_PATTERNS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits:
            event_scores[event_type] = hits
    event_type = max(event_scores, key=event_scores.get) if event_scores else "logistics_disruption"

    # Severity bonus from keywords
    severity_bonus = sum(
        v for kw, v in _SEVERITY_KEYWORDS.items() if kw in lower
    )

    return country, event_type, float(min(severity_bonus, 30))


def _parse_date(date_str: str) -> tuple[datetime, int]:
    """Parse a date string (RSS or GDELT) into (datetime, days_ago)."""
    now = datetime.now()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(date_str[:25], fmt[:len(date_str[:25])])
            dt = dt.replace(tzinfo=None)
            days_ago = max(0, (now - dt).days)
            return dt, days_ago
        except Exception:
            continue
    # Fallback: treat as recent
    return now - timedelta(days=3), 3


# ═════════════════════════════════════════════════════════════════════════════
# Geopolitical Intelligence Engine
# ═════════════════════════════════════════════════════════════════════════════

class GeopoliticalIntelligence:
    """
    Fetches real geopolitical and pharma supply chain events from live sources,
    classifies them via keyword NLP, and maps them to supplier risk overlays.

    Data source priority:
      1. GDELT Project API (free, no key)
      2. FDA Shortage RSS + FDA Warning Letters RSS (free, authoritative)
      3. NewsAPI (optional, requires NEWS_API_KEY in environment)
      4. Synthetic fallback (original Phase 3 behaviour)

    Parameters
    ----------
    n_events         : int   — target number of events to collect (default 30)
    decay_halflife_days : float — score decay half-life in days (default 30)
    news_api_key     : str   — NewsAPI key (optional, read from env if not provided)
    force_synthetic  : bool  — skip live fetches and use synthetic only (for testing)
    """

    def __init__(
        self,
        n_events: int = 30,
        decay_halflife_days: float = 30.0,
        news_api_key: str = "",
        force_synthetic: bool = False,
    ):
        self.n_events = n_events
        self.decay_halflife = decay_halflife_days
        self.force_synthetic = force_synthetic

        # Pull news API key from env if not passed directly
        import os
        self.news_api_key = news_api_key or os.getenv("NEWS_API_KEY", "")

        self.suppliers    = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.risk_scores  = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")

        self.events_: Optional[pd.DataFrame] = None
        self.supplier_alerts_: Optional[pd.DataFrame] = None
        self.country_risk_index_: Optional[pd.DataFrame] = None
        self._data_source: str = "synthetic"

    # ── Source 1: GDELT ───────────────────────────────────────────────────────

    def _fetch_gdelt(self) -> list[dict]:
        """Fetch pharma supply chain articles from GDELT."""
        log.info("Fetching from GDELT…")
        data = _fetch_json(GDELT_URL)
        if not data or "articles" not in data:
            return []

        articles = data["articles"]
        log.info(f"GDELT returned {len(articles)} articles")

        rows = []
        for art in articles[:self.n_events]:
            title = art.get("title", "")
            url   = art.get("url", "")
            seendate = art.get("seendate", "")
            text = f"{title} {art.get('domain', '')} {url}"

            country, event_type, sev_bonus = _classify_text(text)
            if country == "Unknown":
                continue  # skip articles we can't geo-locate

            dt, days_ago = _parse_date(seendate)
            base_sev = EVENT_TYPES.get(event_type, {}).get("severity", 55)
            severity = float(np.clip(base_sev + sev_bonus, 10, 100))
            decay = np.exp(-np.log(2) / self.decay_halflife * days_ago)
            duration = EVENT_TYPES.get(event_type, {}).get("duration_days", 60)

            rows.append({
                "source": "gdelt",
                "event_type": event_type,
                "country": country,
                "event_date": dt.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "description": title[:200] if title else f"{event_type.replace('_',' ').title()} event in {country}",
                "severity": round(severity, 1),
                "duration_days": duration,
                "active": days_ago <= duration,
                "decay_factor": round(float(decay), 4),
                "effective_score": round(float(severity * decay), 1),
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
            })

        log.info(f"GDELT classified {len(rows)} geo-located events")
        return rows

    # ── Source 2: FDA RSS feeds ───────────────────────────────────────────────

    def _fetch_fda_shortage_rss(self) -> list[dict]:
        """Fetch FDA drug shortage announcements from the official RSS feed."""
        log.info("Fetching FDA shortage RSS…")
        items = _fetch_rss(FDA_SHORTAGE_RSS)
        log.info(f"FDA shortage RSS returned {len(items)} items")

        rows = []
        for item in items[:20]:
            text = f"{item['title']} {item['description']}"
            _, event_type, sev_bonus = _classify_text(text)
            event_type = "drug_shortage"  # override — this feed is always shortages

            dt, days_ago = _parse_date(item["pubDate"])
            severity = float(np.clip(80 + sev_bonus, 50, 100))
            decay = np.exp(-np.log(2) / self.decay_halflife * days_ago)
            duration = 90

            # FDA shortages are USA-centric but affect global supply
            country = "USA"

            rows.append({
                "source": "fda_shortage",
                "event_type": event_type,
                "country": country,
                "event_date": dt.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "description": item["title"][:200],
                "severity": round(severity, 1),
                "duration_days": duration,
                "active": days_ago <= duration,
                "decay_factor": round(float(decay), 4),
                "effective_score": round(float(severity * decay), 1),
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
            })

        log.info(f"FDA shortage RSS: {len(rows)} events parsed")
        return rows

    def _fetch_fda_warning_rss(self) -> list[dict]:
        """Fetch FDA warning letters from the official RSS feed."""
        log.info("Fetching FDA warning letters RSS…")
        items = _fetch_rss(FDA_WARNINGS_RSS)
        log.info(f"FDA warning letters RSS returned {len(items)} items")

        rows = []
        for item in items[:15]:
            text = f"{item['title']} {item['description']}"
            country, _, sev_bonus = _classify_text(text)
            event_type = "fda_warning_letter"

            dt, days_ago = _parse_date(item["pubDate"])
            severity = float(np.clip(70 + sev_bonus, 40, 100))
            decay = np.exp(-np.log(2) / self.decay_halflife * days_ago)
            duration = 180

            rows.append({
                "source": "fda_warning",
                "event_type": event_type,
                "country": country if country != "Unknown" else "USA",
                "event_date": dt.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "description": item["title"][:200],
                "severity": round(severity, 1),
                "duration_days": duration,
                "active": days_ago <= duration,
                "decay_factor": round(float(decay), 4),
                "effective_score": round(float(severity * decay), 1),
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
            })

        log.info(f"FDA warning letters: {len(rows)} events parsed")
        return rows

    # ── Source 3: NewsAPI ─────────────────────────────────────────────────────

    def _fetch_newsapi(self) -> list[dict]:
        """Fetch pharma supply chain news from NewsAPI (requires API key)."""
        if not self.news_api_key:
            log.info("NewsAPI skipped — NEWS_API_KEY not set")
            return []

        log.info("Fetching from NewsAPI…")
        params = (
            f"?q=pharmaceutical+supply+chain+disruption+OR+drug+shortage"
            f"+OR+API+manufacturer+shutdown"
            f"&language=en&sortBy=publishedAt&pageSize=30"
            f"&apiKey={self.news_api_key}"
        )
        data = _fetch_json(NEWSAPI_URL + params)
        if not data or data.get("status") != "ok":
            log.warning(f"NewsAPI error: {data.get('message') if data else 'no response'}")
            return []

        articles = data.get("articles", [])
        log.info(f"NewsAPI returned {len(articles)} articles")

        rows = []
        for art in articles[:20]:
            text = f"{art.get('title','')} {art.get('description','')}"
            country, event_type, sev_bonus = _classify_text(text)
            if country == "Unknown":
                continue

            published = art.get("publishedAt", "")
            dt, days_ago = _parse_date(published)
            base_sev = EVENT_TYPES.get(event_type, {}).get("severity", 55)
            severity = float(np.clip(base_sev + sev_bonus, 10, 100))
            decay = np.exp(-np.log(2) / self.decay_halflife * days_ago)
            duration = EVENT_TYPES.get(event_type, {}).get("duration_days", 60)

            title = art.get("title") or f"{event_type.replace('_',' ').title()} in {country}"

            rows.append({
                "source": "newsapi",
                "event_type": event_type,
                "country": country,
                "event_date": dt.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "description": title[:200],
                "severity": round(severity, 1),
                "duration_days": duration,
                "active": days_ago <= duration,
                "decay_factor": round(float(decay), 4),
                "effective_score": round(float(severity * decay), 1),
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
            })

        log.info(f"NewsAPI classified {len(rows)} geo-located events")
        return rows

    # ── Synthetic fallback ────────────────────────────────────────────────────

    def _generate_synthetic(self, n: int = 25) -> list[dict]:
        """Original Phase 3 synthetic event generator — used as fallback only."""
        log.info(f"Generating {n} synthetic fallback events…")
        random.seed(42); np.random.seed(42)
        now = datetime.now()
        countries = list(COUNTRY_RISK_BASELINE.keys())
        weights = [COUNTRY_RISK_BASELINE[c] for c in countries]
        total_w = sum(weights)
        probs = [w / total_w for w in weights]
        event_type_list = list(EVENT_TYPES.keys())

        rows = []
        for i in range(n):
            country = random.choices(countries, weights=probs)[0]
            event_type = random.choice(event_type_list)
            meta = EVENT_TYPES[event_type]
            days_ago = random.randint(0, 180)
            event_date = now - timedelta(days=days_ago)
            severity = float(np.clip(meta["severity"] + random.gauss(0, 10), 10, 100))
            decay = np.exp(-np.log(2) / self.decay_halflife * days_ago)
            desc_templates = {
                "trade_restriction": f"{country} imposes new export restrictions on pharmaceutical APIs",
                "factory_shutdown": f"Major API manufacturing facility in {country} halted due to safety inspection",
                "fda_import_alert": f"FDA issues import alert on {country}-sourced drug ingredients (cGMP violations)",
                "sanctions": f"New economic sanctions restrict pharmaceutical trade with {country}",
                "logistics_disruption": f"Port congestion and shipping delays from {country} affecting API delivery timelines",
                "currency_volatility": f"{country} currency depreciation causing API price instability",
                "regulatory_change": f"{country} updates pharmaceutical manufacturing regulations",
                "political_instability": f"Political unrest in {country} creates supply chain uncertainty",
                "weather_disaster": f"Severe weather event in {country} disrupts pharmaceutical manufacturing",
                "quality_scandal": f"Widespread quality failures detected at {country} API manufacturers",
                "drug_shortage": f"Drug shortage reported affecting {country} pharmaceutical distribution",
                "fda_warning_letter": f"FDA warning letter issued to {country} pharmaceutical facility",
            }
            rows.append({
                "source": "synthetic",
                "event_type": event_type,
                "country": country,
                "event_date": event_date.strftime("%Y-%m-%d"),
                "days_ago": days_ago,
                "description": desc_templates.get(event_type, f"{event_type} in {country}"),
                "severity": round(severity, 1),
                "duration_days": meta["duration_days"],
                "active": days_ago <= meta["duration_days"],
                "decay_factor": round(float(decay), 4),
                "effective_score": round(float(severity * decay), 1),
                "country_baseline_risk": COUNTRY_RISK_BASELINE.get(country, 50),
            })

        return rows

    # ── Event collection orchestrator ─────────────────────────────────────────

    def _collect_events(self) -> pd.DataFrame:
        """
        Collect events from all available sources.
        Returns a DataFrame with standardised columns and an event_id.
        """
        if self.force_synthetic:
            rows = self._generate_synthetic(self.n_events)
            self._data_source = "synthetic"
        else:
            rows = []

            # GDELT
            try:
                gdelt_rows = self._fetch_gdelt()
                rows.extend(gdelt_rows)
            except Exception as e:
                log.warning(f"GDELT fetch error: {e}")

            # FDA shortage RSS
            try:
                rows.extend(self._fetch_fda_shortage_rss())
            except Exception as e:
                log.warning(f"FDA shortage RSS error: {e}")

            # FDA warning letters RSS
            try:
                rows.extend(self._fetch_fda_warning_rss())
            except Exception as e:
                log.warning(f"FDA warning RSS error: {e}")

            # NewsAPI (optional)
            try:
                rows.extend(self._fetch_newsapi())
            except Exception as e:
                log.warning(f"NewsAPI error: {e}")

            if rows:
                real_count = sum(1 for r in rows if r["source"] != "synthetic")
                log.info(f"Collected {len(rows)} events from live sources ({real_count} real)")
                self._data_source = "live"

                # Top up with a few synthetic events if real data is sparse
                if len(rows) < 10:
                    log.info("Topping up with synthetic events (sparse real data)")
                    rows.extend(self._generate_synthetic(15))
                    self._data_source = "mixed"
            else:
                log.warning("All live sources failed — falling back to synthetic events")
                rows = self._generate_synthetic(self.n_events)
                self._data_source = "synthetic"

        # Build DataFrame
        df = pd.DataFrame(rows)

        # Deduplicate by (country, event_type, event_date) — real sources can overlap
        df = df.drop_duplicates(subset=["country", "event_type", "event_date"]).reset_index(drop=True)

        # Assign stable event IDs
        df.insert(0, "event_id", [f"EVT{i+1:03d}" for i in range(len(df))])

        df = df.sort_values("effective_score", ascending=False).reset_index(drop=True)

        log.info(
            f"Event collection complete — {len(df)} events | "
            f"source: {self._data_source} | "
            f"active: {df['active'].sum()}"
        )
        return df

    # ── Supplier overlay (unchanged logic) ────────────────────────────────────

    def _build_supplier_alerts(self, events: pd.DataFrame) -> pd.DataFrame:
        active_events = events[events["active"]].copy()

        rows = []
        for _, sup in self.suppliers.iterrows():
            country = sup.get("country", "Unknown")
            country_events = active_events[active_events["country"] == country]

            if country_events.empty:
                geo_score, top_event, top_event_type, n_events = 0.0, "No active events", "none", 0
            else:
                geo_score = float(min(country_events["effective_score"].sum(), 100))
                top_row = country_events.iloc[0]
                top_event = top_row["description"]
                top_event_type = top_row["event_type"]
                n_events = len(country_events)

            risk_row = self.risk_scores[self.risk_scores["supplier_id"] == sup["id"]]
            base_risk = float(risk_row["risk_score"].iloc[0]) if not risk_row.empty else 50.0
            risk_tier = str(risk_row["risk_tier"].iloc[0]) if not risk_row.empty else "Unknown"

            adjusted_risk = round(min(base_risk * 0.70 + geo_score * 0.30, 100), 1)
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
        if geo_score >= 60 or delta >= 15: return "HIGH"
        if geo_score >= 30 or delta >= 7:  return "MEDIUM"
        if geo_score >= 10:                return "LOW"
        return "CLEAR"

    # ── Country risk index (unchanged logic) ──────────────────────────────────

    def _build_country_risk_index(self, events: pd.DataFrame) -> pd.DataFrame:
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

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Run the full geopolitical intelligence pipeline.

        Returns
        -------
        dict with keys: events_df, supplier_alerts, country_risk, summary
        (Schema identical to original Phase 3 module.)
        """
        log.info("Starting geopolitical intelligence pipeline (Phase 6 — live data)…")

        events = self._collect_events()
        self.events_ = events

        supplier_alerts = self._build_supplier_alerts(events)
        self.supplier_alerts_ = supplier_alerts

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
            "data_source": self._data_source,
        }

        log.info(
            f"Geo intelligence complete — {summary['active_events']} active events | "
            f"{summary['suppliers_on_high_alert']} suppliers on HIGH alert | "
            f"source: {self._data_source}"
        )

        return {
            "events_df":       events,
            "supplier_alerts": supplier_alerts,
            "country_risk":    country_risk,
            "summary":         summary,
        }


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    force_syn = "--synthetic" in sys.argv
    engine = GeopoliticalIntelligence(n_events=30, force_synthetic=force_syn)
    result = engine.run()

    s = result["summary"]
    print("\n" + "=" * 65)
    print(f"GEOPOLITICAL INTELLIGENCE REPORT  [source: {s['data_source']}]")
    print("=" * 65)
    print(f"Total events              : {s['total_events']}")
    print(f"Currently active          : {s['active_events']}")
    print(f"Countries affected        : {s['countries_affected']}")
    print(f"Suppliers on HIGH alert   : {s['suppliers_on_high_alert']}")
    print(f"Suppliers on MEDIUM alert : {s['suppliers_on_medium_alert']}")
    print(f"Most dangerous country    : {s['most_dangerous_country']}")

    print("\nTOP 10 ACTIVE EVENTS:")
    top = result["events_df"][result["events_df"]["active"]].head(10)
    for _, ev in top.iterrows():
        src = ev.get("source", "?")
        print(f"  [{src:10s}] [{ev['event_type']:25s}] {ev['country']:12s} | {ev['effective_score']:5.1f} | {ev['days_ago']}d ago")
        print(f"           {ev['description'][:80]}")

    print("\nSUPPLIER ALERTS (HIGH):")
    high = result["supplier_alerts"][result["supplier_alerts"]["alert_level"] == "HIGH"]
    for _, sup in high.iterrows():
        print(f"  {sup['supplier_name']:<28} base={sup['base_risk_score']:.1f} → adj={sup['adjusted_risk_score']:.1f} (+{sup['risk_delta']:.1f})")
        print(f"    ↳ {sup['top_event'][:80]}")
