# SANKET Engine Pipeline Validation & Verification Report

**Document:** `ENGINE_VALIDATION.md`  
**Execution Date:** September 6, 2026  
**Pipeline Status:** Verified & Fully Operational  
**Test Suite:** 18 passing tests in `tests/` (`pytest`)  
**Input Source:** `DATA/project_monthly.csv` (Immutable)  

---

## 1. Pipeline Execution Summary

The four production pipeline stages were executed in sequence on the full 336-report canonical dataset:

```text
Pipeline Stage        Module             Input File                     Output Artifact                Records   Execution Time
-------------------------------------------------------------------------------------------------------------------------------
1. Timelines          sanket.timeline     DATA/project_monthly.csv       DATA/project_timelines.parquet 443,195   ~3.2 sec
2. Trajectories       sanket.trajectory   DATA/project_timelines.parquet DATA/project_trajectories.parquet 443,195 ~10.4 sec
3. Targets            sanket.targets      DATA/project_timelines.parquet DATA/project_targets.parquet      443,195 ~7.8 sec
4. Model Dataset      sanket.features     trajectories + targets         DATA/model_dataset.parquet     443,195   ~2.1 sec
```

* **Total Processed Rows:** **443,195 project-month records**
* **Total Unique Infrastructure Projects:** **115,693 projects**
* **Total Columns in Final Feature Matrix:** **75 columns**
* **Parquet File Size on Disk:** **33 MB** (compact, columnar, high-throughput)

---

## 2. Eligibility & Target Observability Cohorts

```text
Cohort / Flag                                Count      % of Total   Interpretation
--------------------------------------------------------------------------------------------------------------------------
Total Processed Observations                 443,195    100.0%       Full canonical longitudinal grain
eligible_features == 1                       261,178     58.9%       Has >= 3 prior observation history & valid C_base
target_observable_6m == 1                    246,114     55.5%       Uncensored 6-month forward window
target_observable_12m == 1                   224,060     50.6%       Uncensored 12-month forward window
Eligible Features AND Observable 12m Target  181,449     40.9%       Primary Gold-Standard Training Cohort for ML
```

> [!NOTE]
> The primary modeling cohort comprises **181,449 fully observable, leak-free project-month observations**, representing massive statistical power for gradient boosted trees.

---

## 3. Forward Target Distributions (Observable 12-Month Horizon, N = 224,060)

| Target Variable | Positive Count ($Y=1$) | Negative Count ($Y=0$) | Base Rate (%) | Description |
| :--- | :---: | :---: | :---: | :--- |
| `cost_overrun_12m` | 35,220 | 188,840 | **15.7%** | Cost baseline escalation $\ge 5\%$ over 12m |
| `schedule_overrun_12m` | 27,198 | 196,862 | **12.1%** | Target date drift $\ge 6\text{m}$ or dev increase |
| `overrun_composite_12m` | 57,997 | 166,063 | **25.9%** | **Primary Target:** Cost $\ge 5\%$ OR Schedule $\ge 6\text{m}$ |

### Cause Breakdown (`distress_type_12m`)
```text
Distress Category         Observation Count    Percentage
---------------------------------------------------------
NONE (Stable Projects)              166,063         74.1%
COST (Cost Escalation Only)          30,799         13.7%
SCHEDULE (Delay Drift Only)          22,777         10.2%
BOTH (Dual Deterioration)             4,421          2.0%
UNOBSERVABLE (Right-Censored)       219,135            —
```

---

## 4. Feature Coverage & Trajectory Health

Across all 443,195 records in `DATA/model_dataset.parquet`:

| Feature Name | Non-Null Count | Coverage (%) | Trajectory Role |
| :--- | :---: | :---: | :--- |
| `expenditure_to_baseline` | 411,463 | **92.8%** | Point-in-time financial burn percentage |
| `trajectory_risk_score` | 403,286 | **91.0%** | Transparent 0–100 heuristic distress score |
| `Z_peer_V_fin` | 311,945 | **70.4%** | Sector & scale peer-normalized progress z-score |
| `V_exp_1m` | 308,962 | **69.7%** | 1-month monthly expenditure velocity |
| `EWMA_V_fin` | 298,236 | **67.3%** | Chronological recursive EWMA ($\alpha=0.30$) |
| `V_fin_1m` | 282,730 | **63.8%** | 1-month financial progress velocity |
| `A_exp` | 269,715 | **60.9%** | Spending burn acceleration |
| `V_exp_3m` | 246,707 | **55.7%** | 3-month quarterly expenditure velocity |
| `A_fin` | 246,284 | **55.6%** | Progress acceleration / deceleration |
| `V_fin_3m` | 225,976 | **51.0%** | 3-month quarterly progress velocity |
| `cost_revision_ratio` | 185,911 | **41.9%** | Existing cost overrun ratio relative to sanctioned |
| `completion_date_drift` | 155,417 | **35.1%** | Target completion date slippage (months) |
| `schedule_deviation_change` | 100,312 | **22.6%** | Official delay escalation delta |
| `financial_physical_gap` | 18,108 | **4.1%** | Decoupling gap (active for 2022–2025 modern era) |
| `V_phys_1m` | 13,641 | **3.1%** | Physical progress velocity (2022–2025 modern era) |

### Trajectory Risk Score Summary
```text
Metric     Value
-------------------
Mean       20.61
Std Dev    17.95
Median     25.05
25th Pct    0.00
75th Pct   30.76
Max       100.00
```

---

## 5. Mandatory Leakage Test Results (`tests/test_leakage.py`)

All 7 mandatory leakage tests passed successfully:

1. **Test 1: Future Cost Revision:** Modifying `revised_cost` at $t+12$ from 1,000 to 5,000 resulted in **0.000% difference** across all feature columns at month $t$. (`PASSED ✓`)
2. **Test 2: Future Completion Revision:** Delaying future completion date by 36 months produced **0.000% difference** in schedule features at month $t$. (`PASSED ✓`)
3. **Test 3: Future Expenditure Spikes:** Introducing an extreme spend spike ($+₹99,999\text{ cr}$) at $t+1$ left historical velocity at $t$ completely unchanged. (`PASSED ✓`)
4. **Test 4: Point-in-Time Peer Statistics:** Sector peer distributions at month $t$ were strictly bounded to reports dated month $t$ and never consumed future data. (`PASSED ✓`)
5. **Test 5: Right-Censoring Rigor:** Incomplete future horizons strictly received `NaN` targets and `distress_type = "UNOBSERVABLE"`—**zero** false-negative zero imputations occurred. (`PASSED ✓`)
6. **Test 6: Duplicate Prevention:** Assembly engine asserted uniqueness and refused to process duplicate `(project_id, reporting_month)` pairs. (`PASSED ✓`)
7. **Test 7: Project Boundary Reset:** Group shifting operations strictly reset at project boundaries, preventing cross-project contamination. (`PASSED ✓`)

```text
============================== 18 passed in 1.27s ==============================
```
