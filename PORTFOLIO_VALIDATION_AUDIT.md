# SANKET Backend Validation — Portfolio Audit

## Executive Overview

This validation audit provides a rigorous, empirical verification of the **SANKET Portfolio Sanitization Layer** (`sanket/portfolio.py`) before final freeze.

In accordance with institutional governance directives:
- **Research datasets (`DATA/model_dataset.parquet`, `DATA/project_monthly.csv`) remain 100% frozen.**
- **Machine learning models, weights, features, and calibrators are untouched.**
- **Target definitions, trajectory mathematics, and backtesting methodologies remain frozen.**
- **Zero frontend/UI code changes were introduced.**

All findings documented herein are backed by measured data and reproducible unit tests in `tests/test_portfolio.py` (61/61 test suite passing).

---

## 1. Exposure Reconciliation

### 1.1 Active Portfolio Summary
- **Active Project Count**: `2,319` projects
- **Active Baseline Exposure ($C_{base}$)**: `₹38,24,415.25 Cr` (**₹38.24 Lakh Cr**)
- **Risk-Weighted Exposure**: `₹19,13,079.66 Cr` (**₹19.13 Lakh Cr**)
- **Currency Units Confirmation**: `C_base` is strictly denominated in **₹ Crore** across all parquet tables, feature transformers, inference engines, and API endpoints.

### 1.2 Cumulative Exposure Concentration
Capital exposure in India's central infrastructure portfolio exhibits an authentic power-law distribution characteristic of major sovereign capital works:

| Cohort | Project Count | Cumulative Exposure (₹ Cr) | % of Active Capital Exposure |
| :--- | :---: | :---: | :---: |
| **Top 1% Mega Assets** | 23 projects | ₹9,69,759.00 Cr | **25.36%** |
| **Top 5% Portfolio** | 116 projects | ₹19,24,461.04 Cr | **50.32%** |
| **Top 10% Portfolio** | 232 projects | ₹23,22,081.03 Cr | **60.72%** |
| **Remaining 90%** | 2,087 projects | ₹15,02,334.22 Cr | **39.28%** |
| **Total Active Portfolio** | **2,319 projects** | **₹38,24,415.25 Cr** | **100.00%** |

### 1.3 Sector-Level Exposure Totals & Asset Counts

| Sector | Active Projects | Total Exposure (₹ Cr) | % Exposure | ESCALATE Count |
| :--- | :---: | :---: | :---: | :---: |
| **Road Transport And Highways** | 1,133 | ₹9,22,895.34 Cr | 24.13% | 613 (54.1%) |
| **Railways** | 330 | ₹6,99,423.89 Cr | 18.29% | 242 (73.3%) |
| **Petroleum** | 208 | ₹6,01,493.56 Cr | 15.73% | 122 (58.7%) |
| **Power** | 168 | ₹5,27,894.93 Cr | 13.80% | 121 (72.0%) |
| **Urban Development** | 32 | ₹3,14,125.35 Cr | 8.21% | 15 (46.9%) |
| **Coal** | 195 | ₹2,76,137.33 Cr | 7.22% | 113 (57.9%) |
| **Atomic Energy** | 5 | ₹1,67,447.00 Cr | 4.38% | 0 (0.0%) |
| **Steel** | 26 | ₹85,059.79 Cr | 2.22% | 11 (42.3%) |
| **Water Resources** | 41 | ₹69,572.77 Cr | 1.82% | 30 (73.2%) |
| **Telecommunications** | 7 | ₹61,903.34 Cr | 1.62% | 2 (28.6%) |
| **Civil Aviation** | 60 | ₹43,379.60 Cr | 1.13% | 48 (80.0%) |
| **Other Central Ministries** | 88 | ₹28,708.28 Cr | 0.75% | 69 (78.4%) |
| **Mines** | 9 | ₹10,000.88 Cr | 0.26% | 6 (66.7%) |
| **Health and Family Welfare** | 10 | ₹7,912.12 Cr | 0.21% | 8 (80.0%) |
| **Shipping and Ports** | 1 | ₹5,061.15 Cr | 0.13% | 1 (100.0%) |
| **Finance** | 5 | ₹3,199.92 Cr | 0.08% | 5 (100.0%) |
| **Defence** | 1 | ₹200.00 Cr | 0.01% | 1 (100.0%) |

