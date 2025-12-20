import logging

import pandas as pd

from tradingview_scraper.futures_universe_selector import (
    FuturesUniverseSelector,
    SelectorConfig,
    TrendConfig,
    TrendRuleConfig,
    VolatilityConfig,
    VolumeConfig,
)

logging.basicConfig(level=logging.INFO)

EXCHANGES = ["BINANCE", "OKX", "BYBIT", "BITGET"]


def analyze_exchange(exchange: str):
    print(f"\n{'=' * 20} Exploring {exchange} {'=' * 20}")

    # 1. Fetch RAW Top 200 (With basic symbol type filters enabled now)
    config = SelectorConfig(
        markets=["crypto"],
        exchanges=[exchange],
        limit=200,
        sort_by="Value.Traded",
        sort_order="desc",
        allowed_spot_quotes=["USDT", "USDC", "USD", "DAI", "BUSD", "FDUSD"],
        exclude_dated_futures=True,
        market_cap_rank_limit=None,
        market_cap_floor=0,
        volume=VolumeConfig(value_traded_min=0, min=0, per_exchange={}),
        volatility=VolatilityConfig(min=None, max=None, atr_pct_max=None, fallback_use_atr_pct=False),
        trend=TrendConfig(recommendation=TrendRuleConfig(enabled=False), adx=TrendRuleConfig(enabled=False), momentum=TrendRuleConfig(enabled=False)),
        dedupe_by_symbol=False,
    )

    selector = FuturesUniverseSelector(config)
    # Ensure market_cap_calc is included
    selector.config.columns = ["name", "close", "volume", "change", "Value.Traded", "market_cap_calc", "Recommend.All", "ADX", "Volatility.D"]

    raw_data = selector.run().get("data", [])
    df_raw = pd.DataFrame(raw_data)

    print(f"Raw Count: {len(df_raw)}")
    if not df_raw.empty:
        print("\n--- RAW Top 5 (Liquid) ---")
        print(df_raw[["symbol", "Value.Traded", "market_cap_calc"]].head(5).to_string(index=False))

        print("\n--- RAW Bottom 5 (Least Liquid in Top 200) ---")
        print(df_raw[["symbol", "Value.Traded", "market_cap_calc"]].tail(5).to_string(index=False))

    # 2. Apply Aggregation (The "Understanding" part)
    aggregated = selector._aggregate_by_base(raw_data)
    df_agg = pd.DataFrame(aggregated)
    if not df_agg.empty:
        # Sort by Value.Traded desc like the pipeline does
        df_agg = df_agg.sort_values("Value.Traded", ascending=False)

        print(f"\nAggregated/Deduped Count: {len(df_agg)}")
        print("\n--- AGGREGATED Top 10 ---")
        print(df_agg[["symbol", "Value.Traded", "market_cap_calc"]].head(10).to_string(index=False))

        print("\n--- AGGREGATED Bottom 10 ---")
        print(df_agg[["symbol", "Value.Traded", "market_cap_calc"]].tail(10).to_string(index=False))

    return df_raw, df_agg


def explore_all():
    all_raw = {}
    all_agg = {}
    for ex in EXCHANGES:
        all_raw[ex], all_agg[ex] = analyze_exchange(ex)


if __name__ == "__main__":
    explore_all()
