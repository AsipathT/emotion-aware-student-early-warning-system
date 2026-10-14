"""
backend/tests/test_feature5_privacy.py

Feature 5: Pseudonymization, PII Scrubbing, and Privacy Regression Test Suite.
Validates:
  - Deterministic HMAC-SHA256 pseudonym generation (STU_<8 hex chars>)
  - PID format validation
  - get_nlp() resilience (no spacy.cli shadowing, safe None return when unavailable)
  - scrub_text() regex-only fallback when spaCy or model is unavailable
  - scrub_text() resilience when spaCy NER raises an unexpected exception
  - Multi-stage redaction (Email, URL, Registration ID, Phone, Known Names)
"""

from unittest.mock import patch
import pytest

from app.core import privacy
from app.core.privacy import (
    get_nlp,
    is_valid_pid,
    pseudonymize,
    scrub_text,
)


def test_pseudonymize_deterministic_and_valid():
    student_id = "IT20210001"
    pid1 = pseudonymize(student_id)
    pid2 = pseudonymize(student_id)

    # Determinism
    assert pid1 == pid2
    # Format: STU_ + 8 hex characters
    assert is_valid_pid(pid1)
    assert pid1.startswith("STU_")
    assert len(pid1) == 12

    # Different student IDs produce different PIDs
    assert pseudonymize("IT20210001") != pseudonymize("IT20210002")


def test_is_valid_pid():
    assert is_valid_pid("STU_1a2b3c4d") is True
    assert is_valid_pid("STU_A1B2C3D4") is True
    assert is_valid_pid("STU_12345678") is True

    # Invalid cases
    assert is_valid_pid("") is False
    assert is_valid_pid(None) is False
    assert is_valid_pid("STU_1a2b3c") is False  # Too short
    assert is_valid_pid("STU_1a2b3c4d5e") is False  # Too long
    assert is_valid_pid("STU_1a2b3c4g") is False  # Non-hex 'g'
    assert is_valid_pid("STUDENT_1a2b3c4d") is False
    assert is_valid_pid("1a2b3c4d") is False


def test_get_nlp_returns_none_when_spacy_unavailable():
    """Verifies get_nlp returns None without attempting spacy.cli import or downloads."""
    with patch("app.core.privacy.spacy", None):
        with patch("app.core.privacy._nlp", None):
            nlp = get_nlp()
            assert nlp is None


def test_get_nlp_handles_load_failure_gracefully():
    """Verifies get_nlp returns None when spacy.load fails, without invoking spacy.cli."""
    class FakeSpacy:
        @staticmethod
        def load(name):
            raise OSError("Model not installed")

    with patch("app.core.privacy.spacy", FakeSpacy):
        with patch("app.core.privacy._nlp", None):
            nlp = get_nlp()
            assert nlp is None


def test_scrub_text_regex_only_fallback_without_spacy():
    """
    Verifies scrub_text() performs complete PII redaction using regex rules
    even when spaCy is completely unavailable.
    """
    with patch("app.core.privacy.get_nlp", return_value=None):
        raw_text = (
            "Hello, my name is Alice Smith. My student ID is IT20184422. "
            "Please email me at alice.smith@my.sliit.lk or call +94 77 123 4567. "
            "Visit my portfolio at https://alice.dev/work for details."
        )

        clean_text, report = scrub_text(raw_text, known_names=["Alice Smith"])

        # Check regex redactions
        assert "[NAME]" in clean_text
        assert "Alice Smith" not in clean_text
        assert "[REG_ID]" in clean_text
        assert "IT20184422" not in clean_text
        assert "[EMAIL]" in clean_text
        assert "alice.smith@my.sliit.lk" not in clean_text
        assert "[PHONE]" in clean_text
        assert "+94 77 123 4567" not in clean_text
        assert "[URL]" in clean_text
        assert "https://alice.dev/work" not in clean_text

        # Verify report counts
        assert report["NAME"] == 1
        assert report["REG_ID"] == 1
        assert report["EMAIL"] == 1
        assert report["PHONE"] == 1
        assert report["URL"] == 1


def test_scrub_text_exception_resilience():
    """Verifies scrub_text() does not crash if spaCy raises an exception during parsing."""
    class CrashingNlp:
        def __call__(self, text):
            raise RuntimeError("Unexpected spaCy parser crash")

    with patch("app.core.privacy.get_nlp", return_value=CrashingNlp()):
        raw_text = "Contact support at help@lms.edu immediately."
        clean_text, report = scrub_text(raw_text)

        assert clean_text == "Contact support at [EMAIL] immediately."
        assert report["EMAIL"] == 1


def test_scrub_text_empty_and_whitespace():
    clean_text, report = scrub_text("")
    assert clean_text == ""
    assert all(count == 0 for count in report.values())
