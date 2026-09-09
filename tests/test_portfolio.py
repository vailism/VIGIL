import pytest
from sanket import db
@pytest.fixture(autouse=True)
def mock_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DEFAULT_SQLITE_PATH", str(tmp_path / "test.db"))
"""
tests/test_portfolio.py

Verification suite for VIGIL Portfolio Sanitization Layer:
1. Macro-summary rows are excluded.
2. Genuine numeric MoSPI IDs remain.
3. Legitimate large projects are not removed solely because of cost.
4. Historical projects are excluded from active portfolio.
5. Risk counts use active genuine projects only.
6. Exposure uses latest observation only.
7. Risk-weighted exposure equals probability × C_base.
8. No duplicate project IDs remain in active portfolio.
9. API dashboard values equal portfolio-layer values.
10. Existing replay/inference behavior is unchanged.
"""

import pytest
import numpy as np
from fastapi.testclient import TestClient

from sanket.portfolio import (
    get_portfolio,
    is_macro_summary_artifact,
    is_genuine_project,
    format_inr_currency
)
from sanket.api import app
from sanket.replay import get_project_replay


@pytest.fixture(scope="module")
def portfolio():
    return get_portfolio()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_1_macro_summary_rows_excluded(portfolio):
    """1. Test macro-summary rows and synthetic aggregate extraction artifacts are excluded."""
    # Known contaminated artifacts identified in audit
    is_art_1, _ = is_macro_summary_artifact("FLA RAILWAYS", "PRJ_BB0B04A558ED")
    is_art_2, _ = is_macro_summary_artifact("FLA RAILWAYS", "PRJ_7A8AEAB9026C")
    is_art_3, _ = is_macro_summary_artifact("MULTI STATE", "PRJ_7E1127E0E912")
    is_art_4, _ = is_macro_summary_artifact("KERALA", "PRJ_005CDEFE4BD6")
    is_art_5, _ = is_macro_summary_artifact("RAILWAYS LAS ROAD TRANSPORT AND HIGHWAYS", "PRJ_97FDB60EFC74")

    assert is_art_1 is True
    assert is_art_2 is True
    assert is_art_3 is True
    assert is_art_4 is True
    assert is_art_5 is True

    # Assert these are excluded from sanitized active portfolio
    active_ids = set(portfolio.active_projects_df["project_id"].values)
    assert "PRJ_BB0B04A558ED" not in active_ids
    assert "PRJ_7A8AEAB9026C" not in active_ids
    assert "PRJ_7E1127E0E912" not in active_ids
    assert "PRJ_005CDEFE4BD6" not in active_ids
    assert "PRJ_97FDB60EFC74" not in active_ids


def test_2_genuine_numeric_mospi_ids_remain(portfolio):
    """2. Test genuine numeric MoSPI IDs remain in portfolio."""
    # Parbati HEP (Power)
    assert is_genuine_project("180100210", "PARBATI HYDROELECTRIC PROJECT STAGE-II") is True
    # Udhampur-Srinagar-Baramulla (Railways)
    assert is_genuine_project("220100133", "UDHAMPUR-SRINAGAR- BARAMULLA (NL),NR") is True
    # Kudankulam APP (Atomic Energy)
    assert is_genuine_project("020100040", "KUDANKULAM APP") is True

    genuine_ids = set(portfolio.genuine_projects_df["project_id"].values)
    assert "180100210" in genuine_ids
    assert "220100133" in genuine_ids
    assert "020100040" in genuine_ids


def test_3_legitimate_large_projects_retained(portfolio):
    """3. Test legitimate large infrastructure projects (> 50,000 Cr) are not removed solely by cost."""
    active_ids = set(portfolio.active_projects_df["project_id"].values)

    # Bullet Train (₹1,08,000 Cr)
    assert "N22000463" in active_ids
    bullet_row = portfolio.active_projects_df[portfolio.active_projects_df["project_id"] == "N22000463"].iloc[0]
    assert bullet_row["baseline_cost"] == 108000.0

    # Rajasthan Refinery (₹72,937 Cr)
    assert "N16000513" in active_ids
    refinery_row = portfolio.active_projects_df[portfolio.active_projects_df["project_id"] == "N16000513"].iloc[0]
    assert refinery_row["baseline_cost"] == 72937.0

    # Polavaram Irrigation (₹55,548.87 Cr)
    assert "N30000002" in active_ids

    # Western Dedicated Freight Corridor (₹51,101 Cr)
    assert "N22000464" in active_ids


def test_4_historical_projects_excluded_from_active_portfolio(portfolio):
    """4. Test historical projects (< 2024-01) are excluded from active portfolio."""
    # All active projects must have latest observation >= 2024-01
    min_active_month = portfolio.active_projects_df["reporting_month"].min()
    assert min_active_month >= "2024-01"

    # All historical projects must have latest observation < 2024-01
    max_hist_month = portfolio.historical_projects_df["reporting_month"].max()
    assert max_hist_month < "2024-01"

    # Disjoint intersection
    active_set = set(portfolio.active_projects_df["project_id"])
    hist_set = set(portfolio.historical_projects_df["project_id"])
    assert len(active_set.intersection(hist_set)) == 0


