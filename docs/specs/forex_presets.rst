Forex Trend Preset
==================

Overview
--------
- Base universe: FX, exchanges from discovery: FX_IDC, THINKMARKETS, OANDA, VANTAGE, FUSIONMARKETS (high prevalence in screener results).
- Columns (overview-enriched): ``name, close, volume, change, Recommend.All, ADX, Volatility.D, Perf.W, Perf.1M, Perf.3M, ATR``.
- Volatility gate: ``Volatility.D <= 6%`` or ``ATR/close <= 6%`` fallback.
- Liquidity: volume >= 1,000,000,000 (tick-volume proxy; adjust as needed).
- Sorting: volume desc (base and final).

Preset (configs/forex_trend_momentum.yaml)
-----------------------------------------
- Trend (daily, long): Rec >= 0.2, ADX >= 15, change >= 0, Perf.W >= 0.0%, Perf.1M >= 0.5%, Perf.3M >= 1.5%.
- Volume floor: 1,000,000,000; exchanges limited to FX_IDC/THINKMARKETS/OANDA/VANTAGE/FUSIONMARKETS.
- No export by default.
- Latest run (bearish regime): 4 candidates (THINKMARKETS:CHFJPY, EURJPY, EURNOK, USDBRL).

Usage
-----
.. code-block:: bash

   python -m tradingview_scraper.futures_universe_selector --config configs/forex_trend_momentum.yaml --verbose

Notes
-----
- Screener for FX exposes only a few fields (name, close, change/change_abs, volume, Recommend.All); richer fields come from per-symbol Overview.
- Adjust volume floors and exchanges if targeting majors only (e.g., add include_symbols for EURUSD, GBPUSD, USDJPY, etc.).
- For looser regimes, reduce Rec/ADX or momentum thresholds if the screen returns no candidates.
