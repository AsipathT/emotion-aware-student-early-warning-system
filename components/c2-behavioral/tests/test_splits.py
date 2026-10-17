"""
Unit tests for presentation-temporal dataset splitting and student deduplication.
"""

import pandas as pd
from src.splits import make_splits, split_report


def test_split_disjointness_and_presentation_boundaries():
    """no id_student in more than one of train/val/test;
    test contains only 2014J; val only 2014B; train only 2013B/2013J."""
    df = pd.DataFrame(
        {
            "code_module": ["AAA"] * 6,
            "code_presentation": ["2013B", "2013J", "2014B", "2014B", "2014J", "2014J"],
            "id_student": [101, 102, 103, 104, 105, 106],
            "week": [3, 4, 3, 5, 4, 6],
            "label": ["stable"] * 6,
        }
    )

    splits = make_splits(df)
    train = splits["train"]
    val = splits["val"]
    test = splits["test"]

    # Check presentations
    assert set(train["code_presentation"]).issubset({"2013B", "2013J"})
    assert set(val["code_presentation"]).issubset({"2014B"})
    assert set(test["code_presentation"]).issubset({"2014J"})

    # Check student disjointness
    train_students = set(train["id_student"])
    val_students = set(val["id_student"])
    test_students = set(test["id_student"])

    assert train_students.isdisjoint(val_students)
    assert train_students.isdisjoint(test_students)
    assert val_students.isdisjoint(test_students)


def test_student_overlap_rules():
    """a student present in 2013J and 2014B appears in train only;
    a student in 2014B and 2014J appears in val only."""
    df = pd.DataFrame(
        {
            "code_module": ["AAA"] * 6,
            "code_presentation": [
                "2013J",  # student 1 in 2013J (train)
                "2014B",  # student 1 also in 2014B (must be excluded from val)
                "2014B",  # student 2 in 2014B (val)
                "2014J",  # student 2 also in 2014J (must be excluded from test)
                "2014J",  # student 3 in 2014J only (test)
                "2013B",  # student 4 in 2013B (train)
            ],
            "id_student": [1, 1, 2, 2, 3, 4],
            "week": [3, 3, 4, 4, 5, 5],
            "label": ["stable"] * 6,
        }
    )

    splits = make_splits(df)
    train = splits["train"]
    val = splits["val"]
    test = splits["test"]

    # Student 1 in train only
    assert 1 in set(train["id_student"])
    assert 1 not in set(val["id_student"])
    assert 1 not in set(test["id_student"])

    # Student 2 in val only
    assert 2 not in set(train["id_student"])
    assert 2 in set(val["id_student"])
    assert 2 not in set(test["id_student"])

    # Student 3 in test only
    assert 3 in set(test["id_student"])

    # Check split report removed counts
    rep = split_report(df, splits)
    assert rep["removed_val"] == 1  # Student 1 row in 2014B removed
    assert rep["removed_test"] == 1  # Student 2 row in 2014J removed
