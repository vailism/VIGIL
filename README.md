
# VIGIL
## Infrastructure Early-Warning & Project Trajectory Intelligence System

> **VIGIL monitors where infrastructure projects are heading — not just where they are today.**

VIGIL is an AI-powered early-warning system for large infrastructure projects. It analyzes historical project progress, expenditure, schedule behavior, and trajectory changes to identify projects that are **drifting toward cost or schedule overruns before conventional monitoring systems would flag them**.

The system is designed around a simple distinction:

**Traditional monitoring:**  
> What is the current status of the project?

**VIGIL:**  
> Is the project's trajectory getting worse, and what is likely to happen next?

---

# 1. Problem

Large infrastructure projects are monitored using periodic reports containing information such as:
- Physical progress
- Financial progress
- Expenditure
- Approved project cost
- Revised project cost
- Completion schedules
- Milestones
- Project status

However, a project may still appear acceptable when its underlying trajectory has already started deteriorating.

For example:

```text
Month       Progress       Interpretation
January       42%          Normal
February      44%          Normal
March         45%          Slight slowdown
April         46%          Significant slowdown
May           46.5%        Persistent deterioration
June          47%          High-risk trajectory
```

A conventional status-based system may only identify the problem once the project is already delayed.

VIGIL attempts to detect the deterioration before the failure becomes obvious.

---

# 2. Core Idea

VIGIL follows two complementary approaches:

### Trajectory Intelligence
Detect changes in how a project is progressing.

```text
Progress
   ↓
Velocity
   ↓
Acceleration
   ↓
EWMA / CUSUM
   ↓
Peer deviation
   ↓
Trajectory risk
```

### Predictive Intelligence
Use historical project behavior to estimate the probability of a future overrun.

```text
Historical project data
        ↓
Temporal features
        ↓
LightGBM
        ↓
6-month overrun probability
```

The final system combines these signals into an actionable early-warning system.

---

# 3. System Architecture

```text
                PAIMANA / OCMS REPORTS
                         │
                         ▼
                ┌─────────────────┐
                │ PDF INGESTION   │
                │ & EXTRACTION    │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ NORMALIZATION   │
                │ & VALIDATION    │
                └────────┬────────┘
                         │
                         ▼
              PROJECT × MONTH DATASET
                         │
                 ┌───────┴────────┐
                 ▼                ▼
        ┌────────────────┐ ┌────────────────┐
        │  TRAJECTORY    │ │  PREDICTIVE    │
        │    ENGINE      │ │    ENGINE      │
        │                │ │                │
        │ Velocity       │ │ LightGBM       │
        │ Acceleration   │ │ 6/12 month     │
        │ EWMA           │ │ prediction     │
        │ CUSUM          │ │                │
        │ Peer deviation │ │                │
        └───────┬────────┘ └───────┬────────┘
                │                  │
                └────────┬─────────┘
                         ▼
                ┌─────────────────┐
                │ EARLY WARNING   │
                │ ENGINE          │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ VIGIL DASHBOARD │
                │                 │
                │ National View   │
                │ Project Console │
                │ Why?            │
                │ Replay          │
                │ What-if         │
                └─────────────────┘
```

---

# 4. Current Development Stage

The project is currently in the **Data Ingestion & Normalization** stage.

The first 40 reports were processed successfully to validate the extraction architecture before scaling to the complete report collection.

### Current pilot results

```text
PDFs processed                         40
PDFs successful                        40
PDFs failed                             0
Raw extracted records              55,300
Canonical project-month records   39,017
Unique projects                     5,705
Physical progress coverage           48.5%
Financial progress coverage          94.5%
Duplicate project-month pairs            0
```

The final dataset will be regenerated after the remaining reports are processed.

*These numbers are pilot-stage metrics and are not final VIGIL dataset statistics.*

---

# 5. Data Model

The canonical dataset follows a strict rule:

**ONE ROW = ONE UNIQUE PROJECT + ONE REPORTING MONTH**

Example:

