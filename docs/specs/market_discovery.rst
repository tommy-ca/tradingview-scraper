Trend Presets for US Stocks and ETFs
====================================

US stocks (daily trend)
-----------------------
- Config: ``configs/us_stocks_trend_momentum.yaml``
- Columns: ``name, close, volume, change, Recommend.All, ADX, Volatility.D, Perf.W, Perf.1M, Perf.3M, ATR, market_cap_basic``
- Filters: Rec >= 0.2, ADX >= 15, change >= 0, Perf.W >= 0, Perf.1M >= 1%, Perf.3M >= 3%, volume >= 10M, Vol.D <= 6% (ATR/close <= 8% fallback)
- Sorting: market_cap_basic desc, then volume desc; limit 100

US ETFs (daily trend)
---------------------
- Config: ``configs/us_etf_trend_momentum.yaml``
- Columns: same as stocks
- Filters: Rec >= 0.2, ADX >= 15, change >= 0, Perf.W >= 0, Perf.1M >= 1%, Perf.3M >= 3%, volume >= 5M, Vol.D <= 6% (ATR/close <= 8% fallback)
- Sorting: market_cap_basic desc, then volume desc; limit 100

Notes
-----
- Intended as starting presets; adjust volume floors and thresholds per regime.
- Uses Overview-enriched fields; screener alone won’t provide ADX/Perf/Volatility.
- Exchange is not constrained; base sort by market cap to prioritize larger names.
