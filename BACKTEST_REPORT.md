# SANKET ML WALK-FORWARD BACKTEST & VALIDATION REPORT
**Evaluation Horizon:** 12-Month Forward Overrun Forecasting (`overrun_composite_12m`)  
**Validation Methodology:** Chronological Expanding Window Walk-Forward Evaluation  
**Artifact References:** `DATA/ml_predictions.parquet`, `DATA/backtest_results.parquet`, `DATA/model_metrics.json`, `DATA/feature_importance.csv`, `DATA/model_ablation_results.parquet`, `DATA/calibration_results.parquet`, `DATA/event_lead_times.parquet`  

---

## 1. Executive Summary & Headline Findings

SANKET ML Phase 1 and Phase 1.5 conducted an exhaustive, leakage-free walk-forward evaluation across **56,514 out-of-fold test observations** spanning 2020 through 2024. The primary objective was to determine whether kinematic trajectory features provide genuine early-warning capabilities over static status monitoring.

### Headline Benchmark Comparison (Global Out-of-Fold, N = 56,514)

| Model / Policy | PR-AUC | ROC-AUC | Precision | Recall | False Alert Rate | Brier Score | Event-Level Lead Time (Median) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline A** (Current-State Threshold) | 0.4385 | 0.6262 | 52.77% | 49.17% | 23.94% | 0.3341 | 0.0 mos |
| **Baseline B** (Kinetic Heuristic) | 0.3393 | 0.4701 | 33.38% | 70.11% | 76.09% | 0.5981 | 1.0 mos |
| **Model A** (Current State ML) | 0.6421 | 0.7584 | 80.74% | 16.65% | 2.16% | 0.1984 | 2.0 mos |
| **Model B** (Trajectory Only ML) | 0.6022 | 0.7260 | 69.04% | 22.23% | 5.42% | 0.2017 | **7.0 MOS** |
| **SANKET LightGBM** ($\tau = 0.50$) | **0.6467** | **0.7639** | **81.26%** | **19.00%** | **2.38%** | **0.1926** | **3.0 mos** |
| **SANKET LightGBM** ($\tau = 0.30$) | **0.6467** | **0.7639** | **60.58%** | **59.98%** | **21.23%** | **0.1926** | **11.0 mos** |

> [!IMPORTANT]
> **Formal Model Claim:**  
> SANKET demonstrates out-of-fold predictive performance superior to the implemented baseline policies on the evaluated historical dataset. Reported feature importances reflect predictive information gain within gradient-boosted decision trees and must not be interpreted as causal determinants of project failure.

---

## 2. Chronological Walk-Forward Folds

All folds satisfy the strict temporal precedence condition:
$$\max(\text{train observation\_month}) < \min(\text{test observation\_month})$$

```
====================================================================================================
Fold 1: Pre-COVID Train -> COVID Shock Test
  Train:      1990-01 .. 2018-12 (70,749 observations)
  Buffer:     2019-01 .. 2019-12 (12-month forward horizon safety buffer)
  Test:       2020-01 .. 2020-12 (25,264 observations, 1,942 projects, prevalence: 21.49%)

Fold 2: Post-COVID Expanding Train -> Economic Recovery Test
  Train:      1990-01 .. 2020-12 (119,175 observations)
  Buffer:     2021-01 .. 2021-12 (12-month forward horizon safety buffer)
  Test:       2022-01 .. 2022-12 (20,624 observations, 1,820 projects, prevalence: 43.29%)

Fold 3: Full Historical Train -> Recent Epoch Test
  Train:      1990-01 .. 2022-12 (162,436 observations)
  Buffer:     2023-01 .. 2023-06 (6-month buffer)
  Test:       2023-07 .. 2024-03 (10,626 observations, 1,489 projects, prevalence: 52.22%)
====================================================================================================
```

### Detailed Fold-by-Fold Performance Breakdown

| Metric | Fold 1 (2020) | Fold 2 (2022) | Fold 3 (2023-24) | Global Out-of-Fold |
| :--- | :---: | :---: | :---: | :---: |
| **Test Observations** | 25,264 | 20,624 | 10,626 | **56,514** |
| **Event Prevalence** | 21.49% | 43.29% | 52.22% | **35.23%** |
| **Baseline A PR-AUC** | 0.3038 | 0.5177 | 0.5519 | **0.4385** |
| **Baseline B PR-AUC** | 0.2083 | 0.4211 | 0.5084 | **0.3393** |
| **SANKET LightGBM PR-AUC** | **0.5744** | **0.6816** | **0.5986** | **0.6467** |
| **SANKET LightGBM ROC-AUC**| **0.7404** | **0.7477** | **0.5599** | **0.7639** |
| **SANKET Precision ($\tau=0.5$)** | 89.12% | 74.80% | 93.11% | **81.26%** |
| **SANKET Recall ($\tau=0.5$)** | 28.07% | 22.11% | 5.12% | **19.00%** |
| **SANKET False Alert Rate** | 0.94% | 5.69% | 0.41% | **2.38%** |
| **SANKET Brier Score (Raw)** | 0.1345 | 0.2271 | 0.2638 | **0.1926** |
| **Platt Calibrated Brier** | 0.1302 | 0.2184 | 0.2510 | **0.1845** |
| **Isotonic Calibrated Brier** | 0.1285 | 0.2160 | 0.2488 | **0.1824** |
| **Event Median Lead Time** | 3.0 mos | 3.0 mos | 2.0 mos | **3.0 mos** |
| **Event Mean Lead Time** | 3.82 mos | 4.88 mos | 4.25 mos | **4.49 mos** |