| project_id | reporting_month | physical_progress |
| :--- | :--- | :--- |
| P001 | 2023-01 | 41.2 |
| P001 | 2023-02 | 44.0 |
| P001 | 2023-03 | 45.1 |
| P001 | 2023-04 | 45.8 |

This temporal structure is essential for VIGIL.

The system must never treat multiple extracted table rows representing the same project/month as separate observations.

---

# 6. Data Pipeline

```text
PDF reports
    │
    ▼
PDF extraction
    │
    ▼
Raw extraction records
    │
    ▼
Field normalization
    │
    ▼
Project identity normalization
    │
    ▼
Project × reporting month deduplication
    │
    ▼
Canonical monthly dataset
    │
    ▼
Validation
    │
    ▼
Trajectory Engine
```

---

# 7. Repository Structure

```text
VIGIL/
│
├── DATA/
│   ├── raw_extractions.csv
│   ├── project_monthly.csv
│   ├── project_coverage.csv
│   └── projects.csv
│
├── DATA(RAW)/
│   └── *.pdf
│
├── scripts/
│   ├── extract_pdfs.py
│   ├── normalize.py
│   ├── validate.py
│   └── audit_identity.py
│
├── .venv/
│
├── requirements.txt
│
└── README.md
```

---

# 8. Important Dataset Files

### `raw_extractions.csv`
Contains the raw records extracted from the PDFs.

Raw provenance is preserved through fields such as:
- `raw_record_id`
- `source_pdf`
- `source_page`
- `raw_text`

This file should be treated as the audit layer. Raw data should not be destroyed when cleaning the canonical dataset.

---

### `project_monthly.csv`
The primary dataset used by VIGIL.

Each row represents:
**ONE PROJECT × ONE REPORTING MONTH**

Typical fields include:
- `project_id`
- `project_name`
- `reporting_month`
- `sector`
- `ministry`
- `state`
- `physical_progress`
- `financial_progress`
- `expenditure`
- `approved_cost`
- `revised_cost`
- `schedule_deviation`
- `source_pdf`
- `source_pages`

Additional provenance and extraction-quality fields may also be present.

---

### `project_coverage.csv`
Provides longitudinal coverage for each project.

Example:
- `project_id`
- `project_name`
- `first_observation`
- `last_observation`
- `observation_count`
- `missing_month_count`

This file is used to determine whether projects contain sufficient historical data for trajectory analysis.

---

### `projects.csv`
Project-level master data. One row represents one unique project.

---

### `extraction_quality.csv`
Records extraction quality for each source PDF.

Useful fields include:
- `source_pdf`
- `pages`
- `projects_detected`
- `reporting_month_detected`
- `ocr_used`
- `extraction_status`

---

### `extraction_errors.csv`
Contains PDFs/pages where extraction encountered problems. The pipeline is designed to continue processing other reports even when an individual document fails.

---

### `project_identity_review.csv`
Contains automated project-identity audit results. It is used to identify:
- Table headings
- Report headings
- Column-header artifacts
- Ministry/sector labels
- Other non-project entities

These records are reviewed before entering the canonical dataset.

---

# 9. Data Integrity Rules

The following rules are mandatory:

### Rule 1 — Canonical grain
`(project_id, reporting_month)` must be unique.

Validation:
```python
assert not project_monthly.duplicated(
    ["project_id", "reporting_month"]
).any()
```

---

### Rule 2 — No fabricated values
If a value cannot be reliably extracted:
`NULL` is preferred over guessing.

---

### Rule 3 — Preserve raw provenance
Every canonical observation should be traceable back to its source PDF/page wherever possible.

---

### Rule 4 — Do not delete raw data
Cleaning and deduplication happen in the canonical layer. The raw extraction layer remains available for auditing.

---

# 10. Trajectory Engine

Once the data ingestion stage is frozen, VIGIL will calculate temporal features.

### Progress Velocity
$$V(t) = P(t) - P(t-1)$$
This measures how quickly project progress is changing.

