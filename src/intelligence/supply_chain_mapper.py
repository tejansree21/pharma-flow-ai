"""
PharmaFlow AI — Phase 10: Multi-Tier Supply Chain Mapper
=========================================================
Maps Tier 1 (direct suppliers) → Tier 2 (their raw material suppliers)
→ Tier 3 (chemical feedstock sources) and detects hidden concentration
risks: cases where multiple Tier 1 suppliers share the same upstream source.

This is the structural vulnerability that broke pharma supply chains
during COVID — companies with 5 "diversified" suppliers discovered they
all sourced a critical intermediate from the same factory in Wuhan.

Architecture
------------
The module builds a directed graph:
  Tier 3 (raw feedstock) → Tier 2 (chemical manufacturer) → Tier 1 (API supplier) → Your company

Hidden concentration risk is detected when:
  - 2+ of your Tier 1 suppliers share the same Tier 2 node
  - That shared Tier 2 node supplies > CONCENTRATION_THRESHOLD % of your total
    volume for a given drug

All Tier 2/3 data is synthetic — modelled on realistic chemical supply
chain geography (China/India bulk chemical producers feeding into
specialized API manufacturers).
"""

import logging
import random
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.supplychain")

_ROOT     = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"

CONCENTRATION_THRESHOLD = 0.50   # flag if a shared upstream node covers >50% of drug volume


# ── Tier 2 & 3 entity pools ───────────────────────────────────────────────────

TIER2_CHEMICAL_MANUFACTURERS = [
    # (id, name, country, specialty)
    ("T2-CN-001", "Shandong Xintao Chemicals",    "China",  "API intermediates"),
    ("T2-CN-002", "Zhejiang Huahai Pharma Chem",  "China",  "Antiviral intermediates"),
    ("T2-CN-003", "Hubei Gedian Humanwell",        "China",  "Steroid precursors"),
    ("T2-IN-001", "Divi's Laboratories Chem",      "India",  "API intermediates"),
    ("T2-IN-002", "Hikal Chemical Industries",     "India",  "Fine chemicals"),
    ("T2-IN-003", "Aarti Industries",              "India",  "Specialty chemicals"),
    ("T2-DE-001", "BASF Pharma Solutions",         "Germany","Excipients & solvents"),
    ("T2-CH-001", "Lonza Chemical",                "Switzerland","High-purity intermediates"),
    ("T2-US-001", "Thermo Fisher Chemicals",       "USA",    "Research-grade intermediates"),
    ("T2-JP-001", "Nippon Shinyaku Chemicals",     "Japan",  "Fine chemicals"),
    ("T2-IN-004", "Dishman Carbogen Amcis",        "India",  "Carbohydrate chemistry"),
    ("T2-CN-004", "Sinochem Lantian",              "China",  "Bulk solvents"),
]

TIER3_FEEDSTOCK_SOURCES = [
    # (id, name, country, material)
    ("T3-CN-001", "Wuhan Chemical Industrial",    "China",  "Petroleum derivatives"),
    ("T3-CN-002", "Sinopec Chemical",             "China",  "Aromatic compounds"),
    ("T3-IN-001", "Gujarat Alkali & Chemicals",   "India",  "Chlorine compounds"),
    ("T3-SA-001", "SABIC Feedstock",              "Saudi Arabia", "Ethylene / propylene"),
    ("T3-US-001", "Dow Chemical Feedstock",       "USA",    "Specialty monomers"),
    ("T3-RU-001", "Sibur Holding",                "Russia", "Petrochemical feedstock"),
    ("T3-DE-001", "Evonik Feedstock",             "Germany","Specialty amino acids"),
    ("T3-CN-003", "Jiangsu Yangnong Chemical",   "China",  "Nitrogen compounds"),
]


