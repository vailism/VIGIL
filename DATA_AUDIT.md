# SANKET Dataset Audit & Trajectory Readiness Report

**Audit Date:** September 6, 2026  
**Dataset Scope:** 336 MoSPI Infrastructure PDF Reports (2003–2025)  
**Total Canonical Observations:** 443,195 project-month records  
**Total Unique Projects:** 115,693 projects  
**Audit Status:** Complete — Pre-Modeling Data Quality Review  

---

## Executive Summary

Before initiating the Trajectory Engine or ML models, a complete audit was performed across `DATA/project_monthly.csv`, `DATA/projects.csv`, and `DATA/project_coverage.csv`. 

Key findings:
1. **Physical Progress vs. Financial Progress Asymmetry:** Physical progress is 4.3% across the whole corpus because MoSPI historically (2003–2021) did not track or report physical completion percentages in standard Flash Reports. Physical progress reporting begins selectively in 2022 (2.5%) and becomes widespread only in modern OCMS reports (42.3% in 2024, 95.4% in 2025). In contrast, financial progress is available in **87.2%** of all observations, and cumulative expenditure is present in **95.6%**.
2. **Negative Cost Investigation (421 records):** Zero legitimate infrastructure projects have negative budgets. The 421 records stem from two distinct root causes:
   - **416 records:** Summary/aggregate sector or state rows (e.g., `SHIPPING AND PORTS`, `DEFENCE PRODUCTION`, `D & N HAVELI`) from Flash Report summary tables where a negative `% Cost Variation` / cost savings (e.g., `-4.01%`) was aligned to the expenditure column.
   - **5 records:** Two-digit Date of Approval years containing hyphens (e.g., `Apr-74`, `Mar-84`) in legacy railway annexures where `-74` or `-84` was parsed as negative approved cost.
3. **Trajectory Modeling Population:**
   - **5,857 projects** have $\ge 12$ monthly observations (54.2% of total records, 240,181 project-months), with an average lifespan of 4.7 years (56.7 months).
   - **12,464 projects** have $\ge 6$ monthly observations (66.0% of total records, 292,289 project-months).
4. **Temporal Cadence & Sequence Integrity:**
   - 79.7% of projects with $\ge 12$ observations have a **strictly monthly cadence** (median gap = 1 month).
   - 91.8% have a median reporting gap $\le 2$ months. Gaps are monotonic and form coherent temporal sequences.
5. **Identity Integrity:** 99.4% of long-lived projects exhibit strong name consistency across time. Only 37 projects (0.6%) show token divergence, driven by MoSPI source-PDF clerical code misassignments (e.g. printing `[N12000074]` for both a steel project and a telecom project in the same PDF).

---

## 1. Field Completeness & Longitudinal Reliability

Across all 443,195 canonical observations, field presence is classified into three tiers:

| Tier | Field Name | Non-Null Count | Coverage (%) | Modeling Suitability & Strategy |
| :--- | :--- | :---: | :---: | :--- |
| **Tier 1: Universal & Core** | `project_id` | 443,195 | 100.0% | Primary grouping key for all trajectory sequences. |
| | `project_name` | 443,195 | 100.0% | Entity identification and audit verification. |
| | `reporting_month` | 443,195 | 100.0% | Strict `YYYY-MM` temporal index. |
| | `approved_cost` | 429,837 | 97.0% | Benchmark denominator for budget escalation & scaling. |
| | `expenditure` | 423,513 | 95.6% | Core numeric variable for spending velocity $V_{\text{exp}}(t)$. |
| | `financial_progress` | 386,561 | 87.2% | Primary longitudinal progress signal across 2003–2025. |
| **Tier 2: Semi-Dense Context** | `sector` | 304,154 | 68.6% | Peer-group benchmarking (reaches **84.6%** in $\ge 12$ cohort; can be backfilled from project master). |
| | `milestone_information` | 288,407 | 65.1% | Milestone delivery tracking (reaches **81.7%** in $\ge 12$ cohort). |
| | `original_completion_date` | 249,880 | 56.4% | Schedule slippage anchor (reaches **36.6%** in $\ge 12$ cohort). |
| | `revised_cost` | 187,066 | 42.2% | Explicit cost revision / overrun signal. |
| | `schedule_deviation` | 148,586 | 33.5% | Delay duration in months. |
| | `revised_completion_date` | 140,378 | 31.7% | Target completion drift. |
| **Tier 3: Sparse / Era-Specific** | `physical_progress` | 18,911 | 4.3% | **Era-specific signal:** 0% (2003–2021), 42.3% (2024), 95.4% (2025). |
| | `ministry` | 53,835 | 12.1% | Administrative classification (reaches 54.8% in $\ge 12$ cohort). |
| | `state` | 39,159 | 8.8% | Geographical context (reaches 54.8% in $\ge 12$ cohort). |
| | `district` | 0 | 0.0% | Not published in standard MoSPI Flash Reports. |
| | `project_size` | 0 | 0.0% | Redundant with `approved_cost` classification (Mega vs Major). |

