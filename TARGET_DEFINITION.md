# SANKET: Formal Target Definition & Leakage-Safe Prediction Framework

**Document:** `TARGET_DEFINITION.md`  
**Version:** 2.0 (Methodologically Refined)  
**System:** SANKET (Infrastructure Early-Warning & Trajectory Intelligence)  
**Source Dataset:** `DATA/project_monthly.csv` (443,195 canonical project-months, 2003–2025)  

---

## Executive Summary: Target vs. Predictive Signal Separation

A foundational principle of SANKET is the strict conceptual and mathematical separation between **Predictive Signals (Features)** and **Formal Deterioration Outcomes (Targets)**:

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SANKET ARCHITECTURE                                       │
├─────────────────────────────────────────────────────────────┬───────────────────────────────┤
│                 PREDICTIVE SIGNALS (X)                      │      FORMAL TARGETS (Y)       │
│                  [Observed at or before t]                  │  [Observed in Window (t, t+H]]│
├─────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ • Financial progress velocity V_fin(t)                      │ • Future cost baseline        │
│ • Progress acceleration A_fin(t)                            │   escalation:                 │
│ • Monthly expenditure burn rate B_exp(t)                    │   C_base(t+H) > C_base(t)     │
│ • Burn-rate acceleration & spending anomalies               │                               │
│ • Expenditure-to-baseline ratio: Exp(t) / C_base(t)         │ • Future target completion    │
│ • Rolling EWMA smoothed trajectory trends                   │   date drift:                 │
│ • Milestone execution momentum and stall counts             │   T_target(t+H) > T_target(t) │
│ • Sectoral / peer-group trajectory divergence               │                               │
│ • Physical-vs-financial progress decoupling (2022–2025)     │ • Future schedule deviation   │
│                                                             │   increase:                   │
│                                                             │   Dev(t+H) > Dev(t)           │
└─────────────────────────────────────────────────────────────┴───────────────────────────────┘
```

### Why This Separation Is Non-Negotiable
* **No Label-Feature Circularity:** Cumulative expenditure is **not** a target label. A project spending money faster than its baseline is exhibiting a *behavioral distress signal*. Defining the target using expenditure would create circular leakage with expenditure velocity features. The target must capture the **external, official administrative consequence** (formal cost escalation or schedule slippage declared in future reports).
* **The Core Premise of SANKET:** Trajectory signals *anticipate* future official deterioration before government monitoring systems formally acknowledge and publish revised estimates.

---

## 1. The Fundamental Point-in-Time Rule

At observation month $t$, all information is strictly partitioned into past/present vs. future:

$$\text{Feature Space } \mathbf{X}(t) \in \sigma\Big(\{ \text{Report}(s) : s \le t \}\Big)$$
$$\text{Target Space } \mathbf{Y}(t, H) \in \sigma\Big(\{ \text{Report}(s) : t < s \le t + H \}\Big)$$

```text
                         Observation Month t
                                  │
      PAST & PRESENT (Features)   │         FUTURE (Targets Only)
  ... ──► t-2 ──► t-1 ──► t       │    ──► t+1 ──► ... ──► t+H
 ─────────────────────────────────┼───────────────────────────────► Time
  • Known baseline cost           │    • Future cost revisions
  • Historical spend velocity     │    • Future target date drift
  • Stated delay up to t          │    • Future schedule deviation
  • Historical milestone status   │    • Future completion status
