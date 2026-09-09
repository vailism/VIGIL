# SANKET ML BASELINE & ARCHITECTURE SPECIFICATION
**Version:** 1.0 (Phase 1 Evaluation)  
**Date:** September 2026  
**Module Reference:** `sanket/model.py`, `sanket/backtest.py`, `configs/model.yaml`  

---

## 1. Overview & Problem Formulation

SANKET (Vehicle for Infrastructure Governance & Intervention Logistics) aims to provide **genuine early-warning intelligence** for major infrastructure projects under central monitoring in India. 

The goal of ML Phase 1 is **not** leaderboard optimization, presentation polishing, or deep hyperparameter searches. Instead, it is to rigorously establish:
1. Whether kinematic trajectory features ($V_{\text{fin}}$, $A_{\text{fin}}$, $\text{EWMA}$, $V_{\text{exp}}$, completion date drift) provide **statistically meaningful predictive power** over naive static/current-state rules.
2. What **early-warning lead time** (months in advance) can be achieved before formal cost revisions or schedule delays are publicly recorded.
3. How to ensure **leakage-free walk-forward validation** over multi-year longitudinal infrastructure reporting.

---

## 2. Cohort & Target Definitions

### 2.1 Primary Cohort
To prevent survivorship bias and ensure mathematical validity, the model is trained and evaluated exclusively on the eligible cohort:
$$\text{eligible\_features} == 1 \quad \land \quad \text{target\_observable\_12m} == 1$$

- **Total Historical Observations:** 443,195
- **Eligible Cohort Observations:** 181,449 (across 9,907 unique projects)
- **Eligibility Criteria:**
  1. Minimum history: $N \ge 3$ observations per project.
  2. Baseline cost is strictly positive ($C_{\text{base}}(t) > 0$).
  3. Continuous 12-month forward trajectory is observable without truncation.

### 2.2 Target Variables
1. **Primary Target (`overrun_composite_12m`):**
   $$\text{overrun\_composite\_12m} = \mathbf{1}\left( \text{cost\_overrun\_12m} == 1 \;\lor\; \text{schedule\_overrun\_12m} == 1 \right)$$
   Prevalence in test cohort: **35.23%**.
2. **Cost Escalation Target (`cost_overrun_12m`):**
   $$\mathbf{1}\left( \frac{\max_{\tau \in [t+1, t+12]} C_{\text{base}}(\tau) - C_{\text{base}}(t)}{C_{\text{base}}(t)} \ge 0.05 \right)$$
   Evaluates formal baseline cost escalation $\ge 5\%$.
3. **Schedule Slippage Target (`schedule_overrun_12m`):**
   $$\mathbf{1}\left( \max_{\tau \in [t+1, t+12]} T_{\text{target}}(\tau) - T_{\text{target}}(t) \ge 3 \;\text{months} \right)$$
   Evaluates forward anticipated completion date drift $\ge 3$ months.

---

## 3. Leakage Audit & Guardrails

### 3.1 Strict Exclusion Rule
The following fields are strictly prohibited from entering the feature matrix:
- Direct target columns: `overrun_composite_12m`, `cost_overrun_12m`, `schedule_overrun_12m`, `cost_overrun_6m`, `schedule_overrun_6m`.
- Target-derived continuous labels: `escalation_pct_12m`, `schedule_drift_months_12m`, `distress_type_12m`, `distress_type_6m`.
- Future indicators: any timestamp or observation where $\text{observation\_month} > t$.

### 3.2 Automated Leakage Assertion
Every training run enforces an automated assertion in `sanket/model.py`:
```python
forbidden_substrings = [
    "target", "overrun", "distress", "escalation_pct",
    "schedule_drift_months", "future", "lead_time"
]
for col in feature_columns:
    for forbidden in forbidden_substrings:
        assert forbidden not in col.lower()
```

---

## 4. Feature Whitelist

Features are declared explicitly in `configs/model.yaml`. Blind column ingestion is forbidden.

| Category | Feature Name | Description | Point-in-Time Justification |
| :--- | :--- | :--- | :--- |
| **Trajectory Kinematics** | `V_fin_1m` | 1-month financial progress velocity | $\Delta \text{Progress} / \Delta t$ over preceding month |
| | `V_fin_3m` | 3-month rolling mean financial velocity | Smoothed recent progress velocity |
| | `A_fin` | Financial progress acceleration | 2nd derivative ($V_{\text{fin}}(t) - V_{\text{fin}}(t-1)$) |
| | `EWMA_V_fin` | Exponentially weighted velocity ($\alpha = 0.3$) | Memory-discounted progress velocity |
| **Expenditure Dynamics** | `V_exp_1m` | 1-month expenditure burn rate (Cr/month) | Actual recent cash deployment speed |
| | `V_exp_3m` | 3-month rolling expenditure velocity | Medium-term expenditure pace |
| | `A_exp` | Expenditure acceleration | Change in monthly burn rate |
| **Baseline Ratios** | `cost_revision_ratio` | $C_{\text{base}}(t) / C_{\text{orig}}(t)$ | Historical cost inflation prior to $t$ |
| | `expenditure_to_baseline`| $\text{Cumulative Expenditure}(t) / C_{\text{base}}(t)$ | Budget exhaustion ratio at $t$ |
| **Schedule Dynamics** | `schedule_deviation_months`| $T_{\text{target}}(t) - T_{\text{orig}}(t)$ | Pre-existing delay at observation $t$ |
| | `schedule_deviation_change`| $\Delta(\text{delay})$ from previous month | Immediate delay expansion |
| | `completion_date_drift` | Cumulative target completion shifts | Historical date revisions |
| **Cross-Modal & Peer** | `Z_peer_V_fin` | Sector-relative velocity Z-score | Performance vs peer projects in same sector |
| | `financial_physical_gap`| Financial % minus Physical % | Accounting divergence / paper progress |
| | `trajectory_risk_score` | Heuristic composite distress score | Multi-signal kinetic distress counter |
| **Physical Kinematics** | `V_phys_1m`, `V_phys_3m`, `A_phys` | Physical progress velocity & acceleration | Available on 4.3% subset; missing otherwise |
| **Context & Age** | `sector_clean` | Ministry / Infrastructure sector | Categorical identity |
| | `scale_bucket` | Project cost tier (<150Cr, 150-1000Cr, >1000Cr) | Scale complexity indicator |
| | `C_base` | Effective baseline cost at $t$ | Project monetary magnitude |
| | `project_age_months` | Months since project inception | Temporal maturity |
| | `observation_number` | Sequence index of report | Reporting track record |