---

## 2. Investigation: Physical vs. Financial Progress Disparity

The 4.3% physical progress vs. 87.2% financial progress disparity is **structural to MoSPI reporting conventions**, not an extraction failure.

### Annual Progress Breakdown

| Year | Total Observations | Physical Count | Physical (%) | Financial Count | Financial (%) | Expenditure (%) | Approved Cost (%) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2003–2010** | 115 | 0 | **0.0%** | 87 | 75.7% | 75.7% | 100.0% |
| **2011** | 2,703 | 0 | **0.0%** | 1,397 | 51.7% | 78.8% | 85.4% |
| **2012** | 2,701 | 0 | **0.0%** | 1,503 | 55.6% | 96.1% | 85.4% |
| **2013** | 8,492 | 0 | **0.0%** | 7,106 | 83.7% | 91.9% | 98.8% |
| **2014** | 11,572 | 2 | **0.0%** | 10,375 | 89.7% | 90.8% | 99.2% |
| **2015** | 20,966 | 0 | **0.0%** | 16,927 | 80.7% | 91.1% | 90.7% |
| **2016** | 26,028 | 0 | **0.0%** | 20,509 | 78.8% | 87.0% | 92.7% |
| **2017** | 25,569 | 0 | **0.0%** | 20,614 | 80.6% | 89.0% | 93.9% |
| **2018** | 43,616 | 0 | **0.0%** | 33,352 | 76.5% | 93.8% | 96.4% |
| **2019** | 51,825 | 0 | **0.0%** | 45,168 | 87.2% | 99.0% | 98.2% |
| **2020** | 51,023 | 0 | **0.0%** | 46,721 | 91.6% | 98.6% | 97.9% |
| **2021** | 57,215 | 0 | **0.0%** | 51,261 | 89.6% | 97.4% | 96.9% |
| **2022** | 56,049 | 1,428 | **2.5%** | 51,088 | 91.1% | 96.4% | 97.5% |
| **2023** | 51,922 | 1,499 | **2.9%** | 49,007 | 94.4% | 97.6% | 99.5% |
| **2024** | 29,907 | 12,651 | **42.3%** | 28,122 | 94.0% | 98.3% | 99.9% |
| **2025** | 3,492 | 3,331 | **95.4%** | 3,324 | 95.2% | 99.8% | 100.0% |

### Reporting Format Drivers
- **Standard Flash Reports (2003–2021):** MoSPI's statutory reporting tables (Table 6, Table 7, and Annexures) historically mandated financial tracking (`Cumulative Expenditure` and `Anticipated Cost`), but did **not** publish physical progress percentage columns.
- **QPSR & Modern OCMS (2022–2025):** Physical progress percentage was systematically incorporated when OCMS migrated to detailed project cards and quarterly QPSR Part-II reports (e.g., `July_Part-II.pdf`, `FRMarch2025.pdf`, `QPISR_1st_QTR_2024-25 PART2.pdf`).
- **Modeling Implication:** The longitudinal Trajectory Engine **must use Financial Progress Velocity $V_{\text{fin}}(t) = \text{prog}(t) - \text{prog}(t-1)$ and Expenditure Burn Rate as the universal backbone**, with Physical Progress Velocity activated as an enhanced feature for observations in 2022–2025.

---

## 3. Project Era & Sectoral Coverage

### Coverage by Era

