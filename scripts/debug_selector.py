import yaml

from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, SelectorConfig


def debug_universe(preset_path: str):
    print(f"\n{'=' * 80}")
    print(f"DEBUGGING: {preset_path}")
    print(f"{'=' * 80}")

    with open(preset_path, "r") as f:
        config_dict = yaml.safe_load(f)

    # Ensure export is disabled for debug run
    config_dict["export"]["enabled"] = False
    config = SelectorConfig(**config_dict)
    selector = FuturesUniverseSelector(config)

    # Manually trigger parts of the pipeline to see attrition
    columns = selector._build_columns()
    aggregated = []
    for market in config.markets:
        filters = selector._build_filters(market)
        for exchange in config.exchanges:
            rows, _ = selector._screen_market(market, filters, columns, exchange=exchange, max_rows=config.prefilter_limit)
            aggregated.extend(rows)

    print(f"1. Raw Fetch: {len(aggregated)} symbols")

    # 1. Basic Filters
    rows = selector._apply_basic_filters(aggregated)
    print(f"2. After Basic Filters (Stable/Type): {len(rows)} (Dropped {len(aggregated) - len(rows)})")

    # 2. Market Cap
    rows_mc = selector._apply_market_cap_filter(rows)
    print(f"3. After Market Cap Guards: {len(rows_mc)} (Dropped {len(rows) - len(rows_mc)})")

    # 3. Volatility
    rows_vol = []
    vol_dropped = []
    for r in rows_mc:
        passes, _ = selector._evaluate_volatility(r)
        if passes:
            rows_vol.append(r)
        else:
            vol_dropped.append(r["symbol"])
    print(f"4. After Volatility Guards: {len(rows_vol)} (Dropped {len(rows_mc) - len(rows_vol)})")
    if vol_dropped[:5]:
        print(f"   Samples dropped by Vol: {vol_dropped[:5]}")

    # 4. Liquidity
    rows_liq = [r for r in rows_vol if selector._evaluate_liquidity(r)]
    print(f"5. After Liquidity Floor (${config.volume.value_traded_min / 1e6:.2f}M): {len(rows_liq)} (Dropped {len(rows_vol) - len(rows_liq)})")

    # 5. Aggregation
    rows_agg = selector._aggregate_by_base(rows_liq)
    print(f"6. After Unique Base Aggregation: {len(rows_agg)} (Grouped {len(rows_liq) - len(rows_agg)} duplicates)")

    # 6. Sorting & Final Limit
    base_sort_field = config.base_universe_sort_by or "Value.Traded"
    rows_agg.sort(key=lambda x: x.get(base_sort_field) or 0, reverse=True)
    limit = int(config.base_universe_limit or 50)
    final = rows_agg[:limit]

    print(f"\nFinal Selected: {len(final)}")
    if len(final) < limit:
        print(f"RESULT: UNIVERSE UNDERFILLED (Target {limit}, Got {len(final)})")

        # Check if lowering floor would help
        lower_liq = [r for r in rows_vol if (r.get("Value.Traded") or 0) > config.volume.value_traded_min * 0.5]
        lower_agg = selector._aggregate_by_base(lower_liq)
        if len(lower_agg) > len(rows_agg):
            print(f"ADVICE: Lowering liquidity floor by 50% would add {len(lower_agg) - len(rows_agg)} unique bases.")


if __name__ == "__main__":
    presets = ["configs/presets/crypto_cex_preset_okx_top50_perp.yaml", "configs/presets/crypto_cex_preset_okx_top50_spot.yaml", "configs/presets/crypto_cex_preset_bitget_top50_spot.yaml"]
    for p in presets:
        debug_universe(p)
