# Tests for utility functions like parse_date_string in backend.pipeline
import pytest
from datetime import date
from backend.pipeline import parse_date_string

# Parametrized test for valid date strings
@pytest.mark.parametrize(
    "input_str, expected_date",
    [
        ("2023-01-15", date(2023, 1, 15)),
        ("2023-01-15 ", date(2023, 1, 15)), # With trailing space
        (" 2023-01-15", date(2023, 1, 15)), # With leading space
        (" 2023-01-15 ", date(2023, 1, 15)),# With leading/trailing spaces
        ("2023-01", date(2023, 1, 1)),
        ("2023-1", date(2023, 1, 1)), # Slightly different format for YYYY-M
        ("Jan 2023", date(2023, 1, 1)),
        ("January 2023", date(2023, 1, 1)),
        ("Feb 2023", date(2023, 2, 1)),
        ("Mar 2023", date(2023, 3, 1)),
        ("Apr 2023", date(2023, 4, 1)),
        ("May 2023", date(2023, 5, 1)),
        ("Jun 2023", date(2023, 6, 1)),
        ("Jul 2023", date(2023, 7, 1)),
        ("Aug 2023", date(2023, 8, 1)),
        ("Sep 2023", date(2023, 9, 1)),
        ("Oct 2023", date(2023, 10, 1)),
        ("Nov 2023", date(2023, 11, 1)),
        ("Dec 2023", date(2023, 12, 1)),
        ("2023", date(2023, 1, 1)),
        (" 2023 ", date(2023, 1, 1)), # With spaces
    ],
)
def test_parse_date_string_valid(input_str, expected_date):
    """Tests parse_date_string with various valid date formats."""
    assert parse_date_string(input_str) == expected_date

# Parametrized test for inputs that should result in None
@pytest.mark.parametrize(
    "input_str",
    [
        "Present",
        "present",
        " PRESENT ",
        "",
        None,
    ],
)
def test_parse_date_string_none_outputs(input_str):
    """Tests inputs that should correctly return None (e.g., 'Present', empty string, None)."""
    assert parse_date_string(input_str) is None

# Parametrized test for invalid date strings (should also result in None)
@pytest.mark.parametrize(
    "invalid_input_str",
    [
        "abc",
        "Not a date",
        "2023/01/01", # Uses slashes instead of hyphens
        "15-01-2023", # DD-MM-YYYY format
        "01/2023",    # MM/YYYY
        "Jan-2023",   # Mon-YYYY
        "2023 Jan",   # YYYY Mon
        "23-01-15",   # YY-MM-DD
        "20230115",   # No separators
        "January 1st, 2023", # More complex format
    ],
)
def test_parse_date_string_invalid(invalid_input_str, capsys):
    """
    Tests invalid date strings. Expects None as output.
    Also checks if a warning is printed to stdout/stderr (though this is a basic check).
    """
    assert parse_date_string(invalid_input_str) is None
    # Check if a warning was printed (optional, basic check)
    # This part of the test might be fragile if warning messages change.
    # For this subtask, the primary goal is to check the return value.
    # The `parse_date_string` function in pipeline.py uses `print()` for warnings.
    captured = capsys.readouterr()
    if invalid_input_str and invalid_input_str.strip(): # Only expect warning for non-empty, non-None invalid strings
        assert "Warning: Could not parse date string:" in captured.out or \
               "Warning: Could not parse date string:" in captured.err # Check both stdout and stderr
    else:
        # For empty string or None, no warning is expected by current implementation
        assert "Warning: Could not parse date string:" not in captured.out and \
               "Warning: Could not parse date string:" not in captured.err


def test_parse_date_string_specific_edge_cases():
    """Test specific edge cases or tricky inputs."""
    assert parse_date_string("2024-02-30") is None # Invalid day for Feb
    # Test with capsys to check warning for the invalid day
    # Note: the current implementation of parse_date_string might not catch this specific
    # invalid date (e.g. "2024-02-30") before datetime.strptime does, which would raise ValueError
    # and then caught by the broad try-except, leading to a None return and a generic warning.
    # A more specific test might require changes to parse_date_string itself if more granular
    # validation is needed before strptime. For now, we confirm it returns None.

    # Test month parsing robustness if applicable, e.g. "Sept 2023" vs "Sep 2023"
    # Current implementation uses %b (locale's abbreviated month) and %B (locale's full month name)
    # So, "Sept" might fail if locale's abbreviation is "Sep".
    # This is fine, as long as it's consistent.
    # Example: Assuming standard English locale for %b
    assert parse_date_string("Sept 2023") is None # if "Sept" is not the locale's %b for September
    assert parse_date_string("Sep 2023") == date(2023, 9, 1) # Standard abbreviation
    assert parse_date_string("September 2023") == date(2023, 9, 1) # Full name

def test_parse_date_string_yyyy_mm_without_day_leading_zero():
    """Test YYYY-M format (e.g. 2023-1 for Jan 2023)"""
    # This is implicitly covered by "2023-1" in the parametrized valid tests,
    # but can be made explicit if needed.
    # The strptime format "%Y-%m" should handle "2023-1" if the underlying C library's strptime does.
    # Python's datetime.strptime is usually robust here.
    # If it were an issue, the test "2023-1" would fail in test_parse_date_string_valid.
    # Let's re-affirm one case here for clarity.
    assert parse_date_string("2023-3") == date(2023, 3, 1)
    assert parse_date_string("2023-12") == date(2023, 12, 1)

# Consider adding tests for different locales if the function is expected
# to handle them, though %b and %B are locale-dependent.
# For this project, assuming a consistent (e.g., English-like) locale for tests.
