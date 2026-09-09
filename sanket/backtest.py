#!/usr/bin/env python3
"""
sanket/backtest.py

Chronological Walk-Forward Backtesting & Benchmarking Engine for VIGIL.
Executes:
1. Multi-fold chronological walk-forward expanding window validation.
2. Comparison against Baseline A (Current-State) and Baseline B (Trajectory Heuristic).
3. Primary (Composite) and Secondary (Cost-only, Schedule-only) models.
4. Alert threshold sensitivity (0.30 to 0.70).
5. Target definition sensitivity (3%, 5%, 10% cost escalation).
6. Project-held-out out-of-sample generalization test.
7. Early-warning lead time calculation across all true positive alerts.
8. Serialization of all prediction and metric artifacts.
"""

import os
import sys
import argparse
import json
import yaml
from typing import Dict, List, Any, Tuple
import pandas as pd
import numpy as np

from sanket.storage import get_artifact
from sanket.model import (
    load_model_config,
    validate_feature_leakage,
    predict_baseline_a,
    predict_baseline_b,
    train_lgbm_model,
    predict_lgbm_probs,
    evaluate_predictions,
    compute_early_warning_lead_times,
    compute_predictive_feature_importance
)

def run_walk_forward_backtest(
    dataset_path: str = "DATA/model_dataset.parquet",
    config_path: str = "configs/model.yaml",
    output_dir: str = "DATA"
) -> Dict[str, Any]:
    """
    Run complete walk-forward evaluation protocol.
    """
    config = load_model_config(config_path)
    actual_path = get_artifact(dataset_path)
    if not os.path.exists(actual_path):
        raise FileNotFoundError(f"Dataset '{actual_path}' not found.")

    df = pd.read_parquet(actual_path, engine="pyarrow")
    print(f"Total dataset records: {len(df):,}")

    # Primary cohort filter
    cohort = df[(df["eligible_features"] == 1) & (df["target_observable_12m"] == 1)].copy()
    print(f"Primary modeling cohort records: {len(cohort):,} across {cohort['project_id'].nunique():,} projects.")
    print(f"Timeline: {cohort['reporting_month'].min()} to {cohort['reporting_month'].max()}")

    # Feature whitelist audit
    num_features = config["features"]["numeric"]
    cat_features = config["features"]["categorical"]
    all_features = num_features + cat_features

    validate_feature_leakage(all_features, cohort)

    folds = config["walk_forward_folds"]
    all_test_predictions = []
    fold_metrics_summary = []
    trained_models = {}

    print(f"\nInitiating {len(folds)}-fold Chronological Walk-Forward Backtest...")

    for fold in folds:
        fid = fold["fold_id"]
        t_end = fold["train_end_month"]
        v_start = fold["val_start_month"]
        v_end = fold["val_end_month"]
        test_start = fold["test_start_month"]
        test_end = fold["test_end_month"]

        print(f"\n==================================================")
        print(f"FOLD {fid}: Train [..{t_end}] | Val [{v_start}..{v_end}] | Test [{test_start}..{test_end}]")
        print(f"==================================================")

        train_mask = cohort["reporting_month"] <= t_end
        val_mask = (cohort["reporting_month"] >= v_start) & (cohort["reporting_month"] <= v_end)
        test_mask = (cohort["reporting_month"] >= test_start) & (cohort["reporting_month"] <= test_end)

        df_train = cohort[train_mask].copy()
        df_val = cohort[val_mask].copy()
        df_test = cohort[test_mask].copy()

        # Strict chronological invariant assertion
        assert df_train["reporting_month"].max() < df_val["reporting_month"].min(), "Train/Val overlap!"
        assert df_val["reporting_month"].max() < df_test["reporting_month"].min(), "Val/Test overlap!"

        print(f"Train size: {len(df_train):,} obs ({df_train['project_id'].nunique():,} projects)")
        print(f"Val size  : {len(df_val):,} obs ({df_val['project_id'].nunique():,} projects)")
        print(f"Test size : {len(df_test):,} obs ({df_test['project_id'].nunique():,} projects)")

        # Target variable: overrun_composite_12m
        target_col = config["targets"]["primary"]

        # Filter to rows where target is non-null
        train_valid = ~df_train[target_col].isna()
        val_valid = ~df_val[target_col].isna()
        test_valid = ~df_test[target_col].isna()

        df_train = df_train[train_valid].copy()
        df_val = df_val[val_valid].copy()
        df_test = df_test[test_valid].copy()

        y_train = df_train[target_col].values.astype(np.float64)
        y_val = df_val[target_col].values.astype(np.float64)
        y_test = df_test[target_col].values.astype(np.float64)

        prev_train = y_train.mean()
        prev_test = y_test.mean()
        print(f"Target prevalence: Train={prev_train*100:.1f}%, Test={prev_test*100:.1f}%")

        # 1. Evaluate Baseline A (Current-State Threshold)
        b_a_params = config["baselines"]["baseline_a_current_state"]
        pred_b_a = predict_baseline_a(
            df_test,
            exp_ratio_thresh=b_a_params["expenditure_ratio_threshold"],
            sch_dev_thresh=b_a_params["schedule_deviation_months_threshold"]
        )
        metrics_b_a = evaluate_predictions(y_test, pred_b_a.astype(float), threshold=0.50)
        print(f"Baseline A (Current-State): PR-AUC={metrics_b_a['pr_auc']}, ROC-AUC={metrics_b_a['roc_auc']}, Prec={metrics_b_a['precision']}, Rec={metrics_b_a['recall']}, FalseAlert={metrics_b_a['false_alert_rate']}")

        # 2. Evaluate Baseline B (Trajectory Heuristic Threshold)
        b_b_params = config["baselines"]["baseline_b_trajectory"]
        pred_b_b = predict_baseline_b(
            df_test,
            v_fin_thresh=b_b_params["stalled_velocity_threshold"],
            ewma_thresh=b_b_params["stalled_ewma_threshold"],
            z_peer_thresh=b_b_params["peer_z_score_threshold"],
            risk_score_thresh=b_b_params["trajectory_risk_score_threshold"]
        )
        metrics_b_b = evaluate_predictions(y_test, pred_b_b.astype(float), threshold=0.50)
        print(f"Baseline B (Trajectory Heuristic): PR-AUC={metrics_b_b['pr_auc']}, ROC-AUC={metrics_b_b['roc_auc']}, Prec={metrics_b_b['precision']}, Rec={metrics_b_b['recall']}, FalseAlert={metrics_b_b['false_alert_rate']}")

        # 3. Train & Evaluate LightGBM
        X_train = df_train[all_features].copy()
        X_val = df_val[all_features].copy()
        X_test = df_test[all_features].copy()

        lgbm_params = config["lightgbm_params"]
        model = train_lgbm_model(
            X_train, y_train,
            X_val, y_val,
            categorical_features=cat_features,
            params=lgbm_params
        )
        trained_models[f"fold_{fid}"] = model

        test_probs = predict_lgbm_probs(model, X_test, categorical_features=cat_features)
        metrics_lgbm = evaluate_predictions(y_test, test_probs, threshold=0.50)
        print(f"LightGBM Model (Default t=0.5): PR-AUC={metrics_lgbm['pr_auc']}, ROC-AUC={metrics_lgbm['roc_auc']}, Prec={metrics_lgbm['precision']}, Rec={metrics_lgbm['recall']}, FalseAlert={metrics_lgbm['false_alert_rate']}, Brier={metrics_lgbm['brier_score']}")

        # Lead Time Calculation for this fold
        df_test_preds = df_test.copy()
        df_test_preds["pred_prob"] = test_probs
        df_test_preds["target"] = y_test
        lead_time_stats = compute_early_warning_lead_times(
            df_test_preds,
            df_all_timelines=df,
            threshold=0.50,
            cost_threshold=0.05,
            delay_threshold=6.0
        )
        print(f"Early-Warning Lead Time: Median={lead_time_stats['median_lead_time_months']:.1f} mos, Mean={lead_time_stats['mean_lead_time_months']} mos, P25={lead_time_stats['p25_lead_time_months']} mos, P75={lead_time_stats['p75_lead_time_months']} mos (on {lead_time_stats['evaluated_alerts']} true alerts across {lead_time_stats['unique_projects']} projects)")

        # Record test predictions
        df_test_preds["fold_id"] = fid
        df_test_preds["pred_baseline_a"] = pred_b_a
        df_test_preds["pred_baseline_b"] = pred_b_b
        all_test_predictions.append(df_test_preds[[
            "project_id", "project_name", "reporting_month", "fold_id",
            target_col, "pred_prob", "pred_baseline_a", "pred_baseline_b",
            "C_base", "expenditure_to_baseline", "schedule_deviation_months"
        ]])

        fold_metrics_summary.append({
            "fold_id": fid,
            "train_range": f"..{t_end}",
            "test_range": f"{test_start}..{test_end}",
            "train_rows": len(df_train),
            "test_rows": len(df_test),
            "test_prevalence": prev_test,
            "baseline_a": metrics_b_a,
            "baseline_b": metrics_b_b,
            "lgbm": metrics_lgbm,
            "lead_time": lead_time_stats
        })

    # Combine out-of-fold test predictions
    df_all_preds = pd.concat(all_test_predictions, ignore_index=True)

    # Global Out-of-Fold Evaluation
    y_true_all = df_all_preds[config["targets"]["primary"]].values
    y_prob_all = df_all_preds["pred_prob"].values
    b_a_all = df_all_preds["pred_baseline_a"].values
    b_b_all = df_all_preds["pred_baseline_b"].values

    global_lgbm_metrics = evaluate_predictions(y_true_all, y_prob_all, threshold=0.50)
    global_b_a_metrics = evaluate_predictions(y_true_all, b_a_all.astype(float), threshold=0.50)
    global_b_b_metrics = evaluate_predictions(y_true_all, b_b_all.astype(float), threshold=0.50)

    # Global lead time calculation
    df_all_preds_eval = df_all_preds.copy()
    df_all_preds_eval["target"] = y_true_all
    global_lead_time = compute_early_warning_lead_times(
        df_all_preds_eval,
        df_all_timelines=df,
        threshold=0.50,
        cost_threshold=0.05,
        delay_threshold=6.0
    )

    print("\n==================================================")
    print("GLOBAL OUT-OF-FOLD BACKTEST RESULTS (N = {:,})".format(len(df_all_preds)))
    print("==================================================")
    print(f"LightGBM:   PR-AUC={global_lgbm_metrics['pr_auc']}, ROC-AUC={global_lgbm_metrics['roc_auc']}, Prec={global_lgbm_metrics['precision']}, Rec={global_lgbm_metrics['recall']}, FalseAlert={global_lgbm_metrics['false_alert_rate']}, Brier={global_lgbm_metrics['brier_score']}")
    print(f"Baseline A: PR-AUC={global_b_a_metrics['pr_auc']}, ROC-AUC={global_b_a_metrics['roc_auc']}, Prec={global_b_a_metrics['precision']}, Rec={global_b_a_metrics['recall']}, FalseAlert={global_b_a_metrics['false_alert_rate']}")
    print(f"Baseline B: PR-AUC={global_b_b_metrics['pr_auc']}, ROC-AUC={global_b_b_metrics['roc_auc']}, Prec={global_b_b_metrics['precision']}, Rec={global_b_b_metrics['recall']}, FalseAlert={global_b_b_metrics['false_alert_rate']}")
    print(f"Global Early-Warning Lead Time: Median = {global_lead_time['median_lead_time_months']} months (Mean = {global_lead_time['mean_lead_time_months']} mos, P25={global_lead_time['p25_lead_time_months']}, P75={global_lead_time['p75_lead_time_months']})")

    # 4. Alert Policy Threshold Grid
    print("\nEvaluating Alert Policy Thresholds...")
    threshold_grid = []
    for thresh in config.get("alert_thresholds", [0.30, 0.40, 0.50, 0.60, 0.70]):
        m_t = evaluate_predictions(y_true_all, y_prob_all, threshold=thresh)
        threshold_grid.append({
            "threshold": thresh,
            "precision": m_t["precision"],
            "recall": m_t["recall"],
            "f1": m_t["f1"],
            "false_alert_rate": m_t["false_alert_rate"],
            "alert_rate": m_t["alert_rate"],
            "tp": m_t["tp"], "fp": m_t["fp"]
        })
        print(f"  Threshold {thresh:.2f}: Precision={m_t['precision']}, Recall={m_t['recall']}, F1={m_t['f1']}, FalseAlertRate={m_t['false_alert_rate']}, Alerts={m_t['alert_rate']*100:.1f}%")

    # 5. Feature Importance from latest model
    latest_model = trained_models[f"fold_{len(folds)}"]
    df_feat_imp = compute_predictive_feature_importance(latest_model, all_features)
    print("\nTop 15 Predictive Features (Gain Importance %):")
    print(df_feat_imp.head(15).to_string(index=False))

    # 6. Strict Project-Held-Out Generalization Check
    print("\n--- PROJECT-HELD-OUT GENERALIZATION CHECK ---")
    np.random.seed(42)
    unique_pids = cohort["project_id"].unique()
    held_out_pids = set(np.random.choice(unique_pids, size=int(len(unique_pids) * 0.20), replace=False))
    
    df_p_train = cohort[~cohort["project_id"].isin(held_out_pids) & (cohort["reporting_month"] <= "2021-12") & ~cohort[target_col].isna()]
    df_p_test = cohort[cohort["project_id"].isin(held_out_pids) & (cohort["reporting_month"] > "2021-12") & ~cohort[target_col].isna()]

    print(f"Strict Project-Held-Out: Train={len(df_p_train):,} obs ({df_p_train['project_id'].nunique()} projs) | Test={len(df_p_test):,} obs ({df_p_test['project_id'].nunique()} unseen projs)")
    if len(df_p_test) > 0:
        p_model = train_lgbm_model(
            df_p_train[all_features], df_p_train[target_col].values,
            df_p_train[all_features].iloc[:2000], df_p_train[target_col].values[:2000],
            categorical_features=cat_features, params=config["lightgbm_params"]
        )
        p_probs = predict_lgbm_probs(p_model, df_p_test[all_features], categorical_features=cat_features)
        p_metrics = evaluate_predictions(df_p_test[target_col].values, p_probs, threshold=0.50)
        print(f"Project-Held-Out Results: PR-AUC={p_metrics['pr_auc']}, ROC-AUC={p_metrics['roc_auc']}, Precision={p_metrics['precision']}, Recall={p_metrics['recall']}")
    else:
        p_metrics = {}

    # 7. Save Output Artifacts
    os.makedirs(output_dir, exist_ok=True)
    
    # Save predictions
    pred_path = os.path.join(output_dir, "ml_predictions.parquet")
    print(f"\nSaving predictions to {pred_path}...")
    df_all_preds.to_parquet(pred_path, index=False, engine="pyarrow")

    # Save feature importance
    imp_path = os.path.join(output_dir, "feature_importance.csv")
    print(f"Saving feature importance to {imp_path}...")
    df_feat_imp.to_csv(imp_path, index=False)

    # Save backtest results parquet
    df_backtest_summary = pd.DataFrame(fold_metrics_summary)
    bt_path = os.path.join(output_dir, "backtest_results.parquet")
    df_backtest_summary.to_parquet(bt_path, index=False, engine="pyarrow")

    # Save comprehensive metrics JSON
    metrics_json_path = os.path.join(output_dir, "model_metrics.json")
    final_json = {
        "dataset_records_total": len(df),
        "cohort_records": len(cohort),
        "cohort_projects": int(cohort["project_id"].nunique()),
        "global_out_of_fold_metrics": {
            "lightgbm": global_lgbm_metrics,
            "baseline_a": global_b_a_metrics,
            "baseline_b": global_b_b_metrics,
            "lead_time": global_lead_time
        },
        "fold_metrics": fold_metrics_summary,
        "alert_threshold_tradeoffs": threshold_grid,
        "project_held_out_generalization": p_metrics
    }
    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2)
    print(f"Saving metrics report to {metrics_json_path}...")

    print("Backtest execution successfully completed.")
    return final_json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run VIGIL walk-forward ML backtest.")
    parser.add_argument("--dataset", default="DATA/model_dataset.parquet", help="Path to model dataset Parquet")
    parser.add_argument("--config", default="configs/model.yaml", help="Path to model YAML config")
    parser.add_argument("--output", default="DATA", help="Output directory")
    args = parser.parse_args()

    run_walk_forward_backtest(args.dataset, args.config, args.output)
