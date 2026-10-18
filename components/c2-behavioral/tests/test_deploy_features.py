"""
Unit tests for deployment feature transformations.
"""

import numpy as np
import pandas as pd
import pytest

from src.deploy_features import DEPLOY_FEATURES, to_deploy


def test_deploy_features_calculation():
    """c_lag1 equals e_lag1 - e_mean6 on a hand-made row;
    only DEPLOY_FEATURES columns + passthrough columns are produced;
    NaN lag stays NaN."""
    df = pd.DataFrame(
        {
            "code_module": ["AAA"],
            "code_presentation": ["2013J"],
            "id_student": [1001],
            "week": [3],
            "label": ["stable"],
            "e_lag0": [3.0],
            "e_lag1": [2.0],
            "e_lag2": [1.0],
            "e_lag3": [0.0],
            "e_lag4": [np.nan],
            "e_lag5": [np.nan],
            "e_mean6": [1.5],
            "e_sd6": [0.5],
            "e_slope4": [0.2],
            "e_recent_diff": [0.1],
            "zero_weeks6": [1],
            "zero_run": [0],
            "ad_lag0": [1.0],  # Should be dropped
            "ad_mean3": [1.0],  # Should be dropped
            "subs_sum6": [2.0],
            "delay_mean6": [5.0],
            "week_t": [3],
        }
    )

    deployed = to_deploy(df)

    # 1. c_lag1 == e_lag1 - e_mean6
    assert deployed.iloc[0]["c_lag1"] == pytest.approx(2.0 - 1.5)

    # 2. NaN lag stays NaN
    assert np.isnan(deployed.iloc[0]["c_lag4"])
    assert np.isnan(deployed.iloc[0]["c_lag5"])

    # 3. Only passthrough + DEPLOY_FEATURES columns produced
    expected_cols = ["code_module", "code_presentation", "id_student", "week", "label"] + DEPLOY_FEATURES
    assert list(deployed.columns) == expected_cols
    assert "ad_lag0" not in deployed.columns
    assert "ad_mean3" not in deployed.columns
    assert "e_lag0" not in deployed.columns
