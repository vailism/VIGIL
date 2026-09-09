# SANKET Portfolio Sanitization & Governance Audit

## Executive Summary

An audit of the SANKET Command Center telemetry revealed contamination of presentation metrics caused by automated PDF table extraction of MoSPI Flash Report executive summary tables (Tables 1–12 front matter). These tables contain aggregate macro totals across entire ministries, sectors, and states (e.g. Table 7 and Table 11 Railways totals) that lacked explicit project codes and were assigned synthetic hash identifiers (prefixed with `PRJ_`).

When treated as individual projects, these macro rows inflated:
- Total portfolio entity counts (115,693 raw extracted identities)
- Active capital exposure (previously reported as ₹189.2 Lakh Cr)
- Operational risk tier counts
- Sector capital allocations
- Intervention queue rankings (where `PRJ_BB0B04A558ED` and `PRJ_7A8AEAB9026C`, representing ₹6.87 Lakh Cr aggregate Railways totals, dominated the top ranks).

To establish an institutional-grade, governance-safe presentation layer while **strictly freezing the research dataset (`DATA/model_dataset.parquet`), ML model, target definitions, trajectory mathematics, and backtesting methodology**, SANKET implements the **Portfolio Sanitization Layer** (`sanket/portfolio.py`).

---

## 1. Quantitative Portfolio Transformation

| Metric | Raw Extraction (Pre-Sanitization) | Sanitized Active Portfolio (2024–2025) | Net Impact |
| :--- | :--- | :--- | :--- |
| **Tracked Entity Count** | 115,693 identities | **2,319 active projects** | Cleaned 113,374 non-active/artifact rows |
| **Total Baseline Exposure** | ₹1,89,21,115 Cr (₹189.2 Lakh Cr) | **₹38,24,415 Cr (₹38.24 Lakh Cr)** | -79.8% (-₹150.97 Lakh Cr artifact removal) |
| **Risk-Weighted Exposure** | ₹94,60,557 Cr (₹94.6 Lakh Cr) | **₹19,13,080 Cr (₹19.13 Lakh Cr)** | Accurate risk-calibrated exposure |
| **ESCALATE Tier Count** | 71,452 | **1,407 projects** | Operational signal restored |
| **REVIEW Tier Count** | 9,142 | **175 projects** | Actionable governance queue |
| **WATCH Tier Count** | 22,810 | **435 projects** | Clean early-warning cohort |
| **NORMAL Tier Count** | 12,289 | **302 projects** | Stable baseline cohort |

### Archive Breakdown
- **Total Raw Extracted Identities**: `115,693`
- **Excluded Macro-Summary / Synthetic Artifacts**: `111,522`
- **Total Genuine Infrastructure Projects**: `4,171`
  - **Active Monitoring Portfolio (2024–2025)**: `2,319` projects (`latest_observation >= 2024-01`)
  - **Historical Longitudinal Archive (2003–2023)**: `1,852` projects (`latest_observation < 2024-01`)

---

## 2. Exact Exclusion Rules

The sanitization layer prioritizes **identity and source semantics** rather than arbitrary cost thresholds. Genuine public infrastructure projects can legitimately exceed ₹50,000 Cr, so cost-based truncation was strictly avoided.

1. **Rule 1 — Official Identifier Validation**:
   Genuine projects must possess an authentic MoSPI project identifier:
   - 8–9 digit numeric codes assigned by MoSPI (e.g., `180100210`, `220100133`).
   - Alphanumeric OCMS (Online Computerized Monitoring System) project codes (e.g., `N22000463`, `N02000028`, `N16000518`).
2. **Rule 2 — Macro-Summary Keyword Exclusion**:
   Any entity whose name matches executive flash report headings is excluded:
   `\bFLA\b`, `\bLAS\b`, `\bMULTI\s*STATE\b`, `\bTOTAL\b`, `\bSUMMARY\b`, `\bALL\s*INDIA\b`, `\bGRAND\s*TOTAL\b`.
3. **Rule 3 — Multi-Sector Concatenations**:
   Front-matter summary tables joining sector aggregates are excluded:
   - `RAILWAYS LAS ROAD TRANSPORT AND HIGHWAYS`
   - `ROAD TRANSPORT AND HIGHWAYS AS SHIPPING AND PORTS`
   - `PETROLEUM AS POWER`
   - `COAL A MINES`
4. **Rule 4 — State Aggregate Rows**:
   Rows representing state-wide summary tables (e.g., `KERALA`, `ARUNACHAL PRADESH`, `UTTARAKHAND`, `PUNJAB`, `TELANGANA`, `STATE : BIHAR`) are excluded.