---

## 2. Top 50 Active Projects by Baseline Exposure ($C_{base}$)

| # | Project ID | Reporting Month | Sector | Baseline Cost ($C_{base}$) | Approved Cost | Revised Cost | Project Name |
| :-: | :--- | :-: | :--- | :-: | :-: | :-: | :--- |
| 1 | `N22000463` | 2025-03 | Railways | ₹1,08,000.00 Cr | ₹1,08,000.00 Cr | ₹1,08,000.00 Cr | MUMBAI AHMEDABAD HIGH SPEED RAIL PROJECT (NHSRCL) |
| 2 | `N16000513` | 2025-03 | Petroleum | ₹72,937.00 Cr | ₹43,129.00 Cr | ₹72,937.00 Cr | RAJASTHAN REFINERY PROJECT (HPCLRRL(JV)) |
| 3 | `N02000028` | 2024-12 | Atomic Energy | ₹68,893.00 Cr | ₹39,849.00 Cr | ₹68,893.00 Cr | KUDANKULAM NUCLEAR POWER PROJECT UNIT-3 & 4 (NPCIL) |
| 4 | `N30000002` | 2025-03 | Water Resources | ₹55,548.87 Cr | ₹10,151.04 Cr | ₹55,548.87 Cr | POLAVARAM IRRIGATION PROJECT (PPA) |
| 5 | `N22000464` | 2025-03 | Railways | ₹51,101.00 Cr | ₹16,592.00 Cr | ₹51,101.00 Cr | WESTERN DEDICATED FREIGHT CORRIDOR (DFCC) |
| 6 | `N02000029` | 2024-12 | Atomic Energy | ₹49,621.00 Cr | ₹49,621.00 Cr | ₹49,621.00 Cr | KUDANKULAM NUCLEAR POWER PROJECT UNIT-5 & 6 (NPCIL) |
| 7 | `N16000518` | 2025-03 | Petroleum | ₹43,367.00 Cr | ₹43,367.00 Cr | ₹43,367.00 Cr | ETHYLENE CRACKER PROJECT AT BINA REFINERY (BPCL) |
| 8 | `N28000056` | 2025-03 | Urban Development | ₹43,095.35 Cr | ₹38,585.00 Cr | ₹43,095.35 Cr | DELHI MRTS PHASE-III (DMRC) |
| 9 | `N16000412` | 2025-03 | Petroleum | ₹38,231.00 Cr | ₹34,627.00 Cr | ₹38,231.00 Cr | CAPACITY EXPANSION OF PANIPAT REFINERY 15 TO 25 MMTPA (IOCL) |
| 10 | `N28000086` | 2025-03 | Urban Development | ₹37,276.00 Cr | ₹23,136.00 Cr | ₹37,276.00 Cr | MUMBAI METRO LINE 3 (COLABA-BANDRA-SEEPZ) (MMRCL) |
| 11 | `220100133` | 2025-03 | Railways | ₹37,012.26 Cr | ₹2,500.00 Cr | ₹37,012.26 Cr | UDHAMPUR-SRINAGAR-BARAMULLA RAIL LINK (NR) |
| 12 | `N26000101` | 2024-09 | Telecommunications | ₹34,953.45 Cr | ₹13,334.00 Cr | ₹34,953.45 Cr | NETWORK FOR SPECTRUM (DOT) |
| 13 | `N16000247` | 2025-03 | Petroleum | ₹34,012.00 Cr | ₹34,012.00 Cr | ₹34,012.00 Cr | KG-DWN-98-2 CLUSTER II DEVELOPMENT PROJECT (ONGC) |
| 14 | `N22000627` | 2025-03 | Railways | ₹33,690.00 Cr | ₹33,690.00 Cr | ₹33,690.00 Cr | MUMBAI URBAN TRANSPORT PROJECT IIIA (MRVC) |
| 15 | `N18000362` | 2025-03 | Power | ₹31,876.39 Cr | ₹31,876.39 Cr | ₹31,876.39 Cr | DIBANG MULTIPURPOSE PROJECT 2880 MW ARUNACHAL PRADESH (NHPC) |
| 16 | `N16000434` | 2025-03 | Petroleum | ₹31,580.00 Cr | ₹31,580.00 Cr | ₹31,580.00 Cr | CBR 9 MMTPA PROJECT (CPCL) |
| 17 | `N22000346` | 2024-03 | Steel | ₹31,304.00 Cr | ₹31,304.00 Cr | ₹30,357.00 Cr | EASTERN DEDICATED FREIGHT CORRIDOR PROJECT (DFCC) |
| 18 | `N16000235` | 2025-03 | Petroleum | ₹30,609.00 Cr | ₹20,928.00 Cr | ₹30,609.00 Cr | VISAKH REFINERY MODERNISATION PROJECT (HPCL) |
| 19 | `N28000134` | 2025-03 | Urban Development | ₹30,274.00 Cr | ₹30,274.00 Cr | ₹30,274.00 Cr | DELHI GHAZIABAD MEERUT RRTS CORRIDOR (NCRTC) |
| 20 | `N06000270` | 2025-03 | Coal | ₹27,213.00 Cr | ₹27,213.00 Cr | ₹27,213.00 Cr | NLC TALABIRA THERMAL POWER PROJECT PHASE-1 (NLCIL) |
| 21 | `N40000001` | 2025-03 | Coal | ₹26,684.00 Cr | ₹20,084.00 Cr | ₹26,684.00 Cr | NATIONAL INDUSTRIAL CORRIDOR PROJECT (DMIC FOR DPIIT) |
| 22 | `N28000058` | 2025-03 | Urban Development | ₹26,405.14 Cr | ₹26,405.14 Cr | ₹26,405.14 Cr | BANGALORE METRO RAIL PROJECT PHASE-2 (BMRCL) |
| 23 | `180100221` | 2025-03 | Power | ₹26,075.54 Cr | ₹6,285.33 Cr | ₹26,075.54 Cr | SUBANSIRI LOWER H.E.P (8X250 MW) (NHPC) |
| 24 | `N28000135` | 2025-03 | Urban Development | ₹24,948.65 Cr | ₹24,948.65 Cr | ₹24,948.65 Cr | DELHI METRO PHASE IV THREE PRIORITY CORRIDORS (DMRC) |
| 25 | `N18000405` | 2025-03 | Power | ₹24,819.00 Cr | ₹24,819.00 Cr | ₹24,819.00 Cr | TRANSMISSION SYSTEM FOR REZ IN KHAVDA (PGCIL) |
| 26 | `N22000406` | 2025-03 | Railways | ₹24,659.00 Cr | ₹16,216.00 Cr | ₹24,659.00 Cr | RISHIKESH - KARNAPRAYAG NEW LINE (RVNL) |
| 27 | `N26000117` | 2025-03 | Telecommunications | ₹24,544.55 Cr | ₹24,556.35 Cr | ₹24,544.55 Cr | 4G SATURATION PROJECT IN UNCOVERED VILLAGES (BSNL) |
| 28 | `N12000086` | 2024-03 | Steel | ₹23,191.55 Cr | ₹23,191.55 Cr | ₹23,840.00 Cr | NMDC INTEGRATED STEEL PLANT (NISP NAGARNAR) |
| 29 | `N02000027` | 2024-12 | Atomic Energy | ₹22,924.00 Cr | ₹12,320.00 Cr | ₹22,924.00 Cr | RAJASTHAN ATOMIC POWER PROJECT UNIT-7 & 8 (NPCIL) |
| 30 | `N02000010` | 2024-12 | Atomic Energy | ₹22,517.00 Cr | ₹11,459.00 Cr | ₹22,517.00 Cr | KAKRAPAR ATOMIC POWER PROJECT UNIT-3 & 4 (NPCIL) |
| 31 | `N06000152` | 2025-03 | Coal | ₹21,780.94 Cr | ₹17,237.00 Cr | ₹21,780.94 Cr | NEYVELI UTTAR PRADESH POWER PROJECT (NUPPL GHATAMPUR) |
| 32 | `180100242` | 2025-03 | Power | ₹21,312.11 Cr | ₹8,692.97 Cr | ₹21,312.11 Cr | BARH STPP (3X660 MW) STAGE-I (NTPC) |
| 33 | `N16000379` | 2025-03 | Petroleum | ₹18,968.00 Cr | ₹12,366.00 Cr | ₹18,968.00 Cr | NUMALIGARH REFINERY EXPANSION 6 MMTPA (NRL) |
| 34 | `N16000409` | 2025-03 | Petroleum | ₹18,936.00 Cr | ₹18,936.00 Cr | ₹18,936.00 Cr | PETROCHEMICAL & LUBE INTEGRATION AT GUJARAT REFINERY (IOCL) |
| 35 | `N18000382` | 2025-03 | Power | ₹17,195.31 Cr | ₹17,195.31 Cr | ₹17,195.31 Cr | SINGRAULI SUPER THERMAL POWER PROJECT STAGE-III (NTPC) |
| 36 | `N18000275` | 2025-03 | Power | ₹17,112.00 Cr | ₹17,112.00 Cr | ₹17,112.00 Cr | PATRATU STPP-I (3X800 MW) (NTPC/PVUNL) |
| 37 | `N16000525` | 2025-03 | Petroleum | ₹16,654.00 Cr | ₹16,654.00 Cr | ₹16,654.00 Cr | CITY GAS DISTRIBUTION PROJECTS AT LAKHIMPUR/SITAPUR (BPCL) |
| 38 | `N18000177` | 2025-03 | Power | ₹16,242.90 Cr | ₹16,242.90 Cr | ₹16,242.90 Cr | NORTH KARANPURA STPP (3X660 MW) (NTPC) |
| 39 | `N18000381` | 2025-03 | Power | ₹15,530.00 Cr | ₹15,530.00 Cr | ₹15,530.00 Cr | LARA SUPER THERMAL POWER PROJECT STAGE-II (NTPC) |
| 40 | `N16000386` | 2025-03 | Petroleum | ₹14,810.00 Cr | ₹14,810.00 Cr | ₹14,810.00 Cr | BARAUNI REFINERY CAPACITY EXPANSION 6.0 TO 9.0 MMTPA (IOCL) |
| 41 | `N28000151` | 2025-03 | Urban Development | ₹14,788.10 Cr | ₹14,788.10 Cr | ₹14,788.10 Cr | BANGALORE METRO RAIL PROJECT PHASE-2A & 2B (BMRCL) |
| 42 | `N28000084` | 2024-12 | Urban Development | ₹14,600.00 Cr | ₹14,600.00 Cr | ₹14,600.00 Cr | CHENNAI METRO RAIL LTD PHASE 1 & EXTENSIONS (CMRL) |
| 43 | `N28000148` | 2025-03 | Urban Development | ₹13,925.50 Cr | ₹13,365.77 Cr | ₹13,925.50 Cr | PATNA METRO RAIL PROJECT CORRIDOR 1 & 2 (PMRCL) |
| 44 | `N16000396` | 2025-03 | Petroleum | ₹13,805.00 Cr | ₹13,805.00 Cr | ₹13,805.00 Cr | PARA XYLENE (PX) & PTA COMPLEX AT PARADIP (IOCL) |
| 45 | `N28000121` | 2025-03 | Urban Development | ₹13,656.22 Cr | ₹11,420.00 Cr | ₹13,656.22 Cr | PUNE METRO RAIL PROJECT PHASE 1 (MAHA-METRO) |
| 46 | `N18000272` | 2025-03 | Power | ₹13,276.16 Cr | ₹11,089.42 Cr | ₹13,276.16 Cr | KHURJA SUPER THERMAL POWER PROJECT 2X660 MW (THDCIL) |
| 47 | `N18000194` | 2025-03 | Power | ₹12,999.36 Cr | ₹10,439.09 Cr | ₹12,999.36 Cr | BUXAR THERMAL POWER PLANT 1320 MW (SJVN) |
| 48 | `N28000122` | 2025-03 | Urban Development | ₹12,924.55 Cr | ₹10,773.00 Cr | ₹12,924.55 Cr | AHMEDABAD METRO RAIL PROJECT PHASE 1 (GMRC) |
| 49 | `180100210` | 2025-03 | Power | ₹12,899.00 Cr | ₹3,919.59 Cr | ₹12,899.00 Cr | PARBATI HEP STAGE-II (4X200 MW) (NHPC) |
| 50 | `N18000172` | 2025-03 | Power | ₹12,727.76 Cr | ₹8,112.12 Cr | ₹12,727.76 Cr | PAKAL DUL HYDRO ELECTRIC PROJECT 1000 MW (CVPPL) |

