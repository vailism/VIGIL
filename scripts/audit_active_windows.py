#!/usr/bin/env python3
"""
scripts/audit_active_windows.py
Compare portfolio under three active window definitions:
1. latest >= 2024-01 (current definition)
2. latest >= 2024-07 (past 9 months)
3. latest >= 2025-01 (current calendar year / past 3 months)
"""
from sanket.portfolio import get_portfolio, format_inr_currency
import pandas as pd
import numpy as np

p = get_portfolio()
genuine_df = p.genuine_projects_df.copy()

# Score all genuine projects using frozen inference engine
engine = p.engine
features = engine["features"]
cat_features = engine["categorical_features"]

X = pd.DataFrame(index=genuine_df.index)
for f in features:
    X[f] = genuine_df[f] if f in genuine_df.columns else np.nan
for cat in cat_features:
    if cat in X.columns:
        X[cat] = X[cat].astype("category")

raw_probs = engine["model"].predict_proba(X)[:, 1]
cal_probs = engine["calibrator"].predict(raw_probs)
genuine_df["calibrated_risk"] = np.round(cal_probs, 4)

from sanket.inference import get_risk_tier
genuine_df["risk_tier"] = [get_risk_tier(x) for x in cal_probs]

cbase = pd.to_numeric(genuine_df["C_base"], errors="coerce").fillna(0).round(2)
genuine_df["baseline_cost"] = cbase
genuine_df["risk_weighted_exposure"] = np.round(genuine_df["calibrated_risk"] * genuine_df["baseline_cost"], 2)

windows = [
    ("Current Window: >= 2024-01", "2024-01"),
    ("Tightened 9-Month Window: >= 2024-07", "2024-07"),
    ("Current Year 3-Month Window: >= 2025-01", "2025-01")
]

print("="*100)
print("ACTIVE WINDOW SENSITIVITY AUDIT")
print("="*100)

for label, cutoff in windows:
    sub = genuine_df[genuine_df["reporting_month"] >= cutoff].copy()
    count = len(sub)
    exp = sub["baseline_cost"].sum()
    rwe = sub["risk_weighted_exposure"].sum()
    
    esc = (sub["risk_tier"] == "ESCALATE").sum()
    rev = (sub["risk_tier"] == "REVIEW").sum()
    wat = (sub["risk_tier"] == "WATCH").sum()
    norm = (sub["risk_tier"] == "NORMAL").sum()
    
    print(f"\n--- {label} (cutoff: {cutoff}) ---")
    print(f"Project Count: {count:,}")
    print(f"Baseline Exposure: {format_inr_currency(exp)} (₹{exp:,.2f} Cr)")
    print(f"Risk-Weighted Exposure: {format_inr_currency(rwe)} (₹{rwe:,.2f} Cr)")
    print(f"Mean Calibrated Risk: {sub['calibrated_risk'].mean():.4f}")
    print(f"Median Calibrated Risk: {sub['calibrated_risk'].median():.4f}")
    print(f"Risk Tiers:")
    print(f"  ESCALATE : {esc:4d} ({esc/count*100:5.1f}%)")
    print(f"  REVIEW   : {rev:4d} ({rev/count*100:5.1f}%)")
    print(f"  WATCH    : {wat:4d} ({wat/count*100:5.1f}%)")
    print(f"  NORMAL   : {norm:4d} ({norm/count*100:5.1f}%)")
