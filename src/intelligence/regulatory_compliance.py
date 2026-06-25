"""
PharmaFlow AI — Phase 10: Regulatory Compliance Engine
=======================================================
Tracks FDA approval status, audit schedules, warning letter history,
and auto-generates supplier compliance documentation for audit use.

Regulatory data sources used:
  - FDA Orange Book approval status (from synthetic supplier data)
  - FDA CGMP inspection cycle (synthetic — 2-year cycle for approved suppliers)
  - WHO Prequalification status (synthetic)

In production: connect to FDA's real-time data via:
  - FDA Drug Establishments database (download.open.fda.gov)
  - FDA Warning Letters RSS feed (already wired in geopolitical_intelligence.py)
  - EMA EudraVigilance API
"""

import logging
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
log = logging.getLogger("pharma.compliance")

_ROOT     = Path(__file__).resolve().parents[2]
SYNTHETIC = _ROOT / "data" / "synthetic"
PROCESSED = _ROOT / "data" / "processed"

# ── Regulatory frameworks tracked ─────────────────────────────────────────────

FRAMEWORKS = {
    "FDA_CGMP":      {"full_name": "FDA Current Good Manufacturing Practice",       "cycle_years": 2},
    "EMA_GMP":       {"full_name": "European Medicines Agency GMP",                "cycle_years": 2},
    "WHO_PQ":        {"full_name": "WHO Prequalification Programme",               "cycle_years": 3},
    "ISO_9001":      {"full_name": "ISO 9001 Quality Management System",           "cycle_years": 3},
    "ICH_Q7":        {"full_name": "ICH Q7 Active Pharmaceutical Ingredient Guide","cycle_years": 2},
}

WARNING_LETTER_TYPES = [
    "CGMP non-compliance — data integrity",
    "CGMP non-compliance — contamination control",
    "Failure to establish laboratory controls",
    "Inadequate process validation",
    "Inadequate cleaning validation",
    "Unapproved drug product",
]


