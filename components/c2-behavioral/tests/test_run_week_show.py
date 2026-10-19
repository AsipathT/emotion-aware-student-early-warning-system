"""
Unit tests for format_show_table helper in scripts/run_week.py.
Verifies header presence, row count, compact clicks rendering, and indicator joining.
"""

from scripts.run_week import format_show_table


def test_header_present():
    """Verify that a standard table header and separator are present."""
    table = format_show_table([])
    lines = [line.strip() for line in table.splitlines() if line.strip()]
    assert len(lines) >= 1
    header = lines[0]
    assert "pid_suffix" in header
    assert "clicks_last_6w" in header
    assert "trajectory_label" in header
    assert "confidence" in header
    assert "indicators" in header


def test_one_line_per_row():
    """Verify that each input dictionary produces exactly one corresponding output data line."""
    sample_rows = [
        {
            "pid": "STU_1111aaaa",
            "clicks": [10, 8, 6, 4, 2, 0],
            "trajectory_label": "declining",
            "confidence": 0.88,
            "indicators": ["drop_clicks_w5"],
        },
        {
            "pid": "STU_2222bbbb",
            "clicks": [5, 6, 7, 8, 9, 10],
            "trajectory_label": "improving",
            "confidence": 0.75,
            "indicators": ["rise_clicks_w5"],
        },
        {
            "pid": "STU_3333cccc",
            "clicks": [20, 22, 19, 21, 20, 20],
            "trajectory_label": "stable",
            "confidence": 0.92,
            "indicators": ["steady_engagement"],
        },
    ]

    table = format_show_table(sample_rows)
    lines = [line.strip() for line in table.splitlines() if line.strip()]
    # Expected: 1 header + 1 separator + 3 data rows = 5 lines total
    assert len(lines) == 5
    data_lines = lines[2:]
    assert len(data_lines) == len(sample_rows)
    assert data_lines[0].startswith("aaaa")
    assert data_lines[1].startswith("bbbb")
    assert data_lines[2].startswith("cccc")


def test_clicks_list_rendered():
    """Verify that clicks list is rendered as a compact comma-separated string."""
    sample_rows = [
        {
            "pid": "STU_99991234",
            "clicks": [12, 9, 7, 3, 0, 0],
            "trajectory_label": "declining",
            "confidence": 0.86,
            "indicators": ["drop_clicks"],
        }
    ]
    table = format_show_table(sample_rows)
    assert "12,9,7,3,0,0" in table


def test_indicators_joined():
    """Verify that multiple contributing indicators are joined by commas without extra spaces."""
    sample_rows = [
        {
            "pid": "STU_0000wxyz",
            "clicks": [15, 12, 8, 4, 1, 0],
            "trajectory_label": "declining",
            "confidence": 0.89,
            "indicators": ["drop_clicks_w5", "late_submission", "causal_dormancy"],
        }
    ]
    table = format_show_table(sample_rows)
    assert "drop_clicks_w5,late_submission,causal_dormancy" in table


def test_pid_suffix_and_confidence():
    """Verify that pid is truncated to last 4 chars and confidence rounded to 2 decimals."""
    sample_rows = [
        {
            "pid": "STU_fedcba98",
            "clicks": [0, 0, 0, 0, 0, 0],
            "trajectory_label": "declining",
            "confidence": 0.8567,
            "indicators": ["no_activity_7w"],
        }
    ]
    table = format_show_table(sample_rows)
    assert "ba98" in table
    assert "0.86" in table