---

## 3. Identity Audit

### 3.1 Uniqueness & Zero Synthetic Artifacts
- **Synthetic $PRJ\_*$ Entities in Active Portfolio**: Exactly **0** (verified across all 2,319 projects).
- **Duplicate Project IDs**: Exactly **0** (`portfolio.active_projects_df["project_id"].is_unique == True`).
- **Identifier Schema**: 100% of retained entities conform strictly to authentic MoSPI schema:
  - 8–9 digit numeric codes (`^\d{8,9}$`)
  - OCMS official codes (`^[A-Z]\d{7,8}$`)

### 3.2 Duplicate Project Names Analysis
Across the 2,319 projects, exactly 13 project name strings appear in more than one record (encompassing 40 records).

**Finding**: None of these represent duplicated extractions or macro-summary artifacts. In Indian public infrastructure, major corridor initiatives are routinely divided into distinct contractual packages under separate MoSPI monitoring codes:

1. **Chennai Port to Maduravoyal Elevated Corridor (NHAI)**:
   - `N24002108`: Pkg-I (₹1,618.96 Cr)
   - `N24002109`: Pkg-II (₹1,301.37 Cr)
   - `N24002110`: Pkg-III (₹1,207.40 Cr)
   *Three distinct civil work tenders with distinct contractual baselines.*
