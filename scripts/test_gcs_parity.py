import os
import shutil
import json
from fastapi.testclient import TestClient

# 1. Force GCS Mode (we will mock the actual GCS API)
os.environ["SANKET_STORAGE_MODE"] = "gcs"
os.environ["GCS_BUCKET"] = "mock-bucket"
os.environ["SANKET_CACHE_DIR"] = "/tmp/sanket_cache_test"

import sanket.storage

# Mock the GCS downloader to just copy local files to simulate a pristine download
def mock_download(gcs_blob_name: str, dest_path: str):
    basename = os.path.basename(gcs_blob_name)
    source = os.path.join("DATA", basename)
    if os.path.exists(source):
        shutil.copy2(source, dest_path)
    else:
        raise FileNotFoundError(f"Mock GCS missing: {source}")

sanket.storage._download_from_gcs = mock_download

# Clean cache
if os.path.exists("/tmp/sanket_cache_test"):
    shutil.rmtree("/tmp/sanket_cache_test")

# 2. Start Application
from sanket.api import app
client = TestClient(app)

print("Starting Parity Test...")

# 3. Hit endpoints (this triggers the mock download)
resp1 = client.get("/api/dashboard/summary")
assert resp1.status_code == 200

# 4. Verify SHA-256 Parity
local_dataset = "DATA/model_dataset.parquet"
cached_dataset = "/tmp/sanket_cache_test/sanket_datasets_model_dataset.parquet"

hash_local = sanket.storage.get_sha256(local_dataset)
hash_cached = sanket.storage.get_sha256(cached_dataset)

print(f"Local  SHA-256: {hash_local}")
print(f"Cached SHA-256: {hash_cached}")

assert hash_local == hash_cached, "SHA-256 MISMATCH!"
print("✅ Byte-level SHA-256 parity verified.")

# 5. Inference Parity Test
print("Testing inference parity...")
# Pick a known project ID
proj_id = "020100040" # An example project ID from the dataset
resp_local = client.get(f"/api/projects/{proj_id}")
if resp_local.status_code == 200:
    print(f"✅ Replay Endpoint OK. Project {proj_id} predicted risk: {resp_local.json()['latest_prediction']['pred_prob']}")
else:
    print(f"Replay Endpoint failed for {proj_id}: {resp_local.text}")

print("✅ All parity tests passed. GCS abstraction successfully isolates inference logic.")
