#!/usr/bin/env python3
"""
sanket/portfolio.py

Portfolio Sanitization & Governance Presentation Layer.

Constructs a presentation- and governance-safe project portfolio from
the longitudinal research dataset.

Key Objectives:
1. Distinguish genuine infrastructure project entities from MoSPI executive
   macro-summary extraction artifacts (e.g. Table 1-12 front matter).
2. Protect legitimate large infrastructure projects (e.g. Mumbai-Ahmedabad
   Bullet Train, Kudankulam Nuclear Power, Polavaram Irrigation) based on
   identity/source semantics rather than arbitrary cost thresholds.
3. Partition portfolio into:
   - ACTIVE MONITORING PORTFOLIO: Latest observation >= 2024-01
   - HISTORICAL ARCHIVE: Latest observation < 2024-01
   - RAW EXTRACTED IDENTITIES: 115,693 archive entity tokens
4. Calculate authentic capital exposure and calibrated risk-weighted exposure
   using only the latest point-in-time observation of genuine active projects.
"""

import os
import re
import json
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import pandas as pd

from sanket.inference import load_inference_engine, get_risk_tier
from sanket.storage import get_artifact

# Indian States and Union Territories for state-level aggregate detection
INDIAN_STATES = {
    "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR", "CHHATTISGARH", "GOA", "GUJARAT",
    "HARYANA", "HIMACHAL PRADESH", "JHARKHAND", "KARNATAKA", "KERALA", "MADHYA PRADESH",
    "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND", "ODISHA", "ORISSA", "PUNJAB",
    "RAJASTHAN", "SIKKIM", "TAMIL NADU", "TELANGANA", "TRIPURA", "UTTAR PRADESH", "UTTARAKHAND",
    "WEST BENGAL", "DELHI", "JAMMU & KASHMIR", "JAMMU AND KASHMIR", "LADAKH", "CHANDIGARH",
    "PUDUCHERRY", "ANDAMAN & NICOBAR", "DADRA & NAGAR HAVELI", "DAMAN & DIU"
}

# MoSPI Central Sectors
CENTRAL_SECTORS = {
    "RAILWAYS", "ROAD TRANSPORT AND HIGHWAYS", "POWER", "PETROLEUM", "TELECOMMUNICATIONS",
    "COAL", "FERTILISERS", "STEEL", "CIVIL AVIATION", "SHIPPING", "PORTS AND LIGHTHOUSES",
    "URBAN DEVELOPMENT", "WATER RESOURCES", "ATOMIC ENERGY", "MINES", "HEAVY INDUSTRY"
}

# Regex patterns indicating Flash Report macro-summary tables
MACRO_NAME_PATTERNS = [
    r"\bFLA\b",
    r"\bLAS\b",
    r"\bMULTI\s*STATE\b",
    r"\bTOTAL\b",
    r"\bSUMMARY\b",
    r"\bALL\s*INDIA\b",
    r"\bGRAND\s*TOTAL\b",
    r"\bSTATEMENT\b",
    r"\bTABLE\b",
    r"RAILWAYS\s+(?:LAS|AS|A|AND)?\s*ROAD TRANSPORT",
    r"ROAD TRANSPORT AND HIGHWAYS\s+(?:LAS|AS|AND)?\s*SHIPPING",
    r"PETROLEUM\s+(?:LAS|AS|A|AND)?\s*POWER",
    r"COAL\s+(?:LAS|AS|A|AND)?\s*MINES",
    r"^\s*FL\s+",
    r"^\s*F\s+"
]

_COMPILED_MACRO_PATTERNS = [re.compile(p, re.IGNORECASE) for p in MACRO_NAME_PATTERNS]