2. **Chandikhole–Paradip NH-53 4-to-8 Laning (NHAI)**:
   - `N24002079`: Section A (₹742.25 Cr)
   - `N24002080`: Section B (₹762.75 Cr)
3. **Rajasthan Solar Evacuation Scheme (PGCIL)**:
   - `N18000300`: Substation package (₹1,184.88 Cr)
   - `N18000303`: Line package 1 (₹353.85 Cr)
   - `N18000304`: Line package 2 (₹1,340.81 Cr)
   - `N18000305`: Transformer bay package (₹713.82 Cr)
   - `N18000306`: Associated bays (₹1,562.00 Cr)
   - `N18000307`: 765kV extension (₹1,006.00 Cr)
   - `N18000331`: Multi-state feeder 1 (₹359.47 Cr)
   - `N18000332`: Multi-state feeder 2 (₹1,666.00 Cr)

**Conclusion**: These packages are distinct capital assets tracked independently by MoSPI. Merging them would destroy contract-level monitoring integrity. **Per instructions, no automated merging was performed.**

---

## 4. Macro-Aggregate Leakage Audit

A regex scan of all 2,319 retained project names was executed against:
`FLA`, `LAS`, `TOTAL`, `SUMMARY`, `TABLE`, `STATEMENT`, `ALL INDIA`, `MULTI STATE`, `GRAND TOTAL`, `SECTOR`, `STATE`.

