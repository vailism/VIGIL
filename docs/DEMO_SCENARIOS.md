# SANKET Operational Demo Scenarios

## Executive Overview

The SANKET operational demo scenario dataset provides two canonical, point-in-time deterministic workflows demonstrating the end-to-end lifecycle of infrastructure project governance:

1. **Scenario 1 (`PRJ-DEMO-RECOVERY-01`) — The Contractor Recovery Workflow (5 Months)**:
   A project enters active monitoring healthy, experiences early trajectory deterioration, triggers an automated **Contractor Warning Notice**, submits an enforceable recovery plan with tangible corrective actions, demonstrates measurable progress acceleration, and is empirically confirmed **RECOVERED**.

2. **Scenario 2 (`PRJ-DEMO-ESCALATE-02`) — The Authority Escalation Workflow (7 Months)**:
   A project progressively deteriorates over multiple reporting cycles, crosses the **ESCALATE** threshold triggering a **Contractor Warning Notice**, provides an evasive response with zero physical site mobilization, persists in severe deterioration across the mandatory governance persistence window, and is automatically escalated to ministerial and government oversight bodies via an immutable **Authority Escalation Dossier**.

### Strict Engine Integrity Guarantees

- **Zero Bypasses & Zero Hardcoding**: Every prediction, risk tier, kinetic trajectory score, TreeSHAP explanation factor, and state machine transition is computed live by `sanket/monitoring.py` and `sanket/inference.py`.
- **Identical Feature Pipeline**: Uses the exact canonical 25-feature vector (`compute_canonical_features_for_project`) as the frozen production model.
- **Point-in-Time Correctness**: Features through month $t$ strictly rely on observations up to month $t$, eliminating future information leakage.
- **Audit Ledger Immutability**: Every step records cryptographic event UUIDs in the SQLite `audit_events` ledger.

---

## Scenario 1: Contractor Recovery Workflow

### Project Profile

| Attribute | Specification |
| :--- | :--- |
| **Project ID** | `PRJ-DEMO-RECOVERY-01` |
| **Project Name** | Transmission Grid Substation & 400kV Loop (Package II) |
| **Sector / Ministry** | Power / Ministry of Power |
| **State / Location** | Madhya Pradesh |
| **Original Approved Cost** | ₹50.00 Cr |
| **Revised Sanction Cost** | ₹50.00 Cr (re-baselined to ₹80.00 Cr at Month 5) |
| **Sanction Date** | 2022-01 |
| **Contractor** | Sterling & Wilson Power Infratech Ltd |
| **Initial Monitoring Month** | 2024-01 |

### Month-by-Month Governance Progression

| Month | Period | Fin. Prog | Burn (₹ Cr) | Delay | $P_{\text{cal}}$ | Risk Tier | Governance Action | Recovery State |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M1** | 2024-01 | 10.0% | ₹5.00 Cr | 0.0m | **0.4005** | `WATCH` | `NONE` | — |
| **M2** | 2024-02 | 11.0% | ₹6.00 Cr | 0.0m | **0.4005** | `WATCH` | `NONE` | — |
| **M3** | 2024-03 | 11.2% | ₹35.00 Cr | 36.0m | **0.5195** | `ESCALATE` | `CONTRACTOR_WARNING_ISSUED` | `ACTIVE` |
| **M4** | 2024-04 | 13.5% | ₹37.00 Cr | 36.0m | **0.5195** | `ESCALATE` | `NONE` | `PERSISTENT_DETERIORATION` |
| **M5** | 2024-05 | 25.0% | ₹20.00 Cr | 0.0m | **0.4005** | `WATCH` | `PROJECT_RECOVERED` | `RECOVERED` |

### Step-by-Step Narrative

#### Month 1 (2024-01): Healthy Baseline
- **Observed Metrics**: Financial progress 10.0%, cumulative spend ₹5.0 Cr (10% of baseline), schedule delay 0.0 months.
- **Engine Output**: Calibrated risk is **40.05% (`WATCH`)**, `trajectory_status: INSUFFICIENT_HISTORY`.
- **Governance Outcome**: No intervention required (`action: NONE`). Baseline recorded in audit ledger.

#### Month 2 (2024-02): Minor Deterioration Begins
- **Observed Metrics**: Progress advances slightly to 11.0% (+1.0%/mo), expenditure ₹6.0 Cr, schedule delay remains 0.0 months.
- **Engine Output**: 1-month financial velocity recorded at $V_{\text{fin}} = 1.00\%$/mo. Calibrated risk remains at **40.05% (`WATCH`)**.
- **Governance Outcome**: Continues under active routine observation (`action: NONE`).

