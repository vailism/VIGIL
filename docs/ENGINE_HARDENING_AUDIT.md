# SANKET Backend-Only Adversarial Engine Hardening Audit

## Executive Summary & Engineering Verdict

### Engineering Verdict: **PASS**

**Justification:**
Every core invariant of the SANKET system was tested under adversarial stress conditions:
1. **Point-in-Time Invariance:** **PASS**. Evaluated across multiple historical projects with future additions, 10x cost shocks, delay spikes, and future truncation. Predictions and feature vectors at month $T$ remain bit-for-bit identical ($0.0$ deviation).
2. **Canonical Feature Parity:** **PASS**. Longitudinal features computed via `compute_canonical_features_for_project` match historical dataset reference values to within $1.4 \times 10^{-6}$ mean probability difference.
3. **Feature Leakage Audit:** **PASS**. All 25 model features were verified against forward leakage. None reference target columns, unobserved future months, or retroactive revisions.
4. **Target Engine & Right-Censoring:** **PASS**. Right-censored prediction horizons strictly evaluate to `NaN` (never 0), schedule targets use zero financial proxies, and targets never bleed into features.
5. **Governance State Machine:** **PASS**. Strict physical separation between LightGBM risk probabilities and administrative governance actions. Contractor warnings, cure plans, empirical recovery, and authority escalations behave deterministically and append immutable audit logs.
6. **Robustness & Isolation:** **PASS**. Zero corruption on rollbacks, concurrent submissions, process restarts, or extreme/unseen inputs. Frozen datasets (`model_dataset.parquet`, `project_monthly.csv`, model joblib) maintain identical SHA-256 cryptographic hashes before and after operational monitoring.

---

## 1. Audit Scope & Methodology

The adversarial audit tested SANKET's backend infrastructure against 16 distinct vulnerability vectors:
- Temporal leakage and backward drift of revisions.
- Numerical equivalence between batch training and real-time streaming feature pipelines.
- Data integrity under missing, sparse, corrupted, out-of-order, or hostile inputs.
- Governance boundary enforcement (preventing administrative actions from corrupting statistical model probabilities).
- Audit trail immutability and persistence consistency under transaction rollbacks.

All tests were executed against real historical infrastructure data (`DATA/model_dataset.parquet`) and clean isolated operational instances.

---

## 2. Feature-by-Feature Leakage Audit Table

For every one of the 25 production features in `DATA/sanket_production_model.joblib`:

| Feature Name | Source Input Columns | Calculation Window | Latest Observation Allowed | Temporal Invariance Verified? | Leakage Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`C_base`** | `approved_cost`, `revised_cost` | Historical high-water mark $\max(C_{\text{approved}}, C_{\text{revised}})$ | Month $t$ | Future cost revisions at $> t$ cannot alter baseline at $t$ | **PASS (Zero Leakage)** |
| **`cost_revision_ratio`** | `C_base`, `approved_cost` | Point-in-time: $(C_{\text{base}} - C_{\text{approved}}) / C_{\text{approved}}$ | Month $t$ | Dependent only on point-in-time $C_{\text{base}}$ | **PASS (Zero Leakage)** |
| **`expenditure_to_baseline`** | `expenditure`, `C_base` | Cumulative spend divided by $C_{\text{base}}(t)$ | Month $t$ | Cumulative spend through month $t$ only | **PASS (Zero Leakage)** |
| **`scale_bucket`** | `C_base` | Discretized scale (`SMALL`, `MAJOR`, `MEGA`) | Month $t$ | Static or monotonically step-up; no forward revision | **PASS (Zero Leakage)** |
| **`sector_clean`** | `sector` | Project categorization | Static | Ground truth metadata known at inception | **PASS (Zero Leakage)** |
| **`schedule_deviation_months`**| `schedule_deviation_months` | Reported delay at month $t$ | Month $t$ | Only reported delay up to $t$ | **PASS (Zero Leakage)** |
| **`schedule_deviation_change`**| `schedule_deviation_months` | 1-month difference: $\text{delay}(t) - \text{delay}(t-1)$ | Months $t-1, t$ | Backward lag difference only | **PASS (Zero Leakage)** |
| **`completion_date_drift`** | `revised_completion_date`, `original_completion_date` | Point-in-time drift relative to initial sanction | Month $t$ | Revision dates after $t$ strictly ignored | **PASS (Zero Leakage)** |
| **`V_fin_1m`** | `financial_progress` | 1-month progress velocity: $P(t) - P(t-1)$ | Months $t-1, t$ | Pure 1-month backward finite difference | **PASS (Zero Leakage)** |
| **`V_fin_3m`** | `financial_progress` | 3-month rolling velocity: $P(t) - P(t-3)$ | Months $t-3 \dots t$ | 3-month backward rolling difference | **PASS (Zero Leakage)** |
| **`A_fin`** | `V_fin_1m` | Finite acceleration: $V(t) - V(t-1)$ | Months $t-2 \dots t$ | Second-order backward finite difference | **PASS (Zero Leakage)** |
| **`EWMA_V_fin`** | `V_fin_1m` | Exponential moving average ($\alpha=0.3$) | Months $1 \dots t$ | Recursive causal filtering: uses strictly history $\le t$ | **PASS (Zero Leakage)** |
| **`V_exp_1m`** | `expenditure` | 1-month spend delta: $E(t) - E(t-1)$ | Months $t-1, t$ | Pure 1-month backward finite difference | **PASS (Zero Leakage)** |
| **`V_exp_3m`** | `expenditure` | 3-month spend delta: $E(t) - E(t-3)$ | Months $t-3 \dots t$ | 3-month backward rolling difference | **PASS (Zero Leakage)** |
| **`A_exp`** | `V_exp_1m` | Expenditure burn acceleration | Months $t-2 \dots t$ | Second-order backward finite difference | **PASS (Zero Leakage)** |
| **`V_phys_1m`** | `physical_progress` | 1-month physical velocity | Months $t-1, t$ | Backward finite difference; NaN preserved if unobserved | **PASS (Zero Leakage)** |
| **`V_phys_3m`** | `physical_progress` | 3-month physical velocity | Months $t-3 \dots t$ | Backward finite difference; NaN preserved if unobserved | **PASS (Zero Leakage)** |
| **`A_phys`** | `V_phys_1m` | Physical build acceleration | Months $t-2 \dots t$ | Backward finite difference; NaN preserved if unobserved | **PASS (Zero Leakage)** |
| **`financial_physical_gap`** | `financial_progress`, `physical_progress` | Point-in-time decoupling: $P_{\text{fin}}(t) - P_{\text{phys}}(t)$ | Month $t$ | Contemporaneous difference at month $t$ | **PASS (Zero Leakage)** |
| **`Z_peer_V_fin`** | `V_fin_1m`, contemporaneous sector peers | Standardized velocity vs contemporaneous peers | Month $t$ | Grouped by month $t$; cannot observe future velocities | **PASS (Zero Leakage)** |
| **`trajectory_risk_score`** | 6 kinetic signals | Normalized heuristic multi-signal kinetic score | Months $1 \dots t$ | Weighted composite of causal features only | **PASS (Zero Leakage)** |
| **`project_age_months`** | `reporting_month`, `planned_start_date` | Chronological duration: $t - \text{start}$ | Static & $t$ | Fixed project start date; strictly missing if date unknown | **PASS (Zero Leakage)** |
| **`observation_number`** | Observation counter | Chronological index: $1, 2, 3 \dots$ | Month $t$ | Monotonically increments strictly with time | **PASS (Zero Leakage)** |
| **`months_since_previous_observation`** | `reporting_month` | Calendar month gap from previous report | Months $t-1, t$ | Backward reporting interval only | **PASS (Zero Leakage)** |
| **`reporting_gap_flag`** | `months_since_previous_observation` | Binary flag ($1$ if gap $> 1$, else $0$) | Months $t-1, t$ | Evaluated at month $t$ strictly from prior report | **PASS (Zero Leakage)** |

---

## 3. Detailed Audit Results Across the 16 Areas

### Area 1: Point-in-Time Invariance (PASS)
- Tested across 5 diverse projects in `DATA/model_dataset.parquet`.
- Evaluated at mid-point $T$. Future additions included severe stress perturbations (50x expenditure surges, 120-month schedule blowouts).
- Result: **Zero deviation**. Predictions, calibrated probabilities, risk tiers, and TreeSHAP factors at month $T$ remained 100% identical.