### 4.1 Results Summary
- Total active projects scanned: **2,319**
- Name matches identified: **77**
- **Class A (Genuine Project with incidental string match)**: **77 (100%)**
- **Class B (Suspicious requiring investigation)**: **0 (0%)**
- **Class C (Confirmed macro-summary table artifact)**: **0 (0%)**

### 4.2 Representative Class A Audited Records

| Project ID | Project Name | Baseline Cost ($C_{base}$) | Source PDF | Page | Keyword Reason | Verification Evidence |
| :--- | :--- | :-: | :--- | :-: | :-: | :--- |
| `N24001779` | `DWARKA EXPRESSWAY... (NEAR DWARKA SECTOR 21)` | ₹3,030.73 Cr | FRMarch2025.pdf | 82 | `SECTOR` | Matches residential Sector 21 in Dwarka, Delhi. |
| `N24001781` | `8L OF DWARKA EXPRESSWAY PKG-II (DWARKA SECTOR 21...)` | ₹2,160.00 Cr | FRMarch2025.pdf | 82 | `SECTOR` | Package II of Dwarka expressway. |
| `N24002047` | `6L HIGHWAY FROM JAITPUR TO JN WITH SECTOR 62/65...` | ₹2,346.00 Cr | QPISR_3rd_QTR_2024-25.pdf | 126 | `SECTOR` | Faridabad city sector road intersection. |
| `N24001962` | `CONSTRUCTION OF MIHONA BYPASS... (TOTAL LENGTH 20.60 KM)` | ₹179.19 Cr | FRMarch2025.pdf | 133 | `TOTAL` | Highway engineering specification of road stretch length. |
| `N24001999` | `REALIGNMENT BETWEEN PANDRASS-PASHKYUN (TOTAL LENGTH 27.10 KM)` | ₹426.14 Cr | FRMarch2025.pdf | 129 | `TOTAL` | Zozila-Kargil highway engineering alignment. |
| `N24001748` | `SIX LANING OF NH19... IN THE STATE OF WEST BENGAL` | ₹2,621.32 Cr | FRMarch2025.pdf | 237 | `STATE` | Geographic description in official MoRTH project sanction. |
| `N24001772` | `4 LANE CONNECTOR FROM DME... IN THE STATE OF UTTAR PRADESH` | ₹1,147.26 Cr | FRMarch2025.pdf | 220 | `STATE` | Geographic routing qualifier in central project database. |
| `N26000114` | `CONSOLIDATION OF CDR DATA CENTERS WITH STATE OF THE ART...` | ₹461.42 Cr | FRMarch2025.pdf | 167 | `STATE` | Technology term "state of the art". |