```

**Zero-Leakage Guarantee:** Under no circumstances may any field published in a report dated $s > t$ (such as future revised costs, future completion dates, future schedule deviations, or future milestone outcomes) be utilized in constructing feature vectors at month $t$.

---

## 2. Formal Cost Overrun Target

### 2.1 Cost Baseline Definition
At observation month $t$, the prevailing baseline cost $C_{\text{base}}(t)$ represents the officially approved budget known at that point in time:

$$C_{\text{base}}(t) = \begin{cases} 
\text{revised\_cost}(t) & \text{if } \text{revised\_cost}(t) \text{ is non-null, valid, and } > 0 \\ 
\text{approved\_cost}(t) & \text{otherwise} 
\end{cases}$$

### 2.2 Formal Cost Escalation Formulation
A project incurs a formal cost overrun over forward horizon $H \in \{6, 12\}$ months if its official cost baseline increases by at least a relative threshold $\theta_{\text{cost}}$ at any point during the forward window:

$$Y_{\text{cost}}(t, H) = \begin{cases}
1 & \text{if } \displaystyle \max_{k \in \{1, \dots, H\}} \left[ \frac{C_{\text{base}}(t+k) - C_{\text{base}}(t)}{C_{\text{base}}(t)} \right] \ge \theta_{\text{cost}} \\
0 & \text{if target is observable and no baseline escalation occurs} \\
\text{NaN} & \text{if observation is right-censored (incomplete future window)}
\end{cases}$$

### 2.3 Threshold Sensitivity & Non-Hardcoded Formulation
The 5% threshold ($\theta_{\text{cost}} = 0.05$) is established as an **initial candidate benchmark** reflecting standard government reporting materiality (e.g. ₹250 crore on a ₹5,000 crore project). 

However, SANKET will evaluate a continuous cost escalation metric alongside binary targets:
* **Continuous Metric:** $\Delta C_{\text{pct}}(t, H) = \displaystyle \max_{k \in \{1, \dots, H\}} \left[ \frac{C_{\text{base}}(t+k) - C_{\text{base}}(t)}{C_{\text{base}}(t)} \right]$
* **Sensitivity Suite:** During validation and backtesting, models will be evaluated across candidate thresholds:
  * $\theta_{\text{cost}} \in \{0.03, 0.05, 0.10\}$ (3%, 5%, 10%)
  * Sector-calibrated thresholds (e.g., Railways vs. Petroleum vs. Road Transport, where contractual revision mechanisms differ).
* **Rule:** No ML model or backtest will be permanently locked to a single arbitrary threshold without explicit sensitivity analysis.

---

## 3. Formal Schedule Overrun Target

### 3.1 Genuine Temporal Evidence Rule
Financial progress ($\text{financial\_progress} < 95\%$) is **strictly prohibited** as a proxy for project completion. As established in the dataset audit, physical progress is absent in 95.7% of historical records, and financial expenditure routinely decouples from actual physical construction.

The schedule overrun target relies exclusively on genuine temporal evidence:
1. `original_completion_date` (strict `YYYY-MM`)
2. `revised_completion_date` (strict `YYYY-MM`)
3. `schedule_deviation` (official reported delay in months)

### 3.2 Prevailing Target Completion Date
At month $t$, the prevailing target completion date $T_{\text{target}}(t)$ is defined point-in-time as:
$$T_{\text{target}}(t) = \begin{cases} 
\text{revised\_completion\_date}(t) & \text{if non-null and valid YYYY-MM} \\
\text{original\_completion\_date}(t) & \text{if non-null and valid YYYY-MM} \\
\text{null} & \text{otherwise}
\end{cases}$$

### 3.3 Schedule Deterioration Formulation
A project incurs a formal schedule overrun over horizon $H \in \{6, 12\}$ months if either of two verified temporal events occurs:

1. **Target Date Drift:** The target completion date is officially pushed back by at least $\theta_{\text{delay}}$ months:
   $$\Delta T_{\text{drift}}(t, t+H) = \max_{k \in \{1, \dots, H\}} \text{MonthsBetween}\Big(T_{\text{target}}(t+k),\, T_{\text{target}}(t)\Big) \ge \theta_{\text{delay}}$$
2. **Official Delay Escalation:** The reported `schedule_deviation` increases by at least $\theta_{\text{delay}}$ months:
   $$\Delta \text{Dev}(t, t+H) = \max_{k \in \{1, \dots, H\}} \Big(\text{schedule\_deviation}(t+k) - \text{schedule\_deviation}(t)\Big) \ge \theta_{\text{delay}}$$

### 3.4 Horizon Delay Thresholds
* **6-Month Forward Horizon ($H = 6$):** Candidate threshold $\theta_{\text{delay}} = 3\text{ months}$ (continuous metric: $\Delta T_{\text{months}}$).
* **12-Month Forward Horizon ($H = 12$):** Candidate threshold $\theta_{\text{delay}} = 6\text{ months}$ (continuous metric: $\Delta T_{\text{months}}$).
* **Unobservable Fallback:** If neither $T_{\text{target}}$ nor `schedule_deviation` has valid data across the forward window, the schedule target is marked `NaN` (unobservable), rather than guessing completion from expenditure.

---

## 4. Multi-Target Structure & Cause Preservation

Rather than forcing a single monolithic label, SANKET maintains separate targets to preserve **causality and operational explainability**:

```text
               ┌────────────────────────────────────────────────────────┐
               │              PRIMARY PREDICTION TARGETS                │
               ├───────────────────────────┬────────────────────────────┤
               │   Cost Overrun Target     │   Schedule Overrun Target  │
               │      Y_cost(t, H)         │        Y_sch(t, H)         │
               └─────────────┬─────────────┴─────────────┬──────────────┘
                             │                           │
                             └─────────────┬─────────────┘
                                           │
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │               DERIVED GOVERNANCE TARGETS               │
               ├────────────────────────────────────────────────────────┤
               │ • overrun_composite_H = Y_cost(t, H) OR Y_sch(t, H)    │
               │ • distress_type_H     ∈ {NONE, COST, SCHEDULE, BOTH}   │
               └────────────────────────────────────────────────────────┘
