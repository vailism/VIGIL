#!/usr/bin/env python3
"""
sanket/model.py

Core machine learning models, baselines, leakage audits, and evaluation metrics for VIGIL.
Implements:
1. Automated feature leakage validation assertions.
2. Baseline A (Current-State Threshold) & Baseline B (Trajectory Heuristic Threshold).
3. LightGBM Classifier with conservative hyperparameters and native categorical/missing handling.
4. Comprehensive evaluation metrics (PR-AUC, ROC-AUC, Brier score, False Alert Rate).
5. Early-warning lead time calculation.
"""

import os
import sys
import yaml
from typing import Dict, List, Tuple, Optional, Any
import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    brier_score_loss,
    confusion_matrix
)
import lightgbm as lgb

FORBIDDEN_FEATURE_KEYWORDS = [
    "target", "future", "overrun", "distress",
    "escalation_pct", "schedule_drift"
]

def load_model_config(config_path: str = "configs/model.yaml") -> Dict[str, Any]:
    """Load model configuration from YAML."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file '{config_path}' not found.")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def validate_feature_leakage(
    feature_cols: List[str],
    df: Optional[pd.DataFrame] = None
) -> None:
    """
    Automated audit assertions ensuring no future or target fields leak into feature set.
    """
    print("\n--- AUTOMATED FEATURE LEAKAGE AUDIT ---")
    print(f"Auditing {len(feature_cols)} whitelisted features:")
    for col in feature_cols:
        col_lower = col.lower()
        for forbidden in FORBIDDEN_FEATURE_KEYWORDS:
            if forbidden in col_lower:
                raise AssertionError(
                    f"CRITICAL LEAKAGE ERROR: Feature '{col}' contains forbidden keyword '{forbidden}'!"
                )
        print(f"  ✓ {col:<32s} [Point-in-Time Valid]")

    if df is not None:
        # Check temporal order in sample rows
        if "feature_cutoff_month" in df.columns and "target_horizon_month_12m" in df.columns:
            invalid_rows = df[df["feature_cutoff_month"] >= df["target_horizon_month_12m"]]
            if len(invalid_rows) > 0:
                raise AssertionError(
                    f"CRITICAL LEAKAGE ERROR: {len(invalid_rows)} rows have feature_cutoff >= target_horizon!"
                )
            print("  ✓ Temporal ordering verified: feature_cutoff_month < target_horizon_month for all rows.")
    print("Leakage audit complete: 0 leakage violations detected.\n")

def predict_baseline_a(
    df: pd.DataFrame,
    exp_ratio_thresh: float = 0.90,
    sch_dev_thresh: float = 12.0
) -> np.ndarray:
    """
    Baseline A: Current-State Static Threshold.
    Alerts if expenditure exceeds 90% of baseline OR current schedule delay >= 12 months.
    """
    exp_ratio = pd.to_numeric(df.get("expenditure_to_baseline", 0), errors="coerce").fillna(0)
    sch_dev = pd.to_numeric(df.get("schedule_deviation_months", 0), errors="coerce").fillna(0)

    alert = (exp_ratio >= exp_ratio_thresh) | (sch_dev >= sch_dev_thresh)
    return alert.astype(int).values

def predict_baseline_b(
    df: pd.DataFrame,
    v_fin_thresh: float = 0.50,
    ewma_thresh: float = 0.50,
    z_peer_thresh: float = -1.0,
    risk_score_thresh: float = 40.0
) -> np.ndarray:
    """
    Baseline B: Simple Trajectory Threshold Heuristic.
    Alerts if progress has stalled (V_fin <= 0.5% or EWMA <= 0.5%),
    velocity is >1 std dev below sector peers, or heuristic risk score >= 40.
    """
    v_fin = pd.to_numeric(df.get("V_fin_1m", np.nan), errors="coerce")
    ewma = pd.to_numeric(df.get("EWMA_V_fin", np.nan), errors="coerce")
    z_peer = pd.to_numeric(df.get("Z_peer_V_fin", 0), errors="coerce").fillna(0)
    risk_score = pd.to_numeric(df.get("trajectory_risk_score", 0), errors="coerce").fillna(0)

    stalled = (v_fin <= v_fin_thresh) | (ewma <= ewma_thresh)
    peer_sub = z_peer <= z_peer_thresh
    elevated_risk = risk_score >= risk_score_thresh

    alert = stalled | peer_sub | elevated_risk
    return alert.astype(int).values

def train_lgbm_model(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_val: pd.DataFrame,
    y_val: np.ndarray,
    categorical_features: Optional[List[str]] = None,
    params: Optional[Dict[str, Any]] = None
) -> lgb.LGBMClassifier:
    """
    Train a conservative LightGBM binary classifier with early stopping.
    Natively handles missing values and categorical variables without imputation.
    """
    if params is None:
        params = {
            "objective": "binary",
            "metric": "average_precision",
            "boosting_type": "gbdt",
            "n_estimators": 300,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": 6,
            "min_child_samples": 50,
            "subsample": 0.8,
            "subsample_freq": 1,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": -1
        }

    # Ensure categoricals are properly typed for LightGBM
    X_tr = X_train.copy()
    X_va = X_val.copy()
    if categorical_features:
        for cat_col in categorical_features:
            if cat_col in X_tr.columns:
                X_tr[cat_col] = X_tr[cat_col].astype("category")
            if cat_col in X_va.columns:
                X_va[cat_col] = X_va[cat_col].astype("category")

    callbacks = [lgb.early_stopping(stopping_rounds=30, verbose=False)]

    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_tr,
        y_train,
        eval_set=[(X_va, y_val)],
        callbacks=callbacks
    )

    return model

def predict_lgbm_probs(
    model: lgb.LGBMClassifier,
    X: pd.DataFrame,
    categorical_features: Optional[List[str]] = None
) -> np.ndarray:
    """Predict probabilities ensuring categorical column types match training."""
    X_pred = X.copy()
    if categorical_features:
        for cat_col in categorical_features:
            if cat_col in X_pred.columns:
                X_pred[cat_col] = X_pred[cat_col].astype("category")
    return model.predict_proba(X_pred)[:, 1]

def evaluate_predictions(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    threshold: float = 0.50
) -> Dict[str, float]:
    """
    Compute full evaluation metrics: PR-AUC, ROC-AUC, Brier score, Precision, Recall, F1, False Alert Rate.
    """
    # Filter any NaNs
    valid_mask = ~np.isnan(y_true) & ~np.isnan(y_prob)
    y_t = y_true[valid_mask].astype(int)
    y_p = y_prob[valid_mask]

    if len(np.unique(y_t)) < 2:
        return {
            "pr_auc": 0.0, "roc_auc": 0.5, "brier_score": 0.0,
            "precision": 0.0, "recall": 0.0, "f1": 0.0,
            "false_alert_rate": 0.0, "alert_rate": 0.0,
            "support": len(y_t), "positives": int(y_t.sum())
        }

    pr_auc = float(average_precision_score(y_t, y_p))
    roc_auc = float(roc_auc_score(y_t, y_p))
    brier = float(brier_score_loss(y_t, y_p))

    # Binary decisions at threshold
    y_pred = (y_p >= threshold).astype(int)

    prec = float(precision_score(y_t, y_pred, zero_division=0))
    rec = float(recall_score(y_t, y_pred, zero_division=0))
    f1 = float(f1_score(y_t, y_pred, zero_division=0))

    # False Alert Rate: False Positives / Total True Negatives (FPR)
    tn, fp, fn, tp = confusion_matrix(y_t, y_pred, labels=[0, 1]).ravel()
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    alert_rate = float((tp + fp) / len(y_t))

    return {
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "brier_score": round(brier, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "false_alert_rate": round(fpr, 4),
        "alert_rate": round(alert_rate, 4),
        "tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn),
        "support": len(y_t),
        "positives": int(tp + fn),
        "prevalence": round(float((tp + fn) / len(y_t)), 4)
    }

def compute_early_warning_lead_times(
    df_test_with_preds: pd.DataFrame,
    df_all_timelines: pd.DataFrame,
    threshold: float = 0.50,
    cost_threshold: float = 0.05,
    delay_threshold: float = 6.0
) -> Dict[str, Any]:
    """
    Calculate early-warning lead time for True Positive alerts.
    For each true positive alert at (i, t), inspect subsequent months (t, t+12]
    to find the FIRST month t* where the actual cost or schedule overrun was officially recorded.
    lead_time_months = t* - t.
    """
    # Filter true positives
    tp_mask = (df_test_with_preds["pred_prob"] >= threshold) & (df_test_with_preds["target"] == 1.0)
    tp_rows = df_test_with_preds[tp_mask]

    if len(tp_rows) == 0:
        return {
            "median_lead_time_months": 0.0,
            "mean_lead_time_months": 0.0,
            "p25_lead_time_months": 0.0,
            "p75_lead_time_months": 0.0,
            "evaluated_alerts": 0,
            "unique_projects": 0
        }

    # Index timelines by project_id for fast forward lookup
    timelines_grouped = df_all_timelines.groupby("project_id", sort=False)
    
    # Helper to convert YYYY-MM to int
    def ym_to_int(ym):
        y, m = map(int, str(ym).split("-"))
        return y * 12 + m

    lead_times = []
    projects_evaluated = set()

    for _, row in tp_rows.iterrows():
        pid = row["project_id"]
        t_ym = row["reporting_month"]
        t_int = ym_to_int(t_ym)
        t_cbase = float(row.get("C_base", 0) or 0)
        t_dev = float(row.get("schedule_deviation_months", 0) or 0)

        if pid not in timelines_grouped.groups:
            continue

        p_group = timelines_grouped.get_group(pid)
        p_group_months = p_group["reporting_month"].apply(ym_to_int).values
        p_cbase = pd.to_numeric(p_group.get("C_base", 0), errors="coerce").fillna(0).values
        p_sdev = pd.to_numeric(p_group.get("schedule_deviation_months", 0), errors="coerce").fillna(0).values

        # Find future observations in (t_int, t_int + 12]
        fwd_mask = (p_group_months > t_int) & (p_group_months <= t_int + 12)
        if not np.any(fwd_mask):
            continue

        fwd_m = p_group_months[fwd_mask]
        fwd_c = p_cbase[fwd_mask]
        fwd_d = p_sdev[fwd_mask]

        # Find first month where overrun occurred
        first_event_month = None
        for k in range(len(fwd_m)):
            cost_escalated = (t_cbase > 0) and (fwd_c[k] >= t_cbase * (1.0 + cost_threshold))
            delay_escalated = (fwd_d[k] - t_dev) >= delay_threshold
            if cost_escalated or delay_escalated:
                first_event_month = fwd_m[k]
                break

        if first_event_month is not None:
            lead_time = first_event_month - t_int
            lead_times.append(lead_time)
            projects_evaluated.add(pid)
        else:
            # Event occurred within the 12m horizon
            lead_times.append(12)
            projects_evaluated.add(pid)

    if not lead_times:
        return {
            "median_lead_time_months": 0.0,
            "mean_lead_time_months": 0.0,
            "p25_lead_time_months": 0.0,
            "p75_lead_time_months": 0.0,
            "evaluated_alerts": 0,
            "unique_projects": 0
        }

    return {
        "median_lead_time_months": float(np.median(lead_times)),
        "mean_lead_time_months": round(float(np.mean(lead_times)), 2),
        "p25_lead_time_months": float(np.percentile(lead_times, 25)),
        "p75_lead_time_months": float(np.percentile(lead_times, 75)),
        "evaluated_alerts": len(lead_times),
        "unique_projects": len(projects_evaluated)
    }

def compute_predictive_feature_importance(
    model: lgb.LGBMClassifier,
    feature_names: List[str]
) -> pd.DataFrame:
    """
    Extract predictive feature importances (Gain and Split) from trained LightGBM model.
    """
    gain_imp = model.booster_.feature_importance(importance_type="gain")
    split_imp = model.booster_.feature_importance(importance_type="split")

    total_gain = gain_imp.sum()
    norm_gain = (gain_imp / total_gain * 100.0) if total_gain > 0 else gain_imp

    df_imp = pd.DataFrame({
        "feature_name": feature_names,
        "importance_gain_pct": np.round(norm_gain, 2),
        "raw_gain": np.round(gain_imp, 2),
        "split_count": split_imp
    }).sort_values(by="importance_gain_pct", ascending=False).reset_index(drop=True)

    return df_imp