def is_macro_summary_artifact(project_name: Any, project_id: Any) -> Tuple[bool, str]:
    """
    Determine whether an entity represents an executive macro-summary table row
    rather than an individual infrastructure project.

    Returns:
        (is_artifact: bool, reason: str)
    """
    p_name = str(project_name or "").strip().upper()
    p_id = str(project_id or "").strip()

    # Rule 1: Pure macro keywords as standalone phrase or title
    for pattern in _COMPILED_MACRO_PATTERNS:
        if pattern.search(p_name):
            # If it has an official MoSPI ID and the name is a real project (e.g. mentions railway stretch),
            # check if it is purely an aggregate row or an actual project
            if not p_id.startswith("PRJ_"):
                # Official MoSPI ID: check if it is literally a summary title
                if p_name in ["TOTAL", "SUMMARY", "ALL INDIA", "MULTI STATE", "GRAND TOTAL"]:
                    return True, f"OFFICIAL_MACRO_TITLE_{p_name}"
                # Otherwise, it is a legitimate project with multi-state route or extracted FLA prefix
                continue
            return True, f"MACRO_KEYWORD_{pattern.pattern}"

    # Rule 2: Pure state summary tables (e.g. "KERALA", "ARUNACHAL PRADESH", "STATE : BIHAR")
    clean_state_name = re.sub(r"^STATE\s*:\s*", "", p_name).strip()
    if clean_state_name in INDIAN_STATES:
        return True, f"STATE_SUMMARY_ROW: {clean_state_name}"

    # Rule 3: Pure sector summary tables (e.g. "RAILWAYS", "POWER", "ROAD TRANSPORT AND HIGHWAYS")
    clean_sec_name = re.sub(r"^SECTOR\s*:\s*", "", p_name).strip()
    clean_sec_name = re.sub(r"[\*\s]+$", "", clean_sec_name).strip()
    if clean_sec_name in CENTRAL_SECTORS:
        return True, f"SECTOR_SUMMARY_ROW: {clean_sec_name}"

    # Rule 4: Synthetic extraction ID with executive summary tokens
    if p_id.startswith("PRJ_"):
        if any(tok in p_name for tok in ["EXECUTIVE", "HIGHLIGHTS", "FLASH REPORT", "OVERVIEW"]):
            return True, "SYNTHETIC_EXECUTIVE_SUMMARY"

    return False, "GENUINE"


def is_genuine_project(project_id: Any, project_name: Any) -> bool:
    """
    Check if entity is a genuine infrastructure project.

    A genuine project must:
    1. Not be a macro-summary or executive summary artifact.
    2. Possess an official MoSPI project identifier:
       - 8-9 digit numeric MoSPI code (e.g. 180100210, 220100133)
       - OCMS official alphanumeric code (e.g. N22000463, N02000028)
    """
    p_id = str(project_id or "").strip()
    p_name = str(project_name or "").strip()

    # Exclude macro artifacts
    is_macro, _ = is_macro_summary_artifact(p_name, p_id)
    if is_macro:
        return False

    # Genuine MoSPI IDs:
    # 1. 8-9 digit numeric MoSPI codes (e.g. 180100210, 220100133)
    # 2. OCMS official codes starting with letter + digits (e.g. N22000463, N02000028)
    if re.match(r"^\d{8,9}$", p_id):
        return True
    if re.match(r"^[A-Z]\d{7,8}$", p_id):
        return True

    return False


def format_inr_currency(val_in_cr: float) -> str:
    """
    Format monetary amounts in ₹ Crore according to governance guidelines:
    - < ₹1,000 Cr: ₹X.X Cr
    - ₹1,000–₹99,999 Cr: ₹X,XXX Cr
    - >= ₹1,00,000 Cr: ₹X.XX Lakh Cr
    """
    if val_in_cr is None or np.isnan(val_in_cr):
        return "₹0.0 Cr"

    abs_val = abs(val_in_cr)
    sign = "-" if val_in_cr < 0 else ""

    if abs_val < 1000.0:
        return f"{sign}₹{abs_val:.1f} Cr"
    elif abs_val < 100000.0:
        return f"{sign}₹{round(abs_val):,} Cr"
    else:
        lakh_cr = abs_val / 100000.0
        return f"{sign}₹{lakh_cr:.2f} Lakh Cr"


