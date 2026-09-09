# SANKET Trajectory Engine & Feature Architecture

**Document:** `TRAJECTORY_ENGINE.md`  
**Version:** 1.0  
**Pipeline Modules:** `sanket.timeline`, `sanket.trajectory`, `sanket.targets`, `sanket.features`  
**Configuration:** `configs/trajectory.yaml`  
**Dataset Grain:** Strict Point-in-Time Project-Month (`ONE ROW = ONE UNIQUE PROJECT + ONE REPORTING MONTH`)

---

## 1. System Overview

The SANKET Trajectory Engine converts raw canonical longitudinal observations into an auditable, leakage-safe temporal feature matrix. 

Unlike conventional static infrastructure dashboards that merely ask *"What is the current project status?"*, the Trajectory Engine models the **dynamic rate of change** across expenditure, physical construction, and schedule commitments to answer:
> *"Is the project's momentum accelerating, stalling, or decoupling from expenditure, and will it experience formal cost escalation or schedule slippage over the next 6 to 12 months?"*

```text
 Canonical Records (DATA/project_monthly.csv)
                      │
                      ▼
            sanket/timeline.py
         (DATA/project_timelines.parquet)
          ├── Chronological sorting
          ├── Gap calculation
          └── Point-in-time age & observation counters
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
  sanket/trajectory.py       sanket/targets.py
  (Project Features)        (Forward Outcomes)
  ├── Velocities (1m, 3m)   ├── Cost overrun (6m, 12m)
  ├── Accelerations         ├── Schedule overrun (6m, 12m)
  ├── EWMA trends           ├── Composite overrun (6m, 12m)
  ├── Peer benchmarks       └── Distress types (NONE, COST, SCH, BOTH)
  └── Risk score (0-100)
          │                       │
          └───────────┬───────────┘
                      ▼
              sanket/features.py
         (DATA/model_dataset.parquet)
```

---

## 2. Mathematical Feature Definitions

Every feature at observation month $t$ is computed strictly from reports published at or before $t$.

### 2.1 Core Financial Trajectory
* **Financial Progress Velocity (1-Month Delta):**
  $$V_{\text{fin\_1m}}(t) = \text{financial\_progress}(t) - \text{financial\_progress}(t-1)$$
* **Financial Progress Velocity (3-Month Delta):**
  $$V_{\text{fin\_3m}}(t) = \text{financial\_progress}(t) - \text{financial\_progress}(t-3)$$
* **Financial Progress Acceleration:**
  $$A_{\text{fin}}(t) = V_{\text{fin\_1m}}(t) - V_{\text{fin\_1m}}(t-1)$$

### 2.2 Expenditure Trajectory
* **Expenditure Spend Velocity (1-Month):**
  $$V_{\text{exp\_1m}}(t) = \text{expenditure}(t) - \text{expenditure}(t-1)$$
* **Expenditure Spend Velocity (3-Month):**
  $$V_{\text{exp\_3m}}(t) = \text{expenditure}(t) - \text{expenditure}(t-3)$$
* **Expenditure Acceleration:**
  $$A_{\text{exp}}(t) = V_{\text{exp\_1m}}(t) - V_{\text{exp\_1m}}(t-1)$$

### 2.3 Cost Baseline & Escalation Drift
* **Prevailing Point-in-Time Cost Baseline ($C_{\text{base}}$):**
  $$C_{\text{base}}(t) = \begin{cases} \text{revised\_cost}(t) & \text{if non-null, valid, and } > 0 \\ \text{approved\_cost}(t) & \text{otherwise} \end{cases}$$
* **Current Cost Revision Ratio:**
  $$\text{cost\_revision\_ratio}(t) = \frac{\text{revised\_cost}(t) - \text{approved\_cost}(t)}{\text{approved\_cost}(t)}$$
* **Expenditure-to-Baseline Ratio:**
  $$\text{expenditure\_to\_baseline}(t) = \frac{\text{expenditure}(t)}{C_{\text{base}}(t)}$$

### 2.4 Schedule Trajectory
* **Schedule Deviation Change:**
  $$\Delta \text{dev}(t) = \text{schedule\_deviation}(t) - \text{schedule\_deviation}(t-1)$$
