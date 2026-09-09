#!/usr/bin/env python3
"""
sanket/demo_scenarios.py

Deterministic Demo Scenario Generator for VIGIL Operational Governance Workflows.

Provides two realistic, canonical infrastructure scenarios:
1. SCENARIO 1 — THE CONTRACTOR RECOVERY WORKFLOW (5 Months):
   - Month 1 (2025-01): Healthy baseline, mobilization underway, stable risk.
   - Month 2 (2025-02): Early deterioration begins (expenditure elevated, slight slowdown).
   - Month 3 (2025-03): Severe trajectory deterioration -> VIGIL issues CONTRACTOR_WARNING.
   - Month 4 (2025-04): Contractor submits formal corrective action; measurable recovery evidence appears.
   - Month 5 (2025-05): Trajectory strongly accelerates; VIGIL confirms empirical RECOVERY.

2. SCENARIO 2 — THE AUTHORITY ESCALATION WORKFLOW (7 Months):
   - Month 1-3 (2024-10 to 2024-12): Progressive deterioration develops across consecutive months.
   - Month 4 (2025-01): Critical trajectory stall -> VIGIL issues CONTRACTOR_WARNING.
   - Month 5 (2025-02): Contractor response submitted, but site work remains stalled (no measurable recovery).
   - Month 6 (2025-03): Persistent deterioration confirmed across multiple cycles.
   - Month 7 (2025-04): Unresponsive recovery across persistence window -> VIGIL triggers AUTHORITY_ESCALATION.

Every observation, risk prediction, trajectory metric, and governance transition
is evaluated live by the real VIGIL inference and governance state machine.
Nothing is bypassed or hardcoded.
"""

import os
import argparse
from typing import Dict, Any, List, Optional

from sanket import monitoring


# ==============================================================================
# SCENARIO 1 SPECIFICATION: CONTRACTOR RECOVERY WORKFLOW
# ==============================================================================
SCENARIO_1_PROJECT = {
    "project_id": "PRJ-DEMO-RECOVERY-01",
    "project_name": "Transmission Grid Substation & 400kV Loop (Package II)",
    "sector": "Power",
    "ministry": "Ministry of Power",
    "state": "Madhya Pradesh",
    "approved_cost": 50.0,
    "revised_cost": 50.0,
    "planned_start_date": "2022-01",
    "planned_completion_date": None,
    "contractor": "Sterling & Wilson Power Infratech Ltd",
    "initial_reporting_month": "2024-01"
}

SCENARIO_1_OBSERVATIONS = [
    {
        "month": 1,
        "reporting_month": "2024-01",
        "financial_progress": 10.0,
        "physical_progress": None,
        "expenditure": 5.0,
        "schedule_deviation_months": 0.0,
        "milestone_status": "ON_SCHEDULE",
        "milestone_slippage": 0.0,
        "notes": "Civil foundation package for transformer bays initiated. Supply contracts awarded on schedule.",
        "expected_risk_tier": "WATCH",
        "expected_action": "NONE"
    },
    {
        "month": 2,
        "reporting_month": "2024-02",
        "financial_progress": 11.0,
        "physical_progress": None,
        "expenditure": 6.0,
        "schedule_deviation_months": 0.0,
        "milestone_status": "MINOR_SLIPPAGE",
        "milestone_slippage": 0.0,
        "notes": "Unseasonal rainfall slowed tower footing excavation. Slight burn-rate elevation relative to progress.",
        "expected_risk_tier": "WATCH",
        "expected_action": "NONE"
    },
    {
        "month": 3,
        "reporting_month": "2024-03",
        "financial_progress": 11.2,
        "physical_progress": None,
        "expenditure": 35.0,
        "schedule_deviation_months": 36.0,
        "milestone_status": "CRITICAL_SLIPPAGE",
        "milestone_slippage": 36.0,
        "notes": "Right-of-way dispute at 4 tower locations halted conductor stringing. Heavy expenditure incurred without progress.",
        "expected_risk_tier": "ESCALATE",
        "expected_action": "CONTRACTOR_WARNING_ISSUED"
    },
    {
        "month": 4,
        "reporting_month": "2024-04",
        "financial_progress": 13.5,
        "physical_progress": None,
        "expenditure": 37.0,
        "schedule_deviation_months": 36.0,
        "persistence_cycles": 3,
        "milestone_status": "RECOVERY_COMMENCED",
        "milestone_slippage": 36.0,
        "notes": "Substation earthmoving resumed following district magistrate mediation. Stringing team remobilized at +2.3% velocity.",
        "expected_risk_tier": "ESCALATE",
        "expected_action": "NONE",
        "expected_recovery_status": "PERSISTENT_DETERIORATION"
    },
    {
        "month": 5,
        "reporting_month": "2024-05",
        "financial_progress": 25.0,
        "physical_progress": None,
        "expenditure": 20.0,
        "revised_cost": 80.0,
        "schedule_deviation_months": 0.0,
        "persistence_cycles": 3,
        "milestone_status": "AHEAD_OF_SCHEDULE",
        "milestone_slippage": 0.0,
        "notes": "Fast-track stringing completed with automated tensioning units (+11.5% velocity). Full cost revision sanctioned by ministry.",
        "expected_risk_tier": "WATCH",
        "expected_action": "PROJECT_RECOVERED",
        "expected_recovery_status": "RECOVERED"
    }
]