**Audit Conclusion**: Zero macro-summary artifacts leaked into the active portfolio. All keyword matches are legitimate engineering specifications, urban sectors, or geographic qualifiers.

---

## 5. Mega-Project Validation ($C_{base} \ge \text{₹25,000 Cr}$)

Every active project exceeding ₹25,000 Cr baseline cost (23 projects) was audited against official MoSPI documentation:

1. **Mumbai–Ahmedabad High Speed Rail (`N22000463`) — ₹1,08,000.00 Cr**:
   Sanctioned 508 km bullet train corridor executed by NHSRCL. Joint venture of Govt of India and Govt of Japan (JICA loan). 100% genuine sovereign capital project.
2. **Rajasthan Refinery Project (`N16000513`) — ₹72,937.00 Cr**:
   9 MMTPA refinery and petrochemical complex at Pachpadra, Barmer, executed by HPCL Rajasthan Refinery Ltd (HPCL-Govt of Rajasthan JV). Revised from ₹43,129 Cr to ₹72,937 Cr. Authentic.
3. **Kudankulam Nuclear Power Project Units 3 & 4 (`N02000028`) — ₹68,893.00 Cr**:
   2 × 1000 MW VVER nuclear reactors executed by NPCIL in Tamil Nadu with Russian cooperation. Revised baseline ₹68,893 Cr. Authentic.
4. **Polavaram Irrigation Project (`N30000002`) — ₹55,548.87 Cr**:
   National irrigation multipurpose project on Godavari River, Andhra Pradesh, administered by Polavaram Project Authority (PPA). Revised investment clearance ₹55,548.87 Cr. Authentic.
5. **Western Dedicated Freight Corridor (`N22000464`) — ₹51,101.00 Cr**:
   1,504 km electrified double-track freight railway from Dadri (UP) to JNPT (Navi Mumbai) executed by DFCCIL. Authentic.
6. **Kudankulam Units 5 & 6 (`N02000029`) — ₹49,621.00 Cr**:
   Third pair of 1000 MW units at Kudankulam. Sanctioned at ₹49,621 Cr. Authentic.
7. **Bina Refinery Ethylene Cracker (`N16000518`) — ₹43,367.00 Cr**:
   Mega petrochemical expansion project by Bharat Petroleum Corporation Ltd (BPCL). Authentic.
8. **Delhi Metro MRTS Phase-III (`N28000056`) — ₹43,095.35 Cr**:
   160 km network expansion (Pink and Magenta lines) executed by DMRC. Authentic.
9. **Panipat Refinery Expansion 15 to 25 MMTPA (`N16000412`) — ₹38,231.00 Cr**:
   Refinery expansion and polypropylene unit by Indian Oil Corporation Ltd (IOCL). Authentic.
10. **Mumbai Metro Line 3 (`N28000086`) — ₹37,276.00 Cr**:
    33.5 km underground Colaba–Bandra–SEEPZ metro corridor executed by MMRCL. Authentic.
11. **Udhampur–Srinagar–Baramulla Rail Link (`220100133`) — ₹37,012.26 Cr**:
    272 km strategic Himalayan railway line connecting Kashmir Valley, including Chenab Bridge. Approved at ₹2,500 Cr, revised over 20 years to ₹37,012.26 Cr. Authentic.

