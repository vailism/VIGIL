"""
tests/test_targets.py

Unit tests for sanket.targets:
- Exact evaluation of 6m and 12m cost overrun targets
- Exact evaluation of schedule deterioration targets
- Composite overrun derivation
- Distress type categorization (NONE, COST, SCHEDULE, BOTH, UNOBSERVABLE)
- Strict right-censoring: unobserved future windows remain NaN
- Cold-start feature eligibility flag (eligible_features = 0 for first 3 rows)
"""

import pytest
import pandas as pd
import numpy as np
from sanket.targets import compute_targets

def test_targets_cost_overrun_and_censoring():
    # 15 continuous months of project observations
    months = [f"2020-{m:02d}" for m in range(1, 13)] + ["2021-01", "2021-02", "2021-03"]
    costs = [1000.0] * 10 + [1200.0] * 5 # Cost escalates from 1000 to 1200 at month 11 (2020-11)

    df = pd.DataFrame({
        "project_id": ["P1"] * 15,
        "reporting_month": months,
        "approved_cost": [1000.0] * 15,
        "revised_cost": costs,
    })

    targets = compute_targets(df)
    assert len(targets) == 15

    # Month 1 (2020-01): Month 11 is 10 months ahead.
    # For 6m horizon: window is 2020-02 to 2020-07 (costs are 1000.0 -> no overrun)
    assert targets.loc[0, "cost_overrun_6m"] == 0.0
    assert targets.loc[0, "cost_escalation_pct_6m"] == 0.0

    # For 12m horizon: window is 2020-02 to 2021-01 (cost escalates to 1200 at 2020-11 -> +20% overrun)
    assert targets.loc[0, "cost_overrun_12m"] == 1.0
    assert targets.loc[0, "cost_escalation_pct_12m"] == pytest.approx(0.20)
    assert targets.loc[0, "distress_type_12m"] == "COST"

    # Check right censoring:
    # Month 15 (2021-03) is the last month. Cannot observe +6m or +12m future.
    assert targets.loc[14, "target_observable_6m"] == 0
    assert targets.loc[14, "target_observable_12m"] == 0
    assert np.isnan(targets.loc[14, "cost_overrun_6m"])
    assert np.isnan(targets.loc[14, "cost_overrun_12m"])
    assert targets.loc[14, "distress_type_12m"] == "UNOBSERVABLE"

    # Month 10 (2020-10): Has 5 future months left before 2021-03.
    # 5 < 6 -> right censored for both 6m and 12m!
    assert targets.loc[9, "target_observable_6m"] == 0
    assert np.isnan(targets.loc[9, "cost_overrun_6m"])

def test_targets_schedule_overrun():
    months = [f"2020-{m:02d}" for m in range(1, 15)]
    # Target date shifts from 2022-01 to 2022-08 (+7 months) at month 7 (2020-07)
    rev_dates = ["2022-01"] * 6 + ["2022-08"] * 8

    df = pd.DataFrame({
        "project_id": ["P1"] * 14,
        "reporting_month": months,
        "approved_cost": [1000.0] * 14,
        "revised_completion_date": rev_dates,
        "schedule_deviation": [0.0] * 14
    })

    targets = compute_targets(df)

    # At Month 1 (2020-01): 6m window is [Feb..Jul]. At Jul date drifted +7m -> schedule overrun!
    assert targets.loc[0, "schedule_overrun_6m"] == 1.0
    assert targets.loc[0, "schedule_drift_months_6m"] == pytest.approx(7.0)
    assert targets.loc[0, "overrun_composite_6m"] == 1.0
    assert targets.loc[0, "distress_type_6m"] == "SCHEDULE"

def test_feature_eligibility_cold_start():
    df = pd.DataFrame({
        "project_id": ["P1"] * 5,
        "reporting_month": ["2020-01", "2020-02", "2020-03", "2020-04", "2020-05"],
        "approved_cost": [500.0] * 5
    })
    targets = compute_targets(df)

    # First 3 rows must have eligible_features = 0 (insufficient history)
    assert targets["eligible_features"].tolist() == [0, 0, 0, 1, 1]
