import pytest
from tradingview_scraper.utils.candidates import normalize_candidate_record


def test_direction_preservation():
    """Test that direction field is preserved and normalized."""

    # Case 1: Explicit LONG
    raw_long = {"symbol": "BINANCE:BTCUSDT", "direction": "LONG", "metadata": {"foo": "bar"}}
    norm_long = normalize_candidate_record(raw_long, strict=True)
    assert norm_long["direction"] == "LONG"

    # Case 2: Explicit SHORT (lowercase input)
    raw_short = {"symbol": "BINANCE:BTCUSDT", "direction": "short", "metadata": {"foo": "bar"}}
    norm_short = normalize_candidate_record(raw_short, strict=True)
    assert norm_short["direction"] == "SHORT"

    # Case 3: Missing direction (defaults to LONG if not present? Or None?)
    # Currently code defaults to None for optional fields not in the return dict,
    # but we want to ENFORCE it or default it.
    # Let's check current behavior first - likely missing from output.
    raw_none = {"symbol": "BINANCE:BTCUSDT", "metadata": {"foo": "bar"}}
    norm_none = normalize_candidate_record(raw_none, strict=True)
    # Ideally should be LONG default or preserved as None
    # Based on requirements, we want it to be part of the schema.


def test_direction_in_metadata_priority():
    """Test that top-level direction takes precedence over metadata."""
    raw = {"symbol": "BINANCE:BTCUSDT", "direction": "SHORT", "metadata": {"direction": "LONG"}}
    norm = normalize_candidate_record(raw, strict=True)
    assert norm["direction"] == "SHORT"
    # Metadata should preserve original if needed, but top-level is canonical
