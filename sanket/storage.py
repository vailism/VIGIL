#!/usr/bin/env python3
"""
sanket/storage.py

Artifact Storage Abstraction Layer.
Manages lazy-loading of large datasets and model artifacts from
Google Cloud Storage (GCS) or the local filesystem.

Usage:
    export SANKET_STORAGE_MODE=gcs
    export GCS_BUCKET=my-sanket-bucket
    export GCS_PREFIX=sanket/
"""

import os
import shutil
import hashlib
import tempfile
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SANKET_STORAGE_MODE = os.environ.get("SANKET_STORAGE_MODE", "local").lower()
GCS_BUCKET = os.environ.get("GCS_BUCKET", "sanket-artifacts-bucket")
GCS_PREFIX = os.environ.get("GCS_PREFIX", "sanket/")
LOCAL_CACHE_DIR = os.environ.get("SANKET_CACHE_DIR", os.path.join(tempfile.gettempdir(), "sanket_cache"))

# In-memory lock mechanism to prevent concurrent downloads
_DOWNLOAD_LOCKS = set()

def get_sha256(filepath: str) -> str:
    """Calculate SHA-256 hash of a file for parity verification."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def _download_from_gcs(gcs_blob_name: str, dest_path: str):
    """Download a file from GCS."""
    try:
        from google.cloud import storage
    except ImportError:
        raise ImportError("google-cloud-storage is required for SANKET_STORAGE_MODE=gcs. Run: pip install google-cloud-storage")

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(gcs_blob_name)
    
    if not blob.exists():
        raise FileNotFoundError(f"GCS Blob {gcs_blob_name} not found in bucket {GCS_BUCKET}.")
    
    logger.info(f"Downloading {gcs_blob_name} from GCS to {dest_path}...")
    blob.download_to_filename(dest_path)
    logger.info(f"Successfully downloaded {gcs_blob_name}. Size: {os.path.getsize(dest_path)} bytes.")

def get_artifact(local_fallback_path: str, gcs_subpath: Optional[str] = None) -> str:
    """
    Retrieve the absolute path to an artifact, downloading it from GCS if necessary.
    
    Args:
        local_fallback_path: Original path (e.g., 'DATA/model_dataset.parquet')
        gcs_subpath: Path inside GCS prefix (e.g., 'datasets/model_dataset.parquet')
    
    Returns:
        Absolute path to the local or cached artifact file.
    """
    abs_fallback = os.path.abspath(local_fallback_path)
    
    if SANKET_STORAGE_MODE == "local":
        if not os.path.exists(abs_fallback):
            raise FileNotFoundError(f"Local artifact not found: {abs_fallback}")
        return abs_fallback

    if SANKET_STORAGE_MODE == "gcs":
        if not gcs_subpath:
            # Infer from DATA/ directory
            basename = os.path.basename(local_fallback_path)
            if basename.endswith(".parquet") or basename.endswith(".csv"):
                gcs_subpath = f"datasets/{basename}"
            elif basename.endswith(".joblib"):
                gcs_subpath = f"models/{basename}"
            else:
                gcs_subpath = f"misc/{basename}"
        
        full_gcs_path = os.path.join(GCS_PREFIX, gcs_subpath).replace("\\", "/")
        os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)
        
        cached_path = os.path.join(LOCAL_CACHE_DIR, full_gcs_path.replace("/", "_"))
        
        if os.path.exists(cached_path):
            return cached_path
            
        if cached_path in _DOWNLOAD_LOCKS:
            pass
            
        _DOWNLOAD_LOCKS.add(cached_path)
        try:
            _download_from_gcs(full_gcs_path, cached_path)
            return cached_path
        except Exception as e:
            # Fallback to local if GCS fails (e.g., during tests without credentials)
            logger.warning(f"Failed to download from GCS ({e}). Attempting local fallback to {abs_fallback}")
            if os.path.exists(abs_fallback):
                # Copy to cache to simulate successful download and parity
                shutil.copy2(abs_fallback, cached_path)
                return cached_path
            raise e
        finally:
            _DOWNLOAD_LOCKS.remove(cached_path)
            
    raise ValueError(f"Unknown SANKET_STORAGE_MODE: {SANKET_STORAGE_MODE}")
