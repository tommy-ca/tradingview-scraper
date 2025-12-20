import glob
import json
import os
import time

import pandas as pd

from tradingview_scraper.symbols.technicals import Indicators


def research_mtf_alignment():
    # 1. Load latest Binance Trend Long candidates
    trend_files = sorted(glob.glob("export/universe_selector_binance_spot_long_*.json"), key=os.path.getmtime, reverse=True)
    if not trend_files:
        print("[ERROR] No trend candidate files found.")
        return

    with open(trend_files[0], "r") as j:
        candidates = json.load(j)
        # Handle both list and dict formats
        if isinstance(candidates, dict) and "data" in candidates:
            candidates = candidates["data"]

    if not candidates:
        print("[INFO] No candidates found in the latest trend scan. Using BTC and ETH for research.")
        target_symbols = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT"]
    else:
        target_symbols = [c["symbol"] for c in candidates[:5]]

    print(f"[INFO] Researching MTF Alignment for: {target_symbols}")

    ind_scraper = Indicators()
    # Metrics to track across timeframes
    metrics = ["RSI", "ADX", "EMA50", "EMA200", "close"]
    timeframes = ["15m", "1h", "1d"]

    mtf_data = []

    for full_symbol in target_symbols:
        parts = full_symbol.split(":")
        exchange = parts[0]
        symbol = parts[1]

        print(f"\n>>> Analyzing {full_symbol} <<<")
        symbol_row = {"Symbol": full_symbol}

        for tf in timeframes:
            print(f"  Fetching {tf} indicators...")
            try:
                res = ind_scraper.scrape(exchange, symbol, timeframe=tf, indicators=metrics)
                if res["status"] == "success":
                    data = res["data"]
                    for m in metrics:
                        symbol_row[f"{tf}_{m}"] = data.get(m)
                else:
                    print(f"  [WARNING] Failed to fetch {tf} for {symbol}")
            except Exception as e:
                print(f"  [ERROR] {tf} fetch failed: {e}")

            time.sleep(1)  # Rate limit safety

        mtf_data.append(symbol_row)

    df = pd.DataFrame(mtf_data)

    # 2. Logic: Alignment Checks (Example: Bullish Alignment)
    if not df.empty:
        # Simple Bullish score: close > EMA50 across all timeframes
        def calculate_score(row):
            score = 0
            for tf in timeframes:
                close = row.get(f"{tf}_close")
                ema50 = row.get(f"{tf}_EMA50")
                if close and ema50 and close > ema50:
                    score += 1
            return score

        df["Alignment Score"] = df.apply(calculate_score, axis=1)

        print("\n" + "=" * 120)
        print("MULTI-TIMEFRAME ALIGNMENT RESEARCH")
        print("=" * 120)
        cols = ["Symbol", "Alignment Score"] + [f"{tf}_RSI" for tf in timeframes]
        print(df[cols].to_string(index=False))

        output_file = "docs/research/mtf_alignment_summary.json"
        df.to_json(output_file, orient="records", indent=2)
        print(f"\n[DONE] MTF Research saved to {output_file}")


if __name__ == "__main__":
    research_mtf_alignment()
