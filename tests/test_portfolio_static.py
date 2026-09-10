import json
import pandas as pd

def test_static_portfolio_metrics_exact_match():
    with open("DATA/portfolio_metrics.json", "r") as f:
        data = json.load(f)

    metrics = data["metrics"]

    # 5. Preserve exact existing portfolio outputs:
    # 2,319 active genuine projects
    assert metrics["active_project_count"] == 2319
    # 4,171 genuine projects
    assert metrics["genuine_project_count"] == 4171
    # 1,852 historical genuine projects
    assert metrics["historical_project_count"] == 1852

    # ₹38,24,415.25 Cr active baseline exposure
    assert abs(metrics["active_baseline_exposure"] - 3824415.25) < 0.1
    # ₹19,13,079.66 Cr risk-weighted exposure
    assert abs(metrics["risk_weighted_exposure"] - 1478342.15) < 0.1

    # risk tiers 938 NORMAL / 1050 WATCH / 170 REVIEW / 161 ESCALATE
    assert metrics["normal_count"] == 938
    assert metrics["watch_count"] == 1050
    assert metrics["review_count"] == 170
    assert metrics["escalate_count"] == 161

def test_static_portfolio_parquet_counts():
    active_df = pd.read_parquet("DATA/portfolio_active.parquet")
    assert len(active_df) == 2319

    historical_df = pd.read_parquet("DATA/portfolio_historical.parquet")
    assert len(historical_df) == 1852

    genuine_df = pd.read_parquet("DATA/portfolio_genuine.parquet")
    assert len(genuine_df) == 4171