#### Month 3 (2024-03): Severe Deterioration & Warning Notice
- **Observed Metrics**: Financial progress stalls at 11.2% (+0.2%/mo velocity). Subcontractor right-of-way disputes trigger ₹35.0 Cr expenditure surge (70% of sanction) and a 36.0-month schedule slippage.
- **Engine Output**: Calibrated risk jumps to **51.95% (`ESCALATE`)**. Kinetic trajectory risk index escalates.
- **Governance Outcome**: SANKET triggers **`CONTRACTOR_WARNING_ISSUED`** (`WARN-XXXX`). 15-day cure notice issued requesting acknowledgment and recovery plan.

#### Post-Month 3: Formal Contractor Recovery Submission
Between Month 3 and Month 4, the contractor submits formal acknowledgment and recovery plan via `POST /api/monitor/projects/{id}/warnings/{wid}/response`:
```json
{
  "acknowledged": true,
  "response_text": "Sterling & Wilson Power Infratech formally acknowledges receipt of SANKET Early-Warning Notice. The delay was caused by a temporary liquidity bottleneck with earthmoving subcontractors. All outstanding disbursements have been cleared and escrow accounts replenished.",
  "corrective_action": "1. Deployed 2 additional automated tensioning units to double line-stringing velocity.\n2. Instituted 24x7 double-shift site assembly for tower footing.\n3. Mobilized 120 additional skilled technical personnel.",
  "expected_recovery_date": "2025-06",
  "responsible_person": "Er. Vikramaditya Rathore, VP Power Infrastructure"
}
```
Warning state advances to `RESPONSE_SUBMITTED`; project state updates to `UNDER_RECOVERY`.

#### Month 4 (2024-04): Corrective Action Underway & Velocity Resumes
- **Observed Metrics**: Site works remobilize. Progress advances to 13.5% (+2.3%/mo velocity resumption). Schedule delay stabilized at 36.0m.
- **Engine Output**: Calibrated risk remains in ESCALATE zone at **51.95%** due to historical cost surge.
- **Governance Outcome**: Persistence cycle count is 2 (threshold is 3). Action remains `NONE` (`recovery_status: PERSISTENT_DETERIORATION`), giving the contractor time to execute the cure plan.

#### Month 5 (2024-05): Trajectory Acceleration & Confirmed Recovery
- **Observed Metrics**: Automated stringing units accelerate progress to 25.0% (+11.5%/mo velocity jump). Ministry approves formal revised sanction to ₹80.0 Cr, and revised schedule delay is cleared to 0.0m.
- **Engine Output**: Calibrated risk drops sharply to **40.05% (`WATCH` < 50.0%)**. Trajectory kinetic index normalizes.
- **Governance Outcome**: SANKET state machine verifies:
  1. $P_{\text{cal}} < 0.50$ (Risk reduced).
  2. Velocity accelerated ($V_{\text{fin}} = 11.50\%$/mo $> 0.20\%$/mo at warning).
  3. Schedule delay stabilized ($0.0\text{m} \le 36.0\text{m}$).
- **Final Action**: **`PROJECT_RECOVERED`**. Warning status updated to `RECOVERED`; project status updated to `RECOVERED`. `RECOVERY_DETECTED` event logged to immutable audit ledger.

---

## Scenario 2: Authority Escalation Workflow

### Project Profile

| Attribute | Specification |
| :--- | :--- |
| **Project ID** | `PRJ-DEMO-ESCALATE-02` |
| **Project Name** | Eastern Dedicated Freight Rail Feeder Link (Package IV) |
| **Sector / Ministry** | Railways / Ministry of Railways |
| **State / Location** | West Bengal |
| **Original Approved Cost** | ₹50.00 Cr |
| **Revised Sanction Cost** | ₹50.00 Cr |
| **Sanction Date** | 2022-01 |
| **Contractor** | Navayuga-Braithwaite Joint Venture |
| **Initial Monitoring Month** | 2024-10 |

### Month-by-Month Governance Progression

| Month | Period | Fin. Prog | Burn (₹ Cr) | Delay | $P_{\text{cal}}$ | Risk Tier | Governance Action | Recovery State |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **M1** | 2024-10 | 10.0% | ₹5.00 Cr | 0.0m | **0.4292** | `WATCH` | `NONE` | — |
| **M2** | 2024-11 | 12.0% | ₹6.00 Cr | 0.0m | **0.4005** | `WATCH` | `NONE` | — |
| **M3** | 2024-12 | 12.5% | ₹7.00 Cr | 2.0m | **0.4005** | `WATCH` | `NONE` | — |
| **M4** | 2025-01 | 12.5% | ₹40.00 Cr | 36.0m | **0.6197** | `ESCALATE` | `CONTRACTOR_WARNING_ISSUED` | `ACTIVE` |
| **M5** | 2025-02 | 12.5% | ₹42.00 Cr | 38.0m | **0.6773** | `ESCALATE` | `NONE` | `PERSISTENT_DETERIORATION` (Cycle 2) |
| **M6** | 2025-03 | 12.5% | ₹44.00 Cr | 42.0m | **0.6197** | `ESCALATE` | `NONE` | `PERSISTENT_DETERIORATION` (Cycle 3) |
| **M7** | 2025-04 | 12.5% | ₹46.00 Cr | 48.0m | **0.6197** | `ESCALATE` | `AUTHORITY_ESCALATION_ISSUED` | `PERSISTENT_DETERIORATION` (Cycle 4 $\ge$ 4) |