### Area 2: Canonical Feature Parity (PASS)
- Verified that `compute_canonical_features_for_project` produces identical feature matrices to the historical reference dataset.
- Across all 141 monthly observations of a benchmark project, the mean prediction difference between canonical reconstruction and the production dataset was $1.4 \times 10^{-6}$ (max: $0.0002$).

### Area 3: Feature Leakage Verification (PASS)
- Automated verification confirmed zero forbidden substrings (`overrun`, `target`, `future`, `distress`, etc.) across feature names.
- Future retroactive cost or schedule revisions introduced at $t+2$ did not alter features at months $t$ or $t+1$.

### Area 4: Target Audit & Right-Censoring (PASS)
- Verified on longitudinal test panels:
  - When future observations $< 12$, 12-month overrun targets (`cost_overrun_12m`, `schedule_overrun_12m`, `composite_overrun_12m`) evaluate strictly to `NaN` with `distress_type_12m = "UNOBSERVABLE"`.
  - When future observations $< 6$, 6-month overrun targets evaluate strictly to `NaN`.
  - Schedule overrun targets contain zero financial terms.
  - Targets are never present in feature matrices or operational monitoring stores.

### Area 5: Cold Start & Progressive History Unlock (PASS)
- Simulated unseen project lifecycle across 7 consecutive months:
  - **Month 1**: `trajectory_status: INSUFFICIENT_HISTORY`, `history_confidence: LOW_HISTORY`. Velocities and accelerations evaluate to `NaN`. Model computes valid prediction from current-state metrics.
  - **Month 2**: `trajectory_status: INITIAL_TRAJECTORY`, `history_confidence: LIMITED_HISTORY`. 1-month velocity unlocks ($V_{\text{fin\_1m}}$). Accelerations remain `NaN`.
  - **Months 3–5**: `trajectory_status: ESTABLISHED_TRAJECTORY`, `history_confidence: DEVELOPING_HISTORY`. Full kinetic velocity, acceleration, and EWMA unlock.
  - **Month 6+**: `history_confidence: ESTABLISHED_HISTORY`.

### Area 6: Missing Data Stress Testing (PASS)
- Physical progress omitted $\rightarrow$ preserved as `NaN`; financial-physical decoupling evaluates to `NaN`; model predicts without fallback distortion.
- Planned start date omitted $\rightarrow$ `project_age_months` evaluates explicitly to `NaN` (never defaulted to 0).
- Revised cost omitted $\rightarrow$ defaults cleanly to sanctioned cost baseline without error.
- 6-month reporting hiatus $\rightarrow$ correctly flags `reporting_gap_flag = 1` and `months_since_previous_observation = 6.0`.

### Area 7: Input & Chronology Attacks (PASS)
- Duplicate month submissions $\rightarrow$ rejected (`ValueError`).
- Out-of-order submissions ($t < t_{\text{prev}}$) $\rightarrow$ rejected (`ValueError`).
- Negative expenditure or progress $\rightarrow$ rejected (`ValueError`).
- Physical progress $> 100\%$ $\rightarrow$ rejected (`ValueError`).
- Invalid calendar months (e.g. `"2024-13"`) $\rightarrow$ rejected (`ValueError`).
- Zero or negative sanctioned cost $\rightarrow$ rejected (`ValueError`).
- Extreme magnitude inputs (₹100,000,000 Cr) $\rightarrow$ processed safely without float/integer overflow.

### Area 8: Trajectory Kinetics Edge Cases (PASS)
- Accelerating progress ($A_{\text{fin}} > 0$) $\rightarrow$ risk decreases.
- Sudden stall (velocity drops to 0, delay jumps 12m) $\rightarrow$ immediate risk escalation.
- 12-month reporting hiatus $\rightarrow$ flagged accurately.

