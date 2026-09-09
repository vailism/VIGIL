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
        actual_dataset_path = get_artifact(self.dataset_path)
        actual_lead_time_path = get_artifact(self.lead_time_path)
        
        if not os.path.exists(actual_dataset_path):
            raise FileNotFoundError(f"Dataset '{actual_dataset_path}' does not exist.")

        engine = load_inference_engine()
        self.engine = engine
        features = engine["features"]
        cat_features = engine["categorical_features"]

        cols = list(set(features + [
            "project_id", "project_name", "sector", "sector_clean",
            "ministry", "state", "reporting_month", "approved_cost",
            "revised_cost", "C_base", "expenditure", "financial_progress"
        ]))

        import pyarrow.parquet as pq
        schema = pq.read_schema(actual_dataset_path)
        actual_cols = [c for c in cols if c in schema.names]

        df_full = pd.read_parquet(actual_dataset_path, columns=actual_cols)

        # Total extracted identities across longitudinal archive
        self.total_archive_entities = int(df_full["project_id"].nunique())
        self.archive_start = str(df_full["reporting_month"].min())
        self.archive_end = str(df_full["reporting_month"].max())
        self.latest_data_month = self.archive_end

        # Deduplicate strictly by reporting_month to extract latest observation per entity
        df_sorted = df_full.sort_values("reporting_month")
        latest_all = df_sorted.groupby("project_id").last().reset_index()

        # Identify genuine projects vs macro artifacts
        genuine_flags = [
            is_genuine_project(pid, name)
            for pid, name in zip(latest_all["project_id"], latest_all["project_name"])
        ]
        latest_all["is_genuine"] = genuine_flags

        # Partition
        genuine_df = latest_all[latest_all["is_genuine"]].copy()
        self.genuine_project_count = int(len(genuine_df))
        self.excluded_macro_summary_count = int(self.total_archive_entities - self.genuine_project_count)

        # Active vs Historical partition
        # Reference date: latest observation >= '2024-01' is ACTIVE
        active_mask = genuine_df["reporting_month"] >= "2024-01"
        self.active_projects_df = genuine_df[active_mask].copy().reset_index(drop=True)
        self.historical_projects_df = genuine_df[~active_mask].copy().reset_index(drop=True)

        self.active_project_count = int(len(self.active_projects_df))
        self.historical_project_count = int(len(self.historical_projects_df))

        # Score active portfolio using frozen inference engine
        X_active = pd.DataFrame(index=self.active_projects_df.index)
        for f in features:
            if f in self.active_projects_df.columns:
                X_active[f] = self.active_projects_df[f]
            else:
                X_active[f] = np.nan

        for cat in cat_features:
            if cat in X_active.columns:
                X_active[cat] = X_active[cat].astype("category")

        raw_probs = engine["model"].predict_proba(X_active)[:, 1]
        cal_probs = engine["calibrator"].predict(raw_probs)

        self.active_projects_df["latest_risk"] = np.round(cal_probs, 4)
        self.active_projects_df["risk_tier"] = [get_risk_tier(p) for p in cal_probs]
        self.active_projects_df["latest_risk_tier"] = self.active_projects_df["risk_tier"]

        cbase_vals = pd.to_numeric(self.active_projects_df["C_base"], errors="coerce").fillna(0).values
        self.active_projects_df["baseline_cost"] = np.round(cbase_vals, 2)
        self.active_projects_df["priority_score"] = np.round(
            self.active_projects_df["latest_risk"] * self.active_projects_df["baseline_cost"], 2
        )
        self.active_projects_df["risk_weighted_exposure"] = self.active_projects_df["priority_score"]

        # Clean display columns
        self.active_projects_df["sector_display"] = (
            self.active_projects_df["sector_clean"]
            .fillna(self.active_projects_df.get("sector", "OTHER"))
            .fillna("OTHER")
        )
        self.active_projects_df["state"] = self.active_projects_df["state"].fillna("—")
        self.active_projects_df["ministry"] = self.active_projects_df["ministry"].fillna("—")

        # Operational risk counts (active portfolio only)
        self.watch_count = int((self.active_projects_df["risk_tier"] == "WATCH").sum())
        self.review_count = int((self.active_projects_df["risk_tier"] == "REVIEW").sum())
        self.escalate_count = int((self.active_projects_df["risk_tier"] == "ESCALATE").sum())
        self.normal_count = int((self.active_projects_df["risk_tier"] == "NORMAL").sum())

        # Exposure metrics (active portfolio only)
        self.active_baseline_exposure = float(round(self.active_projects_df["baseline_cost"].sum(), 2))
        esc_mask = self.active_projects_df["risk_tier"] == "ESCALATE"
        self.exposure_in_escalate = float(round(self.active_projects_df.loc[esc_mask, "baseline_cost"].sum(), 2))
        self.risk_weighted_exposure = float(round(self.active_projects_df["risk_weighted_exposure"].sum(), 2))

        # Historical median lead time benchmark
        self.historical_median_warning_lead = 3.0
        if os.path.exists(actual_lead_time_path):
            try:
                df_lt = pd.read_parquet(actual_lead_time_path)
                if "event_lead_time" in df_lt.columns:
                    self.historical_median_warning_lead = float(df_lt["event_lead_time"].median())
            except Exception:
                self.historical_median_warning_lead = 3.0

        # Sector breakdown (sanitized active portfolio)
        sector_groups = self.active_projects_df.groupby("sector_display")
        breakdown = []
        for s_name, s_df in sector_groups:
            breakdown.append({
                "sector": str(s_name),
                "total_projects": int(len(s_df)),
                "escalate_count": int((s_df["risk_tier"] == "ESCALATE").sum()),
                "review_count": int((s_df["risk_tier"] == "REVIEW").sum()),
                "watch_count": int((s_df["risk_tier"] == "WATCH").sum()),
                "total_exposure": round(float(s_df["baseline_cost"].sum()), 2)
            })
        breakdown.sort(key=lambda x: x["total_exposure"], reverse=True)
        self.sector_breakdown = breakdown

        # Also prepare all genuine projects scored/indexed for lookup
        self.genuine_projects_df = genuine_df

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
