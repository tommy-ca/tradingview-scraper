from unittest.mock import patch

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, SelectorConfig


def test_market_cap_rank_guard():
    """
    Test that the rank guard correctly filters out symbols not in the Top N of the market cap file.
    """
    config = SelectorConfig(
        markets=["crypto"],
        market_cap_file="dummy_caps.json",
        market_cap_rank_limit=2,  # Only Top 2
    )

    # Mock market cap map
    # BTC is Top 1, ETH is Top 2, SOL is Top 3
    cap_map = {"BTC": 1000, "ETH": 500, "SOL": 100}

    selector = FuturesUniverseSelector(config)

    with patch.object(selector, "_load_market_cap_map", return_value=cap_map):
        rows = [
            {"symbol": "BINANCE:BTCUSDT", "Value.Traded": 100},
            {"symbol": "BINANCE:ETHUSDT", "Value.Traded": 90},
            {"symbol": "BINANCE:SOLUSDT", "Value.Traded": 80},  # Should be filtered (Rank 3)
        ]

        # We need to simulate the pipeline or call the filter directly
        filtered = selector._apply_market_cap_filter(rows)

        symbols = [r["symbol"] for r in filtered]
        assert "BINANCE:BTCUSDT" in symbols
        assert "BINANCE:ETHUSDT" in symbols
        assert "BINANCE:SOLUSDT" not in symbols


def test_market_cap_floor_guard():
    """
    Test that the floor guard correctly filters out symbols below the minimum market cap value.
    """
    config = SelectorConfig(
        markets=["crypto"],
        market_cap_floor=500000000,  # $500M
    )

    selector = FuturesUniverseSelector(config)

    rows = [
        {"symbol": "BINANCE:BTCUSDT", "market_cap_calc": 1000000000, "Value.Traded": 100},  # $1B - Pass
        {"symbol": "BINANCE:LOWCAP", "market_cap_calc": 100000000, "Value.Traded": 200},  # $100M - Fail
    ]

    # Update: _apply_market_cap_filter needs to handle floor guard too
    filtered = selector._apply_market_cap_filter(rows)

    symbols = [r["symbol"] for r in filtered]
    assert "BINANCE:BTCUSDT" in symbols
    assert "BINANCE:LOWCAP" not in symbols


def test_liquidity_priority_with_guards():
    """
    Test that Value.Traded remains the primary sorting factor after guards are applied.
    """
    config = SelectorConfig(markets=["crypto"], market_cap_rank_limit=10, limit=2, final_sort_by="Value.Traded")

    cap_map = {"BTC": 1000, "ETH": 900, "SOL": 800}

    selector = FuturesUniverseSelector(config)

    with patch.object(selector, "_load_market_cap_map", return_value=cap_map):
        rows = [
            {"symbol": "BINANCE:BTCUSDT", "Value.Traded": 50},  # Rank 1 cap, Low liquidity
            {"symbol": "BINANCE:ETHUSDT", "Value.Traded": 200},  # Rank 2 cap, High liquidity
            {"symbol": "BINANCE:SOLUSDT", "Value.Traded": 150},  # Rank 3 cap, Med liquidity
        ]

        # Simulate the run logic
        filtered = selector._apply_market_cap_filter(rows)
        final = selector._sort_rows(filtered)[: config.limit]

        symbols = [r["symbol"] for r in final]
        assert symbols == ["BINANCE:ETHUSDT", "BINANCE:SOLUSDT"]