---

### Progress Acceleration
$$A(t) = V(t) - V(t-1)$$
This identifies whether progress itself is speeding up or slowing down.

---

### EWMA
Exponentially Weighted Moving Average will be used to reduce sensitivity to isolated noisy observations while retaining persistent changes:
$$Z(t) = \lambda X(t) + (1-\lambda)Z(t-1)$$

---

### CUSUM
CUSUM may be used to detect sustained deviations from a project’s normal behavior.

---

### Peer Deviation
Projects should not be judged using universal thresholds. A large railway project and a small water project may naturally have very different progress patterns.

VIGIL therefore compares projects against appropriate peers based on available attributes such as:
- sector
- ministry
- project size
- duration
- project stage

---

# 11. Predictive Engine

The predictive model will use **LightGBM**.

The model will not simply predict whether a project is currently delayed.

Instead:
> **At month $t$:** Predict whether an overrun will occur within the next 6 months.

Formally:
$$Y(t+6) = 1$$
if the project experiences an overrun during the following six months.

An optional 12-month prediction horizon may also be implemented.

---

# 12. Candidate Features

The initial feature set is intentionally small and interpretable:
- `project_size`
- `sector`
- `ministry`
- `project_age`
- `physical_progress`
- `financial_progress`
- `expenditure_ratio`
- `progress_velocity_1m`
- `progress_velocity_3m`
- `progress_acceleration`
- `cost_growth_3m`
- `schedule_deviation`
- `peer_progress_deviation`
- `reporting_gap`
- `milestone_slippage`

Additional features should only be added when justified by the available data.

---

# 13. Preventing Data Leakage

VIGIL must be evaluated as if it were operating in real time:

```text
March 2023
    ↓
VIGIL prediction
    ↓
April → September 2023
    ↓
Did an overrun occur?
```

The March prediction must never use information from April onward.

The model must also not use final revised costs or completion dates when those values would not have been known at prediction time.

---

# 14. Backtesting

VIGIL will use **walk-forward validation**:

```text
Train:       historical data
Test:        next time period
                     ↓
Move forward
                     ↓
Train:       expanded historical data
Test:        next time period
                     ↓
Repeat
```

This better represents how the system would behave in production.

---

# 15. Evaluation

Accuracy alone is not the primary metric.

The main metric is:

### Early-Warning Lead Time
$$\text{Lead Time} = \text{Actual Overrun Date} - \text{VIGIL Alert Date}$$

For historical projects that eventually overran, VIGIL will calculate how early it could have identified the deteriorating trajectory.

The primary headline metric will be:
$$\textbf{Median Early-Warning Lead Time}$$

Supporting metrics may include:
- Precision
- Recall
- PR-AUC
- False-alert rate
- Calibration
- Detection rate

*No performance number should be presented until it has been produced by leakage-free backtesting.*

---

# 16. Dashboard

The final dashboard will contain two primary views:

### National View
```text
VIGIL
Infrastructure Early Warning System
Projects                 XXXX
High Risk                  XX
Value at Risk           ₹XXX Cr
Median Warning           X months
INTERVENTION QUEUE
Project A     91     ↓↓↓     5 months
Project B     87     ↓↓      8 months
Project C     82     ↓       3 months
```

---

### Project Console
```text
PROJECT A
Risk                  91%
Physical Progress     47%
Financial Progress    51%
Schedule Deviation    +4.2 months
TRAJECTORY
       Progress
          │
          │        Expected
          │       /
          │     /
          │   _/
          │ _/
          └──────────────── Time
WHY?
1. Progress velocity declining
2. Schedule deviation increasing
3. Performance below peer baseline
```

---

# 17. Historical Replay

The historical replay is one of the core demonstration features.

A completed project can be replayed month by month:

```text
JAN     18%
FEB     21%
MAR     24%
APR     29%
MAY     34%
JUN     43%    ⚠
JUL     56%    🔴
AUG     71%
SEP     78%
        ACTUAL OVERRUN
```

