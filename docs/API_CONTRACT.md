# SANKET API Data Contract & Specification

**Service Name:** SANKET Infrastructure Governance & Early Warning API  
**Base URL:** `http://localhost:8000`  
**API Version:** `1.0.0`  
**Protocol:** HTTP/1.1 (JSON RFC 8259)  
**Frozen Methodology Compliance:** Fully verified against frozen LightGBM bundle, validated risk tiers, and zero future leakage.

---

## 1. Architectural Principles

1. **Point-in-Time Integrity:** All project evaluations reflect strictly what was known at or before observation month $t$. No future cost revisions, schedule slips, or expenditures leak into prior observations.
2. **Deterministic & Fact-Grounded:** All "WHY?" explanations are derived strictly from LightGBM native TreeSHAP feature contributions (`pred_contrib=True`) mapped to traceable numerical inputs. Zero stochastic generative LLM models are used.
3. **Validated Operational Risk Tiers:**
   - **`NORMAL`**: Calibrated risk probability $P < 0.40$
   - **`WATCH`**: $0.40 \le P < 0.45$
   - **`REVIEW`**: $0.45 \le P < 0.50$
   - **`ESCALATE`**: $P \ge 0.50$
4. **RFC 8259 JSON Compliance:** All numeric outputs sanitize `NaN`, `+Infinity`, and `-Infinity` into standard JSON `null` values.

---

## 2. API Endpoints

### 2.1 Health Check

```http
GET /health
```

#### Description
Returns system readiness, service metadata, and portfolio index status.

#### Response (200 OK)
```json
{
  "status": "healthy",
  "service": "sanket-api",
  "version": "1.0.0",
  "model_loaded": true,
  "total_projects_indexed": 115693
}
```

---

### 2.2 Portfolio Project Directory