class SupplyChainMapper:
    """
    Builds a 3-tier supply chain graph and detects hidden concentration risks.

    Parameters
    ----------
    seed : int — for reproducible random graph generation
    """

    def __init__(self, seed: int = 42):
        self.seed      = seed
        self.suppliers = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.drugs     = pd.read_csv(SYNTHETIC / "drugs.csv")
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")
        self._rng      = np.random.default_rng(seed)
        random.seed(seed)

        # Build the graph on init
        self._tier1_to_tier2: dict  = {}   # {t1_id: [t2_id, ...]}
        self._tier2_to_tier3: dict  = {}   # {t2_id: [t3_id, ...]}
        self._t2_pool = {t[0]: {"id":t[0],"name":t[1],"country":t[2],"specialty":t[3]} for t in TIER2_CHEMICAL_MANUFACTURERS}
        self._t3_pool = {t[0]: {"id":t[0],"name":t[1],"country":t[2],"material":t[3]}  for t in TIER3_FEEDSTOCK_SOURCES}
        self._build_graph()

    # ── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        """
        Assign Tier 2 suppliers to each Tier 1 supplier.
        Deliberately creates shared Tier 2 nodes to model realistic
        concentration risk (e.g. multiple API suppliers sharing one
        chemical manufacturer).
        """
        t2_ids = list(self._t2_pool.keys())
        t3_ids = list(self._t3_pool.keys())

        for _, sup in self.suppliers.iterrows():
            s_id    = sup["id"]
            country = sup.get("country", "Unknown")

            # Bias toward Tier 2 suppliers in the same region
            if country in ("China",):
                preferred_t2 = [t for t in t2_ids if "CN" in t]
            elif country in ("India",):
                preferred_t2 = [t for t in t2_ids if "IN" in t]
            elif country in ("Germany", "Switzerland", "France", "Ireland", "UK"):
                preferred_t2 = [t for t in t2_ids if any(c in t for c in ("DE","CH","US"))]
            else:
                preferred_t2 = t2_ids

            # 1–3 Tier 2 suppliers per Tier 1, with preference for regional ones
            n_t2 = int(self._rng.integers(1, 4))
            pool = preferred_t2 if len(preferred_t2) >= 2 else t2_ids
            chosen_t2 = list(self._rng.choice(pool, size=min(n_t2, len(pool)), replace=False))
            self._tier1_to_tier2[s_id] = chosen_t2

        for t2_id in t2_ids:
            # Each Tier 2 has 1–2 Tier 3 feedstock sources
            n_t3 = int(self._rng.integers(1, 3))
            # Bias toward country-appropriate Tier 3
            if "CN" in t2_id:
                preferred_t3 = [t for t in t3_ids if "CN" in t or "SA" in t]
            elif "IN" in t2_id:
                preferred_t3 = [t for t in t3_ids if "IN" in t or "CN" in t]
            else:
                preferred_t3 = [t for t in t3_ids if "US" in t or "DE" in t or "SA" in t]
            pool = preferred_t3 if preferred_t3 else t3_ids
            self._tier2_to_tier3[t2_id] = list(
                self._rng.choice(pool, size=min(n_t3, len(pool)), replace=False)
            )

    # ── Concentration risk detection ──────────────────────────────────────────

    def _detect_concentration_risks(self) -> list[dict]:
        """
        Find Tier 2 nodes shared by multiple Tier 1 suppliers.
        Returns list of concentration risk alerts.
        """
        # Map Tier 2 → list of Tier 1 suppliers using it
        t2_to_t1: dict = {}
        for t1_id, t2_list in self._tier1_to_tier2.items():
            for t2_id in t2_list:
                t2_to_t1.setdefault(t2_id, []).append(t1_id)

        risks = []
        for t2_id, t1_ids in t2_to_t1.items():
            if len(t1_ids) < 2:
                continue
            t2  = self._t2_pool[t2_id]
            t1s = self.suppliers[self.suppliers["id"].isin(t1_ids)]
            pct = len(t1_ids) / len(self.suppliers)

            risks.append({
                "shared_node_id":      t2_id,
                "shared_node_name":    t2["name"],
                "shared_node_country": t2["country"],
                "shared_node_tier":    2,
                "tier1_suppliers_affected": t1_ids,
                "tier1_supplier_names": t1s["name"].tolist(),
                "num_affected":        len(t1_ids),
                "pct_of_portfolio":    round(pct * 100, 1),
                "risk_level":         "CRITICAL" if pct >= 0.5 else "HIGH" if pct >= 0.3 else "MEDIUM",
                "description": (
                    f"{len(t1_ids)} of your Tier 1 suppliers all source from "
                    f"{t2['name']} ({t2['country']}). If this facility goes offline, "
                    f"{pct*100:.0f}% of your supplier portfolio is simultaneously impacted."
                ),
            })

        # Also detect Tier 3 shared nodes
        t3_to_t2: dict = {}
        for t2_id, t3_list in self._tier2_to_tier3.items():
            for t3_id in t3_list:
                t3_to_t2.setdefault(t3_id, []).append(t2_id)

        for t3_id, t2_ids in t3_to_t2.items():
            if len(t2_ids) < 2:
                continue
            t3 = self._t3_pool[t3_id]
            # How many Tier 1 suppliers are exposed?
            exposed_t1 = set()
            for t2_id in t2_ids:
                exposed_t1.update(self._tier1_to_tier2.get(t2_id, []))
            pct = len(exposed_t1) / len(self.suppliers)
            if pct < 0.2:
                continue
            risks.append({
                "shared_node_id":      t3_id,
                "shared_node_name":    t3["name"],
                "shared_node_country": t3["country"],
                "shared_node_tier":    3,
                "tier1_suppliers_affected": list(exposed_t1),
                "tier1_supplier_names": self.suppliers[self.suppliers["id"].isin(list(exposed_t1))]["name"].tolist(),
                "num_affected":        len(exposed_t1),
                "pct_of_portfolio":    round(pct * 100, 1),
                "risk_level":         "CRITICAL" if pct >= 0.6 else "HIGH" if pct >= 0.4 else "MEDIUM",
                "description": (
                    f"{t3['name']} ({t3['country']}) is a shared Tier 3 feedstock source "
                    f"feeding {len(t2_ids)} of your Tier 2 chemical manufacturers, "
                    f"which together supply {len(exposed_t1)} of your Tier 1 suppliers."
                ),
            })

        return sorted(risks, key=lambda x: x["num_affected"], reverse=True)

    # ── Network nodes + edges for frontend ───────────────────────────────────

    def _build_network(self) -> dict:
        """Return nodes and edges for graph visualisation."""
        nodes, edges = [], []

        # Root node — your company
        nodes.append({"id": "root", "label": "Your Company", "tier": 0, "type": "root"})

        # Tier 1
        for _, sup in self.suppliers.iterrows():
            risk_row  = self.risk_scores[self.risk_scores["supplier_id"] == sup["id"]]
            risk_score = float(risk_row["risk_score"].iloc[0]) if not risk_row.empty else 50.0
            nodes.append({
                "id":         sup["id"],
                "label":      sup["name"],
                "tier":       1,
                "type":       "tier1",
                "country":    sup.get("country", ""),
                "risk_score": round(risk_score, 0),
                "fda_approved": bool(sup.get("fda_approved", False)),
            })
            edges.append({"source": sup["id"], "target": "root", "tier": 1})

        # Tier 2
        for t2_id, t2 in self._t2_pool.items():
            nodes.append({
                "id":       t2_id,
                "label":    t2["name"],
                "tier":     2,
                "type":     "tier2",
                "country":  t2["country"],
                "specialty": t2["specialty"],
            })

        for t1_id, t2_ids in self._tier1_to_tier2.items():
            for t2_id in t2_ids:
                edges.append({"source": t2_id, "target": t1_id, "tier": 2})

        # Tier 3
        for t3_id, t3 in self._t3_pool.items():
            nodes.append({
                "id":      t3_id,
                "label":   t3["name"],
                "tier":    3,
                "type":    "tier3",
                "country": t3["country"],
                "material": t3["material"],
            })

        for t2_id, t3_ids in self._tier2_to_tier3.items():
            for t3_id in t3_ids:
                edges.append({"source": t3_id, "target": t2_id, "tier": 3})

        return {"nodes": nodes, "edges": edges}

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> dict:
        log.info("Building multi-tier supply chain map…")
        network  = self._build_network()
        risks    = self._detect_concentration_risks()
        critical = sum(1 for r in risks if r["risk_level"] == "CRITICAL")
        high     = sum(1 for r in risks if r["risk_level"] == "HIGH")

        # Country exposure summary across all tiers
        all_countries: dict = {}
        for node in network["nodes"]:
            if node.get("country") and node.get("tier", 0) > 0:
                c = node["country"]
                all_countries[c] = all_countries.get(c, 0) + 1

        summary = {
            "tier1_suppliers":       len(self.suppliers),
            "tier2_manufacturers":   len(self._t2_pool),
            "tier3_feedstock":       len(self._t3_pool),
            "total_nodes":           len(network["nodes"]),
            "total_edges":           len(network["edges"]),
            "concentration_risks":   len(risks),
            "critical_risks":        critical,
            "high_risks":            high,
            "countries_exposed":     len(all_countries),
            "highest_exposure_country": max(all_countries, key=all_countries.get) if all_countries else "N/A",
        }

        log.info(
            f"Supply chain map complete — {len(network['nodes'])} nodes | "
            f"{len(risks)} concentration risks ({critical} critical)"
        )

        return {
            "network":               network,
            "concentration_risks":   risks,
            "country_exposure":      [{"country": c, "node_count": n} for c, n in sorted(all_countries.items(), key=lambda x: -x[1])],
            "summary":               summary,
        }
