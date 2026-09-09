"""
tests/test_backtest.py

Unit tests for walk-forward validation structure:
- Strictly non-overlapping chronological boundaries
- Train < Val < Test ordering
- Verification that expanding window preserves history
"""

import pytest
import yaml
from sanket.model import load_model_config

def test_walk_forward_fold_configurations():
    config = load_model_config("configs/model.yaml")
    folds = config["walk_forward_folds"]

    assert len(folds) >= 2

    for fold in folds:
        t_end = fold["train_end_month"]
        v_start = fold["val_start_month"]
        v_end = fold["val_end_month"]
        test_start = fold["test_start_month"]
        test_end = fold["test_end_month"]

        # 1. Train must strictly precede Val
        assert t_end < v_start, f"Fold {fold['fold_id']}: Train end ({t_end}) not strictly before Val start ({v_start})"

        # 2. Val start <= Val end
        assert v_start <= v_end, f"Fold {fold['fold_id']}: Val start ({v_start}) > Val end ({v_end})"

        # 3. Val end must strictly precede Test start
        assert v_end < test_start, f"Fold {fold['fold_id']}: Val end ({v_end}) not strictly before Test start ({test_start})"

        # 4. Test start <= Test end
        assert test_start <= test_end, f"Fold {fold['fold_id']}: Test start ({test_start}) > Test end ({test_end})"

def test_expanding_window_progression():
    config = load_model_config("configs/model.yaml")
    folds = config["walk_forward_folds"]

    # In expanding window, train_end of fold k+1 must be greater than or equal to test_end of fold k
    for k in range(len(folds) - 1):
        f_curr = folds[k]
        f_next = folds[k + 1]
        assert f_next["train_end_month"] >= f_curr["test_end_month"], \
            f"Fold {f_next['fold_id']} train window does not expand past fold {f_curr['fold_id']} test window!"