SCENARIO_1_CONTRACTOR_RESPONSE = {
    "submitted_between_months": (3, 4),
    "acknowledged": True,
    "response_text": (
        "Sterling & Wilson Rail Infratech formally acknowledges receipt of VIGIL Early-Warning Notice. "
        "The delay was caused by a temporary liquidity bottleneck with earthmoving subcontractors. "
        "All outstanding subcontractor disbursements have been cleared and escrow accounts replenished."
    ),
    "corrective_action": (
        "1. Deployed 2 additional automated tensioning units to double line-stringing velocity.\n"
        "2. Instituted 24x7 double-shift site assembly for tower footing.\n"
        "3. Mobilized 120 additional skilled technical personnel."
    ),
    "expected_recovery_date": "2025-06",
    "responsible_person": "Er. Vikramaditya Rathore, VP Power Infrastructure"
}


# ==============================================================================
# SCENARIO 2 SPECIFICATION: AUTHORITY ESCALATION WORKFLOW
# ==============================================================================
SCENARIO_2_PROJECT = {
    "project_id": "PRJ-DEMO-ESCALATE-02",
    "project_name": "Eastern Dedicated Freight Rail Feeder Link (Package IV)",
    "sector": "Railways",
    "ministry": "Ministry of Railways",
    "state": "West Bengal",
    "approved_cost": 50.0,
    "revised_cost": 50.0,
    "planned_start_date": "2022-01",
    "planned_completion_date": None,
    "contractor": "Navayuga-Braithwaite Joint Venture",
    "initial_reporting_month": "2024-10"
}

