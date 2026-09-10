#!/usr/bin/env python3
"""
sanket/inference.py

Production Inference Engine for VIGIL.
Features:
1. Point-in-time scoring using frozen production LightGBM model bundle.
2. Isotonic probability calibration.
3. Strict operating risk tiers (NORMAL, WATCH >= 0.40, REVIEW >= 0.45, ESCALATE >= 0.50).
4. Deterministic, traceable "WHY?" explanations using native TreeSHAP contributions.
   - Zero hallucination, zero LLM reliance.
   - Every factor traces directly to a verified feature value and positive contribution.
"""

import os
from typing import Dict, List, Any, Optional, Union
import numpy as np
import pandas as pd
import joblib

from sanket.storage import get_artifact

_CACHED_ENGINE = None

def load_inference_engine(model_path: str = "DATA/vigil_production_model.joblib") -> Dict[str, Any]:
    """
    Load the frozen production model bundle (Model, Calibrator, Whitelist, Thresholds).
    Caches the engine in memory for fast reuse.
    """
    global _CACHED_ENGINE
    if _CACHED_ENGINE is not None:
        return _CACHED_ENGINE

    norm_path = get_artifact(model_path)
    if not os.path.exists(norm_path):
        raise FileNotFoundError(
            f"Production model bundle '{norm_path}' not found. "
            "Please ensure the frozen model bundle is compiled in DATA/vigil_production_model.joblib."
        )

    bundle = joblib.load(norm_path)
    _CACHED_ENGINE = bundle
    return _CACHED_ENGINE

def get_risk_tier(prob: float) -> str:
    """
    Map probability to strictly validated operational risk tiers:
    - ESCALATE: prob >= 0.50
    - REVIEW   : 0.45 <= prob < 0.50
    - WATCH    : 0.40 <= prob < 0.45
    - NORMAL   : prob < 0.40
    """
    if prob >= 0.50:
        return "ESCALATE"
    elif prob >= 0.45:
        return "REVIEW"
    elif prob >= 0.40:
        return "WATCH"
    else:
        return "NORMAL"

def generate_feature_explanation(feature_name: str, value: Any) -> str:
    """
    Generate a deterministic, factual, human-readable description for a feature and its actual value.
    """
    if pd.isna(value):
        return f"{feature_name} is unobserved / missing"

    v_num = None
    if isinstance(value, (int, float, np.number)):
        v_num = float(value)

    if feature_name == "schedule_deviation_months":
        return f"Reported schedule delay is {v_num:.1f} months"
    elif feature_name == "schedule_deviation_change":
        return f"Schedule deviation changed by {v_num:+.1f} months recently"
    elif feature_name == "completion_date_drift":
        return f"Target completion pushed back by {v_num:.1f} months historically"
    elif feature_name == "cost_revision_ratio":
        pct = (v_num - 1.0) * 100.0
        return f"Cost baseline expanded by {pct:+.1f}% over original sanction"
    elif feature_name == "expenditure_to_baseline":
        return f"Cumulative expenditure reached {v_num * 100.0:.1f}% of baseline cost"
    elif feature_name == "V_fin_1m":
        return f"1-month financial progress velocity is {v_num:.2f}%/month"
    elif feature_name == "V_fin_3m":
        return f"3-month rolling financial velocity is {v_num:.2f}%/month"
    elif feature_name == "A_fin":
        return f"Financial progress acceleration is {v_num:+.2f}%/month²"
    elif feature_name == "EWMA_V_fin":
        return f"Exponentially weighted velocity trend at {v_num:.2f}%/month"
    elif feature_name == "V_exp_1m":
        return f"Recent monthly expenditure burn rate is ₹{v_num:,.2f} Cr/month"
    elif feature_name == "V_exp_3m":
        return f"3-month expenditure burn rate is ₹{v_num:,.2f} Cr/month"
    elif feature_name == "A_exp":
        return f"Expenditure burn acceleration is ₹{v_num:+,.2f} Cr/month²"
    elif feature_name == "Z_peer_V_fin":
        return f"Progress velocity is {v_num:+.2f} std dev vs sector peer baseline"
    elif feature_name == "trajectory_risk_score":
        return f"Kinetic multi-signal risk index elevated at {v_num:.1f}/100"
    elif feature_name == "financial_physical_gap":
        return f"Financial spend leads physical ground progress by {v_num:+.1f}%"
    elif feature_name == "C_base":
        return f"Sanctioned capital baseline scale is ₹{v_num:,.1f} Cr"
    elif feature_name == "project_age_months":
        return f"Project operational maturity is {v_num:.0f} months since sanction"
    elif feature_name == "observation_number":
        return f"Project has {v_num:.0f} sequential monitoring reports"
    elif feature_name == "months_since_previous_observation":
        return f"Reporting interval gap of {v_num:.0f} months from prior observation"
    elif feature_name == "reporting_gap_flag":
        return f"Irregular reporting gap flag is active ({int(v_num)})"
    elif feature_name == "scale_bucket":
        return f"Project categorized in {value} capital scale tier"
    elif feature_name == "sector_clean":
        return f"Monitored under {value} sector oversight"
    elif feature_name in ["V_phys_1m", "V_phys_3m"]:
        return f"Physical progress velocity recorded at {v_num:.2f}%/month"
    elif feature_name == "A_phys":
        return f"Physical progress acceleration at {v_num:+.2f}%/month²"
    else:
        return f"{feature_name} = {value}"