def test_5_risk_counts_use_active_genuine_projects_only(portfolio):
    """5. Test risk counts use active genuine projects only and match operational thresholds."""
    total_active = portfolio.active_project_count
    tier_sum = (
        portfolio.watch_count +
        portfolio.review_count +
        portfolio.escalate_count +
        portfolio.normal_count
    )
    assert tier_sum == total_active

    # Check that thresholds are respected
    for _, row in portfolio.active_projects_df.iterrows():
        p = row["latest_risk"]
        tier = row["risk_tier"]
        if p >= 0.50:
            assert tier == "ESCALATE"
        elif p >= 0.45:
            assert tier == "REVIEW"
        elif p >= 0.40:
            assert tier == "WATCH"
        else:
            assert tier == "NORMAL"


def test_6_exposure_uses_latest_observation_only(portfolio):
    """6. Test exposure calculation sums only latest valid C_base of active projects."""
    expected_sum = round(float(portfolio.active_projects_df["baseline_cost"].sum()), 2)
    assert round(portfolio.active_baseline_exposure, 2) == expected_sum

    # Must be authentic central sector scale (~38 Lakh Cr), not corrupted 189 Lakh Cr
    assert 3500000.0 <= portfolio.active_baseline_exposure <= 4200000.0


def test_7_risk_weighted_exposure_calculation(portfolio):
    """7. Test risk-weighted exposure equals calibrated_risk * baseline_cost."""
    for _, row in portfolio.active_projects_df.head(50).iterrows():
        expected_rwe = round(row["latest_risk"] * row["baseline_cost"], 2)
        assert abs(row["risk_weighted_exposure"] - expected_rwe) <= 0.05

    # Check format helper
    assert format_inr_currency(500.0) == "₹500.0 Cr"
    assert format_inr_currency(35000.0) == "₹35,000 Cr"
    assert format_inr_currency(108000.0) == "₹1.08 Lakh Cr"


def test_8_no_duplicate_project_ids_in_active_portfolio(portfolio):
    """8. Test no duplicate project IDs remain in active portfolio."""
    assert portfolio.active_projects_df["project_id"].is_unique is True
    assert len(portfolio.active_projects_df) == portfolio.active_projects_df["project_id"].nunique()


def test_9_api_dashboard_equals_portfolio_layer(client, portfolio):
    """9. Test API dashboard endpoint values exactly equal portfolio layer values."""
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()

    assert data["active_project_count"] == portfolio.active_project_count
    assert data["archive_entity_count"] == portfolio.total_archive_entities
    assert data["latest_data_month"] == portfolio.latest_data_month
    assert abs(data["active_baseline_exposure"] - portfolio.active_baseline_exposure) < 0.01
    assert abs(data["risk_weighted_exposure"] - portfolio.risk_weighted_exposure) < 0.01
    assert data["watch_count"] == portfolio.watch_count
    assert data["review_count"] == portfolio.review_count
    assert data["escalate_count"] == portfolio.escalate_count
    assert data["normal_count"] == portfolio.normal_count
    assert data["historical_median_warning_lead"] == portfolio.historical_median_warning_lead


def test_10_existing_replay_inference_behavior_unchanged(portfolio):
    """10. Test existing point-in-time replay and inference behavior remains unchanged."""
    pid = "180100210"
    rep = get_project_replay(pid, dataset_path=portfolio.dataset_path, engine=portfolio.engine)

    assert rep["project_id"] == pid
    assert len(rep["timeline"]) > 0
    assert rep["approved_cost"] == 5366.0
    assert rep["lead_time"] == 20
    assert rep["first_alert"]["alert_month"] == "2013-06"
    assert rep["first_alert"]["risk_tier"] == "WATCH"


def test_11_zero_synthetic_prj_in_active_portfolio_and_endpoints(client, portfolio):
    """11. Test zero synthetic PRJ_* entities exist in active portfolio or API responses."""
    # Active dataframe
    assert not any(pid.startswith("PRJ_") for pid in portfolio.active_projects_df["project_id"])

    # API projects
    r_proj = client.get("/api/projects?limit=50")
    assert r_proj.status_code == 200
    for p in r_proj.json()["projects"]:
        assert not p["project_id"].startswith("PRJ_")

    # API interventions
    r_intv = client.get("/api/dashboard/interventions?limit=50")
    assert r_intv.status_code == 200
    for p in r_intv.json()["projects"]:
        assert not p["project_id"].startswith("PRJ_")
        assert p["baseline_cost"] > 0


def test_12_mega_projects_integrity_and_concentration(portfolio):
    """12. Test mega-projects (>= 25,000 Cr) integrity and portfolio concentration."""
    mega = portfolio.active_projects_df[portfolio.active_projects_df["baseline_cost"] >= 25000]
    assert len(mega) == 23

    # Ensure all 23 have non-null sectors and positive C_base
    for _, r in mega.iterrows():
        assert r["sector_display"] != ""
        assert r["baseline_cost"] >= 25000.0

    # Top 1% projects (23 projects) concentration between 20% and 30%
    total_exp = portfolio.active_baseline_exposure
    top1pct_exp = portfolio.active_projects_df.sort_values("baseline_cost", ascending=False).head(23)["baseline_cost"].sum()
    share = top1pct_exp / total_exp
    assert 0.20 <= share <= 0.30