| Project Era | Total Project-Months | Physical Prog (%) | Financial Prog (%) | Expenditure (%) | Approved Cost (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Legacy Era (2003–2010)** | 115 | 0.0% | 75.7% | 75.7% | 100.0% |
| **Middle Era (2011–2020)** | 244,495 | 0.0% | 83.3% | 94.1% | 95.9% |
| **Modern OCMS Era (2021–2025)** | 198,585 | 9.5% | 92.1% | 97.3% | 98.3% |

### Coverage by Sector

| Sector | Observations | Unique Projects | Physical (%) | Financial (%) |
| :--- | :---: | :---: | :---: | :---: |
| **Atomic Energy** | 70,741 | 6,643 | 0.3% | 89.5% |
| **Railways** | 45,345 | 6,873 | 13.1% | 89.5% |
| **Road Transport & Highways** | 36,307 | 6,234 | 16.8% | 87.7% |
| **Civil Aviation** | 29,593 | 6,255 | 1.6% | 86.5% |
| **Power** | 29,398 | 7,052 | 4.9% | 85.9% |
| **Petroleum** | 27,303 | 6,899 | 5.3% | 87.4% |
| **Coal** | 14,428 | 4,896 | 7.7% | 87.2% |
| **Health & Family Welfare** | 13,436 | 4,558 | 3.1% | 86.0% |
| **Urban Development** | 9,730 | 3,121 | 2.1% | 85.7% |
| **Mines** | 6,081 | 3,023 | 1.8% | 91.2% |
| **Steel** | 5,025 | 2,533 | 3.6% | 79.2% |
| **Heavy Industry** | 4,989 | 1,952 | 0.0% | 79.8% |
| **Water Resources** | 3,417 | 1,555 | 10.9% | 90.0% |
| **Shipping and Ports** | 2,586 | 1,360 | 0.4% | 72.9% |
| **Telecommunications** | 2,545 | 1,076 | 3.3% | 84.9% |

---

## 4. Negative-Cost Audit & Classification (421 Records)

An exhaustive inspection was conducted on all 421 records with negative numeric values. **Zero records represent legitimate negative project costs.**

```text
Negative value breakdown by column:
  expenditure   : 416 records
  approved_cost : 5 records
```

### Classification Breakdown

1. **Date-Parsing Artifacts in Approved Cost (5 records):**
   - **Records:** `PRJ_9A71ABAA764D`, `PRJ_A3C085C6D8A1`, `PRJ_AA9645E2BF11`, `PRJ_C06EC77CCDB4`, `PRJ_F28E709AA844` in `FR_OCTOBER_2012.pdf` (p.14).
   - **Root Cause:** In legacy railway tables, Date of Approval was written as `Apr-74`, `Mar-81`, `Apr-83`, `Mar-84`. The column parser picked up `-74`, `-81`, `-83`, `-84` as approved cost values (`-74.0`, `-81.0`).
   - **Classification:** **Extraction column alignment artifact**.
   - **Action:** Retain in raw data; in Trajectory Engine feature matrix, nullify negative approved costs.

2. **Summary Table Variance in Expenditure (416 records):**
   - **Records:** 45 aggregate pseudo-project IDs (e.g., `PRJ_3EA4D397D07D` "SHIPPING AND PORTS", `PRJ_7D5BC1C57132` "D & N HAVELI", `PRJ_875B446A732A` "DEFENCE PRODUCTION", `PRJ_F46F0AD46CE0` "PUNJAB").
   - **Root Cause:** Flash Reports contain executive summary tables (Table 2/3: "Sector-wise Cost Overrun", Table 4: "State-wise Summary") with columns `[Original Cost | Anticipated Cost | % Variation | No. Delayed]`. When a sector or state experienced aggregate cost savings (e.g. `-4.01%`, `-13.7%`, `-0.08%`), the negative percentage was extracted into the expenditure column.
   - **Classification:** **Summary-table aggregate variance artifact**.
   - **Action:** These pseudo-project IDs belong to the identity review exclusions list and will be naturally filtered from trajectory modeling.

---

## 5. Modeling Cohort Population Analysis

To train robust velocity, acceleration, and early-warning overrun models, projects must have a sufficient longitudinal observation window:

| Observation Cohort | Unique Projects | % of All Projects | Total Project-Months | % of Dataset | Trajectory Feasibility |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Cohort $\ge 3$ Obs** | 24,922 | 21.5% | 338,479 | 76.4% | Minimum threshold to calculate acceleration $A(t)$. |
| **Cohort $\ge 4$ Obs** | 18,647 | 16.1% | 319,654 | 72.1% | Quarterly baseline trend analysis. |
| **Cohort $\ge 6$ Obs** | **12,464** | **10.8%** | **292,289** | **66.0%** | **Recommended Primary Training Cohort.** Half-year baseline with stable rolling velocity. |
| **Cohort $\ge 8$ Obs** | 9,217 | 8.0% | 271,383 | 61.2% | Robust EWMA smoothing. |
| **Cohort $\ge 12$ Obs** | **5,857** | **5.1%** | **240,181** | **54.2%** | **Deep Longitudinal Benchmark Cohort.** Full annual cycle, seasonal adjustment, and 12-month forward horizon. |
| **Cohort $\ge 24$ Obs** | 3,380 | 2.9% | 199,920 | 45.1% | Multi-year mega-project analysis (2+ years history). |
| **Cohort $\ge 36$ Obs** | 2,499 | 2.2% | 174,231 | 39.3% | Decadal infrastructure lifecycles (3+ years history). |

> [!NOTE]
> Even though projects with $\ge 6$ observations represent 10.8% of unique project IDs, they account for **66.0% of all monthly observations** in the dataset. This represents a rich longitudinal foundation for ML modeling.

---

## 6. Project Identity & Collision Verification

An automated consistency scan was run across all 5,857 projects with $\ge 12$ observations to verify whether repeated `project_id` values represent the exact same physical asset over time:

1. **High Name Consistency (99.4%):** 5,820 out of 5,857 projects have consistent token-level names across years (e.g. *Varanasi-Aurangabad Highway*, *Sevok-Rangpo Railway*, *Kolkata Metro Extension*).
2. **Name Divergence Cases (0.6% / 37 projects):**
   - **Clerical Code Collisions in Source PDFs:** In rare instances, MoSPI reports printed identical project codes for different projects across reporting eras (e.g., `N12000074` was assigned to *Durgapur Steel Plant* in Mines/Steel, but MoSPI clerical errors printed `[N12000074]` for a *BSNL Defence Telecom* project in June–Nov 2015).
   - **Recommendation:** In the Trajectory Engine, define project identity as a composite key `(project_id, sector)` or apply a disambiguation pass when name token similarity across observations drops to zero.

---

## 7. Temporal Cadence & Sequence Continuity

For projects in the longitudinal cohort ($\ge 12$ observations):

```text
Cadence Metric                   Value
--------------------------------------------------------------------------------
Mean project observation count   : 41.0 monthly records
Mean temporal span               : 56.7 calendar months (~4.7 years)
Median gap between observations  : 1.0 month (strictly monthly for 79.7% of projects)
Observations with gap <= 2 mos   : 91.8% of projects
Strict monthly continuity ratio  : 78.3% of consecutive pairs have gap == 1 month
```

- **Monotonicity:** All sequences in `project_monthly.csv` are strictly chronological.
- **Reporting Stability:** Infrastructure projects in India are reported continuously on a monthly cycle. Occasional 2-to-3 month gaps reflect skipped MoSPI monthly publications, which can be handled with standard forward-filling or interval-normalized velocity formulas:
  $$V(t) = \frac{P(t) - P(t - \Delta t)}{\Delta t}$$

---

## 8. Recommended Modeling Fields for Trajectory Engine

Based on data quality, density, and historical presence across 2003–2025, the following feature set is recommended for the SANKET Trajectory Engine:

### Core Trajectory Metrics (All Eras: 2003–2025)
1. **Financial Progress Velocity ($V_{\text{fin}}$):**
   $$V_{\text{fin}}(t) = \frac{\text{financial\_progress}(t) - \text{financial\_progress}(t-k)}{\Delta t}$$
2. **Financial Progress Acceleration ($A_{\text{fin}}$):**
   $$A_{\text{fin}}(t) = V_{\text{fin}}(t) - V_{\text{fin}}(t-1)$$
3. **Monthly Expenditure Burn Rate ($B_{\text{exp}}$):**
   $$B_{\text{exp}}(t) = \frac{\text{expenditure}(t) - \text{expenditure}(t-k)}{\Delta t}$$
4. **Cost Revision Escalation Ratio ($R_{\text{cost}}$):**
   $$R_{\text{cost}}(t) = \frac{\text{revised\_cost}(t) - \text{approved\_cost}(t)}{\text{approved\_cost}(t)}$$
5. **Schedule Slippage Deviation ($D_{\text{sch}}$):**
   Derived from `schedule_deviation` and drift between `original_completion_date` and `revised_completion_date`.
6. **EWMA Smoothed Trend ($\tilde{V}_{\text{fin}}$):**
   Exponentially weighted moving average ($\alpha = 0.3$) to separate systemic momentum from monthly accounting noise.

### Enhanced Features (Modern OCMS Era: 2022–2025)
7. **Physical Progress Velocity ($V_{\text{phys}}$):**
   Available for modern projects to contrast physical work completion against financial expenditure burn rate (identifying "spending money without building" anomalies).
8. **Physical vs. Financial Decoupling Gap:**
   $$\Delta_{\text{decouple}}(t) = \text{financial\_progress}(t) - \text{physical\_progress}(t)$$

---

## 9. Next Steps

With the data audit completed and verified:
1. **Dataset Integrity Maintained:** No rows deleted; raw extractions preserved in full.
2. **Clean Modeling Cohort Defined:** Projects with $\ge 6$ observations (12,464 projects / 292,289 observations) for general modeling; projects with $\ge 12$ observations (5,857 projects / 240,181 observations) for deep trajectory benchmarking.
3. **Ready for Trajectory Engine:** Ready to proceed with `scripts/trajectory_engine.py` following user review and approval.