```http
GET /api/projects
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `search` | string | Optional | `null` | Case-insensitive substring match on `project_id` or `project_name` |
| `sector` | string | Optional | `null` | Filter by sector classification (e.g. `Power`, `Railways`, `Road Transport`) |
| `risk_tier` | string | Optional | `null` | Filter by operational tier: `WATCH`, `REVIEW`, `ESCALATE`, `NORMAL` |
| `limit` | integer | Optional | `50` | Pagination page size ($1 \le \text{limit} \le 500$) |
| `offset` | integer | Optional | `0` | Pagination record offset |

#### Response (200 OK)
```json
{
  "total": 115693,
  "limit": 2,
  "offset": 0,
  "projects": [
    {
      "project_id": "180100210",
      "project_name": "PARBATI HEP (NHPC) II NHPC,Himachal Pradesh",
      "sector": "OTHER",
      "latest_observation": "2025-03",
      "latest_risk": 0.2783,
      "latest_risk_tier": "NORMAL",
      "baseline_cost": 3919.59
    },
    {
      "project_id": "020100044",
      "project_name": "PROTOTYPE FAST BREEDER REACTOR (BHAVINI, 500 MWE)",
      "sector": "Atomic Energy",
      "latest_observation": "2024-04",
      "latest_risk": 0.4005,
      "latest_risk_tier": "WATCH",
      "baseline_cost": 5677.00
    }
  ]
}
```

---

### 2.3 Single Project Detail & Point-in-Time State

```http
GET /api/projects/{project_id}
```

#### Path Parameters
- `project_id` (string, required): Unique longitudinal identifier of the infrastructure project.

#### Response (200 OK)
```json
{
  "project_id": "180100210",
  "project_name": "PARBATI HEP (NHPC) II NHPC,Himachal Pradesh Railways",
  "sector": "OTHER",
  "ministry": "NHPC",
  "state": "Himachal Pradesh",
  "approved_cost": 5366.0,
  "total_observations": 139,
  "start_month": "2013-05",
  "end_month": "2025-03",
  "latest_observation": "2025-03",
  "latest_prediction": {
    "raw_prob": 0.2312,
    "pred_prob": 0.2783,
    "risk_tier": "NORMAL",
    "alert": false
  },
  "current_trajectory_metrics": {
    "C_base": 3919.59,
    "expenditure": 11063.49,
    "financial_progress": 282.26,
    "schedule_deviation_months": null,
    "V_fin_1m": 0.0,
    "V_fin_3m": null,
    "A_fin": null,
    "EWMA_V_fin": 0.0,
    "Z_peer_V_fin": -0.12,
    "trajectory_risk_score": 25.0
  },
  "current_risk_tier": "NORMAL",
  "top_explanations": [
    {
      "feature": "C_base",
      "value": 3919.59,
      "contribution": 0.3812,
      "explanation": "Sanctioned capital baseline scale is ₹3,919.6 Cr"
    },
    {
      "feature": "sector_clean",
      "value": "OTHER",
      "contribution": 0.213,
      "explanation": "Monitored under OTHER sector oversight"
    },
    {
      "feature": "scale_bucket",
      "value": "MEGA",
      "contribution": 0.026,
      "explanation": "Project categorized in MEGA capital scale tier"
    }
  ]
}
```

#### Error Response (404 Not Found)
```json
{
  "detail": "Project 'NONEXISTENT_ID' not found."
}
```

---

### 2.4 Longitudinal Point-in-Time Historical Replay

```http
GET /api/projects/{project_id}/replay
```

#### Path Parameters
- `project_id` (string, required)

#### Description
Executes full longitudinal historical reconstruction through `get_project_replay(project_id)`. Reconstructs monthly predictions, detects actual deterioration milestones (using established high-water mark baselines), identifies first alerts, and computes early warning lead time.

#### Response (200 OK)
```json
{
  "project_id": "180100210",
  "project_name": "PARBATI HEP (NHPC) II NHPC,Himachal Pradesh Railways",
  "sector": "OTHER",
  "ministry": "NHPC",
  "state": "Himachal Pradesh",
  "approved_cost": 5366.0,
  "total_observations": 139,
  "start_month": "2013-05",
  "end_month": "2025-03",
  "timeline": [
    {
      "reporting_month": "2013-06",
      "observation_number": 2,
      "C_base": 5366.0,
      "expenditure": 3479.78,
      "financial_progress": 64.85,
      "schedule_deviation_months": null,
      "V_fin_1m": 0.46,
      "V_fin_3m": null,
      "A_fin": null,
      "EWMA_V_fin": 0.46,
      "Z_peer_V_fin": -0.2736,
      "trajectory_risk_score": 33.17,
      "raw_prob": 0.342,
      "pred_prob": 0.4005,
      "risk_tier": "WATCH",
      "alert": true,
      "top_explanations": [
        {
          "feature": "C_base",
          "value": 5366.0,
          "contribution": 0.6575,
          "explanation": "Sanctioned capital baseline scale is ₹5,366.0 Cr"
        }
      ],
      "actual_event": false,
      "lead_time_if_event": 20
    }
  ],
  "alert_points": [
    {
      "reporting_month": "2013-06",
      "observation_number": 2,
      "risk_tier": "WATCH",
      "pred_prob": 0.4005,
      "top_explanation": "Sanctioned capital baseline scale is ₹5,366.0 Cr"
    }
  ],
  "actual_deterioration_event": {
    "event_index": 21,
    "event_month": "2015-02",
    "reasons": [
      "Cost escalated +40.4% (₹5,366.0 Cr -> ₹7,531.7 Cr)"
    ],
    "prior_cbase": 5366.0,
    "new_cbase": 7531.72,
    "prior_sdev": null,
    "new_sdev": null
  },
  "all_deterioration_events": [ ... ],
  "first_alert": {
    "alert_month": "2013-06",
    "risk_tier": "WATCH",
    "pred_prob": 0.4005,
    "lead_time_months": 20,
    "top_explanation": "Sanctioned capital baseline scale is ₹5,366.0 Cr"
  },
  "lead_time": 20
}
```

---

### 2.5 Project Timeline Records

```http
GET /api/projects/{project_id}/timeline
```

#### Path Parameters
- `project_id` (string, required)

#### Description
Returns sequence of monthly point-in-time prediction records and trajectory kinematics.

#### Response (200 OK)
```json
{
  "project_id": "180100210",
  "project_name": "PARBATI HEP (NHPC) II NHPC,Himachal Pradesh Railways",
  "total_observations": 139,
  "timeline": [
    {
      "reporting_month": "2013-05",
      "observation_number": 1,
      "C_base": 5366.0,
      "expenditure": 3455.29,
      "financial_progress": 64.39,
      "schedule_deviation_months": null,
      "V_fin_1m": null,
      "V_fin_3m": null,
      "A_fin": null,
      "EWMA_V_fin": null,
      "Z_peer_V_fin": null,
      "trajectory_risk_score": null,
      "raw_prob": 0.281,
      "pred_prob": 0.3289,
      "risk_tier": "NORMAL",
      "alert": false,
      "top_explanations": [],
      "actual_event": false,
      "lead_time_if_event": null
    }
  ]
}
```

---

### 2.6 Dashboard Portfolio Governance Summary

```http
GET /api/dashboard/summary
```

#### Description
Returns national macro-level metrics, active risk tier counts, capital exposure under distress, and median warning lead time from validated historical backtests.

#### Response (200 OK)
```json
{
  "total_projects": 115693,
  "projects_currently_scored": 115693,
  "watch_count": 11574,
  "review_count": 2465,
  "escalate_count": 8008,
  "total_baseline_exposure": 12845620.45,
  "exposure_in_escalate": 3491204.12,
  "median_warning_lead_time": 3.0,
  "sector_breakdown": [
    {
      "sector": "Road Transport and Highways",
      "total_projects": 42104,
      "escalate_count": 2980,
      "review_count": 890,
      "watch_count": 4120,
      "total_exposure": 4512090.10
    },
    {
      "sector": "Railways",
      "total_projects": 31200,
      "escalate_count": 2410,
      "review_count": 780,
      "watch_count": 3400,
      "total_exposure": 3810450.60
    },
    {
      "sector": "Power",
      "total_projects": 18450,
      "escalate_count": 1240,
      "review_count": 410,
      "watch_count": 2100,
      "total_exposure": 2450120.30
    }
  ]
}
```

---

### 2.7 Transparent Intervention Prioritization Ranking

```http
GET /api/dashboard/interventions
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | integer | Optional | `20` | Maximum number of candidate projects to return ($1 \le \text{limit} \le 100$) |
| `sector` | string | Optional | `null` | Filter by sector |
| `min_risk_tier` | string | Optional | `null` | Minimum operational risk tier (e.g. `WATCH`, `REVIEW`, `ESCALATE`) |

