"""
Unit tests for enrolment table construction and censoring logic.
"""

import numpy as np
import pandas as pd
import pytest

from src.enrolment import build_enrolment_table


def _make_sample_frames(
    final_result: str,
    date_unregistration: float,
    module_presentation_length: int = 269,
    code_module: str = "AAA",
    code_presentation: str = "2013J",
    id_student: int = 1001,
):
    info = pd.DataFrame([{
        "code_module": code_module,
        "code_presentation": code_presentation,
        "id_student": id_student,
        "final_result": final_result,
    }])
    reg = pd.DataFrame([{
        "code_module": code_module,
        "code_presentation": code_presentation,
        "id_student": id_student,
        "date_unregistration": date_unregistration,
    }])
    courses = pd.DataFrame([{
        "code_module": code_module,
        "code_presentation": code_presentation,
        "module_presentation_length": module_presentation_length,
    }])
    return info, reg, courses


def test_withdrawn_valid_unregistration():
    info, reg, courses = _make_sample_frames(
        final_result="Withdrawn",
        date_unregistration=30.0,
        module_presentation_length=269,
    )
    res = build_enrolment_table(info, reg, courses)
    assert len(res) == 1
    row = res.iloc[0]
    assert row["last_week"] == 38
    assert row["end_week"] == 4
    assert row["excluded"] == False
    assert row["exclude_reason"] == ""


def test_withdrawn_clipped_to_last_week():
    info, reg, courses = _make_sample_frames(
        final_result="Withdrawn",
        date_unregistration=444.0,
        module_presentation_length=269,
    )
    res = build_enrolment_table(info, reg, courses)
    row = res.iloc[0]
    assert row["last_week"] == 38
    assert row["end_week"] == 38
    assert row["excluded"] == False
    assert row["exclude_reason"] == ""


def test_withdrawn_missing_unregistration_date():
    info, reg, courses = _make_sample_frames(
        final_result="Withdrawn",
        date_unregistration=np.nan,
        module_presentation_length=269,
    )
    res = build_enrolment_table(info, reg, courses)
    row = res.iloc[0]
    assert row["excluded"] == True
    assert row["exclude_reason"] == "withdrawn_no_unreg_date"
    assert row["end_week"] == -1


def test_withdrawn_negative_unregistration_date():
    info, reg, courses = _make_sample_frames(
        final_result="Withdrawn",
        date_unregistration=-5.0,
        module_presentation_length=269,
    )
    res = build_enrolment_table(info, reg, courses)
    row = res.iloc[0]
    assert row["excluded"] == True
    assert row["exclude_reason"] == "unreg_before_start"
    assert row["end_week"] == -1


def test_pass_with_nan_or_negative_unregistration():
    # Pass with NaN date -> end_week = last_week, excluded False
    info1, reg1, courses1 = _make_sample_frames(
        final_result="Pass",
        date_unregistration=np.nan,
        module_presentation_length=269,
    )
    res1 = build_enrolment_table(info1, reg1, courses1)
    row1 = res1.iloc[0]
    assert row1["last_week"] == 38
    assert row1["end_week"] == 38
    assert row1["excluded"] == False
    assert row1["exclude_reason"] == ""

    # Pass with negative date -> still end_week = last_week, excluded False
    info2, reg2, courses2 = _make_sample_frames(
        final_result="Pass",
        date_unregistration=-3.0,
        module_presentation_length=269,
    )
    res2 = build_enrolment_table(info2, reg2, courses2)
    row2 = res2.iloc[0]
    assert row2["last_week"] == 38
    assert row2["end_week"] == 38
    assert row2["excluded"] == False
    assert row2["exclude_reason"] == ""