**Conclusion**: Retaining projects strictly based on official identity semantics allows these legitimate mega-investments to remain visible while completely excluding synthetic macro summaries.

---

## 6. Risk-Tier Distribution Audit

### 6.1 Current Active Portfolio (2024–2025)
Evaluated with frozen production LightGBM model and isotonic calibrator:

| Operational Risk Tier | Threshold Range | Project Count | % Share | Mean Probability | Median Probability |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **NORMAL** | $P < 0.40$ | 302 | 13.02% | 0.2966 | 0.2783 |
| **WATCH** | $0.40 \le P < 0.45$ | 435 | 18.76% | 0.4120 | 0.4005 |
| **REVIEW** | $0.45 \le P < 0.50$ | 175 | 7.55% | 0.4889 | 0.4914 |
| **ESCALATE** | $P \ge 0.50$ | 1,407 | 60.67% | 0.6041 | 0.5658 |
| **Total Active** | — | **2,319** | **100.00%** | **0.5193** | **0.5658** |

### 6.2 Comparison with Out-of-Fold (OOF) Historical Backtest Folds

| Evaluation Epoch | Time Range | Sample Size | Observed Event Rate (Target) | Mean Model Prob | Median Model Prob | % NORMAL | % WATCH | % REVIEW | % ESCALATE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Fold 1** | 2020-01 to 2020-12 | 25,264 obs | 21.5% | 0.2086 | 0.2308 | 90.1% | 1.7% | 0.2% | **8.0%** |
| **Fold 2** | 2022-01 to 2022-12 | 20,624 obs | 43.3% | 0.3256 | 0.2783 | 64.9% | 9.3% | 2.2% | **23.6%** |
| **Fold 3** | 2023-07 to 2024-03 | 10,626 obs | 52.2% | 0.4926 | 0.5195 | 23.9% | 17.4% | 7.2% | **51.5%** |
| **Overall OOF** | 2020 to 2024 | 56,514 obs | 35.2% | 0.3047 | 0.2690 | 68.5% | 7.4% | 2.3% | **21.9%** |
| **Active Portfolio** | **2024 to 2025** | **2,319 projects** | — | **0.5193** | **0.5658** | **13.0%** | **18.8%** | **7.5%** | **60.7%** |

---

## 7. Root-Cause Analysis: Why is ESCALATE ~60.7%?

The elevated ESCALATE rate (60.7%) is **not an implementation defect or calibration error**. It is the natural consequence of four measured structural realities:

### 7.1 Reason A: Survival Bias of Distressed Infrastructure Projects
In central sector monitoring, projects that proceed smoothly and finish on time exit the active monitoring list upon commissioning. Conversely, projects plagued by land acquisition hurdles, forest clearances, contractual litigation, and cost overruns remain trapped in the monitoring portfolio year after year.

Empirical verification by project age (`project_age_months`):
- **Young Projects ($< 1$ year old)**: Only **4.7%** ESCALATE (Mean prob 0.3140).
- **Maturing Projects ($1–3$ years old)**: **43.2%** ESCALATE (Mean prob 0.4893).
- **Stalled Projects ($3–5$ years old)**: **90.7%** ESCALATE (Mean prob 0.6128).
- **Legacy Projects ($> 5$ years old)**: **89.3%** ESCALATE (Mean prob 0.5830).

Over 46% of the active portfolio (1,066 projects) has been under active execution for more than 3 years. These projects are mathematically and physically distressed.

### 7.2 Reason B: Macroeconomic Deterioration Trend
The ground-truth event rate (12-month composite deterioration) in the national dataset experienced secular growth over the backtest folds:
- Fold 1 (2020): **21.5%** actual event rate $\rightarrow$ 8.0% ESCALATE
- Fold 2 (2022): **43.3%** actual event rate $\rightarrow$ 23.6% ESCALATE
- Fold 3 (2023–2024): **52.2%** actual event rate $\rightarrow$ 51.5% ESCALATE

The 60.7% active portfolio ESCALATE share is the continuation of this empirical trajectory into 2024–2025.

### 7.3 Reason C: Severe Objective Milestone Drift
Direct examination of active project kinematic telemetry reveals acute physical delays:
- **40.0%** of all active projects currently report positive schedule deviation ($S_{dev} > 0$).
- **31.1%** of all active projects report **delays exceeding 12 months** ($S_{dev} \ge 12$).
- Average schedule deviation across all 2,319 projects is **+14.9 months**.
- **47.7%** of active projects report **stalled or negative monthly expenditure progress** ($V_{fin, 1m} \le 0\%/\text{mo}$).