### Step-by-Step Narrative

#### Months 1 to 3 (2024-10 to 2024-12): Incipient Deterioration
- Initial earthworks proceed at 10.0% to 12.5% progress.
- Mild delay (+2.0m) reported in Month 3 due to pier footing seepage.
- Calibrated risk remains in `WATCH` zone (**42.92% $\to$ 40.05% $\to$ 40.05%**). Action is `NONE`.

#### Month 4 (2025-01): Severe Stall & Contractor Warning
- Progress freezes completely at 12.5% ($V_{\text{fin}} = 0.0\%$/mo).
- Working capital dispute between JV partners triggers ₹40.0 Cr expenditure surge without progress and 36.0-month schedule slippage.
- Calibrated risk surges to **61.97% (`ESCALATE`)**.
- **Action**: **`CONTRACTOR_WARNING_ISSUED`** (`WARN-YYYY`). 15-day response cure window initiated.

#### Post-Month 4: Contractor Excuses / Inadequate Response
Contractor submits formal response citing partner disputes and requesting extension without mobilization:
```json
{
  "acknowledged": true,
  "response_text": "Navayuga-Braithwaite JV acknowledges receipt of SANKET Warning Notice. Working capital bottleneck due to consortium restructuring.",
  "corrective_action": "1. Seeking credit limits from lenders.\n2. Pledged to deploy tampers upon bill clearance.\n3. Requested 6-month non-penalty extension.",
  "expected_recovery_date": "2025-09",
  "responsible_person": "Debasish Mukherjee, Project Director"
}
```

#### Month 5 (2025-02): Stagnation Persists (Cycle 2)
- Zero physical progress recorded (still 12.5%). Spend continues to ₹42.0 Cr. Schedule slips to 38.0m.
- Calibrated risk elevates to **67.73% (`ESCALATE`)**.
- Persistence count advances to 2. Action: `NONE`.

#### Month 6 (2025-03): Arbitration & Frozen Accounts (Cycle 3)
- Progress remains at 12.5%. Subcontractors initiate civil arbitration. Schedule slips to 42.0m.
- Calibrated risk remains **61.97% (`ESCALATE`)**.
- Persistence count advances to 3. Action: `NONE`.

#### Month 7 (2025-04): Complete Abandonment & Authority Escalation (Cycle 4)
- Site completely abandoned. Schedule delay increases to 48.0m. Cumulative expenditure reaches ₹46.0 Cr (92% of original sanction).
- Calibrated risk remains **61.97% (`ESCALATE`)**.
- Persistence count reaches 4 $\ge$ mandatory escalation threshold (4 cycles).
- **Governance Action**: **`AUTHORITY_ESCALATION_ISSUED`**.
- Formal dossier `ESC-ZZZZ` generated and permanently archived in `authority_escalations`. Project status transitioned to `ESCALATED`.

---

## Execution & Reproducibility Guide

### 1. Command Line Interface (CLI)

Run the deterministic demo generator directly from terminal:

```bash
# Seed both scenarios into default production database (DATA/sanket_monitoring.db)
PYTHONPATH=. .venv/bin/python sanket/demo_scenarios.py --scenario all

# Seed specific scenario into isolated test database
PYTHONPATH=. .venv/bin/python sanket/demo_scenarios.py --scenario 1 --db DATA/test_scenario1.db
PYTHONPATH=. .venv/bin/python sanket/demo_scenarios.py --scenario 2 --db DATA/test_scenario2.db
```

### 2. REST API Integration

Trigger automated seeding via FastAPI endpoints:

```bash
# Seed all scenarios
curl -X POST "http://localhost:8000/api/monitor/demo/seed?scenario=all"

# Inspect Scenario 1 status (Recovered)
curl -X GET "http://localhost:8000/api/monitor/projects/PRJ-DEMO-RECOVERY-01/status"

# Inspect Scenario 2 escalations (Escalated to oversight authorities)
curl -X GET "http://localhost:8000/api/monitor/escalations"
```

### 3. Automated Pytest Verification

Execute automated test suite proving all monthly state transitions:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_demo_scenarios.py -v
```
All 4 tests execute in under 3 seconds with 100% deterministic reproducibility.
