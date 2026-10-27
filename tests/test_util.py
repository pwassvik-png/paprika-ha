"""Unit tests for Paprika util helpers."""

from datetime import datetime

from homeassistant.util import dt as dt_util

from custom_components.paprika.util import parse_meal_datetime


def test_parse_meal_datetime_valid():
    """Parse valid Paprika timestamp."""
    result = parse_meal_datetime("2025-11-06 18:30:00")
    assert result is not None
    assert result.tzinfo == dt_util.DEFAULT_TIME_ZONE
    assert result.year == 2025
    assert result.hour == 18
    assert result.minute == 30


def test_parse_meal_datetime_invalid():
    """Invalid strings should return None."""
    assert parse_meal_datetime("") is None
    assert parse_meal_datetime("invalid") is None
    assert parse_meal_datetime(None) is None