### Area 9: Governance State Machine (PASS)
- Transitions tested: `NORMAL` $\rightarrow$ `WATCH` $\rightarrow$ `REVIEW` $\rightarrow$ `CONTRACTOR_WARNING_ISSUED` $\rightarrow$ `RESPONSE_SUBMITTED` $\rightarrow$ `UNDER_RECOVERY` $\rightarrow$ `RECOVERED`.
- Persistent deterioration across 2 consecutive cycles with risk $\ge 0.50$ triggers `AUTHORITY_ESCALATION_ISSUED` and transitions project status to `ESCALATED`.
- Response without warning $\rightarrow$ rejected (`ValueError`).
- Duplicate response to already-responded warning $\rightarrow$ rejected (`ValueError`).
- Recovery without demonstrable trajectory improvement $\rightarrow$ flagged `INSUFFICIENT_EVIDENCE`.
- **Model Invariance**: Governance actions never alter underlying LightGBM deterioration probabilities.

### Area 10: Audit Immutability (PASS)
- All transitions append immutable records to `audit_events` with unique `event_id`, UTC ISO timestamp, actor attribution, and JSON payload.
- Failed submissions or duplicates leave zero orphan audit rows.

### Area 11: Data Isolation (PASS)
- SHA-256 cryptographic hashes verified before and after extensive operational monitoring actions:
  - `DATA/model_dataset.parquet`: `MATCH (100% Identical)`
  - `DATA/sanket_production_model.joblib`: `MATCH (100% Identical)`
  - `DATA/project_monthly.csv`: `MATCH (100% Identical)`

### Area 12: Database Concurrency & Atomicity (PASS)
- Simulated mid-submission validation failure: transaction rolled back cleanly with zero orphan records in `monthly_observations` or `audit_events`.
- SQLite connection reopening and WAL journal mode preserve database state without corruption.

### Area 13: API Full Regression (PASS)
- All legacy and operational REST endpoints tested:
  - `GET /health`
  - `GET /api/projects`
  - `GET /api/dashboard/summary`
  - `POST /api/monitor/projects`
  - `GET /api/monitor/projects`
  - `POST /api/monitor/projects/{id}/observations`
  - `GET /api/monitor/projects/{id}/status`
  - `GET /api/monitor/escalations`
- All HTTP status codes and response schemas strictly adhere to documented API contracts.

### Area 14: Reproducibility (PASS)
- Repeated 100 consecutive predictions on identical feature inputs: zero difference across raw probabilities, calibrated probabilities, risk tiers, and TreeSHAP contributions.

### Area 15: Explainability Traceability (PASS)
- All top-3 explanations trace directly to non-NaN whitelisted features and positive TreeSHAP contributions. Textual descriptions reflect factual numerical inputs without synthetic hallucinations.

### Area 16: Model Robustness (PASS)
- Evaluated on unseen sectors ("Space Mining"), unseen scale categories ("SUPER_GIANT"), micro-costs (₹0.01 Cr), and mega-costs (₹2,000,000 Cr).
- In all cases, the model returned valid probabilities $\in [0, 1]$ and valid risk tiers without exceptions.

---

## 4. Bugs Discovered & Fixed During Audit