The system then shows the point at which VIGIL would have raised an alert.

The final statement should be based entirely on actual backtesting:
> *"VIGIL would have detected the deteriorating trajectory X months before the recorded overrun."*

---

# 18. Scenario Analysis

A lightweight scenario feature may allow users to modify selected inputs and observe the resulting model sensitivity.

Example:
```text
Schedule deviation
-3 months ───────●────── +6 months
Risk:
64% → 81%
```

This should be described as a **Model Sensitivity Estimate** and not as a causal prediction.

---

# 19. Intervention Prioritization

High risk alone is not enough.

VIGIL can prioritize projects using:
$$\text{Priority} = \text{Risk} \times \text{Exposure}$$

This allows administrators to focus attention on projects where deterioration is both:
- highly probable
- potentially financially significant

The output is an intervention queue rather than an optimization system.

---

# 20. Technology Stack

- **Data & ML:** Python, Pandas, NumPy, scikit-learn, LightGBM
- **PDF Processing:** PyMuPDF, pdfplumber, Camelot / table extraction tools
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **Frontend:** React, TypeScript, Tailwind CSS, Recharts / Plotly
- **Deployment:** Docker

---

# 21. Development Roadmap

```text
PHASE 1 — DATA INGESTION
        │
        ├── PDF extraction
        ├── normalization
        ├── project identity
        ├── deduplication
        └── validation
                 │
                 ▼
PHASE 2 — TRAJECTORY ENGINE
        │
        ├── timeline builder
        ├── velocity
        ├── acceleration
        ├── EWMA
        ├── CUSUM
        └── peer deviation
                 │
                 ▼
PHASE 3 — PREDICTIVE ENGINE
        │
        ├── target generation
        ├── LightGBM
        ├── feature engineering
        └── probability calibration
                 │
                 ▼
PHASE 4 — BACKTESTING
        │
        ├── walk-forward validation
        ├── lead-time calculation
        ├── precision / recall
        └── PR-AUC
                 │
                 ▼
PHASE 5 — PRODUCT
        │
        ├── FastAPI
        ├── national dashboard
        ├── project console
        ├── historical replay
        └── intervention queue
                 │
                 ▼
PHASE 6 — POLISH
        │
        ├── scenario sensitivity
        └── optional LLM assistant
```

---

# 22. Current Priority

The immediate priority is not ML.

The remaining source reports must first be processed through the validated ingestion pipeline.

After the complete dataset is available:

```text
PDF collection
      ↓
Canonical project_monthly.csv
      ↓
DATA QUALITY FREEZE
      ↓
TIMELINE ENGINE
```

Only after the temporal dataset has been verified should model development begin.

---

# 23. Design Principles

- **Monitor the direction, not the state:** A project that is deteriorating slowly may be more important than a project that is already delayed but stable.
- **Never use future information:** Predictions must represent what could genuinely have been known at that time.
- **Prefer interpretable signals:** Velocity, acceleration, peer deviation, and schedule behavior should remain understandable to administrators.
- **Never fabricate performance:** All model metrics must come from actual backtesting.
- **Preserve provenance:** Every important prediction should ultimately be traceable to the underlying project observations.
- **Keep the system focused:** VIGIL is an early-warning system, not a generic AI chatbot.

---

# 24. Final Vision

VIGIL transforms infrastructure monitoring from:
> *"What went wrong?"*

to:
> *"Where are we heading?"*

The objective is not simply to identify failed projects. The objective is to identify the trajectory toward failure early enough for intervention to still matter.

---

### Status
- **Current:** Data ingestion and validation
- **Next:** Trajectory Intelligence Engine
- **Target:** Leakage-free infrastructure early-warning system with measurable early-warning lead time.

---

### Project
**VIGIL** — Infrastructure Early-Warning & Project Trajectory Intelligence System  
*Built for intelligent, proactive infrastructure project monitoring.*

---

## License

This project is licensed under the [MIT License](LICENSE).
---