```

### 4.1 Independent Binary Targets
* `cost_overrun_6m`, `cost_overrun_12m` $\in \{0, 1, \text{NaN}\}$
* `schedule_overrun_6m`, `schedule_overrun_12m` $\in \{0, 1, \text{NaN}\}$

### 4.2 Derived Governance Composite Target
For administrative oversight (e.g. Cabinet / MoSPI executive dashboards):
$$\text{overrun\_composite\_H}(t) = \begin{cases}
1 & \text{if } Y_{\text{cost}}(t, H) = 1 \quad \lor \quad Y_{\text{sch}}(t, H) = 1 \\
0 & \text{if both targets are observable and neither overruns} \\
\text{NaN} & \text{if both targets are unobservable, or one is unobservable and the other is 0}
\end{cases}$$

### 4.3 Cause Categorization (`distress_type_H`)
To enable SANKET's dashboard to explain *why* an alert was generated:
$$\text{distress\_type\_12m}(t) = \begin{cases}
\text{"BOTH"} & \text{if } Y_{\text{cost}}(t, 12) = 1 \text{ and } Y_{\text{sch}}(t, 12) = 1 \\
\text{"COST"} & \text{if } Y_{\text{cost}}(t, 12) = 1 \text{ and } Y_{\text{sch}}(t, 12) = 0 \\
\text{"SCHEDULE"} & \text{if } Y_{\text{cost}}(t, 12) = 0 \text{ and } Y_{\text{sch}}(t, 12) = 1 \\
\text{"NONE"} & \text{if } Y_{\text{cost}}(t, 12) = 0 \text{ and } Y_{\text{sch}}(t, 12) = 0 \\
\text{"UNOBSERVABLE"} & \text{if targets are right-censored}
\end{cases}$$

---

## 5. Dual Eligibility: History Window vs. Target Censoring

SANKET explicitly separates two distinct eligibility concepts:

```text
[First Seen] ────► [History Window >= 3 mos] ────► Month t ────► [Forward Window H] ────► [Dataset End]
◄─────────────────────── Feature Eligibility ─────────────►│
                                                           │◄──────── Target Observability ────────►