1. **`ym_to_month_number` Calendar Month Validation (Fixed)**:
   - *Issue*: `ym_to_month_number` previously verified that `parts[1].isdigit()`, but failed to bound the integer value between 1 and 12. Consequently, impossible calendar strings like `"2024-13"` were erroneously converted to integer month numbers ($2024 \times 12 + 13$) instead of returning `None`.
   - *Fix*: Added explicit `1 <= m <= 12` check in [`sanket/trajectory.py`](file:///Volumes/Coding%20/SIH/sanket/trajectory.py). Invalid months now fail validation cleanly with `ValueError`.

2. **Contractor Response Duplicate Prevention (Fixed)**:
   - *Issue*: `submit_contractor_response` previously checked whether the warning was in terminal states (`RECOVERED`, `ESCALATED`), but did not prevent a contractor from submitting repeated responses to an active warning already in `RESPONSE_SUBMITTED` state.
   - *Fix*: Added check for existing responses in `contractor_responses` and enforced rejection if the warning is already in `RESPONSE_SUBMITTED` state in [`sanket/monitoring.py`](file:///Volumes/Coding%20/SIH/sanket/monitoring.py).

3. **Convenience Output Fields in `submit_observation` (Hardened)**:
   - *Enhancement*: Added top-level convenience keys (`calibrated_prob`, `raw_prob`, `risk_tier`, `alert`, `features_snapshot`, `governance_outcome`) to the `submit_observation` response dictionary to provide seamless access for both programmatic callers and the REST API while maintaining full backwards compatibility.

---

## 5. Peer Statistics: Exact Discrepancy & Documentation

### Findings on Peer Statistics (`Z_peer_V_fin`):
1. **Historical Training Population**:
   - In `DATA/model_dataset.parquet`, peer normalization grouped 443,195 observations across all projects reporting contemporaneously in the same calendar month: `["reporting_month", "sector_clean", "scale_bucket"]`.
   - Where a group contained $\ge 5$ contemporaneous projects, $Z = (V_{\text{fin\_1m}} - \mu) / \sigma$.
   - Where a group contained $< 5$ projects, $Z = 0.0$ (or `NaN` if $V_{\text{fin\_1m}}$ was unobserved).

2. **Operational Single-Project Surveillance**:
   - When a newly onboarded project reports in real time (e.g. in 2025 or 2026), contemporaneous peer observations in that exact month and sector/scale may be absent or fewer than 5.
   - In accordance with the canonical trajectory specification, when peer count is $< 5$, $Z_{\text{peer}}$ defaults to `0.0` (neutral peer performance).
   - If velocity is unobserved (Month 1), $Z_{\text{peer}}$ evaluates to `NaN`.

3. **Empirical Model Impact**:
   - Feature importance audit indicates `Z_peer_V_fin` accounts for only **0.10%** of total model gain (rank 22 of 25 features).
   - Our parity test demonstrated that when project age and baseline parameters are preserved, the difference in calibrated probability between batch-normalized $Z_{\text{peer}}$ and streaming neutral $Z = 0.0$ is bounded by **$< 0.0002$** (0.02%).
   - **Conclusion**: The streaming neutral fallback ($Z=0.0$ when peers $< 5$) is sound, robust, and requires no speculative artificial baselines.

---

## 6. Audit Test Summary

| Test Suite | File | Tests Run | Result |
| :--- | :--- | :---: | :---: |
| **Adversarial Validation Suite** | [`tests/test_adversarial_engine.py`](file:///Volumes/Coding%20/SIH/tests/test_adversarial_engine.py) | **16** | **16 PASSED** |
| **Operational Monitoring Suite** | [`tests/test_monitoring.py`](file:///Volumes/Coding%20/SIH/tests/test_monitoring.py) | **14** | **14 PASSED** |
| **Portfolio Sanitization Suite** | [`tests/test_portfolio.py`](file:///Volumes/Coding%20/SIH/tests/test_portfolio.py) | **12** | **12 PASSED** |
| **API Integration Suite** | [`tests/test_api.py`](file:///Volumes/Coding%20/SIH/tests/test_api.py) | **10** | **10 PASSED** |
| **Replay & Audit Suite** | [`tests/test_replay.py`](file:///Volumes/Coding%20/SIH/tests/test_replay.py) | **9** | **9 PASSED** |
| **Leakage Assertion Suite** | [`tests/test_leakage.py`](file:///Volumes/Coding%20/SIH/tests/test_leakage.py) | **7** | **7 PASSED** |
| **Predictive Model Suite** | [`tests/test_model.py`](file:///Volumes/Coding%20/SIH/tests/test_model.py) | **5** | **5 PASSED** |
| **Trajectory Engine Suite** | [`tests/test_trajectory.py`](file:///Volumes/Coding%20/SIH/tests/test_trajectory.py) | **4** | **4 PASSED** |
| **Timeline Engine Suite** | [`tests/test_timeline.py`](file:///Volumes/Coding%20/SIH/tests/test_timeline.py) | **4** | **4 PASSED** |
| **Target Engine Suite** | [`tests/test_targets.py`](file:///Volumes/Coding%20/SIH/tests/test_targets.py) | **3** | **3 PASSED** |
| **Backtesting & CV Suite** | [`tests/test_backtest.py`](file:///Volumes/Coding%20/SIH/tests/test_backtest.py) | **2** | **2 PASSED** |
| **Inference Core Suite** | [`tests/test_inference.py`](file:///Volumes/Coding%20/SIH/tests/test_inference.py) | **5** | **5 PASSED** |
| **TOTAL** | | **91** | **91 PASSED (100% GREEN)** |