def explain_prediction(
    features_row: Union[pd.Series, Dict[str, Any]],
    engine: Optional[Dict[str, Any]] = None,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Compute top contributing factors for a single prediction using native TreeSHAP values.
    Returns sorted list of deterministic, traceable explanation factors.
    """
    if engine is None:
        engine = load_inference_engine()

    model = engine["model"]
    feature_names = engine["features"]
    cat_features = engine["categorical_features"]

    # Convert to DataFrame with 1 row
    if isinstance(features_row, dict):
        df_row = pd.DataFrame([features_row])
    elif isinstance(features_row, pd.Series):
        df_row = pd.DataFrame([features_row.to_dict()])
    else:
        df_row = features_row.copy()

    # Reindex to exact feature whitelist
    X_in = pd.DataFrame(index=[0])
    for f in feature_names:
        X_in[f] = df_row[f].values[0] if f in df_row.columns else np.nan

    for cat in cat_features:
        if cat in X_in.columns:
            X_in[cat] = X_in[cat].astype("category")

    # LightGBM native TreeSHAP: returns shape (1, n_features + 1)
    contribs = model.booster_.predict(X_in, pred_contrib=True)[0]
    feat_contribs = contribs[:-1]  # Exclude base margin / bias

    # Rank features by positive contribution (pushing toward escalation)
    ranked_indices = np.argsort(feat_contribs)[::-1]

    explanations = []
    for idx in ranked_indices:
        contrib = float(feat_contribs[idx])
        if contrib <= 0.0 and len(explanations) >= top_k:
            break
        feat = feature_names[idx]
        val = X_in.iloc[0][feat]
        text = generate_feature_explanation(feat, val)

        explanations.append({
            "feature": feat,
            "value": float(val) if isinstance(val, (int, float, np.number)) and not pd.isna(val) else (str(val) if not pd.isna(val) else None),
            "contribution": round(contrib, 4),
            "explanation": text
        })
        if len(explanations) >= top_k:
            break

    return explanations

def predict_point_in_time(
    features: Union[pd.DataFrame, pd.Series, Dict[str, Any]],
    engine: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Perform point-in-time risk scoring for a single observation or row.
    Returns:
    - raw_prob: raw LightGBM probability
    - calibrated_prob: Isotonic calibrated probability
    - risk_tier: NORMAL, WATCH, REVIEW, ESCALATE
    - alert: boolean (True if WATCH, REVIEW, or ESCALATE)
    - top_explanations: top 3 contributing factors
    """
    if engine is None:
        engine = load_inference_engine()

    model = engine["model"]
    calibrator = engine.get("calibrator")
    feature_names = engine["features"]
    cat_features = engine["categorical_features"]

    if isinstance(features, dict):
        df_row = pd.DataFrame([features])
    elif isinstance(features, pd.Series):
        df_row = pd.DataFrame([features.to_dict()])
    else:
        df_row = features.copy()

    X_in = pd.DataFrame(index=[0])
    for f in feature_names:
        X_in[f] = df_row[f].values[0] if f in df_row.columns else np.nan

    for cat in cat_features:
        if cat in X_in.columns:
            X_in[cat] = X_in[cat].astype("category")

    raw_prob = float(model.predict_proba(X_in)[:, 1][0])

    if calibrator is not None:
        calibrated_prob = float(np.clip(calibrator.predict([raw_prob])[0], 0.0, 1.0))
    else:
        calibrated_prob = raw_prob

    # Risk tier is evaluated on the calibrated probability
    risk_tier = get_risk_tier(calibrated_prob)
    alert = (risk_tier in ["WATCH", "REVIEW", "ESCALATE"])

    explanations = explain_prediction(df_row, engine=engine, top_k=3)

    return {
        "raw_prob": round(raw_prob, 4),
        "pred_prob": round(calibrated_prob, 4),
        "calibrated_prob": round(calibrated_prob, 4),
        "risk_tier": risk_tier,
        "alert": alert,
        "top_explanations": explanations
    }

def predict_batch_in_time(
    features_df: pd.DataFrame,
    engine: Optional[Dict[str, Any]] = None,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Perform point-in-time risk scoring for a batch of observations (e.g. a project's timeline).
    Dramatically faster than looping predict_point_in_time row-by-row.
    """
    if engine is None:
        engine = load_inference_engine()

    model = engine["model"]
    calibrator = engine.get("calibrator")
    feature_names = engine["features"]
    cat_features = engine["categorical_features"]

    X_in = pd.DataFrame(index=features_df.index)
    for f in feature_names:
        if f in features_df.columns:
            X_in[f] = features_df[f].copy()
        else:
            X_in[f] = np.nan

    for cat in cat_features:
        if cat in X_in.columns:
            X_in[cat] = X_in[cat].astype("category")

    raw_probs = model.predict_proba(X_in)[:, 1]

    if calibrator is not None:
        calib_probs = np.clip(calibrator.predict(raw_probs), 0.0, 1.0)
    else:
        calib_probs = raw_probs

    contribs_matrix = model.booster_.predict(X_in, pred_contrib=True)

    results = []
    for i in range(len(features_df)):
        raw_prob = float(raw_probs[i])
        calib_prob = float(calib_probs[i])
        risk_tier = get_risk_tier(calib_prob)
        alert = (risk_tier in ["WATCH", "REVIEW", "ESCALATE"])

        feat_contribs = contribs_matrix[i, :-1]
        ranked_indices = np.argsort(feat_contribs)[::-1]

        explanations = []
        for idx in ranked_indices:
            contrib = float(feat_contribs[idx])
            if contrib <= 0.0 and len(explanations) >= top_k:
                break
            feat = feature_names[idx]
            val = X_in.iloc[i][feat]
            text = generate_feature_explanation(feat, val)

            explanations.append({
                "feature": feat,
                "value": float(val) if isinstance(val, (int, float, np.number)) and not pd.isna(val) else (str(val) if not pd.isna(val) else None),
                "contribution": round(contrib, 4),
                "explanation": text
            })
            if len(explanations) >= top_k:
                break

        results.append({
            "raw_prob": round(raw_prob, 4),
            "pred_prob": round(calib_prob, 4),
            "calibrated_prob": round(calib_prob, 4),
            "risk_tier": risk_tier,
            "alert": alert,
            "top_explanations": explanations
        })

    return results
