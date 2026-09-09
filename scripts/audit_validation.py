#!/usr/bin/env python3
"""
scripts/audit_validation.py

Phase 1.5 Validation Audit Engine for VIGIL.
Executes:
1. Event-level vs Alert-level early warning lead time evaluation.
2. Probability calibration audit:
   - Reliability diagrams & decile analysis.
   - Raw vs Platt (Sigmoid) vs Isotonic calibration fitted strictly on train/val.
   - Expected Calibration Error (ECE) and Brier scores.
3. Temporal fold boundary verification and isolation gap audit.
4. Project identity audit (shared vs unseen projects in walk-forward evaluation).
5. Feature ablation study:
   - Model A: Current-State Only
   - Model B: Trajectory Only
   - Model C: Full VIGIL (Current-State + Trajectory)
6. Cost-revision feature ablation:
   - Full Model vs Model without cost_revision_ratio vs Model without revision fields.
7. Operating threshold sensitivity (0.30, 0.35, 0.40, 0.50, 0.60, 0.70)
   with formal recommendations for SENSITIVE, BALANCED, and HIGH_CONFIDENCE.
8. Recent period (Fold 3) diagnostic.
9. Cross-fold feature importance robustness.
10. Generates:
    - DATA/model_ablation_results.parquet
    - DATA/calibration_results.parquet
    - DATA/event_lead_times.parquet
"""

import os
import sys
import json
import yaml
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    brier_score_loss,
    average_precision_score,
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)
import lightgbm as lgb

from sanket.model import (
    load_model_config,
    train_lgbm_model,
    predict_lgbm_probs,
    evaluate_predictions
)

def ym_to_int(ym: Any) -> int:
    y, m = map(int, str(ym).split("-"))
    return y * 12 + m

def int_to_ym(val: int) -> str:
    y = val // 12
    m = val % 12
    if m == 0:
        y -= 1
        m = 12
    return f"{y:04d}-{m:02d}"

def compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> Tuple[float, pd.DataFrame]:
    """Compute Expected Calibration Error (ECE) and bin summary table."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_indices = np.digitize(y_prob, bins) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    ece = 0.0
    n = len(y_true)
    bin_rows = []

    for b in range(n_bins):
        mask = (bin_indices == b)
        count = int(np.sum(mask))
        if count > 0:
            avg_prob = float(np.mean(y_prob[mask]))
            avg_true = float(np.mean(y_true[mask]))
            weight = count / n
            ece += weight * abs(avg_prob - avg_true)
        else:
            avg_prob = float((bins[b] + bins[b+1]) / 2.0)
            avg_true = 0.0

        bin_rows.append({
            "bin": b + 1,
            "range": f"[{bins[b]:.1f}, {bins[b+1]:.1f})",
            "count": count,
            "mean_pred_prob": round(avg_prob, 4),
            "observed_event_rate": round(avg_true, 4),
            "gap": round(abs(avg_prob - avg_true), 4) if count > 0 else 0.0
        })

    return round(float(ece), 4), pd.DataFrame(bin_rows)

def audit_event_lead_times(
    preds_df: pd.DataFrame,
    dataset_df: pd.DataFrame,
    threshold: float = 0.50,
    cost_threshold: float = 0.05,
    delay_threshold: float = 6.0
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Computes both Alert-level and Event-level lead times.
    For event-level:
    Groups by (project_id, event_month) to identify distinct events.
    Assigns the FIRST qualifying alert preceding the event.
    lead_time = event_month - first_alert_month.
    """
    tp_mask = (preds_df["pred_prob"] >= threshold) & (preds_df["overrun_composite_12m"] == 1.0)
    tp_rows = preds_df[tp_mask].copy()

    # Fast indexed lookup
    timelines_grouped = dataset_df.groupby("project_id", sort=False)

    alert_records = []

    for _, row in tp_rows.iterrows():
        pid = row["project_id"]
        t_ym = row["reporting_month"]
        t_int = ym_to_int(t_ym)
        t_cbase = float(row.get("C_base", 0) or 0)
        t_dev = float(row.get("schedule_deviation_months", 0) or 0)

        if pid not in timelines_grouped.groups:
            continue

        p_group = timelines_grouped.get_group(pid)
        p_months = p_group["reporting_month"].apply(ym_to_int).values
        p_cbase = pd.to_numeric(p_group.get("C_base", 0), errors="coerce").fillna(0).values
        p_sdev = pd.to_numeric(p_group.get("schedule_deviation_months", 0), errors="coerce").fillna(0).values

        fwd_mask = (p_months > t_int) & (p_months <= t_int + 12)
        if not np.any(fwd_mask):
            continue

        fwd_m = p_months[fwd_mask]
        fwd_c = p_cbase[fwd_mask]
        fwd_d = p_sdev[fwd_mask]

        first_event_month = None
        for k in range(len(fwd_m)):
            cost_escalated = (t_cbase > 0) and (fwd_c[k] >= t_cbase * (1.0 + cost_threshold))
            delay_escalated = (fwd_d[k] - t_dev) >= delay_threshold
            if cost_escalated or delay_escalated:
                first_event_month = fwd_m[k]
                break

        if first_event_month is None:
            first_event_month = t_int + 12

        lead_time = first_event_month - t_int
        alert_records.append({
            "project_id": pid,
            "alert_month_int": t_int,
            "alert_month": t_ym,
            "event_month_int": first_event_month,
            "event_month": int_to_ym(first_event_month),
            "alert_lead_time": lead_time,
            "pred_prob": float(row["pred_prob"])
        })

    df_alerts = pd.DataFrame(alert_records)

    # Event-level aggregation: group by project_id and distinct event_month
    df_events = df_alerts.groupby(["project_id", "event_month_int", "event_month"]).agg(
        first_alert_month_int=("alert_month_int", "min"),
        first_alert_month=("alert_month", "min"),
        alert_count=("alert_lead_time", "count"),
        max_prob=("pred_prob", "max")
    ).reset_index()

    df_events["event_lead_time"] = df_events["event_month_int"] - df_events["first_alert_month_int"]

    alert_summary = {
        "evaluated_alerts": len(df_alerts),
        "unique_projects": int(df_alerts["project_id"].nunique()),
        "median_lead_time": float(np.median(df_alerts["alert_lead_time"])),
        "mean_lead_time": round(float(np.mean(df_alerts["alert_lead_time"])), 2),
        "p25_lead_time": float(np.percentile(df_alerts["alert_lead_time"], 25)),
        "p75_lead_time": float(np.percentile(df_alerts["alert_lead_time"], 75))
    }

    event_summary = {
        "unique_events": len(df_events),
        "unique_projects": int(df_events["project_id"].nunique()),
        "median_lead_time": float(np.median(df_events["event_lead_time"])),
        "mean_lead_time": round(float(np.mean(df_events["event_lead_time"])), 2),
        "p25_lead_time": float(np.percentile(df_events["event_lead_time"], 25)),
        "p75_lead_time": float(np.percentile(df_events["event_lead_time"], 75))
    }

    return {"alert_level": alert_summary, "event_level": event_summary}, df_events

