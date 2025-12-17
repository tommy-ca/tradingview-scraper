Crypto CEX Screening Presets
============================

Overview
--------
- Base universe: Binance/OKX/Bybit/Bitget symbols excluding stable bases (USDT/USDC/BUSD/FDUSD/TUSD/DAI/PAX/USDP/EUR/GBP/BIDR/TRY/BRL/UST/USTC/CHF/JPY).
- Exchange filtering: spot presets set ``exchanges: [BINANCE, OKX, BYBIT, BITGET]`` with ``exclude_perps: true``; TS (perps) presets set ``include_perps_only: true`` for the same exchanges.
- Ordering: take top candidates sorted by ``market_cap_calc`` (with volume floor applied) and limit to 100 before filters.
- Columns: ``name, close, volume, change, Recommend.All, ADX, Volatility.D, Perf.W, Perf.1M, Perf.3M, ATR``.
- Volatility gate (all presets): ``Volatility.D <= 6%`` or ``ATR/close <= 8%``.
- Volume floors: spot and perps share the same floor in configs (50M or 30M depending on preset); override if needed for perps.

Presets (config paths under configs/)
-------------------------------------
- Trend Momentum (long, daily spot) – ``crypto_cex_trend_momentum.yaml``
  - Rec >= 0.15, ADX >= 20, change >= 0, Perf.W >= 1%, Perf.1M >= 2%, Perf.3M >= 5%, volume >= 75M, timeframe daily; base sort market cap then volume.
- Trend Momentum (long, weekly spot) – ``crypto_cex_trend_momentum_weekly.yaml``
  - Weekly timeframe version of the above; Rec >= 0.15, ADX >= 20, Perf.W >= 0%, Perf.1M >= 0.5%, Perf.3M >= 1%; volume >= 75M.
- Mean Reversion (long, spot) – ``crypto_cex_mean_reversion.yaml``
  - Rec >= -0.1, ADX max 30, change <= -0.3%, Perf.W <= -1%, Perf.1M >= -12%, RSI <= 55, Stoch.K <= 60, volume >= 30M, timeframe daily; base sort market cap then volume.
- Cross-Sectional Momentum (long, spot) – ``crypto_cex_xs_momentum.yaml``
  - Rec >= 0.15, ADX >= 18, Perf.W >= 0.5%, Perf.1M >= 2%, change >= 0, volume >= 50M; base sort market cap then volume; take top decile by Perf.W for XS longs.
- Cross-Sectional Mean Reversion (long, spot) – ``crypto_cex_xs_mean_reversion.yaml``
  - Rec >= -0.05, ADX max 40, change <= -0.3%, Perf.W <= -0.5%, Perf.1M >= -10%, RSI <= 55, Stoch.K <= 60, volume >= 30M; base sort market cap then volume; take bottom decile by Perf.W for XS longs.
- TS Momentum (long, perps daily) – ``crypto_cex_ts_momentum_long.yaml``
  - Rec >= 0.1, ADX >= 18, change >= 0.2%, Perf.W >= 1.5%, Perf.1M >= 1%, volume >= 75M, timeframe daily; base sort market cap then volume; ranks by Perf.W desc.
- TS Momentum (long, perps weekly) – ``crypto_cex_ts_momentum_long_weekly.yaml``
  - Weekly timeframe TS perps; Rec >= 0.1, ADX >= 18, Perf.W >= 0%, Perf.1M >= 0.5%, Perf.3M >= 1%, volume >= 75M.
- TS Mean Reversion (long, perps) – ``crypto_cex_ts_mean_reversion_long.yaml``
  - Rec >= -0.05, ADX max 35, change <= -0.2%, Perf.W <= -0.5%, Perf.1M >= -10%, RSI <= 55, Stoch.K <= 60, volume >= 30M; base sort market cap then volume; ranks by Perf.W asc.
- TS Momentum (short, perps) – ``crypto_cex_ts_momentum_short.yaml``
  - Direction short, Rec <= -0.1, ADX >= 18, change <= -0.1%, Perf.W <= -0.5%, Perf.1M <= -2%, volume >= 50M, timeframe daily; base sort market cap then volume.
- TS Mean Reversion (short, perps) – ``crypto_cex_ts_mean_reversion_short.yaml``
  - Direction short, Rec <= 0, ADX max 25, change <= -0.3%, Perf.W <= -1%, Perf.1M <= -6%, volume >= 30M, timeframe daily; base sort market cap then volume.

Usage
-----
Run any preset via CLI (example):

.. code-block:: bash

   python -m tradingview_scraper.futures_universe_selector --config configs/crypto_cex_trend_momentum.yaml --verbose

Indicator Field Categories (crypto overview availability)
-------------------------------------------------------
- Trend/strength: ``Recommend.All``, ``ADX``
- Momentum/returns: ``change``, ``Perf.W``, ``Perf.1M``, ``Perf.3M``, ``Perf.6M``
- Volatility: ``Volatility.D``, ``Volatility.W``, ``Volatility.M``, ``ATR``
- Oscillators: ``RSI``, ``Stoch.K``
- Liquidity/size: ``volume``, ``Value.Traded``, ``market_cap_calc`` (and basic/diluted variants)

Screener vs. Overview field availability
---------------------------------------
- Screener (crypto) fields are limited: ``name``, ``symbol``, ``close``, ``change``, ``change_abs``, ``volume``, ``market_cap_calc``, ``Recommend.All``. Use these for server-side filters.
- Overview provides richer fields used in presets: ``Perf.W``, ``Perf.1M``, ``Perf.3M``, ``Perf.6M``, ``ADX``, ``Volatility.*``, ``ATR``, ``RSI``, ``Stoch.K``, and liquidity proxies like ``Value.Traded``. (Fundamental fields may be present but are often not meaningful for crypto.)

Notes from latest runs (bearish regime at time of test)
------------------------------------------------------
- Long-biased presets returned 0–2 names (momentum/mean-reversion mostly empty).
- Short-biased presets returned small/mid-cap alts (e.g., TS momentum short: SPELLUSDT, XRPUSDT/P, 1000XECUSDT.P, SCUSDT; TS mean-reversion short: IOTXUSDT.P, ACHUSDT.P, DYMUSDT.P, IQUSDT, 1000CHEEMSUSDT, etc.).
- Cross-sectional mean reversion produced duplicate symbols (e.g., SHIBDOGE) in the output; deduplicate in downstream consumers if needed.
- Sorting by ``market_cap_calc`` keeps larger caps prioritized while volume floors screen out illiquid names; adjust floors if running perps-only or majors-only.
- Exchange discovery snapshot (top-volume screener sample): BYBIT, OKX, BITGET all return data alongside BINANCE; DEX venues dominate tail listings and remain excluded by exchange filter.