5. **Rule 5 — Sector Aggregate Rows**:
   Rows representing sector-level summary tables (e.g., `RAILWAYS`, `POWER`, `ROAD TRANSPORT AND HIGHWAYS`, `TELECOMMUNICATIONS`) are excluded.
6. **Rule 6 — Executive Front-Matter Tokens**:
   Rows sourced from non-project tables matching `EXECUTIVE SUMMARY`, `HIGHLIGHTS`, `STATEMENT`, or `TABLE` are excluded.
7. **Rule 7 — Temporal Partitioning**:
   - `ACTIVE MONITORING PORTFOLIO`: `latest_observation >= 2024-01`
   - `HISTORICAL LONGITUDINAL ARCHIVE`: `latest_observation < 2024-01`

---

## 3. Excluded Entity Audit (Examples)

The following entities were prominent in the pre-sanitization queue and are now strictly excluded:

| Project ID | Raw Entity Name | Sector | Baseline Cost (Cr) | Extraction Nature |
| :--- | :--- | :--- | :--- | :--- |
| `PRJ_BB0B04A558ED` | `FLA RAILWAYS` | OTHER | ₹6,87,288.42 | MoSPI Flash Report Table 7 (All Railways Total) |
| `PRJ_7A8AEAB9026C` | `FLA RAILWAYS` | OTHER | ₹6,87,288.42 | MoSPI Flash Report Table 11 (Duplicate Railways Total) |
| `PRJ_97FDB60EFC74` | `RAILWAYS LAS ROAD TRANSPORT...` | OTHER | ₹6,68,133.77 | Front-matter multi-sector summary row |
| `PRJ_7E1127E0E912` | `MULTI STATE` | OTHER | ₹4,81,156.64 | State summary table (Multi-state total) |
| `PRJ_005CDEFE4BD6` | `KERALA` | OTHER | ₹72,524.97 | MoSPI Table 12 State-level summary row |
| `PRJ_DAB05D8CA1CF` | `ARUNACHAL PRADESH` | OTHER | ₹63,829.33 | MoSPI Table 12 State-level summary row |
| `PRJ_0449ED559A91` | `TELECOMMUNICATIO NS` | OTHER | ₹40,295.69 | Sector-wide aggregate table row |

---

## 4. Legitimate Large Projects Retained

Because sanitization is based on identity semantics rather than cost thresholds, authentic mega-projects are preserved in full:

| Project ID | Project Name | Sector | Baseline Cost (Cr) | Latest Obs | Risk Tier |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `N22000463` | Mumbai Ahmedabad High Speed Rail (NHSRCL) | Railways | ₹1,08,000.00 | 2025-03 | ESCALATE |
| `N16000513` | Rajasthan Refinery Project (HPCLRRL) | Petroleum | ₹72,937.00 | 2025-03 | ESCALATE |
| `N02000028` | Kudankulam Nuclear Power Project Unit-3 & 4 (NPCIL) | Atomic Energy | ₹68,893.00 | 2024-12 | REVIEW |
| `N30000002` | Polavaram Irrigation Project (PPA) | Water Resources | ₹55,548.87 | 2025-03 | WATCH |
| `N22000464` | Western Dedicated Freight Corridor (DFCC) | Railways | ₹51,101.00 | 2025-03 | ESCALATE |
| `N02000029` | Kudankulam Nuclear Power Project Unit-5 & 6 (NPCIL) | Atomic Energy | ₹49,621.00 | 2024-12 | WATCH |
| `N16000518` | Ethylene Cracker Project at Bina Refinery (BPCL) | Petroleum | ₹43,367.00 | 2025-03 | ESCALATE |
| `N28000056` | Delhi MRTS Phase-III (DMRC) | Urban Development | ₹43,095.35 | 2025-03 | REVIEW |
| `N16000412` | Panipat Refinery Capacity Expansion 15 to 25 MMTPA (IOCL) | Petroleum | ₹38,231.00 | 2025-03 | ESCALATE |
| `220100133` | Udhampur-Srinagar-Baramulla Railway Line (NR) | Railways | ₹37,012.26 | 2025-03 | ESCALATE |

---

## 5. Active Central Sector Exposure (Sanitized)

The active portfolio exhibits an authentic sector distribution aligning with MoSPI Flash Report publications:

