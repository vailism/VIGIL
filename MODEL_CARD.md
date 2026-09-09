# SANKET Model Card: Infrastructure Trajectory Early-Warning Model
**Model Version:** 1.0 (Phase 1 Frozen Baseline)  
**Date:** September 2026  
**Framework:** LightGBM `4.7.0` (GBDT Classifier)  
**Repository Module:** `sanket/model.py`, `sanket/backtest.py`, `configs/model.yaml`  

---

## 1. Model Details & Intended Use

### 1.1 Developer & Context
Developed as part of the SANKET system (Vehicle for Infrastructure Governance & Intervention Logistics) for central monitoring of major and mega public sector infrastructure projects in India (sanctioned cost $\ge ₹150\text{ crore}$) tracked by the Ministry of Statistics and Programme Implementation (MoSPI).

### 1.2 Primary Objective & Intended Use
- **Primary Objective:** Provide predictive early warning of upcoming project distress (formal baseline cost revisions and schedule completion date drift) 3 to 11 months in advance of official administrative recording.
- **Intended Users:** Project Monitoring Units (PMUs), line ministries (Railways, Road Transport, Power, Petroleum), and central infrastructure appraisal committees.
- **Primary Operating Context:** Periodic (monthly) ingestion of project status reports to flag accelerating trajectory anomalies and prioritize field audits.

### 1.3 Out-of-Scope & Prohibited Uses
- **Automated Sanctioning/De-funding:** This model is **not** an automated decision-maker and must never be used to automatically terminate, penalize, or de-fund contracts without independent engineering and administrative review.
- **Contractor Litigation:** Predictive alert probabilities must not be introduced as evidence of contractor fault or fraud.
- **Real-Time Daily Dispatch:** The model operates on monthly longitudinal cadences and is not designed for daily construction site dispatch.

---

## 2. Target Definitions & Formal Governance Formulation

All targets strictly observe the **Fundamental Point-in-Time Rule**: targets at month $t$ inspect exclusively reports dated $s \in (t, t+12]$.

### 2.1 Primary Composite Target (`overrun_composite_12m`)
$$\text{overrun\_composite\_12m}(t) = \mathbf{1}\Big(Y_{\text{cost}}(t, 12) == 1 \;\lor\; Y_{\text{sch}}(t, 12) == 1\Big)$$
- **Historical Population Prevalence:** 26.92% (181,449 eligible observations)
- **Out-of-Fold Evaluation Prevalence:** 35.23% (56,514 test observations)

### 2.2 Cost Escalation Target ($Y_{\text{cost}}(t, 12)$)
$$\max_{k \in \{1, \dots, 12\}} \left[ \frac{C_{\text{base}}(t+k) - C_{\text{base}}(t)}{C_{\text{base}}(t)} \right] \ge 0.05 \quad (5\%\text{ baseline cost increase})$$
where $C_{\text{base}}(t) = \text{revised\_cost}(t)$ if valid/positive, else $\text{approved\_cost}(t)$.

### 2.3 Schedule Slippage Target ($Y_{\text{sch}}(t, 12)$)
$$\max\Big(\Delta T_{\text{drift}}(t, t+12),\, \Delta \text{Dev}(t, t+12)\Big) \ge 6.0\text{ months}$$
- Requires at least **6.0 months** of genuine forward target completion drift ($T_{\text{target}}$) or official reported schedule deviation ($\text{Dev}$) increase.
- A minor 1-month reporting adjustment does **not** trigger a schedule overrun.

---

## 3. Feature Groups & Point-in-Time Whitelist

Features are restricted strictly to point-in-time observations known at or before month $t$:

| Feature Category | Count | Primary Features | Point-in-Time Rationale |
| :--- | :---: | :--- | :--- |
| **Trajectory Kinematics** | 4 | `V_fin_1m`, `V_fin_3m`, `A_fin`, `EWMA_V_fin` | Progress velocities ($\Delta\% / \Delta t$) and acceleration over preceding 1–3 months |
| **Expenditure Dynamics** | 3 | `V_exp_1m`, `V_exp_3m`, `A_exp` | Actual monthly cash deployment burn rates and acceleration (Cr/month) |
| **Baseline Ratios & Age** | 5 | `C_base`, `expenditure_to_baseline`, `cost_revision_ratio`, `project_age_months`, `observation_number` | Cumulative financial exhaustion and lifecycle maturity at $t$ |
| **Schedule Dynamics** | 3 | `schedule_deviation_months`, `schedule_deviation_change`, `completion_date_drift` | Historical accumulated delays and prior shifts in anticipated completion |
| **Cross-Modal & Peer** | 3 | `Z_peer_V_fin`, `financial_physical_gap`, `trajectory_risk_score` | Peer velocity divergence, paper spend vs ground progress decoupling |
| **Physical Kinematics** | 3 | `V_phys_1m`, `V_phys_3m`, `A_phys` | Physical progress velocity (available in 4.3% of records; natively routed) |
| **Context & Sector** | 4 | `sector_clean`, `scale_bucket`, `months_since_previous_obs`, `reporting_gap_flag` | Ministry sector, capital scale category, and administrative reporting regularity |

---

## 4. Training Population & Eligibility Rules

- **Total Historical Corpus:** 443,195 project-month records (2003–2025).
- **Eligible Modeling Cohort:** 181,449 records across 9,907 unique projects.
- **Eligibility Criteria:**
  1. Minimum observation track record: $N \ge 3$ historical reports per project.
  2. Strictly positive cost baseline: $C_{\text{base}}(t) > 0$.
  3. Uncensored forward window: observable reports across $(t, t+12]$ (right-censored observations marked NaN).

---