* **Completion Date Drift (Months):**
  $$\text{completion\_date\_drift}(t) = T_{\text{target}}(t) - T_{\text{target}}(t-1)$$
  Where $T_{\text{target}}$ resolves point-in-time to `revised_completion_date` if valid, otherwise `original_completion_date`.

### 2.5 Chronological Recursive EWMA
To filter transient reporting volatility and extract underlying momentum, an Exponentially Weighted Moving Average (EWMA) is calculated recursively:
$$\text{EWMA}_{V}(t) = \alpha \cdot V_{\text{fin\_1m}}(t) + (1 - \alpha) \cdot \text{EWMA}_{V}(t-1)$$
* **Default parameter:** $\alpha = 0.30$ (configured in `configs/trajectory.yaml`).
* **Boundary Invariant:** The recursion strictly resets across project boundaries.

---

## 3. Point-in-Time Peer Normalization

Public infrastructure velocity varies substantially by sector (e.g. tunneling in Railways vs. pipeline laying in Petroleum vs. surface paving in Highways) and project scale.

To avoid universal static thresholds, SANKET normalizes velocity against a project's dynamic peer cohort:
* **Stratification Dimensions:**
  1. `sector` (e.g. Railways, Road Transport, Power, Coal, Petroleum, etc.)
  2. `scale_bucket` (Small: $< ₹150\text{ cr}$, Major: $₹150–1,000\text{ cr}$, Mega: $\ge ₹1,000\text{ cr}$)
* **Temporal Restriction:** Peer statistics ($\mu_{\text{peer}}, \sigma_{\text{peer}}$) are computed **strictly within each reporting month $t$**.
* **Peer Standardized Z-Score:**
  $$Z_{\text{peer\_V\_fin}}(t) = \frac{V_{\text{fin\_1m}}(t) - \mu_{\text{peer}}(t)}{\max(\sigma_{\text{peer}}(t),\, 0.01)}$$
  *(Computed when peer cohort size $N \ge 5$, else 0.0).*

---

## 4. Physical Progress & Decoupling (2022–2025 Modern Cohort)

Where physical progress percentage is reported in modern OCMS reports, SANKET activates enhanced physical trajectory signals without imputing missing historical data:
* $V_{\text{phys\_1m}}(t) = \text{physical\_progress}(t) - \text{physical\_progress}(t-1)$
* $A_{\text{phys}}(t) = V_{\text{phys\_1m}}(t) - V_{\text{phys\_1m}}(t-1)$
* **Financial-Physical Decoupling Gap:**
  $$\Delta_{\text{gap}}(t) = \text{financial\_progress}(t) - \text{physical\_progress}(t)$$
  *Interpretation:* A high positive gap reveals an alarming early-warning pattern: **rapid financial disbursement without corresponding on-the-ground physical progress**.

---

## 5. Interpretable Trajectory Risk Score (0–100)

Before deploying black-box machine learning, SANKET provides an operational, fully auditable heuristic risk score:

### 5.1 Component Signals (Normalized $[0.0, 1.0]$)
1. **`score_stalled_velocity`:** Penalizes progress velocity $\le 0.0\%$ ($\text{clip}(1.0 - V/3.0, 0, 1)$).
2. **`score_deceleration`:** Penalizes negative acceleration $A \le -2.0\%$ ($\text{clip}(-A/2.0, 0, 1)$).
3. **`score_burn_anomaly`:** Penalizes excessive cash burn relative to progress achieved.
4. **`score_cost_revision`:** Measures existing budget escalation ($\text{clip}(\text{ratio}/0.25, 0, 1)$).
5. **`score_schedule_deterioration`:** Penalizes completion date drift $\ge 6$ months.
6. **`score_peer_underperformance`:** Penalizes velocity $\ge 2$ standard deviations below sector peers.
7. **`score_physical_decoupling`:** Penalizes spending $> 20\%$ ahead of physical completion.

### 5.2 Composite Weighted Formulation
$$\text{trajectory\_risk\_score}(t) = 100 \times \frac{\sum_{k} w_k \cdot S_k(t) \cdot \mathbb{I}(S_k \text{ valid})}{\sum_{k} w_k \cdot \mathbb{I}(S_k \text{ valid})}$$
* Weights are defined in `configs/trajectory.yaml` and sum to 1.0.
* Preserved transparently in `DATA/model_dataset.parquet`.