#### Description
Ranks active projects by expected financial exposure to 12-month deterioration:
$$\text{Priority Score} = P(\text{overrun}_{12\text{m}}) \times C_{\text{base}}$$

> [!NOTE]
> **Governance Transparency Notice:**  
> This endpoint does not claim to be an automated prescriptive optimization algorithm. It is a transparent prioritization ranking designed to maximize auditing efficiency by focusing oversight resources on high-exposure, high-risk capital assets.

#### Response (200 OK)
```json
{
  "total_eligible": 115693,
  "limit": 2,
  "methodology_note": "Transparent prioritization ranking calculated as calibrated_risk_probability * baseline_cost. Not an automated causal intervention algorithm.",
  "projects": [
    {
      "project_id": "PRJ_BB0B04A558ED",
      "project_name": "FLA RAILWAYS",
      "sector": "Railways",
      "latest_observation": "2024-04",
      "latest_risk": 0.5658,
      "latest_risk_tier": "ESCALATE",
      "baseline_cost": 687288.4,
      "priority_score": 388867.79
    },
    {
      "project_id": "PRJ_7A8AEAB9026C",
      "project_name": "FLA RAILWAYS",
      "sector": "Railways",
      "latest_observation": "2024-04",
      "latest_risk": 0.5658,
      "latest_risk_tier": "ESCALATE",
      "baseline_cost": 687288.4,
      "priority_score": 388867.79
    }
  ]
}
```

---

## 3. Error Handling

All HTTP errors follow standard FastAPI JSON responses:

| HTTP Status | Error Scenario | Response Format |
| :--- | :--- | :--- |
| `400 Bad Request` | Invalid query parameter (e.g. `limit > 500`) | `{"detail": [{"loc": ["query", "limit"], "msg": "Input should be less than or equal to 500", "type": "less_than_equal"}]}` |
| `404 Not Found` | Project ID not in longitudinal dataset | `{"detail": "Project 'NONEXISTENT_ID' not found."}` |
| `500 Internal Server Error` | Unexpected backend or model loading failure | `{"detail": "Internal server error description."}` |
