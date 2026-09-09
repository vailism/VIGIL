#!/usr/bin/env python3
"""
scripts/audit_risk_distribution.py
In-depth audit of risk tier distribution, historical fold prevalence,
and root-cause decomposition of the active portfolio ESCALATE share.
"""
from sanket.portfolio import get_portfolio
from sanket.inference import load_inference_engine
import pandas as pd
import numpy as np

p = get_portfolio()
active_df = p.active_projects_df.copy()

print("="*80)
print("1. ACTIVE PORTFOLIO RISK DISTRIBUTION (2024-2025)")
print("="*80)
total_active = len(active_df)
probs = active_df["latest_risk"]

counts = {
    "NORMAL": p.normal_count,
    "WATCH": p.watch_count,
    "REVIEW": p.review_count,
    "ESCALATE": p.escalate_count
}

print(f"Total Active Projects: {total_active}")
print(f"Mean Calibrated Probability: {probs.mean():.4f}")
print(f"Median Calibrated Probability: {probs.median():.4f}")
print(f"Standard Deviation: {probs.std():.4f}")
print(f"Min: {probs.min():.4f}, Max: {probs.max():.4f}")
print()
for tier in ["NORMAL", "WATCH", "REVIEW", "ESCALATE"]:
    cnt = counts[tier]
    pct = cnt / total_active * 100
    t_probs = active_df[active_df["risk_tier"] == tier]["latest_risk"]
    t_mean = t_probs.mean() if len(t_probs) > 0 else 0
    t_med = t_probs.median() if len(t_probs) > 0 else 0
    print(f"{tier:<10} | Count: {cnt:5d} ({pct:5.1f}%) | Mean Prob: {t_mean:.4f} | Median Prob: {t_med:.4f}")

print("\n" + "="*80)
print("2. HISTORICAL BACKTEST FOLD PREVALENCE (OOF)")
print("="*80)
engine = load_inference_engine()
df_pred = pd.read_parquet("DATA/ml_predictions.parquet")
raw = df_pred["pred_prob"].values
cal = engine["calibrator"].predict(raw)
df_pred["calibrated_prob"] = cal

for fold_id in sorted(df_pred["fold_id"].unique()):
    sub = df_pred[df_pred["fold_id"] == fold_id]
    c = sub["calibrated_prob"].values
    y = sub["overrun_composite_12m"].values
    s_min = sub["reporting_month"].min()
    s_max = sub["reporting_month"].max()
    esc = (c >= 0.50).mean() * 100
    rev = ((c >= 0.45) & (c < 0.50)).mean() * 100
    wat = ((c >= 0.40) & (c < 0.45)).mean() * 100
    norm = (c < 0.40).mean() * 100
    print(f"Fold {fold_id} ({s_min} to {s_max}) - {len(sub):,} observations:")
    print(f"  Target prevalence: {y.mean()*100:5.1f}%")
    print(f"  Calibrated Prob Mean: {c.mean():.4f} | Median: {np.median(c):.4f}")
    print(f"  NORMAL: {norm:5.1f}% | WATCH: {wat:5.1f}% | REVIEW: {rev:5.1f}% | ESCALATE: {esc:5.1f}%")

# Overall OOF
print(f"\nOverall OOF ({len(df_pred):,} observations):")
print(f"  Target prevalence: {df_pred['overrun_composite_12m'].mean()*100:5.1f}%")
print(f"  Calibrated Prob Mean: {cal.mean():.4f} | Median: {np.median(cal):.4f}")
print(f"  NORMAL: {(cal < 0.40).mean()*100:5.1f}% | WATCH: {((cal >= 0.40) & (cal < 0.45)).mean()*100:5.1f}% | REVIEW: {((cal >= 0.45) & (cal < 0.50)).mean()*100:5.1f}% | ESCALATE: {(cal >= 0.50).mean()*100:5.1f}%")

print("\n" + "="*80)
print("3. ESCALATE RATE BREAKDOWNS (WHY IS IT ~60.7%?)")
print("="*80)

# A. By Sector
print("\nA. ESCALATE Share by Sector:")
sec_esc = active_df.groupby("sector_display").agg(
    total=("project_id", "count"),
    escalate=("risk_tier", lambda s: (s == "ESCALATE").sum()),
    mean_prob=("latest_risk", "mean")
)
sec_esc["escalate_pct"] = sec_esc["escalate"] / sec_esc["total"] * 100
sec_esc = sec_esc.sort_values("total", ascending=False)
for idx, r in sec_esc.iterrows():
    print(f"{idx:<30} | Total: {int(r['total']):4d} | Escalate: {int(r['escalate']):4d} ({r['escalate_pct']:5.1f}%) | Mean Prob: {r['mean_prob']:.4f}")

