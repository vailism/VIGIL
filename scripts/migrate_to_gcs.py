#!/usr/bin/env python3
import os
import glob
import subprocess
from sanket.storage import get_sha256

def run_cmd(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

bucket = os.environ.get("GCS_BUCKET", "YOUR_BUCKET_NAME_HERE")
prefix = os.environ.get("GCS_PREFIX", "sanket/")

files_to_upload = [
    ("DATA/model_dataset.parquet", "datasets/model_dataset.parquet"),
    ("DATA/event_lead_times.parquet", "datasets/event_lead_times.parquet"),
    ("DATA/project_trajectories.parquet", "datasets/project_trajectories.parquet"),
    ("DATA/project_targets.parquet", "datasets/project_targets.parquet"),
    ("DATA/project_timelines.parquet", "datasets/project_timelines.parquet"),
    ("DATA/project_monthly.csv", "datasets/project_monthly.csv"),
    ("DATA/vigil_production_model.joblib", "models/vigil_production_model.joblib"),
]

print(f"Uploading artifacts to gs://{bucket}/{prefix} ...")

for local_path, remote_subpath in files_to_upload:
    if os.path.exists(local_path):
        gs_path = f"gs://{bucket}/{prefix}{remote_subpath}"
        run_cmd(f"gsutil cp {local_path} {gs_path}")
        # Assuming gsutil calculates md5, but we rely on our SHA256 parity script
        print(f"Uploaded {local_path} (SHA-256: {get_sha256(local_path)})")

print("\nUploading source PDFs...")
run_cmd(f"gsutil -m cp -r 'DATA(RAW)/*.pdf' gs://{bucket}/{prefix}source-pdfs/")

print("\nUpload complete! Run `scripts/test_gcs_parity.py` with SANKET_STORAGE_MODE=gcs to verify.")
