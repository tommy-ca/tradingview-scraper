from tradingview_scraper.settings import get_settings


def debug_prep():
    active_settings = get_settings()
    # Mock universe
    universe = [{"symbol": "BINANCE:BTCUSDT", "direction": "LONG"}]

    # 2. Benchmark Enforcement
    universe_symbols = {c["symbol"] for c in universe}
    for b_sym in active_settings.benchmark_symbols:
        if b_sym not in universe_symbols:
            universe.append({"symbol": b_sym, "direction": "LONG", "is_benchmark": True})

    print(f"Universe after benchmark enforcement: {universe}")

    for candidate in universe:
        symbol = candidate["symbol"]
        is_bench = candidate.get("is_benchmark", False)
        print(f"Symbol: {symbol}, is_benchmark: {is_bench}")


if __name__ == "__main__":
    debug_prep()
