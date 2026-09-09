#!/usr/bin/env python3
"""
scripts/audit_mega_projects.py
Audit all active projects with C_base >= 25,000 Cr.
"""
from sanket.portfolio import get_portfolio
import pandas as pd
import numpy as np

p = get_portfolio()
df = p.active_projects_df.copy()

mega = df[df["baseline_cost"] >= 25000].sort_values("baseline_cost", ascending=False).reset_index(drop=True)
print(f"Total active projects with C_base >= 25,000 Cr: {len(mega)}")
print("="*130)
cols = ["#", "PROJECT ID", "MONTH", "SECTOR", "STATE", "C_BASE (Cr)", "APPROVED", "REVISED", "PROJECT NAME"]
print(f"{cols[0]:<3} | {cols[1]:<11} | {cols[2]:<7} | {cols[3]:<18} | {cols[4]:<14} | {cols[5]:<12} | {cols[6]:<10} | {cols[7]:<10} | {cols[8]}")
print("="*130)

for i, r in mega.iterrows():
    app = r.get("approved_cost", np.nan)
    rev = r.get("revised_cost", np.nan)
    sec = str(r["sector_display"])[:18]
    st = str(r.get("state", "—"))[:14]
    name = str(r["project_name"])[:55]
    print(f"{i+1:<3} | {r['project_id']:<11} | {r['reporting_month']:<7} | {sec:<18} | {st:<14} | {r['baseline_cost']:12.2f} | {app:10.2f} | {rev:10.2f} | {name}")
