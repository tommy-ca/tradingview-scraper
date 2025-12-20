import json
import time

import pandas as pd

from tradingview_scraper.symbols.technicals import Indicators


def research_alternative_fields():
    # Large set of fields to test, based on indicators.txt and TV Technicals page
    fields_to_test = [
        # Oscillators & Summaries
        "Recommend.All",
        "Recommend.Other",
        "Recommend.MA",
        "RSI",
        "Stoch.K",
        "CCI20",
        "ADX",
        "AO",
        "Mom",
        "MACD.macd",
        "MACD.signal",
        "W.R",
        "BBPower",
        "UO",
        # Moving Averages
        "EMA10",
        "SMA10",
        "EMA20",
        "SMA20",
        "EMA30",
        "SMA30",
        "EMA50",
        "SMA50",
        "EMA100",
        "SMA100",
        "EMA200",
        "SMA200",
        "Ichimoku.BLine",
        "VWMA",
        "HullMA9",
        # Pivots (Daily usually)
        "Pivot.M.Classic.Middle",
        "Pivot.M.Fibonacci.Middle",
        "Pivot.M.Camarilla.Middle",
    ]

    ind = Indicators()
    symbol = "BTCUSDT"
    exchange = "BINANCE"
    timeframes = ["15m", "1h", "1d"]

    print(f"[INFO] Researching alternative technical fields for {exchange}:{symbol}...")

    research_results = {}

    for tf in timeframes:
        print(f"  Fetching {tf} data...")
        try:
            res = ind.scrape(exchange=exchange, symbol=symbol, timeframe=tf, indicators=fields_to_test)
            if res["status"] == "success":
                research_results[tf] = res["data"]
            else:
                print(f"  [FAILED] No data for {tf}")
        except Exception as e:
            print(f"  [ERROR] {tf} request failed: {e}")
        time.sleep(1)

    # Analyze which fields actually returned data
    analysis = []
    for field in fields_to_test:
        row = {"Field": field}
        for tf in timeframes:
            val = research_results.get(tf, {}).get(field)
            row[tf] = "OK" if val is not None else "MISSING"
        analysis.append(row)

    df = pd.DataFrame(analysis)
    print("\n" + "=" * 100)
    print("FIELD AVAILABILITY ACROSS TIMEFRAMES")
    print("=" * 100)
    print(df.to_string(index=False))

    output_file = "docs/research/alternative_fields_availability.json"
    with open(output_file, "w") as f:
        json.dump(research_results, f, indent=2)

    print(f"\n[DONE] Detailed data saved to {output_file}")


if __name__ == "__main__":
    research_alternative_fields()
