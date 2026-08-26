import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from script import auto_db


def test_normalize_page_range_returns_zero_when_missing():
    assert auto_db.normalize_page_range(None) == 0


def test_normalize_page_range_uses_floor_for_invalid_values():
    assert auto_db.normalize_page_range('abc') == 0
    assert auto_db.normalize_page_range(-5) == 0