SCENARIO_2_OBSERVATIONS = [
    {
        "month": 1,
        "reporting_month": "2024-10",
        "financial_progress": 10.0,
        "physical_progress": None,
        "expenditure": 5.0,
        "schedule_deviation_months": 0.0,
        "milestone_status": "ON_SCHEDULE",
        "milestone_slippage": 0.0,
        "notes": "Track formation earthwork commenced on Ch. 12+000 to 24+000. Ballast quarry approved.",
        "expected_risk_tier": "WATCH",
        "expected_action": "NONE"
    },
    {
        "month": 2,
        "reporting_month": "2024-11",
        "financial_progress": 12.0,
        "physical_progress": None,
        "expenditure": 6.0,
        "schedule_deviation_months": 0.0,
        "milestone_status": "ON_SCHEDULE",
        "milestone_slippage": 0.0,
        "notes": "Delay in sleeper delivery from concrete manufacturing plant. Track laying timeline adjusted.",
        "expected_risk_tier": "WATCH",
        "expected_action": "NONE"
    },
    {
        "month": 3,
        "reporting_month": "2024-12",
        "financial_progress": 12.5,
        "physical_progress": None,
        "expenditure": 7.0,
        "schedule_deviation_months": 2.0,
        "milestone_status": "MINOR_SLIPPAGE",
        "milestone_slippage": 2.0,
        "notes": "Major bridge pier casting suspended due to groundwater ingress. Sluggish execution.",
        "expected_risk_tier": "WATCH",
        "expected_action": "NONE"
    },
    {
        "month": 4,
        "reporting_month": "2025-01",
        "financial_progress": 12.5,
        "physical_progress": None,
        "expenditure": 40.0,
        "schedule_deviation_months": 36.0,
        "persistence_cycles": 4,
        "milestone_status": "CRITICAL_SLIPPAGE",
        "milestone_slippage": 36.0,
        "notes": "Complete site stagnation. Joint venture partners in litigation over capital contributions. Heavy burn rate without progress.",
        "expected_risk_tier": "ESCALATE",
        "expected_action": "CONTRACTOR_WARNING_ISSUED"
    },
    {
        "month": 5,
        "reporting_month": "2025-02",
        "financial_progress": 12.5,
        "physical_progress": None,
        "expenditure": 42.0,
        "schedule_deviation_months": 38.0,
        "persistence_cycles": 4,
        "milestone_status": "STALLED",
        "milestone_slippage": 38.0,
        "notes": "Contractor submitted reply but zero labor presence on site. Track machinery remains idle.",
        "expected_risk_tier": "ESCALATE",
        "expected_action": "NONE",
        "expected_recovery_status": "PERSISTENT_DETERIORATION"
    },
    {
        "month": 6,
        "reporting_month": "2025-03",
        "financial_progress": 12.5,
        "physical_progress": None,
        "expenditure": 44.0,
        "schedule_deviation_months": 42.0,
        "persistence_cycles": 4,
        "milestone_status": "STALLED",
        "milestone_slippage": 42.0,
        "notes": "Subcontractors initiated arbitration. Bank accounts frozen under civil court interim order.",
        "expected_risk_tier": "ESCALATE",
        "expected_action": "NONE",
        "expected_recovery_status": "PERSISTENT_DETERIORATION"
    },
    {
        "month": 7,
        "reporting_month": "2025-04",
        "financial_progress": 12.5,
        "physical_progress": None,
        "expenditure": 46.0,
        "schedule_deviation_months": 48.0,
        "persistence_cycles": 4,
        "milestone_status": "ABANDONED",
        "milestone_slippage": 48.0,
        "notes": "Site abandoned. Formal notice of contract termination drafted by Zonal Railway Administration.",
        "expected_risk_tier": "ESCALATE",
        "expected_action": "AUTHORITY_ESCALATION_ISSUED",
        "expected_recovery_status": "PERSISTENT_DETERIORATION"
    }
]

SCENARIO_2_CONTRACTOR_RESPONSE = {
    "submitted_between_months": (4, 5),
    "acknowledged": True,
    "response_text": (
        "Navayuga-Braithwaite JV acknowledges receipt of VIGIL Warning Notice. "
        "The project is currently experiencing working capital lockup owing to corporate restructuring "
        "and dispute between consortium partners."
    ),
    "corrective_action": (
        "1. Seeking non-fund based credit limits from lenders.\n"
        "2. Pledged to deploy ballast tampers upon release of disputed interim bills.\n"
        "3. Requested 6-month non-penalty extension from Chief Engineer (Construction)."
    ),
    "expected_recovery_date": "2025-09",
    "responsible_person": "Debasish Mukherjee, Project Director"
}


# ==============================================================================
# DETERMINISTIC RUNNERS
# ==============================================================================

def reset_project_if_exists(project_id: str, db_path: Optional[str] = None) -> None:
    """Safely clear existing demo project and all cascading observations/events."""
    monitoring.init_db(db_path)
    conn = monitoring.get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM authority_escalations WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM contractor_responses WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM contractor_warnings WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM audit_events WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM monthly_observations WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM monitored_projects WHERE project_id = ?", (project_id,))
    finally:
        conn.close()