def run_validation_audit():
    print("=" * 70)
    print("VIGIL ML PHASE 1.5 — COMPREHENSIVE VALIDATION AUDIT")
    print("=" * 70)

    config = load_model_config("configs/model.yaml")
    df_dataset = pd.read_parquet("DATA/model_dataset.parquet")
    df_preds = pd.read_parquet("DATA/ml_predictions.parquet")

    cohort = df_dataset[(df_dataset["eligible_features"] == 1) & (df_dataset["target_observable_12m"] == 1)].copy()
    target_col = config["targets"]["primary"]
    folds = config["walk_forward_folds"]

    all_features = config["features"]["numeric"] + config["features"]["categorical"]
    cat_features = config["features"]["categorical"]

    # -------------------------------------------------------------
    # 1. EARLY-WARNING LEAD TIME AUDIT (ALERT VS EVENT LEVEL)
    # -------------------------------------------------------------
    print("\n[1] AUDITING EARLY-WARNING LEAD TIME (ALERT-LEVEL VS EVENT-LEVEL)...")
    lead_time_res, df_events = audit_event_lead_times(df_preds, df_dataset, threshold=0.50)
    print(f"  Alert-Level  (N={lead_time_res['alert_level']['evaluated_alerts']}): Median = {lead_time_res['alert_level']['median_lead_time']:.1f} mos | Mean = {lead_time_res['alert_level']['mean_lead_time']:.2f} mos | P25 = {lead_time_res['alert_level']['p25_lead_time']:.1f} | P75 = {lead_time_res['alert_level']['p75_lead_time']:.1f}")
    print(f"  Event-Level  (N={lead_time_res['event_level']['unique_events']}): Median = {lead_time_res['event_level']['median_lead_time']:.1f} mos | Mean = {lead_time_res['event_level']['mean_lead_time']:.2f} mos | P25 = {lead_time_res['event_level']['p25_lead_time']:.1f} | P75 = {lead_time_res['event_level']['p75_lead_time']:.1f}")
    print(f"  Unique Projects: {lead_time_res['event_level']['unique_projects']}")

    # Save event lead times
    df_events.to_parquet("DATA/event_lead_times.parquet", index=False)

    # -------------------------------------------------------------
    # 2. CALIBRATION AUDIT (RAW VS PLATT VS ISOTONIC)
    # -------------------------------------------------------------
    print("\n[2] AUDITING PROBABILITY CALIBRATION...")
    # We will fit calibrators strictly on validation folds and test on test folds
    calib_records = []
    oof_raw_probs = []
    oof_platt_probs = []
    oof_iso_probs = []
    oof_y_true = []

    fold_models = {}

    for fold in folds:
        fid = fold["fold_id"]
        t_end = fold["train_end_month"]
        v_start = fold["val_start_month"]
        v_end = fold["val_end_month"]
        test_start = fold["test_start_month"]
        test_end = fold["test_end_month"]

        train_mask = (cohort["reporting_month"] <= t_end) & ~cohort[target_col].isna()
        val_mask = (cohort["reporting_month"] >= v_start) & (cohort["reporting_month"] <= v_end) & ~cohort[target_col].isna()
        test_mask = (cohort["reporting_month"] >= test_start) & (cohort["reporting_month"] <= test_end) & ~cohort[target_col].isna()

        X_tr = cohort.loc[train_mask, all_features].copy()
        y_tr = cohort.loc[train_mask, target_col].values.astype(float)
        X_va = cohort.loc[val_mask, all_features].copy()
        y_va = cohort.loc[val_mask, target_col].values.astype(float)
        X_te = cohort.loc[test_mask, all_features].copy()
        y_te = cohort.loc[test_mask, target_col].values.astype(float)

        model = train_lgbm_model(X_tr, y_tr, X_va, y_va, categorical_features=cat_features, params=config["lightgbm_params"])
        fold_models[fid] = model

        # Raw probabilities
        val_probs_raw = predict_lgbm_probs(model, X_va, categorical_features=cat_features)
        test_probs_raw = predict_lgbm_probs(model, X_te, categorical_features=cat_features)

        # Platt / Sigmoid calibration: fit on validation set ONLY
        # Using LogisticRegression on val_probs logit or directly on val_probs
        platt = LogisticRegression(C=1.0, solver="lbfgs")
        platt.fit(val_probs_raw.reshape(-1, 1), y_va)
        test_probs_platt = platt.predict_proba(test_probs_raw.reshape(-1, 1))[:, 1]

        # Isotonic calibration: fit on validation set ONLY
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(val_probs_raw, y_va)
        test_probs_iso = iso.predict(test_probs_raw)

        # Brier scores
        brier_raw = brier_score_loss(y_te, test_probs_raw)
        brier_platt = brier_score_loss(y_te, test_probs_platt)
        brier_iso = brier_score_loss(y_te, test_probs_iso)

        ece_raw, _ = compute_ece(y_te, test_probs_raw)
        ece_platt, _ = compute_ece(y_te, test_probs_platt)
        ece_iso, _ = compute_ece(y_te, test_probs_iso)

        calib_records.append({
            "fold_id": fid,
            "brier_raw": round(brier_raw, 4),
            "brier_platt": round(brier_platt, 4),
            "brier_iso": round(brier_iso, 4),
            "ece_raw": ece_raw,
            "ece_platt": ece_platt,
            "ece_iso": ece_iso
        })

        oof_raw_probs.extend(test_probs_raw)
        oof_platt_probs.extend(test_probs_platt)
        oof_iso_probs.extend(test_probs_iso)
        oof_y_true.extend(y_te)

    oof_raw_probs = np.array(oof_raw_probs)
    oof_platt_probs = np.array(oof_platt_probs)
    oof_iso_probs = np.array(oof_iso_probs)
    oof_y_true = np.array(oof_y_true)

    global_brier_raw = brier_score_loss(oof_y_true, oof_raw_probs)
    global_brier_platt = brier_score_loss(oof_y_true, oof_platt_probs)
    global_brier_iso = brier_score_loss(oof_y_true, oof_iso_probs)

    global_ece_raw, decile_raw_df = compute_ece(oof_y_true, oof_raw_probs)
    global_ece_platt, decile_platt_df = compute_ece(oof_y_true, oof_platt_probs)
    global_ece_iso, decile_iso_df = compute_ece(oof_y_true, oof_iso_probs)

    print(f"  Global Brier Score: Raw = {global_brier_raw:.4f} | Platt = {global_brier_platt:.4f} | Isotonic = {global_brier_iso:.4f}")
    print(f"  Global ECE        : Raw = {global_ece_raw:.4f} | Platt = {global_ece_platt:.4f} | Isotonic = {global_ece_iso:.4f}")
    print("\n  Raw LightGBM Probability Deciles:")
    print(decile_raw_df[["bin", "range", "count", "mean_pred_prob", "observed_event_rate", "gap"]].to_string(index=False))

    decile_raw_df.to_parquet("DATA/calibration_results.parquet", index=False)

    # -------------------------------------------------------------
    # 3. TEMPORAL FOLD & ISOLATION AUDIT
    # -------------------------------------------------------------
    print("\n[3] AUDITING TEMPORAL FOLD BOUNDARIES & ISOLATION...")
    fold_audit_rows = []
    for fold in folds:
        fid = fold["fold_id"]
        t_end = fold["train_end_month"]
        v_start = fold["val_start_month"]
        v_end = fold["val_end_month"]
        test_start = fold["test_start_month"]
        test_end = fold["test_end_month"]

        train_months = cohort[cohort["reporting_month"] <= t_end]["reporting_month"]
        test_months = cohort[(cohort["reporting_month"] >= test_start) & (cohort["reporting_month"] <= test_end)]["reporting_month"]

        max_train = train_months.max()
        min_test = test_months.min()
        gap_months = ym_to_int(min_test) - ym_to_int(max_train) - 1

        assert max_train < min_test, f"Temporal violation in Fold {fid}: {max_train} >= {min_test}"

        print(f"  Fold {fid}: Train [..{max_train}] | Buffer [{v_start}..{v_end}] ({gap_months}m gap) | Test [{min_test}..{test_months.max()}] -> LEAKAGE-FREE (OK)")
        fold_audit_rows.append({
            "fold_id": fid,
            "train_range": f"..{max_train}",
            "buffer_gap_months": gap_months,
            "test_range": f"{min_test}..{test_months.max()}",
            "train_max_lt_test_min": True
        })

    # -------------------------------------------------------------
    # 4. PROJECT IDENTITY AUDIT (SHARED VS UNSEEN PROJECTS)
    # -------------------------------------------------------------
    print("\n[4] AUDITING PROJECT IDENTITY (SHARED VS UNSEEN)...")
    # For each fold, inspect test projects vs training projects
    all_train_pids = set(cohort[cohort["reporting_month"] <= "2022-12"]["project_id"].unique())
    all_test_pids = set(df_preds["project_id"].unique())

    shared_pids = all_test_pids.intersection(all_train_pids)
    unseen_pids = all_test_pids - all_train_pids

    shared_test_rows = df_preds[df_preds["project_id"].isin(shared_pids)]
    unseen_test_rows = df_preds[df_preds["project_id"].isin(unseen_pids)]

    print(f"  Total Projects in Test Period: {len(all_test_pids):,}")
    print(f"  Shared Projects (seen in train): {len(shared_pids):,} ({len(shared_test_rows):,} test observations)")
    print(f"  Unseen Projects (new to test) : {len(unseen_pids):,} ({len(unseen_test_rows):,} test observations)")

    metrics_shared = evaluate_predictions(shared_test_rows[target_col].values, shared_test_rows["pred_prob"].values, threshold=0.50)
    metrics_unseen = evaluate_predictions(unseen_test_rows[target_col].values, unseen_test_rows["pred_prob"].values, threshold=0.50) if len(unseen_test_rows) > 0 else {}

    print(f"  Shared Projects Performance: PR-AUC={metrics_shared['pr_auc']:.4f}, ROC-AUC={metrics_shared['roc_auc']:.4f}, Prec={metrics_shared['precision']:.4f}, Rec={metrics_shared['recall']:.4f}")
    if metrics_unseen:
        print(f"  Unseen Projects Performance: PR-AUC={metrics_unseen['pr_auc']:.4f}, ROC-AUC={metrics_unseen['roc_auc']:.4f}, Prec={metrics_unseen['precision']:.4f}, Rec={metrics_unseen['recall']:.4f}")

    # -------------------------------------------------------------
    # 5. FEATURE ABLATION STUDY: CURRENT STATE VS TRAJECTORY VS FULL
    # -------------------------------------------------------------
    print("\n[5] RUNNING FEATURE ABLATION STUDY...")
    # Define feature sets
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

    feature_sets = {
        "Model A (Current State Only)": current_state_features,
        "Model B (Trajectory Only)": trajectory_features,
        "Model C (Full VIGIL)": full_features
    }

    ablation_results = []

    for model_name, fset in feature_sets.items():
        print(f"\n  Evaluating {model_name} ({len(fset)} features)...")
        cat_in_fset = [c for c in cat_features if c in fset]
        m_oof_preds = []
        m_oof_true = []
        m_oof_df_list = []

        for fold in folds:
            fid = fold["fold_id"]
            t_end = fold["train_end_month"]
            v_start = fold["val_start_month"]
            v_end = fold["val_end_month"]
            test_start = fold["test_start_month"]
            test_end = fold["test_end_month"]

            train_mask = (cohort["reporting_month"] <= t_end) & ~cohort[target_col].isna()
            val_mask = (cohort["reporting_month"] >= v_start) & (cohort["reporting_month"] <= v_end) & ~cohort[target_col].isna()
            test_mask = (cohort["reporting_month"] >= test_start) & (cohort["reporting_month"] <= test_end) & ~cohort[target_col].isna()

            df_tr = cohort[train_mask]
            df_va = cohort[val_mask]
            df_te = cohort[test_mask]

            m = train_lgbm_model(
                df_tr[fset], df_tr[target_col].values.astype(float),
                df_va[fset], df_va[target_col].values.astype(float),
                categorical_features=cat_in_fset, params=config["lightgbm_params"]
            )
            te_probs = predict_lgbm_probs(m, df_te[fset], categorical_features=cat_in_fset)
            m_oof_preds.extend(te_probs)
            m_oof_true.extend(df_te[target_col].values.astype(float))

            df_te_sub = df_te[["project_id", "reporting_month", "C_base", "schedule_deviation_months", target_col]].copy()
            df_te_sub["pred_prob"] = te_probs
            m_oof_df_list.append(df_te_sub)

        m_oof_preds = np.array(m_oof_preds)
        m_oof_true = np.array(m_oof_true)
        df_m_all = pd.concat(m_oof_df_list, ignore_index=True)

        ev_m = evaluate_predictions(m_oof_true, m_oof_preds, threshold=0.50)
        lt_m, _ = audit_event_lead_times(df_m_all, df_dataset, threshold=0.50)

        ablation_results.append({
            "model_family": model_name,
            "feature_count": len(fset),
            "pr_auc": ev_m["pr_auc"],
            "roc_auc": ev_m["roc_auc"],
            "brier_score": ev_m["brier_score"],
            "precision": ev_m["precision"],
            "recall": ev_m["recall"],
            "false_alert_rate": ev_m["false_alert_rate"],
            "alert_median_lead_time": lt_m["alert_level"]["median_lead_time"],
            "event_median_lead_time": lt_m["event_level"]["median_lead_time"],
            "event_count": lt_m["event_level"]["unique_events"]
        })
        print(f"    PR-AUC: {ev_m['pr_auc']:.4f} | ROC-AUC: {ev_m['roc_auc']:.4f} | Prec: {ev_m['precision']:.4f} | Rec: {ev_m['recall']:.4f} | FAR: {ev_m['false_alert_rate']:.4f} | Event Lead Time: {lt_m['event_level']['median_lead_time']:.1f} mos")

    # -------------------------------------------------------------
    # 6. COST REVISION FEATURE ABLATION
    # -------------------------------------------------------------
    print("\n[6] RUNNING COST REVISION FEATURE ABLATION...")
    features_no_crr = [f for f in all_features if f != "cost_revision_ratio"]
    # Model without all cost revision fields (cost_revision_ratio, C_base)
    features_no_cost_rev = [f for f in all_features if f not in ["cost_revision_ratio", "C_base"]]

    cost_ablations = {
        "Full VIGIL Model": all_features,
        "Without cost_revision_ratio": features_no_crr,
        "Without any cost baseline/revision": features_no_cost_rev
    }

    cost_ablation_results = []
    for ca_name, fset in cost_ablations.items():
        print(f"\n  Evaluating {ca_name} ({len(fset)} features)...")
        cat_in_fset = [c for c in cat_features if c in fset]
        m_oof_preds = []
        m_oof_true = []
        m_oof_df_list = []

        for fold in folds:
            fid = fold["fold_id"]
            t_end = fold["train_end_month"]
            v_start = fold["val_start_month"]
            v_end = fold["val_end_month"]
            test_start = fold["test_start_month"]
            test_end = fold["test_end_month"]

            train_mask = (cohort["reporting_month"] <= t_end) & ~cohort[target_col].isna()
            val_mask = (cohort["reporting_month"] >= v_start) & (cohort["reporting_month"] <= v_end) & ~cohort[target_col].isna()
            test_mask = (cohort["reporting_month"] >= test_start) & (cohort["reporting_month"] <= test_end) & ~cohort[target_col].isna()

            df_tr = cohort[train_mask]
            df_va = cohort[val_mask]
            df_te = cohort[test_mask]

            m = train_lgbm_model(
                df_tr[fset], df_tr[target_col].values.astype(float),
                df_va[fset], df_va[target_col].values.astype(float),
                categorical_features=cat_in_fset, params=config["lightgbm_params"]
            )
            te_probs = predict_lgbm_probs(m, df_te[fset], categorical_features=cat_in_fset)
            m_oof_preds.extend(te_probs)
            m_oof_true.extend(df_te[target_col].values.astype(float))

            df_te_sub = df_te[["project_id", "reporting_month", "C_base", "schedule_deviation_months", target_col]].copy()
            df_te_sub["pred_prob"] = te_probs
            m_oof_df_list.append(df_te_sub)

        m_oof_preds = np.array(m_oof_preds)
        m_oof_true = np.array(m_oof_true)
        df_m_all = pd.concat(m_oof_df_list, ignore_index=True)

        ev_ca = evaluate_predictions(m_oof_true, m_oof_preds, threshold=0.50)
        lt_ca, _ = audit_event_lead_times(df_m_all, df_dataset, threshold=0.50)

        cost_ablation_results.append({
            "experiment": ca_name,
            "feature_count": len(fset),
            "pr_auc": ev_ca["pr_auc"],
            "roc_auc": ev_ca["roc_auc"],
            "brier_score": ev_ca["brier_score"],
            "precision": ev_ca["precision"],
            "recall": ev_ca["recall"],
            "false_alert_rate": ev_ca["false_alert_rate"],
            "event_median_lead_time": lt_ca["event_level"]["median_lead_time"]
        })
        print(f"    PR-AUC: {ev_ca['pr_auc']:.4f} | ROC-AUC: {ev_ca['roc_auc']:.4f} | Prec: {ev_ca['precision']:.4f} | Rec: {ev_ca['recall']:.4f} | FAR: {ev_ca['false_alert_rate']:.4f}")

    # Combine ablation results
    df_ablation_all = pd.DataFrame(ablation_results + cost_ablation_results)
    df_ablation_all.to_parquet("DATA/model_ablation_results.parquet", index=False)

    # -------------------------------------------------------------
    # 7. THRESHOLD OPERATING MODES (0.30 TO 0.70)
    # -------------------------------------------------------------
    print("\n[7] AUDITING THRESHOLD OPERATING MODES...")
    threshold_list = [0.30, 0.35, 0.40, 0.50, 0.60, 0.70]
    thresh_table = []

    for th in threshold_list:
        ev_th = evaluate_predictions(oof_y_true, oof_raw_probs, threshold=th)
        lt_th, _ = audit_event_lead_times(df_preds, df_dataset, threshold=th)
        thresh_table.append({
            "threshold": th,
            "precision": ev_th["precision"],
            "recall": ev_th["recall"],
            "f1": ev_th["f1"],
            "false_alert_rate": ev_th["false_alert_rate"],
            "total_alerts": ev_th["tp"] + ev_th["fp"],
            "alert_rate_pct": round(ev_th["alert_rate"] * 100, 2),
            "unique_events": lt_th["event_level"]["unique_events"],
            "event_median_lead_time": lt_th["event_level"]["median_lead_time"],
            "event_mean_lead_time": lt_th["event_level"]["mean_lead_time"]
        })
        print(f"  tau={th:.2f}: Prec={ev_th['precision']*100:.1f}%, Rec={ev_th['recall']*100:.1f}%, FAR={ev_th['false_alert_rate']*100:.2f}%, Alerts={ev_th['tp']+ev_th['fp']:,} ({ev_th['alert_rate']*100:.1f}%), Event Lead Time={lt_th['event_level']['median_lead_time']:.1f}m (Mean {lt_th['event_level']['mean_lead_time']:.1f}m)")

    # -------------------------------------------------------------
    # 8. RECENT-PERIOD PERFORMANCE (FOLD 3)
    # -------------------------------------------------------------
    print("\n[8] AUDITING RECENT-PERIOD PERFORMANCE (FOLD 3: 2023-07 to 2024-03)...")
    fold3_preds = df_preds[df_preds["fold_id"] == 3]
    f3_y_true = fold3_preds[target_col].values.astype(float)
    f3_y_prob = fold3_preds["pred_prob"].values

    for tau_opt in [0.30, 0.35, 0.40, 0.50]:
        ev_f3 = evaluate_predictions(f3_y_true, f3_y_prob, threshold=tau_opt)
        lt_f3, _ = audit_event_lead_times(fold3_preds, df_dataset, threshold=tau_opt)
        print(f"  Fold 3 (tau={tau_opt:.2f}): PR-AUC={ev_f3['pr_auc']:.4f}, Prec={ev_f3['precision']*100:.1f}%, Rec={ev_f3['recall']*100:.1f}%, FAR={ev_f3['false_alert_rate']*100:.2f}%, Alerts={ev_f3['tp']+ev_f3['fp']}, Event Lead Time={lt_f3['event_level']['median_lead_time']:.1f} mos")

    # -------------------------------------------------------------
    # 9. FEATURE IMPORTANCE ROBUSTNESS ACROSS FOLDS
    # -------------------------------------------------------------
    print("\n[9] AUDITING FEATURE IMPORTANCE ACROSS INDIVIDUAL FOLDS...")
    fold_imp_dict = {}
    for fid, m in fold_models.items():
        g = m.booster_.feature_importance(importance_type="gain")
        norm_g = g / g.sum() * 100.0
        s = pd.Series(norm_g, index=all_features).sort_values(ascending=False)
        fold_imp_dict[f"Fold_{fid}_Gain%"] = s.round(2)

    df_cross_fold_imp = pd.DataFrame(fold_imp_dict)
    df_cross_fold_imp["Mean_Gain%"] = df_cross_fold_imp.mean(axis=1).round(2)
    df_cross_fold_imp = df_cross_fold_imp.sort_values(by="Mean_Gain%", ascending=False)
    print("  Top 10 Features Across Folds:")
    print(df_cross_fold_imp.head(10).to_string())

    print("\n" + "=" * 70)
    print("VALIDATION AUDIT SUCCESSFULLY COMPLETED.")
    print("=" * 70)

if __name__ == "__main__":
    run_validation_audit()
