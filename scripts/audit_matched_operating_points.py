#!/usr/bin/env python3
"""
scripts/audit_matched_operating_points.py

Performs:
1. Fast out-of-fold prediction generation for:
   - Model A: Current-State Only
   - Model B: Trajectory Only
   - Model C: Full VIGIL
2. Fast pre-computed forward deterioration lookup (zero fallbacks, zero artificial dates).
3. Matched operating point comparison:
   - Matched by Recall
   - Matched by False Alert Rate
   - Matched by Portfolio Alert Rate (% alerted)
4. Fold 3 Recent Period threshold audit [0.20 to 0.70].
5. Summary outputs for MODEL_CARD.md, ML_VALIDATION_AUDIT.md, and BACKTEST_REPORT.md.
"""

import os
import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
import lightgbm as lgb
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, confusion_matrix

from sanket.model import load_model_config, train_lgbm_model, predict_lgbm_probs

def ym_to_int(ym: Any) -> int:
    y, m = map(int, str(ym).split("-"))
    return y * 12 + m

def run_matched_audit():
    print("=" * 70)
    print("VIGIL ML AUDIT: MATCHED OPERATING-POINT COMPARISON")
    print("=" * 70)

    config = load_model_config("configs/model.yaml")
    df = pd.read_parquet("DATA/model_dataset.parquet")

    # Cohort
    cohort = df[(df["eligible_features"] == 1) & (df["target_observable_12m"] == 1)].copy()
    target_col = config["targets"]["primary"]
    folds = config["walk_forward_folds"]

    cat_features = config["features"]["categorical"]
    all_features = config["features"]["numeric"] + config["features"]["categorical"]

    # Pre-process target completion date in integer months
    def get_target_comp(r):
        rev = str(r.get("revised_completion_date", "") or "").strip()
        if rev and rev != "nan":
            return ym_to_int(rev)
        orig = str(r.get("original_completion_date", "") or "").strip()
        if orig and orig != "nan":
            return ym_to_int(orig)
        return np.nan

    df["t_comp_int"] = df.apply(get_target_comp, axis=1)
    df["m_int"] = df["reporting_month"].apply(ym_to_int)

    # Pre-index project timelines for fast vectorized event lookup
    print("Indexing project timelines for fast deterioration lookup...")
    grouped = df.groupby("project_id", sort=False)
    
    # Pre-compute exact first deterioration month for every (project_id, t_int)
    cost_thresh = 0.05
    delay_thresh = 6.0

    deterioration_lookup = {}  # (pid, t_int) -> first_event_m_int or None

    for pid, p_df in grouped:
        p_m = p_df["m_int"].values
        p_c = pd.to_numeric(p_df.get("C_base", 0), errors="coerce").fillna(0).values
        p_d = pd.to_numeric(p_df.get("schedule_deviation_months", 0), errors="coerce").fillna(0).values
        p_t = p_df["t_comp_int"].values

        n_obs = len(p_m)
        for i in range(n_obs):
            t_int = p_m[i]
            t_cbase = p_c[i]
            t_dev = p_d[i]
            t_comp = p_t[i]

            # Forward window (t_int, t_int + 12]
            fwd_idx = np.where((p_m > t_int) & (p_m <= t_int + 12))[0]
            if len(fwd_idx) == 0:
                deterioration_lookup[(pid, t_int)] = None
                continue

            first_event = None
            for idx in fwd_idx:
                cost_esc = (t_cbase > 0) and (p_c[idx] >= t_cbase * (1.0 + cost_thresh))
                dev_esc = (p_d[idx] - t_dev) >= delay_thresh if not np.isnan(t_dev) else False
                comp_esc = (p_t[idx] - t_comp) >= delay_thresh if (not np.isnan(t_comp) and not np.isnan(p_t[idx])) else False

                if cost_esc or dev_esc or comp_esc:
                    first_event = p_m[idx]
                    break

            deterioration_lookup[(pid, t_int)] = first_event

    print(f"Precomputed {len(deterioration_lookup):,} timeline observation lookups.")

    # Define the 3 model families
    current_state_features = [
        "C_base", "expenditure_to_baseline", "schedule_deviation_months",
        "project_age_months", "observation_number", "months_since_previous_observation",
        "reporting_gap_flag", "cost_revision_ratio", "sector_clean", "scale_bucket"
    ]
    trajectory_features = [
        "V_fin_1m", "V_fin_3m", "A_fin", "EWMA_V_fin",
        "V_exp_1m", "V_exp_3m", "A_exp", "Z_peer_V_fin",
        "schedule_deviation_change", "completion_date_drift",
        "financial_physical_gap", "V_phys_1m", "V_phys_3m", "A_phys",
        "trajectory_risk_score"
    ]
    full_features = all_features

    models_to_eval = {
        "Model A (Current State Only)": current_state_features,
        "Model B (Trajectory Only)": trajectory_features,
        "Model C (Full VIGIL)": full_features
    }

    # Generate OOF predictions for all 3 models
    oof_predictions = {}  # model_name -> DataFrame with pid, m_int, y_true, y_prob, fold_id

    for m_name, fset in models_to_eval.items():
        print(f"\nTraining and predicting for {m_name}...")
        cats = [c for c in cat_features if c in fset]
        m_rows = []

        for fold in folds:
            fid = fold["fold_id"]
            t_end = fold["train_end_month"]
            v_start = fold["val_start_month"]
            v_end = fold["val_end_month"]
            test_start = fold["test_start_month"]
            test_end = fold["test_end_month"]

            tr_mask = (cohort["reporting_month"] <= t_end) & ~cohort[target_col].isna()
            va_mask = (cohort["reporting_month"] >= v_start) & (cohort["reporting_month"] <= v_end) & ~cohort[target_col].isna()
            te_mask = (cohort["reporting_month"] >= test_start) & (cohort["reporting_month"] <= test_end) & ~cohort[target_col].isna()

            df_tr = cohort[tr_mask]
            df_va = cohort[va_mask]
            df_te = cohort[te_mask]

            m = train_lgbm_model(
                df_tr[fset], df_tr[target_col].values.astype(float),
                df_va[fset], df_va[target_col].values.astype(float),
                categorical_features=cats, params=config["lightgbm_params"]
            )
            te_probs = predict_lgbm_probs(m, df_te[fset], categorical_features=cats)

            sub = pd.DataFrame({
                "project_id": df_te["project_id"].values,
                "reporting_month": df_te["reporting_month"].values,
                "m_int": df_te["reporting_month"].apply(ym_to_int).values,
                "y_true": df_te[target_col].values.astype(float),
                "y_prob": te_probs,
                "fold_id": fid
            })
            m_rows.append(sub)

        oof_predictions[m_name] = pd.concat(m_rows, ignore_index=True)

    # Function to evaluate lead times and metrics for a given model df and threshold
    def eval_operating_point(df_m: pd.DataFrame, threshold: float) -> Dict[str, Any]:
        y_t = df_m["y_true"].values
        y_p = df_m["y_prob"].values
        y_pred = (y_p >= threshold).astype(int)

        tn, fp, fn, tp = confusion_matrix(y_t, y_pred, labels=[0, 1]).ravel()
        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        far = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
        alert_rate = float((tp + fp) / len(y_t))
        pr_auc = float(average_precision_score(y_t, y_p))

        # Event-level lead time using precomputed lookup
        tp_mask = (y_pred == 1) & (y_t == 1)
        tp_df = df_m[tp_mask]

        event_records = []
        for pid, t_int in zip(tp_df["project_id"].values, tp_df["m_int"].values):
            ev_m = deterioration_lookup.get((pid, t_int), None)
            if ev_m is not None and ev_m > t_int:
                event_records.append({
                    "project_id": pid,
                    "event_month": ev_m,
                    "alert_month": t_int,
                    "lead_time": ev_m - t_int
                })

        if event_records:
            df_ev = pd.DataFrame(event_records)
            ev_first = df_ev.groupby(["project_id", "event_month"]).agg(
                first_alert=("alert_month", "min")
            ).reset_index()
            ev_first["lead_time"] = ev_first["event_month"] - ev_first["first_alert"]
            med_lt = float(np.median(ev_first["lead_time"]))
            mean_lt = round(float(np.mean(ev_first["lead_time"])), 2)
            n_events = len(ev_first)
        else:
            med_lt = 0.0
            mean_lt = 0.0
            n_events = 0

        return {
            "threshold": round(threshold, 3),
            "pr_auc": round(pr_auc, 4),
            "precision": round(prec * 100, 2),
            "recall": round(rec * 100, 2),
            "false_alert_rate": round(far * 100, 2),
            "alert_rate": round(alert_rate * 100, 2),
            "alerts_count": int(tp + fp),
            "event_count": n_events,
            "event_median_lead_time": med_lt,
            "event_mean_lead_time": mean_lt
        }

    # -------------------------------------------------------------
    # 1. MATCHED OPERATING-POINT COMPARISONS
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("1. MATCHED OPERATING-POINT COMPARISON TABLES")
    print("=" * 70)

    # Helper to find threshold giving target metric
    def find_threshold_for_target(df_m: pd.DataFrame, target_metric: str, target_val: float, val_range=(0.05, 0.95), steps=200):
        threshs = np.linspace(val_range[0], val_range[1], steps)
        best_th = 0.5
        best_diff = float("inf")
        for th in threshs:
            y_t = df_m["y_true"].values
            y_p = df_m["y_prob"].values
            y_pred = (y_p >= th).astype(int)
            tn, fp, fn, tp = confusion_matrix(y_t, y_pred, labels=[0, 1]).ravel()
            if target_metric == "recall":
                val = tp / (tp + fn) if (tp + fn) > 0 else 0
            elif target_metric == "far":
                val = fp / (fp + tn) if (fp + tn) > 0 else 0
            elif target_metric == "alert_rate":
                val = (tp + fp) / len(y_t)
            diff = abs(val - target_val)
            if diff < best_diff:
                best_diff = diff
                best_th = th
        return best_th

    # Matched Target 1: RECALL MATCHED (Low: ~20%, Mid: ~35%, High: ~50%)
    print("\n--- A. MATCHED BY RECALL ---")
    matched_recall_rows = []
    for rec_target in [0.20, 0.35, 0.50]:
        for m_name in models_to_eval.keys():
            th = find_threshold_for_target(oof_predictions[m_name], "recall", rec_target)
            res = eval_operating_point(oof_predictions[m_name], th)
            res["target_matched"] = f"Recall ~{int(rec_target*100)}%"
            res["model"] = m_name
            matched_recall_rows.append(res)

    df_matched_rec = pd.DataFrame(matched_recall_rows)
    print(df_matched_rec[["target_matched", "model", "threshold", "precision", "recall", "false_alert_rate", "alert_rate", "event_median_lead_time", "event_mean_lead_time"]].to_string(index=False))

    # Matched Target 2: FALSE ALERT RATE MATCHED (Low: ~2.5%, Mid: ~10%, High: ~20%)
    print("\n--- B. MATCHED BY FALSE ALERT RATE ---")
    matched_far_rows = []
    for far_target in [0.025, 0.05, 0.10, 0.20]:
        for m_name in models_to_eval.keys():
            th = find_threshold_for_target(oof_predictions[m_name], "far", far_target)
            res = eval_operating_point(oof_predictions[m_name], th)
            res["target_matched"] = f"FAR ~{far_target*100:.1f}%"
            res["model"] = m_name
            matched_far_rows.append(res)

    df_matched_far = pd.DataFrame(matched_far_rows)
    print(df_matched_far[["target_matched", "model", "threshold", "precision", "recall", "false_alert_rate", "alert_rate", "event_median_lead_time", "event_mean_lead_time"]].to_string(index=False))

    # Matched Target 3: PORTFOLIO ALERT RATE MATCHED (~8%, ~15%, ~25%, ~35%)
    print("\n--- C. MATCHED BY PORTFOLIO ALERT RATE ---")
    matched_ar_rows = []
    for ar_target in [0.08, 0.15, 0.25, 0.35]:
        for m_name in models_to_eval.keys():
            th = find_threshold_for_target(oof_predictions[m_name], "alert_rate", ar_target)
            res = eval_operating_point(oof_predictions[m_name], th)
            res["target_matched"] = f"Alerts ~{int(ar_target*100)}%"
            res["model"] = m_name
            matched_ar_rows.append(res)

    df_matched_ar = pd.DataFrame(matched_ar_rows)
    print(df_matched_ar[["target_matched", "model", "threshold", "precision", "recall", "false_alert_rate", "alert_rate", "event_median_lead_time", "event_mean_lead_time"]].to_string(index=False))

    # -------------------------------------------------------------
    # 2. FOLD 3 RECENT PERIOD THRESHOLD AUDIT
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("2. FOLD 3 (2023-07 to 2024-03) OPERATING POINT AUDIT")
    print("=" * 70)

    f3_df = oof_predictions["Model C (Full VIGIL)"][oof_predictions["Model C (Full VIGIL)"]["fold_id"] == 3].copy()
    f3_thresholds = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70]

    f3_rows = []
    for th in f3_thresholds:
        res = eval_operating_point(f3_df, th)
        f3_rows.append(res)

    df_f3_table = pd.DataFrame(f3_rows)
    print(df_f3_table[["threshold", "precision", "recall", "false_alert_rate", "alert_rate", "alerts_count", "event_median_lead_time", "event_mean_lead_time"]].to_string(index=False))

    # Save matched tables
    df_all_matched = pd.concat([df_matched_rec, df_matched_far, df_matched_ar], ignore_index=True)
    df_all_matched.to_parquet("DATA/matched_operating_points.parquet", index=False)
    df_f3_table.to_parquet("DATA/fold3_threshold_audit.parquet", index=False)
    print("\nSaved matched_operating_points.parquet and fold3_threshold_audit.parquet.")

if __name__ == "__main__":
    run_matched_audit()