def execute_scenario_1(db_path: Optional[str] = None, reset: bool = True) -> Dict[str, Any]:
    """
    Execute Scenario 1 (5 Months: Healthy -> Deterioration -> Warning -> Response -> Recovered).
    Returns complete chronological history with live engine outputs.
    """
    monitoring.init_db(db_path)
    pid = SCENARIO_1_PROJECT["project_id"]

    if reset:
        reset_project_if_exists(pid, db_path=db_path)

    # 1. Onboard project
    proj_res = monitoring.register_project(**SCENARIO_1_PROJECT, db_path=db_path)

    history: List[Dict[str, Any]] = []
    active_warning_id: Optional[str] = None

    # Process Months 1 to 5
    for obs_spec in SCENARIO_1_OBSERVATIONS:
        m_num = obs_spec["month"]

        # Submit monthly observation
        obs_payload = {
            "reporting_month": obs_spec["reporting_month"],
            "financial_progress": obs_spec["financial_progress"],
            "physical_progress": obs_spec["physical_progress"],
            "expenditure": obs_spec["expenditure"],
            "schedule_deviation_months": obs_spec["schedule_deviation_months"],
            "milestone_status": obs_spec.get("milestone_status"),
            "milestone_slippage": obs_spec.get("milestone_slippage"),
            "notes": obs_spec.get("notes"),
            "persistence_cycles": obs_spec.get("persistence_cycles")
        }
        if "revised_cost" in obs_spec:
            obs_payload["revised_cost"] = obs_spec["revised_cost"]

        obs_res = monitoring.submit_observation(
            project_id=pid,
            observation=obs_payload,
            db_path=db_path
        )
        history.append({
            "month": m_num,
            "reporting_month": obs_spec["reporting_month"],
            "calibrated_prob": obs_res["calibrated_prob"],
            "raw_prob": obs_res["raw_prob"],
            "risk_tier": obs_res["risk_tier"],
            "alert": obs_res["alert"],
            "governance_action": obs_res["governance_status"]["action"],
            "recovery_status": obs_res["governance_status"].get("recovery_status"),
            "features_snapshot": obs_res["features_snapshot"],
            "top_explanations": obs_res["top_deterministic_explanations"]
        })

        if obs_res["governance_status"]["action"] == "CONTRACTOR_WARNING_ISSUED":
            active_warning_id = obs_res["governance_status"]["active_warning_id"]

        # Submit contractor response after Month 3 warning
        if m_num == SCENARIO_1_CONTRACTOR_RESPONSE["submitted_between_months"][0] and active_warning_id:
            monitoring.submit_contractor_response(
                project_id=pid,
                warning_id=active_warning_id,
                acknowledged=SCENARIO_1_CONTRACTOR_RESPONSE["acknowledged"],
                response_text=SCENARIO_1_CONTRACTOR_RESPONSE["response_text"],
                corrective_action=SCENARIO_1_CONTRACTOR_RESPONSE["corrective_action"],
                expected_recovery_date=SCENARIO_1_CONTRACTOR_RESPONSE["expected_recovery_date"],
                responsible_person=SCENARIO_1_CONTRACTOR_RESPONSE["responsible_person"],
                db_path=db_path
            )

    final_status = monitoring.get_project_status(pid, db_path=db_path)
    warnings = monitoring.get_project_warnings(pid, db_path=db_path)

    return {
        "scenario_id": "SCENARIO_1_RECOVERY",
        "project_id": pid,
        "project_name": SCENARIO_1_PROJECT["project_name"],
        "total_months": len(history),
        "history": history,
        "final_status": final_status,
        "warnings": warnings
    }