## 5. Walk-Forward Validation & Out-of-Fold Performance

Validation strictly enforces chronological walk-forward splits with a 12-month forward horizon safety buffer ($\max(\text{train}) < \min(\text{test})$):
- **Fold 1:** Train $\le 2018-12$ (70,749 obs) $\rightarrow$ Test $2020-01 .. 2020-12$ (25,264 obs)
- **Fold 2:** Train $\le 2020-12$ (119,175 obs) $\rightarrow$ Test $2022-01 .. 2022-12$ (20,624 obs)
- **Fold 3:** Train $\le 2022-12$ (162,436 obs) $\rightarrow$ Test $2023-07 .. 2024-03$ (10,626 obs)

### Benchmark Summary (Global Out-of-Fold, N = 56,514)

| Metric | Baseline A (Status Heuristic) | Baseline B (Kinetic Heuristic) | Model A (Current State) | Model B (Trajectory Only) | Full SANKET Model |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **PR-AUC** | 0.4385 | 0.3393 | 0.6421 | 0.6022 | **0.6467** |
| **ROC-AUC** | 0.6262 | 0.4701 | 0.7584 | 0.7260 | **0.7639** |
| **Brier Score** | 0.3341 | 0.5981 | 0.1984 | 0.2017 | **0.1926** (Calibrated: **0.1824**) |
| **Precision ($\tau=0.50$)** | 52.77% | 33.38% | 80.74% | 69.04% | **81.26%** |
| **Recall ($\tau=0.50$)** | 49.17% | 70.11% | 16.65% | 22.23% | **19.00%** |
| **False Alert Rate** | 23.94% | 76.09% | 2.16% | 5.42% | **2.38%** |
| **Event Lead Time (Median)**| 0.0 mos | 1.0 mos | 2.0 mos | **7.0 MOS** | **3.0 to 4.0 mos** |

---

## 6. Recommended Operational Modes

Operating thresholds must be chosen according to explicit administrative tradeoffs:

| Mode Label | Threshold ($\tau$) | Target Precision | Target Recall | False Alert Rate | Portfolio Alert % | Event Lead Time | Operational Function |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **WATCH** | **0.40** | **65.5%** | **39.5%** | **11.3%** | ~21.2% | **8.0 months** | **Broad Surveillance:** Automated screening to capture emerging delays with >7 months runway. |
| **REVIEW** | **0.45** | **73.8%** | **25.2%** | **4.9%** | ~12.0% | **4.0 to 6.0 mos** | **PMU Monthly Scrutiny:** Prioritized audit list with $<5\%$ false alarms for divisional review. |
| **ESCALATE** | **0.50** | **81.3%** | **19.0%** | **2.4%** | ~8.2% | **3.0 to 4.0 mos** | **Ministerial Action:** High-confidence alerts ($>81\%$ precision) for formal committee escalation. |

---

## 7. Probability Calibration

- **Raw Probabilities:** Monotonically ordered (9.4% observed in Decile 1 up to 97.5% in Decile 10), but conservative in mid-ranges (under-estimating true risk in high-prevalence epochs).
- **Post-Hoc Calibration:** Isotonic calibration reduces Brier score from 0.1926 to **0.1824** and cuts Expected Calibration Error from 8.91% to **5.32%**.
- **Deployment Recommendation:** Use isotonic calibration for dashboards displaying numerical risk percentages.

---

## 8. Known Limitations & Failure Modes

1. **Physical Progress Feature Sparsity:**
   Physical progress velocity features (`V_phys_1m`, `V_phys_3m`, `A_phys`) contribute zero split gain because physical progress is recorded in only **4.3% of historical reports**. While LightGBM natively routes missing features without distortion, ground-truth physical tracking remains constrained by source reporting.
2. **Administrative Lag in Ground Truth:**
   Formal cost revisions and revised completion dates reflect Cabinet/CCEA administrative approvals, which often occur 3 to 9 months after physical technical failure has materialized on site. Therefore, SANKET's 3.0–8.0 month lead time reflects advance notice *before official administrative gazetting*.
3. **Macro Prevalence Shifts:**
   In Fold 3 (2023–2024), schedule overrun prevalence increased to 47.9% (composite 52.2%) due to post-COVID deadline realignments and improved MoSPI schedule tracking coverage (rising from 28.6% in 2020 to 92.2% in 2023). Uncalibrated probabilities require threshold adjustments to $\tau = 0.40$–$0.45$ for balanced operational recall during high-prevalence epochs.

---

## 9. Interpretability & Claims Guidance

### 9.1 Non-Causal Interpretation
Feature importance scores reflect **predictive information gain** in gradient-boosted decision trees. High gain for `cost_revision_ratio` or `C_base` indicates that prior revisions and capital scale are strong statistical predictors of future revisions, **not** that past revisions cause project failure.

### 9.2 Defensible & Appropriate Claims
* "SANKET demonstrates out-of-fold predictive performance superior to the implemented baseline policies on the evaluated historical dataset."
* "SANKET's trajectory signals identify deteriorating infrastructure projects earlier than current-state monitoring while maintaining a practical false-alert burden."
* "At matched operational alert burden (8% of portfolio), trajectory features provide 4.0 months of early warning compared to 2.0 months for current-state metrics."
* "At high confidence ($\tau = 0.50$), SANKET maintains an 81.3% precision with a 2.38% false alert rate."

### 9.3 Inappropriate & Disallowed Claims
* *Do not claim:* "SANKET is empirically proven to eliminate project overruns."
* *Do not claim:* "SANKET identifies the root causal drivers of engineering failure."
* *Do not claim:* "Raw LightGBM probabilities are perfectly calibrated without post-hoc adjustment."