# 25. SANKET — Infrastructure Risk Admin Dashboard

A production-quality command-center dashboard for government infrastructure risk monitoring and intelligence. Built with vanilla HTML, CSS, and JavaScript.

![Status](https://img.shields.io/badge/status-operational-10b981)
![Security](https://img.shields.io/badge/security-TLS%201.3-06b6d4)
![Clearance](https://img.shields.io/badge/clearance-TIER--1-ef4444)

## Features

- **Portfolio Vital Metrics** — Total monitored projects, high-risk excursions, value-at-risk, warning lead times
- **Ongoing Projects** — Filterable, scored project cards with severity indicators
- **Trajectory Divergence Model** — SVG line chart with anomaly markers, discrepancy annotations, and deviation envelopes
- **Execution Disparity** — Radial score, physical vs. financial progress spread, quarterly bar chart
- **Sensor Array Status** — Live sensor meters (RTK, InSAR, LiDAR, Strain)
- **AI Analyst Assistant** — Chat panel powered by Google Gemini for data-driven risk analysis
- **Responsive Design** — Desktop-first with tablet and mobile breakpoints

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Typography | Inter + JetBrains Mono (Google Fonts) |
| Charts | Custom SVG rendering |
| Backend | Node.js + Express |
| AI | Google Gemini API (`@google/generative-ai`) |

## Quick Start

### Prerequisites

- **Node.js** ≥ 18
- A [Google Gemini API key](https://aistudio.google.com/app/apikey) (optional — dashboard works without it)

### Installation

```bash
# Clone and install
cd frontend
npm install

# Configure environment (optional, for AI assistant)
cp .env.example .env
# Edit .env and add your Gemini API key
```

### Running

```bash
npm start
# → Server runs at http://localhost:3001
```

Open [http://localhost:3001](http://localhost:3001) in your browser.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | No | Google Gemini API key for the AI assistant |
| `PORT` | No | Server port (default: `3001`) |

> **Security**: The API key is read server-side only. It is never exposed to the frontend. The `.env` file is git-ignored.

## Project Structure

```
frontend/
├── server.js              # Express server + Gemini API route
├── package.json
├── .env.example           # Environment template
├── .gitignore
├── README.md
└── public/
    ├── index.html         # Main dashboard HTML
    ├── css/
    │   └── styles.css     # Complete stylesheet (tokens, layout, components)
    └── js/
        ├── data.js        # Mock dashboard data
        ├── charts.js      # SVG sparkline + trajectory chart renderer
        ├── assistant.js   # AI assistant (panel, API, persistence)
        └── app.js         # Main controller (init, events, interactions)
```

## Gemini AI Assistant

The AI assistant is accessible via the floating cyan button in the lower-right corner. It connects to the Gemini API through `POST /api/assistant`.

### How it works

1. Frontend sends the user message + a dashboard context snapshot
2. Express server forwards to Gemini with a system prompt instructing it to be a concise infrastructure-risk analyst
3. Response is displayed in the chat panel with citation formatting

### Configuration

1. Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Copy `.env.example` to `.env`
3. Replace `your_gemini_api_key_here` with your actual key
4. Restart the server

### Without a key

The dashboard is fully functional without an API key. The AI assistant will show a friendly offline message.

## API Reference

### `POST /api/assistant`

**Request body:**
```json
{
  "message": "Why is NH-44 flagged critical?",
  "context": { /* dashboard snapshot */ }
}
```

**Success response (200):**
```json
{
  "reply": "NH-44 Package 3B is flagged critical with a score of 92/100 due to..."
}
```

**Error responses:**
- `400` — Missing or invalid message
- `429` — Rate limit exceeded
- `500` — Gemini API error
- `503` — API key not configured

## Responsive Breakpoints

| Breakpoint | Layout |
|------------|--------|
| > 1280px | Full 3-column grid |
| 1024–1280px | Compact 3-column |
| 768–1024px | 2-column + stacked detail |
| < 768px | Single column |

## License

This project is provided for demonstration purposes.