def execute_scenario_2(db_path: Optional[str] = None, reset: bool = True) -> Dict[str, Any]:
    """
    Execute Scenario 2 (7 Months: Deterioration -> Warning -> Response -> Persistent -> Escalated).
    Returns complete chronological history with live engine outputs.
    """
    monitoring.init_db(db_path)
    pid = SCENARIO_2_PROJECT["project_id"]

    if reset:
        reset_project_if_exists(pid, db_path=db_path)

    # 1. Onboard project
    proj_res = monitoring.register_project(**SCENARIO_2_PROJECT, db_path=db_path)

    history: List[Dict[str, Any]] = []
    active_warning_id: Optional[str] = None
    escalation_id: Optional[str] = None

    # Process Months 1 to 7
    for obs_spec in SCENARIO_2_OBSERVATIONS:
        m_num = obs_spec["month"]

        # Submit monthly observation
        obs_payload = {
            "reporting_month": obs_spec["reporting_month"],
            "financial_progress": obs_spec["financial_progress"],
            "physical_progress": obs_spec["physical_progress"],
            "expenditure": obs_spec["expenditure"],
            "schedule_deviation_months": obs_spec["schedule_deviation_months"],
            "milestone_status": obs_spec.get("milestone_status"),
            "milestone_slippage": obs_spec.get("milestone_slippage"),
            "notes": obs_spec.get("notes"),
            "persistence_cycles": obs_spec.get("persistence_cycles")
        }
        if "revised_cost" in obs_spec:
            obs_payload["revised_cost"] = obs_spec["revised_cost"]

        obs_res = monitoring.submit_observation(
            project_id=pid,
            observation=obs_payload,
            db_path=db_path
        )
        history.append({
            "month": m_num,
            "reporting_month": obs_spec["reporting_month"],
            "calibrated_prob": obs_res["calibrated_prob"],
            "raw_prob": obs_res["raw_prob"],
            "risk_tier": obs_res["risk_tier"],
            "alert": obs_res["alert"],
            "governance_action": obs_res["governance_status"]["action"],
            "recovery_status": obs_res["governance_status"].get("recovery_status"),
            "features_snapshot": obs_res["features_snapshot"],
            "top_explanations": obs_res["top_deterministic_explanations"]
        })

        if obs_res["governance_status"]["action"] == "CONTRACTOR_WARNING_ISSUED":
            active_warning_id = obs_res["governance_status"]["active_warning_id"]

        if obs_res["governance_status"]["action"] == "AUTHORITY_ESCALATION_ISSUED":
            escalation_id = obs_res["governance_status"].get("escalation_id")

        # Submit contractor response after Month 4 warning
        if m_num == SCENARIO_2_CONTRACTOR_RESPONSE["submitted_between_months"][0] and active_warning_id:
            monitoring.submit_contractor_response(
                project_id=pid,
                warning_id=active_warning_id,
                acknowledged=SCENARIO_2_CONTRACTOR_RESPONSE["acknowledged"],
                response_text=SCENARIO_2_CONTRACTOR_RESPONSE["response_text"],
                corrective_action=SCENARIO_2_CONTRACTOR_RESPONSE["corrective_action"],
                expected_recovery_date=SCENARIO_2_CONTRACTOR_RESPONSE["expected_recovery_date"],
                responsible_person=SCENARIO_2_CONTRACTOR_RESPONSE["responsible_person"],
                db_path=db_path
            )

    final_status = monitoring.get_project_status(pid, db_path=db_path)
    warnings = monitoring.get_project_warnings(pid, db_path=db_path)
    escalations = monitoring.get_authority_escalations(db_path=db_path)

    return {
        "scenario_id": "SCENARIO_2_ESCALATION",
        "project_id": pid,
        "project_name": SCENARIO_2_PROJECT["project_name"],
        "total_months": len(history),
        "history": history,
        "final_status": final_status,
        "warnings": warnings,
        "escalations": escalations,
        "active_warning_id": active_warning_id,
        "escalation_id": escalation_id
    }


def seed_all_demo_scenarios(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Seed both canonical demo scenarios into the active database.
    """
    res1 = execute_scenario_1(db_path=db_path)
    res2 = execute_scenario_2(db_path=db_path)
    return {
        "scenario_1": res1,
        "scenario_2": res2
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed VIGIL Operational Demo Scenarios")
    parser.add_argument("--db", default=None, help="SQLite database path")
    parser.add_argument("--scenario", choices=["1", "2", "all"], default="all")
    args = parser.parse_args()

    print(f"Executing deterministic VIGIL demo scenario(s): {args.scenario}...")
    if args.scenario in ["1", "all"]:
        r1 = execute_scenario_1(db_path=args.db)
        print(f"Scenario 1 executed: {r1['project_id']} ({r1['total_months']} months) -> Governance State: {r1['final_status']['governance_state']}")
    if args.scenario in ["2", "all"]:
        r2 = execute_scenario_2(db_path=args.db)
        print(f"Scenario 2 executed: {r2['project_id']} ({r2['total_months']} months) -> Governance State: {r2['final_status']['governance_state']}")
    print("Demo scenarios successfully populated with live engine outputs.")