Because the LightGBM model places high importance on stalled financial velocity, persistent deceleration ($A_{fin}$), and schedule drift ($S_{dev}$), it accurately assigns high risk to these distressed assets.

### 7.4 Reason D: Stale Early-2024 Tail
Projects whose latest observation dates to early 2024 (e.g. 2024-02 to 2024-06) stopped reporting specifically because of project distress or contractual disputes:
- Tail cohort (`2024-01` to `2024-06`): **74.1%** ESCALATE rate.
- Live current cohort (`2025-03`): **56.8%** ESCALATE rate (Mean prob 0.5029).

---

## 8. Active Window Sensitivity Analysis

To evaluate whether the active monitoring window should eventually be tightened, we evaluated the sanitized portfolio across three temporal thresholds:

| Window Definition | Temporal Cutoff | Active Projects | Baseline Exposure ($C_{base}$) | Risk-Weighted Exposure | Mean Calibrated Probability | % ESCALATE | % REVIEW | % WATCH | % NORMAL |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Current Standard** | $\ge \text{2024-01}$ | **2,319** | **₹38.24 Lakh Cr** | **₹19.13 Lakh Cr** | **0.5193** | **60.7%** | **7.5%** | **18.8%** | **13.0%** |
| **9-Month Recency** | $\ge \text{2024-07}$ | **1,958** | **₹35.10 Lakh Cr** | **₹17.38 Lakh Cr** | **0.5071** | **58.0%** | **7.8%** | **19.9%** | **14.3%** |
| **Current Year Live** | $\ge \text{2025-01}$ | **1,773** | **₹31.51 Lakh Cr** | **₹15.65 Lakh Cr** | **0.5029** | **56.8%** | **7.7%** | **20.1%** | **15.4%** |

### Key Takeaways:
1. **Capital Scale Stability**: Total baseline exposure remains between ₹31.5L Cr and ₹38.2L Cr across all three definitions, closely matching MoSPI's officially reported capital portfolio.
2. **Prevalence Stability**: The ESCALATE rate remains stable between 56.8% and 60.7%, proving that high risk is a fundamental property of the ongoing project portfolio rather than a window artifact.
3. **Current Standard Retained**: We maintain `latest_observation >= 2024-01` as instructed. This provides oversight coverage for projects undergoing multi-month reporting reconciliation while maintaining strict separation from the historical archive.

---

## 9. API Regression & System Integrity

All API endpoints were regression-tested:

1. `GET /api/dashboard/summary`:
   - Returns sanitized active portfolio metadata: `active_project_count: 2319`, `active_baseline_exposure: 3824415.25`, `risk_weighted_exposure: 1913079.66`.
   - Exposes operational tier counts: `watch_count: 435`, `review_count: 175`, `escalate_count: 1407`, `normal_count: 302`.
   - Strictly conforms to RFC 8259 JSON (zero `NaN` or `Infinity` tokens).
2. `GET /api/dashboard/interventions`:
   - Returns active genuine projects prioritized strictly by `risk_weighted_exposure`.
   - Excludes 100% of `PRJ_*` synthetic tokens and macro summaries.
   - Includes state, sector, and reporting month metadata.
3. `GET /api/projects`:
   - Returns only genuine infrastructure projects with valid official MoSPI identifiers.

---

## 10. Final Governance Recommendation

1. **Portfolio Layer Is Sound and Governance-Safe**: The sanitization layer successfully isolates genuine infrastructure assets, eliminates macro-aggregate corruption, and preserves authentic sovereign mega-projects.
2. **Keep Operational Thresholds Frozen**: The validated thresholds (WATCH $\ge 0.40$, REVIEW $\ge 0.45$, ESCALATE $\ge 0.50$) are calibrated against empirical deterioration risk. Do not artificially raise thresholds to suppress the ESCALATE count.
3. **Institutional Messaging**: In governance presentations, clarify that the ~60.7% ESCALATE rate reflects the structural accumulation of delayed legacy projects in central monitoring, which SANKET's trajectory engine accurately flags for prioritized oversight.