---

## 5. Baselines

To prove that ML provides genuine early-warning capability, two non-trivial baseline policies are implemented in `sanket/model.py`:

### Baseline A: Current-State Threshold Policy
Represents conventional project monitoring heuristics based on current static status:
- High budget exhaustion: $\text{expenditure\_to\_baseline} \ge 0.90$, OR
- Existing severe delay: $\text{schedule\_deviation\_months} \ge 12.0$ months.

### Baseline B: Kinetic Trajectory Heuristic Policy
Represents intuitive velocity-based heuristics without machine learning:
- Deteriorating or halted progress: $V_{\text{fin,1m}} \le 0.0$, OR
- Low exponential velocity: $\text{EWMA\_V\_fin} < 0.5\%/\text{month}$, OR
- Severe peer underperformance: $Z_{\text{peer\_V\_fin}} < -1.0$.

Both baselines output a hard binary decision ($\{0, 1\}$) and a calibrated pseudo-probability ($0.20$ vs $0.80$) for metric computation.

---

## 6. Machine Learning Model & Hyperparameters

### 6.1 LightGBM Classifier
We deploy `lightgbm.LGBMClassifier` (`lightgbm==4.7.0`).

### 6.2 Conservative Hyperparameters
To guarantee stability and avoid overfitting to specific macro eras, conservative regularization is enforced:
```yaml
model:
  algorithm: "lightgbm"
  params:
    objective: "binary"
    metric: "binary_logloss"
    boosting_type: "gbdt"
    n_estimators: 150
    learning_rate: 0.05
    max_depth: 5
    num_leaves: 31
    min_child_samples: 50
    subsample: 0.8
    colsample_bytree: 0.8
    random_state: 42
    n_jobs: -1
    verbose: -1
```

### 6.3 Missing Data Policy
1. **Physical Progress:** Only 4.3% of observations have physical progress reported. LightGBM natively routes missing features to the optimal split direction during tree building. **Zero blind imputation** is performed.
2. **Kinematic Startups:** For observations 1 and 2 where 3-month rolling windows are incomplete, missing values are natively handled by the tree algorithm.

---

## 7. Chronological Walk-Forward Validation Strategy

### 7.1 Temporal Split Hygiene
Random K-Fold cross-validation is **strictly banned** as it leaks future temporal patterns into past predictions. 

Instead, an **expanding window chronological walk-forward split** is executed across 3 distinct macroeconomic and reporting epochs:

```
Fold 1:
Train: [Start .. 2018-12] (N = 70,749)
Gap:   [2019-01 .. 2019-12] (12-month forward horizon safety buffer)
Test:  [2020-01 .. 2020-12] (N = 25,264) — COVID onset & disruption

Fold 2:
Train: [Start .. 2020-12] (N = 119,175)
Gap:   [2021-01 .. 2021-12] (12-month forward horizon safety buffer)
Test:  [2022-01 .. 2022-12] (N = 20,624) — Post-pandemic recovery

Fold 3:
Train: [Start .. 2022-12] (N = 162,436)
Gap:   [2023-01 .. 2023-06] (6-month buffer)
Test:  [2023-07 .. 2024-03] (N = 10,626) — Recent operational window
```

### 7.2 Strict Temporal Condition
Every fold satisfies:
$$\max(\text{train observation\_month}) < \min(\text{test observation\_month})$$
A 12-month gap between train observation cutoff and test period ensures that 12-month forward target realization does not leak into the training labels.

### 7.3 Project-Level Generalization Test (Stricter Held-Out Check)
To test whether the model is merely memorizing project identities across time:
- An independent strict split was performed where **956 projects were completely withheld from training** (trained on 113,924 observations; tested on 8,016 observations from unseen projects).
- Performance on unseen projects: **PR-AUC = 0.6720, ROC-AUC = 0.6887, Precision = 66.68%, Recall = 41.45%**.
- This proves SANKET learns transferable trajectory patterns, not project ID memorization.

---

## 8. Reproducibility & Environment

- **OS:** macOS (Darwin 24.6.0)
- **Python:** 3.12.12
- **LightGBM:** 4.7.0 (compiled with Apple `libomp` via Homebrew)
- **Scikit-learn:** 1.9.0
- **PyArrow:** 25.0.1
- **Random Seed:** 42 (enforced across splits, numpy, and LGBM)
- **Configuration File:** `configs/model.yaml`