class ComplianceEngine:
    """
    Tracks and reports regulatory compliance status for all Tier 1 suppliers.

    Parameters
    ----------
    seed : int — for reproducible synthetic compliance data
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.suppliers   = pd.read_csv(SYNTHETIC / "suppliers.csv")
        self.risk_scores = pd.read_csv(PROCESSED / "supplier_risk_scores.csv")
        self._rng = np.random.default_rng(seed)
        self._now = datetime.now()

    # ── Compliance record generation ──────────────────────────────────────────

    def _last_audit_date(self, supplier_id: str, framework: str, fda_approved: bool) -> datetime:
        """Compute a synthetic last audit date for a supplier-framework pair."""
        seed = sum(ord(c) for c in supplier_id + framework)
        rng  = np.random.default_rng(self.seed + seed)
        cycle_years = FRAMEWORKS[framework]["cycle_years"]

        if not fda_approved and framework in ("FDA_CGMP", "EMA_GMP"):
            # Non-approved: may never have been audited or very long ago
            days_ago = int(rng.integers(365, 365 * 5))
        else:
            # Approved: within the cycle window, some overdue
            overdue_prob = 0.25
            if rng.random() < overdue_prob:
                days_ago = int(rng.integers(cycle_years * 365, cycle_years * 365 + 500))
            else:
                days_ago = int(rng.integers(30, cycle_years * 365 - 30))

        return self._now - timedelta(days=days_ago)

    def _warning_letters(self, supplier_id: str, risk_tier: str) -> list[dict]:
        """Generate synthetic warning letter history."""
        seed = sum(ord(c) for c in supplier_id)
        rng  = np.random.default_rng(self.seed + seed)

        # Higher risk tier → more likely to have warning letters
        prob = {"Low": 0.05, "Moderate": 0.20, "High": 0.50, "Critical": 0.80}.get(risk_tier, 0.20)
        if rng.random() > prob:
            return []

        n = int(rng.integers(1, 3))
        letters = []
        for i in range(n):
            days_ago = int(rng.integers(30, 1095))
            letters.append({
                "date":     (self._now - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                "type":     rng.choice(WARNING_LETTER_TYPES),
                "resolved": days_ago > 180,
                "days_ago": days_ago,
            })
        return sorted(letters, key=lambda x: x["days_ago"])

    def _compliance_status(self, last_audit: datetime, cycle_years: int) -> dict:
        """Determine compliance status based on audit date and cycle."""
        days_since = (self._now - last_audit).days
        cycle_days  = cycle_years * 365
        days_until_due = cycle_days - days_since

        if days_since > cycle_days + 90:
            status = "OVERDUE"
            urgency = "CRITICAL"
        elif days_since > cycle_days:
            status = "OVERDUE"
            urgency = "HIGH"
        elif days_until_due <= 90:
            status = "DUE_SOON"
            urgency = "MEDIUM"
        else:
            status = "CURRENT"
            urgency = "LOW"

        next_due = (last_audit + timedelta(days=cycle_days)).strftime("%Y-%m-%d")
        return {
            "status":         status,
            "urgency":        urgency,
            "last_audit":     last_audit.strftime("%Y-%m-%d"),
            "next_due":       next_due,
            "days_since_audit": days_since,
            "days_until_due":  days_until_due,
        }

    # ── Per-supplier compliance record ────────────────────────────────────────

    def _supplier_compliance(self, sup: pd.Series) -> dict:
        s_id        = sup["id"]
        fda_approved = bool(sup.get("fda_approved", False))
        risk_row    = self.risk_scores[self.risk_scores["supplier_id"] == s_id]
        risk_tier   = str(risk_row["risk_tier"].iloc[0]) if not risk_row.empty else "Moderate"

        # Per-framework compliance
        framework_records = {}
        for fw, meta in FRAMEWORKS.items():
            last_audit = self._last_audit_date(s_id, fw, fda_approved)
            status     = self._compliance_status(last_audit, meta["cycle_years"])
            framework_records[fw] = {
                "framework": fw,
                "full_name": meta["full_name"],
                **status,
                "approved": fda_approved if fw in ("FDA_CGMP", "EMA_GMP") else (self._rng.random() > 0.3),
            }

        # Overall compliance score (0–100)
        status_scores = {"CURRENT": 100, "DUE_SOON": 65, "OVERDUE": 20}
        avg_score = sum(status_scores.get(v["status"], 50) for v in framework_records.values()) / len(FRAMEWORKS)

        # Warning letters
        letters = self._warning_letters(s_id, risk_tier)
        active_letters = [l for l in letters if not l["resolved"]]

        overall_status = "COMPLIANT"
        if active_letters or any(v["status"] == "OVERDUE" for v in framework_records.values()):
            if active_letters and any(v["urgency"] == "CRITICAL" for v in framework_records.values()):
                overall_status = "NON_COMPLIANT"
            else:
                overall_status = "AT_RISK"

        return {
            "supplier_id":       s_id,
            "supplier_name":     sup["name"],
            "country":           sup.get("country", ""),
            "fda_approved":      fda_approved,
            "risk_tier":         risk_tier,
            "compliance_score":  round(avg_score, 1),
            "overall_status":    overall_status,
            "frameworks":        list(framework_records.values()),
            "warning_letters":   letters,
            "active_warnings":   len(active_letters),
            "total_warnings":    len(letters),
            "next_audit_due":    min(
                (v["next_due"] for v in framework_records.values()),
                default="N/A",
            ),
            "overdue_frameworks": [
                fw for fw, v in framework_records.items() if v["status"] == "OVERDUE"
            ],
        }

    # ── Audit report text ─────────────────────────────────────────────────────

    def generate_audit_report(self, supplier_id: str) -> dict:
        """Generate a plain-text audit compliance report for one supplier."""
        sup_row = self.suppliers[self.suppliers["id"] == supplier_id]
        if sup_row.empty:
            return {"error": f"Supplier {supplier_id} not found"}
        sup    = sup_row.iloc[0]
        record = self._supplier_compliance(sup)
        now_str = self._now.strftime("%d %B %Y")

        lines = [
            f"PHARMAFLOW AI — SUPPLIER COMPLIANCE REPORT",
            f"Generated: {now_str}",
            f"{'='*60}",
            f"",
            f"SUPPLIER: {record['supplier_name']}",
            f"Country : {record['country']}",
            f"Supplier ID: {supplier_id}",
            f"FDA Approved: {'Yes' if record['fda_approved'] else 'No'}",
            f"Risk Tier: {record['risk_tier']}",
            f"Overall Compliance Status: {record['overall_status']}",
            f"Compliance Score: {record['compliance_score']:.0f}/100",
            f"",
            f"REGULATORY FRAMEWORK STATUS",
            f"{'-'*40}",
        ]
        for fw in record["frameworks"]:
            lines += [
                f"  {fw['full_name']}",
                f"    Status       : {fw['status']}",
                f"    Last Audit   : {fw['last_audit']}",
                f"    Next Due     : {fw['next_due']}",
                f"    Approved     : {'Yes' if fw['approved'] else 'No'}",
                f"",
            ]

        lines += [f"WARNING LETTERS: {record['total_warnings']} total, {record['active_warnings']} active"]
        if record["warning_letters"]:
            for wl in record["warning_letters"]:
                status = "ACTIVE" if not wl["resolved"] else "Resolved"
                lines.append(f"  [{status}] {wl['date']} — {wl['type']}")
        else:
            lines.append("  None on record.")

        lines += [
            f"",
            f"OVERDUE FRAMEWORKS: {', '.join(record['overdue_frameworks']) or 'None'}",
            f"",
            f"GENERATED BY: PharmaFlow AI v4.0.0",
            f"DISCLAIMER: This report is based on synthetic data for demonstration purposes.",
            f"In production, connect to FDA.gov and EMA.europa.eu for live regulatory data.",
        ]

        return {
            "supplier_id":   supplier_id,
            "supplier_name": record["supplier_name"],
            "report_date":   now_str,
            "report_text":   "\n".join(lines),
            "compliance_score": record["compliance_score"],
            "overall_status":   record["overall_status"],
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> dict:
        log.info("Running compliance engine…")
        records = [self._supplier_compliance(sup) for _, sup in self.suppliers.iterrows()]
        records.sort(key=lambda x: x["compliance_score"])

        compliant    = sum(1 for r in records if r["overall_status"] == "COMPLIANT")
        at_risk      = sum(1 for r in records if r["overall_status"] == "AT_RISK")
        non_compliant= sum(1 for r in records if r["overall_status"] == "NON_COMPLIANT")
        total_active_warnings = sum(r["active_warnings"] for r in records)
        overdue_any  = sum(1 for r in records if r["overdue_frameworks"])

        summary = {
            "total_suppliers":        len(records),
            "compliant":              compliant,
            "at_risk":                at_risk,
            "non_compliant":          non_compliant,
            "total_active_warnings":  total_active_warnings,
            "suppliers_with_overdue": overdue_any,
            "avg_compliance_score":   round(sum(r["compliance_score"] for r in records) / max(len(records),1), 1),
            "lowest_compliance_supplier": records[0]["supplier_name"] if records else "N/A",
        }

        log.info(
            f"Compliance complete — {non_compliant} non-compliant | "
            f"{at_risk} at risk | {total_active_warnings} active warnings"
        )
        return {"suppliers": records, "summary": summary}
