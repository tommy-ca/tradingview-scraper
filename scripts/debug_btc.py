from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, load_config


def debug_btc():
    cfg = load_config("configs/presets/crypto_cex_preset_binance_top50_spot.yaml")
    s = FuturesUniverseSelector(cfg)
    columns = s._build_columns()

    # 0. Raw fetch
    aggregated, _ = s._screen_market("crypto", s._build_filters("crypto"), columns, exchange="BINANCE")
    btcs_raw = [r["symbol"] for r in aggregated if "BTC" in r["symbol"]]
    print(f"Raw fetch BTCs: {btcs_raw}")

    # 1. Basic Filters
    rows = s._apply_basic_filters(aggregated)
    btcs_basic = [r["symbol"] for r in rows if "BTC" in r["symbol"]]
    print(f"After basic filters BTCs: {btcs_basic}")

    # 2. Market Cap
    rows = s._apply_market_cap_filter(rows)
    btcs_mc = [r["symbol"] for r in rows if "BTC" in r["symbol"]]
    print(f"After MC filter BTCs: {btcs_mc}")

    # 3. Volatility
    rows = [r for r in rows if s._evaluate_volatility(r)[0]]
    btcs_vol = [r["symbol"] for r in rows if "BTC" in r["symbol"]]
    print(f"After Vol filter BTCs: {btcs_vol}")

    # 4. Liquidity
    rows = [r for r in rows if s._evaluate_liquidity(r)]
    btcs_liq = [r["symbol"] for r in rows if "BTC" in r["symbol"]]
    print(f"After Liq filter BTCs: {btcs_liq}")

    # 5. Aggregation
    rows = s._aggregate_by_base(rows)
    btcs_agg = [r["symbol"] for r in rows if "BTC" in r["symbol"]]
    print(f"After Aggregation BTCs: {btcs_agg}")


if __name__ == "__main__":
    debug_btc()
