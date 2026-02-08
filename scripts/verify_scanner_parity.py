#!/usr/bin/env python3
"""
Verify behavior of FuturesUniverseSelector vectorized logic.
Tests fuzzy tie-breaking, regex parsing, and filtering.
"""

import logging
import sys
from typing import Any
import pandas as pd
import numpy as np

# Adjust path to import tradingview_scraper
import os

sys.path.append(os.getcwd())

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, SelectorConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_test(name: str, config_overrides: dict[str, Any], raw_data: list[dict[str, Any]], assertions: callable):
    """Run a test case."""
    logger.info(f"--- Running Test: {name} ---")

    # Create config
    # defaults
    cfg_dict = {
        "markets": ["futures"],
        "exchanges": [],
        "sort_by": "volume",
        "sort_order": "desc",
        "limit": 100,
        "volume": {"min": 0},
        "volatility": {},
        # Disable all trend checks by default
        "trend": {
            "recommendation": {"enabled": False},
            "adx": {"enabled": False},
            "momentum": {"enabled": False},
            "confirmation_momentum": {"enabled": False},
        },
        "quote_priority": ["USDT", "USDC", "USD"],
        "perp_exchange_priority": ["BINANCE", "OKX", "BYBIT"],
    }
    cfg_dict.update(config_overrides)

    config = SelectorConfig.model_validate(cfg_dict)
    selector = FuturesUniverseSelector(config=config)

    # Process data
    result = selector.process_data(raw_data)
    data = result["data"]

    try:
        assertions(data)
        logger.info(f"PASS: {name}")
    except AssertionError as e:
        logger.error(f"FAIL: {name} - {e}")
        # Print data for debugging
        import json

        logger.error(f"Result Data: {json.dumps(data, indent=2, default=str)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"ERROR: {name} - {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def test_regex_parsing():
    """Test Case 3: 1000-Prefix and Exotic Symbol Parsing."""

    raw_data = [
        {"symbol": "BINANCE:1000PEPEUSDT", "close": 0.001, "volume": 1000, "Value.Traded": 1000, "type": "futures"},
        {"symbol": "BINANCE:DOGEUSDT.P", "close": 0.1, "volume": 2000, "Value.Traded": 2000, "type": "futures"},
        {"symbol": "BYBIT:BTCUSD_250328", "close": 50000, "volume": 500, "Value.Traded": 500, "type": "futures"},  # Dated
        {"symbol": "BINANCE:ETHUSDT", "close": 3000, "volume": 3000, "Value.Traded": 3000, "type": "futures"},
    ]

    def assertions(data):
        # Check base extraction (this logic happens inside process_data -> _extract_base_quote_vectorized)
        # But process_data aggregates by base, so we check if they survived and under what identity.

        # 1000PEPEUSDT -> Base PEPE
        pepe = next((r for r in data if "PEPE" in r["symbol"]), None)
        assert pepe is not None, "PEPE should be present"
        # The selector dedupes by base.
        # We can't easily check the internal 'base' column unless we modify the class or inspect logs.
        # But we can check that it didn't get dropped or misidentified.

        # DOGEUSDT.P -> Base DOGE
        doge = next((r for r in data if "DOGE" in r["symbol"]), None)
        assert doge is not None, "DOGE should be present"

        # BTCUSD_250328 -> Base BTC
        # Dated futures often have different base parsing.
        # _extract_base_quote_vectorized:
        # core = BTCUSD_250328 -> strip dated -> BTCUSD -> base BTC, quote USD.
        btc = next((r for r in data if "BTC" in r["symbol"]), None)
        assert btc is not None, "BTC should be present"

        # Verify count
        assert len(data) == 4, f"Expected 4 items, got {len(data)}"

    run_test("Regex Parsing", {}, raw_data, assertions)


def test_fuzzy_quote_tie_breaker():
    """Test Case 1: Fuzzy Quote Tie-Breaker."""
    # Scenario: USDT is priority #0, USD is #2.
    # Case A: USDT (1000 vol) vs USD (900 vol). USDT should win clearly.
    # Case B: USDT (100 vol) vs USD (1000 vol). USD should win (Liquidity dominance).
    # Logic: Prefer candidate (USDT) if liq > current * 0.3.
    # Logic: Prefer current (USD) if best > candidate * 0.3.

    # Case A
    raw_a = [
        {"symbol": "BINANCE:BTCUSDT", "volume": 1000, "Value.Traded": 1000, "type": "futures"},
        {"symbol": "BINANCE:BTCUSD", "volume": 900, "Value.Traded": 900, "type": "futures"},
    ]

    def assert_a(data):
        assert len(data) == 1
        assert data[0]["symbol"] == "BINANCE:BTCUSDT", "USDT should win (better quote, similar vol)"

    run_test("Fuzzy Quote A (USDT wins)", {}, raw_a, assert_a)

    # Case B
    raw_b = [
        {"symbol": "BINANCE:BTCUSDT", "volume": 100, "Value.Traded": 100, "type": "futures"},
        {"symbol": "BINANCE:BTCUSD", "volume": 1000, "Value.Traded": 1000, "type": "futures"},
    ]

    def assert_b(data):
        assert len(data) == 1
        # USDT is candidate. USD is best (if sorted by vol descending).
        # Wait, process_data sorts by 'sort_by' (volume) inside _aggregate_by_base logic?
        # _aggregate_by_base iterates through rows.
        # If we pass raw_data, order matters if not sorted.
        # But FuturesUniverseSelector doesn't sort BEFORE aggregation?
        # It iterates rows.
        # If we pass [USDT(100), USD(1000)], first is USDT. Best=USDT.
        # Next is USD. USD vs USDT.
        # USD quote rank (2) > USDT quote rank (0).
        # So USD is "worse" quote.
        # Logic: "Prefer current (USDT) if best_value (100) > candidate_value (1000) * 0.3".
        # 100 > 300 -> False.
        # So it does NOT prefer current.
        # It falls through.
        # "Tie-break by Value.Traded" (or sort field).
        # Candidate (1000) > Best (100).
        # So USD should replace USDT.

        assert data[0]["symbol"] == "BINANCE:BTCUSD", "USD should win (massive liquidity advantage)"

    run_test("Fuzzy Quote B (USD wins by liq)", {}, raw_b, assert_b)


def test_fuzzy_exchange_tie_breaker():
    """Test Case 2: Fuzzy Exchange Tie-Breaker."""
    # Priority: BINANCE, OKX

    # Case A: BINANCE (100) vs OKX (90). BINANCE wins (better rank + sim liq).
    raw_a = [
        {"symbol": "OKX:BTCUSDT", "volume": 90, "Value.Traded": 90, "type": "futures"},
        {"symbol": "BINANCE:BTCUSDT", "volume": 100, "Value.Traded": 100, "type": "futures"},
    ]
    # Note: input order might matter if logic isn't robust.
    # If OKX comes first. Best=OKX.
    # BINANCE comes. Rank BINANCE (0) < OKX (1).
    # "Prefer candidate (BIN) if candidate > best * 0.5".
    # 100 > 90 * 0.5 (45) -> True.
    # BINANCE wins.

    def assert_a(data):
        assert len(data) == 1
        assert data[0]["symbol"] == "BINANCE:BTCUSDT"

    run_test("Fuzzy Exchange A (BINANCE wins)", {}, raw_a, assert_a)

    # Case B: BINANCE (40) vs OKX (100).
    # OKX comes first. Best=OKX(100).
    # BINANCE comes. Rank BIN(0) < OKX(1).
    # "Prefer candidate (BIN) if candidate > best * 0.5".
    # 40 > 100 * 0.5 (50) -> False.
    # Does not swap. OKX stays.

    raw_b = [
        {"symbol": "OKX:BTCUSDT", "volume": 100, "Value.Traded": 100, "type": "futures"},
        {"symbol": "BINANCE:BTCUSDT", "volume": 40, "Value.Traded": 40, "type": "futures"},
    ]

    def assert_b(data):
        assert len(data) == 1
        assert data[0]["symbol"] == "OKX:BTCUSDT", "OKX should win (liquidity dominance > exchange pref)"

    run_test("Fuzzy Exchange B (OKX wins by liq)", {}, raw_b, assert_b)


def test_missing_data_handling():
    """Test Case 4: Missing Data (None/NaN) handling."""
    # Row with None volume. Config requires min volume 100.
    raw = [
        {"symbol": "BINANCE:GOOD", "volume": 1000, "Value.Traded": 1000, "type": "futures"},
        {"symbol": "BINANCE:BAD", "volume": None, "Value.Traded": None, "type": "futures"},  # Should be dropped
        {"symbol": "BINANCE:NAN", "volume": float("nan"), "Value.Traded": 1000, "type": "futures"},  # NaN volume
    ]

    cfg = {"volume": {"min": 100}}

    def assert_missing(data):
        symbols = [r["symbol"] for r in data]
        assert "BINANCE:GOOD" in symbols
        assert "BINANCE:BAD" not in symbols
        # NaN volume usually treated as 0 or fails filter.
        # Logic: vol = fillna(0). 0 >= 100 is False.
        assert "BINANCE:NAN" not in symbols

    run_test("Missing Data", cfg, raw, assert_missing)


def test_strategy_filter_boolean_logic():
    """Test Case 5: Strategy Filter Boolean Logic."""
    # Trend config: Recommend.All >= 0.3 AND ADX >= 20

    raw = [
        {"symbol": "PASS", "Recommend.All": 0.5, "ADX": 25, "volume": 1000, "Value.Traded": 1000, "type": "futures"},
        {"symbol": "FAIL_REC", "Recommend.All": 0.1, "ADX": 25, "volume": 1000, "Value.Traded": 1000, "type": "futures"},
        {"symbol": "FAIL_ADX", "Recommend.All": 0.5, "ADX": 10, "volume": 1000, "Value.Traded": 1000, "type": "futures"},
    ]

    cfg = {
        "trend": {
            # TrendConfig has logic="AND", recommendation={min=0.3}, adx={min=20}
            "recommendation": {"min": 0.3},
            "adx": {"min": 20},
            "momentum": {"enabled": False},
            "confirmation_momentum": {"enabled": False},
            "logic": "AND",
        }
    }

    def assert_strategy(data):
        symbols = [r["symbol"] for r in data]
        assert "PASS" in symbols
        assert "FAIL_REC" not in symbols
        assert "FAIL_ADX" not in symbols
        assert len(data) == 1

    run_test("Strategy Logic", cfg, raw, assert_strategy)


def main():
    test_regex_parsing()
    test_fuzzy_quote_tie_breaker()
    test_fuzzy_exchange_tie_breaker()
    test_missing_data_handling()
    test_strategy_filter_boolean_logic()
    logger.info("All parity tests passed!")


if __name__ == "__main__":
    main()
