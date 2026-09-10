import pandas as pd
import numpy as np
import time
import json
import psutil
import os
from sanket.inference import predict_point_in_time, predict_batch_in_time, load_inference_engine
from sanket.api import sanitize_for_json

def check_parity_and_benchmark():
    df = pd.read_parquet("DATA/model_dataset.parquet")
    engine = load_inference_engine()
    
    # Select 10 diverse projects
    # We want varied lengths and risk tiers
    # We'll just grab a few known ones, plus some others
    sample_pids = [
        "N24000252", # Escalated
        "N16000115", # Long history
        "N18000110", # Another one
    ]
    
    # Find a few more diverse projects
    project_counts = df.groupby("project_id").size()
    sample_pids.append(project_counts[project_counts < 10].index[0]) # Short
    sample_pids.append(project_counts[(project_counts > 30) & (project_counts < 60)].index[0]) # Medium
    sample_pids.append(project_counts[project_counts > 100].index[0] if len(project_counts[project_counts > 100]) > 0 else project_counts.idxmax()) # Long
    
    # Fill remaining to get 10
    remaining = list(set(project_counts.index) - set(sample_pids))
    sample_pids.extend(remaining[:10 - len(sample_pids)])
    
    print(f"Testing projects: {sample_pids}")
    
    max_prob_diff = 0.0
    risk_mismatches = 0
    explanation_mismatches = 0
    
    total_row_time = 0.0
    total_batch_time = 0.0
    
    # Test each project
    for pid in sample_pids:
        p_df = df[df["project_id"] == pid].sort_values("reporting_month").reset_index(drop=True)
        print(f"\nProject {pid} - {len(p_df)} observations")
        
        # 1. Row by row
        start_t = time.time()
        row_preds = []
        for i in range(len(p_df)):
            row = p_df.iloc[i]
            row_preds.append(predict_point_in_time(row, engine=engine))
        row_time = time.time() - start_t
        total_row_time += row_time
        
        # 2. Batch
        start_t = time.time()
        batch_preds = predict_batch_in_time(p_df, engine=engine)
        batch_time = time.time() - start_t
        total_batch_time += batch_time
        
        print(f"  Row-by-row time: {row_time:.4f}s")
        print(f"  Batch time:      {batch_time:.4f}s")
        print(f"  Speedup:         {row_time / batch_time:.1f}x")
        
        # 3. Compare
        for i in range(len(p_df)):
            r_pred = row_preds[i]
            b_pred = batch_preds[i]
            
            diff = abs(r_pred["pred_prob"] - b_pred["pred_prob"])
            if diff > max_prob_diff:
                max_prob_diff = diff
                
            if r_pred["risk_tier"] != b_pred["risk_tier"]:
                risk_mismatches += 1
                
            # Compare explanations
            r_expl = r_pred["top_explanations"]
            b_expl = b_pred["top_explanations"]
            
            if len(r_expl) != len(b_expl):
                explanation_mismatches += 1
            else:
                for j in range(len(r_expl)):
                    if r_expl[j]["feature"] != b_expl[j]["feature"]:
                        explanation_mismatches += 1
                    elif abs(r_expl[j]["contribution"] - b_expl[j]["contribution"]) > 1e-4:
                        explanation_mismatches += 1
                        
    print("\n--- RESULTS ---")
    print(f"Max Probability Diff: {max_prob_diff}")
    print(f"Risk Tier Mismatches: {risk_mismatches}")
    print(f"Explanation Mismatches: {explanation_mismatches}")
    print(f"Total Row Time: {total_row_time:.4f}s")
    print(f"Total Batch Time: {total_batch_time:.4f}s")
    print(f"Overall Speedup: {total_row_time / total_batch_time:.1f}x")
    
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"Peak RSS: {mem_mb:.1f} MB")

if __name__ == '__main__':
    check_parity_and_benchmark()