```

### 5.1 Historical Feature Eligibility (`eligible_features = 1`)
A project-month observation $(i, t)$ is eligible to produce trajectory features if and only if:
1. **Longitudinal History:** The project has at least $K_{\text{history}} \ge 3$ preceding monthly observations ($t-1, t-2, t-3$) to compute velocities $V(t)$, acceleration $A(t)$, and EWMA trends.
2. **Valid Point-in-Time Baseline:** Baseline cost $C_{\text{base}}(t) > 0$ and is non-negative.
3. **Identity Disambiguation:** For projects with identical MoSPI codes across distinct physical assets (e.g., the 37 audit collision codes), sequences are partitioned by `(project_id, sector)`.

### 5.2 Future Target Observability (`target_observable_H = 1`)
A project-month observation $(i, t)$ is observable for horizon $H$ if and only if:
1. **Uncensored Future Window:** The project's final observation in the dataset $T_{\text{last}}(i)$ satisfies:
   $$\text{MonthsBetween}\big(T_{\text{last}}(i),\, t\big) \ge H$$
2. **Forward Density:** At least 1 verified reporting observation exists within the window $[t + \lfloor H/2 \rfloor, \, t + H]$ to inspect the prevailing baseline.

### 5.3 Strict Right-Censoring Rule
* When `target_observable_H == 0`, all target fields (`cost_overrun_H`, `schedule_overrun_H`, `overrun_composite_H`) **MUST be set to `NaN`**.
* **CRITICAL:** Right-censored rows must **NEVER** be imputed as 0. Imputing unobserved future windows as 0 injects massive false-negative contamination into training sets.

---

## 6. Target Table Schema Design (`DATA/project_targets.csv`)

| Column Name | Type | Nullable | Category | Description |
| :--- | :--- | :---: | :--- | :--- |
| `project_id` | `VARCHAR(32)` | No | Key | Project MoSPI identifier or canonical slug. |
| `observation_month` | `VARCHAR(7)` | No | Key | Effective observation month (`YYYY-MM`). |
| **Independent Targets** | | | | |
| `cost_overrun_6m` | `FLOAT` | Yes | Target | Binary {0.0, 1.0} or `NaN` (cost baseline escalation $\ge \theta_{\text{cost}}$). |
| `cost_overrun_12m` | `FLOAT` | Yes | Target | Binary {0.0, 1.0} or `NaN` (cost baseline escalation $\ge \theta_{\text{cost}}$). |
| `schedule_overrun_6m` | `FLOAT` | Yes | Target | Binary {0.0, 1.0} or `NaN` (target date drift $\ge 3\text{m}$ or dev increase). |
| `schedule_overrun_12m` | `FLOAT` | Yes | Target | Binary {0.0, 1.0} or `NaN` (target date drift $\ge 6\text{m}$ or dev increase). |
| **Derived Targets** | | | | |
| `overrun_composite_6m` | `FLOAT` | Yes | Derived | Binary {0.0, 1.0} or `NaN` (`cost_6m` OR `sch_6m`). |
| `overrun_composite_12m`| `FLOAT` | Yes | Derived | Binary {0.0, 1.0} or `NaN` (`cost_12m` OR `sch_12m`). |
| `distress_type_6m` | `VARCHAR(16)` | No | Categorical| `NONE`, `COST`, `SCHEDULE`, `BOTH`, `UNOBSERVABLE`. |
| `distress_type_12m` | `VARCHAR(16)` | No | Categorical| `NONE`, `COST`, `SCHEDULE`, `BOTH`, `UNOBSERVABLE`. |
| **Continuous Metrics** | | | | |
| `cost_escalation_pct_6m` | `FLOAT` | Yes | Metric | Continuous $\max \Delta C_{\text{base}} / C_{\text{base}}$ over 6 months. |
| `cost_escalation_pct_12m`| `FLOAT` | Yes | Metric | Continuous $\max \Delta C_{\text{base}} / C_{\text{base}}$ over 12 months. |
| `schedule_drift_months_6m` | `FLOAT` | Yes | Metric | Continuous target date shift (months) over 6 months. |
| `schedule_drift_months_12m`| `FLOAT` | Yes | Metric | Continuous target date shift (months) over 12 months. |
| **Eligibility & Observability**| | | | |
| `eligible_features` | `INTEGER` | No | Flag | {0, 1}: Sufficient prior history ($K \ge 3$) and valid baseline. |
| `target_observable_6m` | `INTEGER` | No | Flag | {0, 1}: Sufficient future window ($T_{\text{last}} - t \ge 6$). |
| `target_observable_12m`| `INTEGER` | No | Flag | {0, 1}: Sufficient future window ($T_{\text{last}} - t \ge 12$). |

---

## 7. Concrete Real-World Scenarios

### Scenario A: Valid Positive Cost Target (Future Baseline Escalation)
* **Project:** `020100044` (*Prototype Fast Breeder Reactor, BHAVINI*)
* **Observation Month ($t$):** `2013-05`
  * Baseline Cost $C_{\text{base}}(t) = ₹3,492.0\text{ cr}$ (sanctioned budget).
  * Feature vector at $t$: Computes spending velocity and burn rate relative to $₹3,492.0\text{ cr}$.
* **Forward Event at $t+10$ (`2014-03`):**
  * Official cabinet revision raises anticipated cost to $₹5,677.0\text{ cr}$ ($+62.6\%$ escalation).
* **Target Label at $t$:**
  * `cost_overrun_12m = 1.0`
  * `cost_escalation_pct_12m = 0.626`
  * `target_observable_12m = 1`

### Scenario B: Valid Schedule-Only Overrun (Date Drift without Cost Revision)
* **Project:** `180100210` (*Parbati Hydroelectric Project II, NHPC*)
* **Observation Month ($t$):** `2019-01`
  * Baseline Cost $C_{\text{base}}(t) = ₹3,919.59\text{ cr}$
  * Target Completion Date $T_{\text{target}}(t) = \text{2020-12}$
* **Forward Window Outcome at $t+12$ (`2020-01`):**
  * Baseline cost remains unchanged at $₹3,919.59\text{ cr}$ (`cost_overrun_12m = 0.0`).
  * Target completion date is officially deferred to `2022-03` ($+15\text{ months}$ slippage).
* **Target Label at $t$:**
  * `cost_overrun_12m = 0.0`
  * `schedule_overrun_12m = 1.0`
  * `overrun_composite_12m = 1.0`
  * `distress_type_12m = "SCHEDULE"`

### Scenario C: Clean Negative Target (On-Track Project)
* **Project:** `N24000182` (*Varanasi-Aurangabad Highway Section, NHAI*)
* **Observation Month ($t$):** `2016-01`
  * Baseline Cost $C_{\text{base}}(t) = ₹2,848.0\text{ cr}$
  * Target Completion Date $T_{\text{target}}(t) = \text{2017-06}$
* **Forward Window Outcome (`2016-02` to `2017-01`):**
  * Cost baseline remains stable at $₹2,848.0\text{ cr}$ ($0.0\%$ change).
  * Target completion date remains unchanged at `2017-06` ($0\text{ months}$ drift).
* **Target Label at $t$:**
  * `cost_overrun_12m = 0.0`, `schedule_overrun_12m = 0.0`
  * `overrun_composite_12m = 0.0`
  * `distress_type_12m = "NONE"`
  * `target_observable_12m = 1`

### Scenario D: Right-Censored Observation (Dataset Boundary)
* **Project:** `220100188` (*Nangaldam-Talwara Railway Project, NR*)
* **Observation Month ($t$):** `2024-10`
  * Baseline Cost $C_{\text{base}}(t) = ₹1,200.0\text{ cr}$
* **Dataset Horizon:** The dataset terminates at `2025-03` (only 5 future reporting months observed).
* **Target Label at $t$:**
  * `target_observable_6m = 0`, `cost_overrun_6m = NaN`, `schedule_overrun_6m = NaN`
  * `target_observable_12m = 0`, `cost_overrun_12m = NaN`, `schedule_overrun_12m = NaN`
  * `distress_type_12m = "UNOBSERVABLE"`
  * *Reason:* The 6-month and 12-month outcomes cannot be evaluated. The record must not be labeled 0.

### Scenario E: Future Cost Revision That Must NOT Leak
* **Project:** `180100221` (*Subansiri Lower Hydroelectric Project, NHPC*)
* **Observation Month ($t$):** `2013-05`
  * Prevailing cost reported at $t$: $₹10,667.0\text{ cr}$.
* **Subsequent Event at $t+24$ (`2015-05`):**
  * Major revision escalates cost to $₹26,075.54\text{ cr}$.
* **Leakage Guard:**
  * Feature algorithms generating features at $t = \text{2013-05}$ MUST see $C_{\text{base}} = ₹10,667.0\text{ cr}$.
  * The $₹26,075.54\text{ cr}$ number must never enter the feature pipeline for any observation dated before May 2015.

### Scenario F: Project with Insufficient Historical Window (Cold-Start)
* **Project:** `PRJ_E50E2C8C1465`
* **Observation Month ($t$):** `2021-04` (Month 1 of appearance in MoSPI reports).
* **Target & Feature Evaluation:**
  * While future targets $Y(t, 12)$ may be observable if the project continues through 2022, `eligible_features = 0`.
  * *Reason:* Trajectory velocities $V_{\text{fin}}(t) = P(t) - P(t-1)$ and acceleration $A_{\text{fin}}(t)$ cannot be mathematically computed without prior observation history.

---

## 8. Final Recommendation: SANKET Multi-Target Prediction Strategy

### Primary Model Architecture: Multi-Task / Multi-Target Suite
Rather than collapsing all predictions into a single opaque number, SANKET will deploy a **trio of coordinated models**:

1. **Model 1 (Cost Escalation Risk):** Predicts $P\big(Y_{\text{cost}}(t, 12) = 1\big)$  
   *Target Audience:* Ministry Finance Advisers, Expenditure Department, Project Financial Officers.
2. **Model 2 (Schedule Slippage Risk):** Predicts $P\big(Y_{\text{sch}}(t, 12) = 1\big)$  
   *Target Audience:* Project Directors, EPC Contractors, Site Engineers, Logistics Planners.
3. **Model 3 (Systemic Governance Alert):** Predicts $P\big(\text{overrun\_composite\_12m}(t) = 1\big)$  
   *Target Audience:* Cabinet Secretariat, Prime Minister’s Project Monitoring Group (PMG), MoSPI Apex Committee.

### Why `overrun_composite_12m` Serves as the Primary Executive Benchmark
* **Time-Cost Substitution Reality:** In large infrastructure contracts, project managers routinely accelerate expenditure to prevent delay, or absorb delay to avoid cost claims. Focusing exclusively on cost or schedule creates severe blind spots; the composite target identifies projects undergoing **systemic distress**.
* **The 12-Month Operational Window:** A 12-month advance warning gives public authorities the requisite lead time to resolve right-of-way disputes, fast-track environmental clearances, or re-allocate budgetary capital before projects reach irreversible failure.
* **Explainability via `distress_type_12m`:** While executive alert rankings use the composite probability, the SANKET UI directly exposes whether the predicted distress is driven by **Cost**, **Schedule**, or **Both**.