| Sector | Active Projects | ESCALATE | REVIEW | WATCH | Active Capital Exposure |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Road Transport & Highways** | 1,133 | 821 | 91 | 161 | ₹9,22,895 Cr (₹9.23 Lakh Cr) |
| **Railways** | 330 | 185 | 32 | 90 | ₹6,99,424 Cr (₹6.99 Lakh Cr) |
| **Petroleum** | 208 | 134 | 22 | 41 | ₹6,01,494 Cr (₹6.01 Lakh Cr) |
| **Power** | 168 | 114 | 11 | 37 | ₹5,27,895 Cr (₹5.28 Lakh Cr) |
| **Urban Development** | 32 | 19 | 4 | 7 | ₹3,14,125 Cr (₹3.14 Lakh Cr) |
| **Coal** | 195 | 59 | 7 | 48 | ₹2,76,137 Cr (₹2.76 Lakh Cr) |
| **Atomic Energy** | 5 | 0 | 1 | 4 | ₹1,67,447 Cr (₹1.67 Lakh Cr) |
| **Steel** | 26 | 13 | 1 | 8 | ₹85,060 Cr |
| **Water Resources** | 41 | 18 | 3 | 13 | ₹69,573 Cr |
| **Telecommunications** | 7 | 4 | 0 | 2 | ₹61,903 Cr |
| **Civil Aviation** | 60 | 25 | 1 | 11 | ₹43,380 Cr |
| **Other / Central Ministries** | 114 | 15 | 2 | 13 | ₹54,082 Cr |
| **Total Active Portfolio** | **2,319** | **1,407** | **175** | **435** | **₹38,24,415 Cr (₹38.24 Lakh Cr)** |

---

## 6. Top 10 National Intervention Priority Queue

Projects are ranked descending by **Risk-Weighted Exposure**:
$$\text{Priority Score} = \text{Calibrated 12-Month Deterioration Probability} \times \text{Baseline Capital Exposure}$$

| Rank | Project ID | Project Name | Sector | Risk Tier | Calibrated Risk | Baseline Exposure | Risk-Weighted Exposure |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| 1 | `N22000463` | Mumbai Ahmedabad High Speed Rail Project (NHSRCL) | Railways | ESCALATE | 58.8% | ₹1,08,000 Cr | ₹63,482 Cr |
| 2 | `N16000513` | Rajasthan Refinery Project (HPCLRRL) | Petroleum | ESCALATE | 56.6% | ₹72,937 Cr | ₹41,268 Cr |
| 3 | `N02000028` | Kudankulam Nuclear Power Project Unit-3 & 4 (NPCIL) | Atomic Energy | REVIEW | 49.2% | ₹68,893 Cr | ₹33,868 Cr |
| 4 | `N22000464` | Western Dedicated Freight Corridor (DFCC) | Railways | ESCALATE | 54.7% | ₹51,101 Cr | ₹27,947 Cr |
| 5 | `N30000002` | Polavaram Irrigation Project (PPA) | Water Resources | WATCH | 40.1% | ₹55,549 Cr | ₹22,247 Cr |
| 6 | `N16000412` | Capacity Expansion of Panipat Refinery 15 to 25 MMTPA (IOCL) | Petroleum | ESCALATE | 56.6% | ₹38,231 Cr | ₹21,631 Cr |
| 7 | `N28000056` | Delhi MRTS Phase-III (DMRC) | Urban Development | REVIEW | 49.2% | ₹43,095 Cr | ₹21,186 Cr |
| 8 | `220100133` | Udhampur-Srinagar-Baramulla Rail Link (NR) | Railways | ESCALATE | 54.5% | ₹37,012 Cr | ₹20,168 Cr |
| 9 | `N02000029` | Kudankulam Nuclear Power Project Unit-5 & 6 (NPCIL) | Atomic Energy | WATCH | 40.1% | ₹49,621 Cr | ₹19,873 Cr |
| 10 | `N16000247` | KG-DWN-98-2 Cluster II Development Project (ONGC) | Petroleum | ESCALATE | 56.6% | ₹34,012 Cr | ₹19,244 Cr |

---

## 7. Compliance Verification

- [x] Frozen research dataset (`DATA/model_dataset.parquet`, `DATA/project_monthly.csv`) untouched.
- [x] ML model, weights, features, and calibrator untouched.
- [x] Validated operating thresholds preserved: WATCH $\ge 0.40$, REVIEW $\ge 0.45$, ESCALATE $\ge 0.50$.
- [x] Historical median early warning lead time benchmark remains 3.0 months.
- [x] Zero LLM generation in scoring or prioritization.
- [x] Complete test suite passing.