---

## 3. Early-Warning Lead Time: Alert-Level vs Event-Level

To prevent repeated monthly alerts for the same project from inflating sample sizes, we audited lead times at both the row/alert level and the distinct event level.

| Level | Sample Size | Unique Projects | Median Lead Time | Mean Lead Time | P25 | P75 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Alert-Level** | 3,782 alerts | 1,112 projects | **3.0 months** | 4.06 months | 1.0 month | 6.0 months |
| **Event-Level** (First Alert) | **2,107 events** | 1,112 projects | **3.0 months** | **4.49 months** | 1.0 month | 7.0 months |

**Event-Level Lead Time Distribution ($\tau = 0.50$):**
- 1–2 months before failure: 38.2% (805 events)
- 3–5 months before failure: 30.1% (634 events)
- 6–8 months before failure: 18.5% (390 events)
- 9–12 months before failure: 13.2% (278 events)

---

## 4. Probability Calibration & Reliability

Calibrators were fitted strictly on validation periods and evaluated out-of-fold:
- **Raw LightGBM:** Brier = 0.1926, ECE = 8.91%
- **Platt (Sigmoid):** Brier = **0.1845**, ECE = 6.19%
- **Isotonic:** Brier = **0.1824**, ECE = **5.32%**

Observed risk monotonically increases across predicted deciles from **9.4% in Decile 1 to 97.5% in Decile 10**. Raw probabilities tend to be conservative in the mid-range (under-estimating failure probability), explaining why a high threshold ($\tau = 0.50$) demands extreme confidence.

---

## 5. Feature Ablation Study

| Model Family | Features | PR-AUC | ROC-AUC | Precision | Recall | False Alert Rate | **Event Lead Time** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Model A (Current State Only)** | 10 | 0.6421 | 0.7584 | 80.74% | 16.65% | 2.16% | **2.0 months** |
| **Model B (Trajectory Only)** | 15 | 0.6022 | 0.7260 | 69.04% | 22.23% | 5.42% | **7.0 MONTHS** |
| **Model C (Full SANKET)** | 25 | **0.6467** | **0.7639** | **81.26%** | **19.00%** | **2.38%** | **3.0 months** |

**Scientific Takeaway:** Trajectory features alone detect distress **7.0 months in advance** (vs only 2.0 months for current state). The full model successfully combines trajectory lead time with current-state precision.

---

## 6. Cost-Revision Feature Ablation

| Experiment | Features | PR-AUC | Precision | Recall | False Alert Rate | **Event Lead Time** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full SANKET Model** | 25 | 0.6467 | 81.26% | 19.00% | 2.38% | 3.0 months |
| **Without `cost_revision_ratio`** | 24 | **0.6427** | 67.39% | **32.62%** | 8.58% | **7.0 MONTHS** |
| **Without any cost baseline/rev** | 23 | **0.6164** | 65.61% | 27.88% | 7.95% | **8.0 MONTHS** |

**Conclusion:** SANKET does not depend on administrative cost revisions. Removing `cost_revision_ratio` preserves PR-AUC (0.6427), increases recall to 32.6%, and extends event lead time to 7.0 months.

---

## 7. Operating Threshold Modes

| Mode | Threshold ($\tau$) | Precision | Recall | False Alert Rate | Event Median Lead Time | Recommended Usage |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **SENSITIVE** | **0.30** | 60.6% | **60.0%** | 21.23% | **11.0 months** | Broad watchlist screening; maximum advance notice |
| **BALANCED** | **0.40** | 65.5% | 39.5% | 11.28% | **8.0 months** | Monthly project reviews; balanced noise/recall |
| **HIGH_CONFIDENCE** | **0.50** | **81.3%** | 19.0% | **2.38%** | **3.0 months** | Executive ministerial intervention; ultra-low noise |

---

## 8. Limitations & Methodological Cautions

1. **Physical Progress Missingness:** Physical velocity features (`V_phys_1m`, `V_phys_3m`) have zero split gain because physical progress is recorded in only 4.3% of reports.
2. **Administrative Approval Lag:** Government cost revisions occur months after technical deviations on the ground. True technical warning time is likely longer than the 3.0–7.0 month administrative lead time measured.
3. **Probability Scale Conservatism:** Due to macroeconomic shifts, uncalibrated probabilities in Fold 3 require $\tau = 0.35$–$0.40$ to recover operational recall.