# B. By Reporting Year of latest observation
print("\nB. ESCALATE Share by Latest Observation Period:")
yr_esc = active_df.groupby(active_df["reporting_month"].str.slice(0, 7)).agg(
    total=("project_id", "count"),
    escalate=("risk_tier", lambda s: (s == "ESCALATE").sum()),
    mean_prob=("latest_risk", "mean")
)
yr_esc["escalate_pct"] = yr_esc["escalate"] / yr_esc["total"] * 100
for idx, r in yr_esc.iterrows():
    print(f"Month: {idx} | Total: {int(r['total']):4d} | Escalate: {int(r['escalate']):4d} ({r['escalate_pct']:5.1f}%) | Mean Prob: {r['mean_prob']:.4f}")

# C. By Project Age
print("\nC. ESCALATE Share by Project Age (project_age_months):")
if "project_age_months" in active_df.columns:
    active_df["age_bucket"] = pd.cut(
        pd.to_numeric(active_df["project_age_months"], errors="coerce"),
        bins=[-1, 12, 36, 60, 120, 1000],
        labels=["< 1 yr", "1-3 yrs", "3-5 yrs", "5-10 yrs", "> 10 yrs"]
    )
    age_esc = active_df.groupby("age_bucket", observed=False).agg(
        total=("project_id", "count"),
        escalate=("risk_tier", lambda s: (s == "ESCALATE").sum()),
        mean_prob=("latest_risk", "mean")
    )
    age_esc["escalate_pct"] = age_esc["escalate"] / age_esc["total"] * 100
    for idx, r in age_esc.iterrows():
        print(f"Age: {str(idx):<10} | Total: {int(r['total']):4d} | Escalate: {int(r['escalate']):4d} ({r['escalate_pct']:5.1f}%) | Mean Prob: {r['mean_prob']:.4f}")

# D. By Cost Size Bucket (scale_bucket or C_base)
print("\nD. ESCALATE Share by Cost Scale Bucket (scale_bucket):")
if "scale_bucket" in active_df.columns:
    sc_esc = active_df.groupby("scale_bucket").agg(
        total=("project_id", "count"),
        escalate=("risk_tier", lambda s: (s == "ESCALATE").sum()),
        mean_prob=("latest_risk", "mean")
    )
    sc_esc["escalate_pct"] = sc_esc["escalate"] / sc_esc["total"] * 100
    for idx, r in sc_esc.iterrows():
        print(f"Scale: {str(idx):<15} | Total: {int(r['total']):4d} | Escalate: {int(r['escalate']):4d} ({r['escalate_pct']:5.1f}%) | Mean Prob: {r['mean_prob']:.4f}")

# E. Key model features driving risk in active portfolio
print("\nE. Key Driver Features in Active Portfolio:")
sdev = pd.to_numeric(active_df.get("schedule_deviation_months", 0), errors="coerce").fillna(0)
print(f"Schedule Deviation (months): Median = {sdev.median():.1f}, Mean = {sdev.mean():.1f}, % > 0 mos = {(sdev > 0).mean()*100:.1f}%, % >= 12 mos = {(sdev >= 12).mean()*100:.1f}%")

c_rev = pd.to_numeric(active_df.get("cost_revision_ratio", 1.0), errors="coerce").fillna(1.0)
print(f"Cost Revision Ratio: Median = {c_rev.median():.2f}, Mean = {c_rev.mean():.2f}, % > 1.0 = {(c_rev > 1.0).mean()*100:.1f}%")

fin_prog = pd.to_numeric(active_df.get("financial_progress", 0), errors="coerce").fillna(0)
print(f"Financial Progress (%): Median = {fin_prog.median():.1f}%, Mean = {fin_prog.mean():.1f}%")

v_fin_1m = pd.to_numeric(active_df.get("V_fin_1m", 0), errors="coerce").fillna(0)
print(f"V_fin_1m (%/mo): Median = {v_fin_1m.median():.2f}%, Mean = {v_fin_1m.mean():.2f}%, % <= 0 = {(v_fin_1m <= 0).mean()*100:.1f}%")

traj_score = pd.to_numeric(active_df.get("trajectory_risk_score", 0), errors="coerce").fillna(0)
print(f"Trajectory Risk Score: Median = {traj_score.median():.2f}, Mean = {traj_score.mean():.2f}")