class SanitizedPortfolio:
    """
    In-memory representation of the presentation-safe project portfolio.
    """

    def __init__(
        self,
        dataset_path: str = "DATA/model_dataset.parquet",
        lead_time_path: str = "DATA/event_lead_times.parquet"
    ):
        self.dataset_path = dataset_path
        self.lead_time_path = lead_time_path
        self._load_and_sanitize()

    def _load_and_sanitize(self):
        metrics_path = get_artifact("DATA/portfolio_metrics.json")
        active_path = get_artifact("DATA/portfolio_active.parquet")
        hist_path = get_artifact("DATA/portfolio_historical.parquet")
        gen_path = get_artifact("DATA/portfolio_genuine.parquet")

        if not os.path.exists(metrics_path):
            raise FileNotFoundError(f"Portfolio metrics cache '{metrics_path}' missing.")

        with open(metrics_path, "r") as f:
            data = json.load(f)

        meta = data.get("_metadata", {})
        if "source_dataset_hash" not in meta or "schema_version" not in meta:
            raise ValueError("Invalid portfolio_metrics.json: missing required artifact metadata.")

        metrics = data.get("metrics", {})

        self.active_projects_df = pd.read_parquet(active_path)
        self.historical_projects_df = pd.read_parquet(hist_path)
        self.genuine_projects_df = pd.read_parquet(gen_path)

        if len(self.active_projects_df) != metrics.get("active_project_count"):
            raise ValueError("Artifact corruption: active_projects_df row count does not match metrics.")

        for k, v in metrics.items():
            setattr(self, k, v)

        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            self._engine = load_inference_engine()
        return self._engine

    def get_summary_dict(self) -> Dict[str, Any]:
        """Return high-level summary metrics for Command Center."""
        return {
            "active_project_count": self.active_project_count,
            "archive_entity_count": self.total_archive_entities,
            "genuine_project_count": self.genuine_project_count,
            "historical_project_count": self.historical_project_count,
            "latest_data_month": self.latest_data_month,
            "archive_start": self.archive_start,
            "archive_end": self.archive_end,
            "active_baseline_exposure": self.active_baseline_exposure,
            "exposure_in_escalate": self.exposure_in_escalate,
            "risk_weighted_exposure": self.risk_weighted_exposure,
            "watch_count": self.watch_count,
            "review_count": self.review_count,
            "escalate_count": self.escalate_count,
            "normal_count": self.normal_count,
            "historical_median_warning_lead": self.historical_median_warning_lead,
            # Backwards-compatible aliases for frontend
            "total_projects": self.active_project_count,
            "projects_currently_scored": self.active_project_count,
            "total_baseline_exposure": self.active_baseline_exposure,
            "median_warning_lead_time": self.historical_median_warning_lead,
            "sector_breakdown": self.sector_breakdown
        }

    def get_interventions(
        self,
        limit: int = 30,
        sector: Optional[str] = None,
        min_risk_tier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Return prioritized active genuine projects sorted by risk-weighted exposure.
        """
        df = self.active_projects_df.copy()

        if sector:
            s_term = sector.strip().lower()
            df = df[df["sector_display"].astype(str).str.lower() == s_term]

        tier_ranks = {"NORMAL": 0, "WATCH": 1, "REVIEW": 2, "ESCALATE": 3}
        if min_risk_tier:
            min_t = min_risk_tier.strip().upper()
            if min_t in tier_ranks:
                df = df[df["risk_tier"].map(lambda t: tier_ranks.get(t, 0) >= tier_ranks[min_t])]

        ranked_df = df.sort_values(by="risk_weighted_exposure", ascending=False).head(limit)

        results = []
        for _, r in ranked_df.iterrows():
            results.append({
                "project_id": str(r["project_id"]),
                "project_name": str(r.get("project_name", r["project_id"])),
                "sector": str(r.get("sector_display", "OTHER")),
                "state": str(r.get("state", "—")),
                "ministry": str(r.get("ministry", "—")),
                "reporting_month": str(r.get("reporting_month", "")),
                "latest_observation": str(r.get("reporting_month", "")),
                "latest_risk": float(r["latest_risk"]),
                "risk_tier": str(r["risk_tier"]),
                "latest_risk_tier": str(r["risk_tier"]),
                "baseline_cost": float(r["baseline_cost"]),
                "baseline_exposure": float(r["baseline_cost"]),
                "priority_score": float(r["risk_weighted_exposure"]),
                "risk_weighted_exposure": float(r["risk_weighted_exposure"])
            })

        return {
            "total_eligible": len(df),
            "limit": limit,
            "methodology_note": (
                "Transparent prioritization ranking metric weighting capital exposure by 12-month "
                "deterioration probability for oversight resource allocation. "
                "Priority Score = Calibrated Risk × Baseline Exposure."
            ),
            "projects": results
        }


# Global singleton cache for portfolio
_PORTFOLIO_INSTANCE: Optional[SanitizedPortfolio] = None


def get_portfolio(dataset_path: str = "DATA/model_dataset.parquet") -> SanitizedPortfolio:
    """Retrieve or initialize singleton SanitizedPortfolio."""
    global _PORTFOLIO_INSTANCE
    if _PORTFOLIO_INSTANCE is None:
        _PORTFOLIO_INSTANCE = SanitizedPortfolio(dataset_path=dataset_path)
    return _PORTFOLIO_INSTANCE
