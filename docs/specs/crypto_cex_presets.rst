Crypto CEX Screening Presets
============================

Overview
--------
- Base universes are now split by instrument type: spot, perps (.P suffix), and dated futures (expiry-coded). Exchange scope remains ``[BINANCE, OKX, BYBIT, BITGET]``.
- Spot presets enforce a quote whitelist (USDT/USD/USDC/FDUSD/BUSD) and exclude perps and dated futures; perps presets require ``include_perps_only: true``; dated presets require expiry-coded symbols.
- Ordering: fetch with ``prefilter_limit`` (1500) sorted by ``market_cap_calc`` (spot) or ``Value.Traded`` (perps/dated), then final sort ``Value.Traded`` and cap at ``limit``.
- Columns: ``name, close, volume, Value.Traded, market_cap_calc, change, Recommend.All, ADX, Volatility.D/W/M, Perf.W/1M/3M, ATR``.
- Liquidity/volatility guard (current presets): ``Value.Traded >= 50M``; ``Volatility.D <= 8%`` or ``ATR/close <= 12%``. Adjust per instrument if needed.

Presets (config paths under configs/)
-------------------------------------
Spot trend (daily/weekly)
- ``crypto_cex_trend_momentum_spot_daily_long.yaml`` / ``..._short.yaml`` plus per-exchange spot trend variants: ``crypto_cex_trend_<exchange>_spot_daily_long.yaml`` / ``..._short.yaml`` (BINANCE/OKX/BYBIT/BITGET)
  - Liquidity: Value.Traded >= 50M (20M for per-exchange), Vol.D <= 8–15% or ATR/close <= 12%; quote whitelist USDT/USD/USDC/FDUSD/BUSD; exclude perps and dated futures.
  - Long: Rec>=0, ADX>=10, momentum change>=-0.2, Perf.W>=-0.5, Perf.1M>=0, Perf.3M>=0.5. Short: Rec<=-0.2, ADX>=10, momentum inverted.
  - Sort: market_cap_calc then Value.Traded; limit 100 (spot) or 50 (per-exchange).
- ``crypto_cex_trend_momentum_spot_weekly_long.yaml`` / ``..._short.yaml``
  - Same liquidity/vol caps; weekly horizons (long: Perf.W>=0, Perf.1M>=0.5, Perf.3M>=1; shorts inverted).

Perps trend (daily)
- ``crypto_cex_trend_momentum_perp_daily_long.yaml`` / ``..._short.yaml`` (multi-exchange)
- Per-exchange: ``crypto_cex_trend_<exchange>_perp_daily_long.yaml`` / ``..._short.yaml``
  - ``include_perps_only: true``; Liquidity Value.Traded >= 50M (20M per-exchange); Vol.D <= 8–15% or ATR/close <= 12%.
  - Sort by Value.Traded; majors ensured via .P symbols in per-exchange variants.

Dated futures trend (daily)
- ``crypto_cex_trend_momentum_dated_daily_long.yaml`` / ``..._short.yaml`` (multi-exchange)
- Per-exchange: ``crypto_cex_trend_<exchange>_dated_daily_long.yaml`` / ``..._short.yaml``
  - ``include_dated_futures_only: true``; quote whitelist; Liquidity Value.Traded >= 50M (10M per-exchange); Vol caps as above; daily momentum as spot.

Legacy/other presets
- Cross-sectional, mean-reversion, and TS momentum presets remain as-is (xs_momentum/mean_reversion, ts_momentum/mean_reversion, MTF variants). Volume/vol thresholds there may differ; adjust per strategy.

Base universes
--------------
- Spot: ``crypto_cex_base_top50.yaml`` – excludes perps and dated futures, quote whitelist USDT/USD/USDC/FDUSD/BUSD, Value.Traded >= 1.5M, volume >= 2M, Vol.D <= 20% or ATR/close <= 15%, dedupe by base, limit 50, sorted by market_cap_calc then Value.Traded. Majors ensured.
- Perps: ``crypto_cex_base_top50_perp.yaml`` – `include_perps_only: true`, excludes dated, Value.Traded >= 7.5M, volume >= 2M, Vol.D <= 20% or ATR/close <= 15%, dedupe by base, prefer perps, limit 50, sorted by Value.Traded; majors ensured via `.P` symbols.
- Dated futures: ``crypto_cex_base_top50_dated.yaml`` – `include_dated_futures_only: true`, excludes perps, quote whitelist, Value.Traded >= 5M, Vol.D <= 25% or ATR/close <= 20%, dedupe by base, limit 50, sorted by Value.Traded (currently yields 0 under these floors).
- Per-exchange splits for spot/perps/dated: ``crypto_cex_base_top50_<exchange>.yaml``, ``..._<exchange>_perp.yaml``, ``..._<exchange>_dated.yaml`` (BINANCE/OKX/BYBIT/BITGET). Spot floors per exchange: BINANCE/OKX/BYBIT Value.Traded >= 1.5M; BITGET >= 1.0M (volume >= 2M, same vol caps as multi-spot). Perps use Value.Traded >= 7.5M (volume >= 2M). Dated use Value.Traded >= 5M.
- Merged views: ``outputs/crypto_trend_runs/merged_base_universe_spot.json`` and ``..._perp.json`` aggregate per-exchange spot/perp bases into normalized symbols with their tradable exchange symbols; dated is empty at current floors.

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

Multi-Timeframe (MTF) crypto notes
----------------------------------
- Intraday fields (e.g., ``change|1h``, ``Perf.4H``) are not available via Screener/Overview; MTF must use daily/weekly/monthly fields.
- Recommended MTF sets given constraints: (A) monthly → weekly → daily, (B) weekly → daily → daily. Trend: Perf.1M/3M/6M (or Perf.W/Perf.1M); Confirm: Perf.W/Perf.1M; Execute: daily change/Perf.W plus oscillators (RSI/Stoch.K) and volatility guard.
- Sample configs:
  - Spot long: ``configs/crypto_cex_mtf_monthly_weekly_daily.yaml``, ``configs/crypto_cex_mtf_weekly_daily_daily.yaml``.
  - Spot short: ``configs/crypto_cex_mtf_monthly_weekly_daily_short.yaml``, ``configs/crypto_cex_mtf_weekly_daily_daily_short.yaml``.
  - Perps short: ``configs/crypto_cex_mtf_weekly_daily_daily_perps_short.yaml``.
  - Mixed trend/MR: ``configs/crypto_cex_mtf_trend_mr_trend.yaml`` (monthly trend → weekly MR → daily trend) and ``configs/crypto_cex_mtf_mr_trend_trend.yaml`` (monthly MR → weekly trend → daily trend).
- All current runs returned 0 under bearish regime/thresholds; lower volume floors or relax Perf/RSI/Stoch gates to widen coverage.

Notes
-----
- Recent runs (prefilter 400) show spot longs empty and dated futures empty under current thresholds; shorts return sparse sets, perps shorts return healthy lists. To surface longs or dated: lower Value.Traded floors (e.g., spot/perps to 10–20M, dated to 5–10M) and relax long momentum/Rec/ADX gates.
- Majors can still be filtered out under bearish regimes if Perf.W/1M/3M thresholds stay positive; relax momentum gates or add ``ensure_symbols`` per exchange to guarantee inclusion.
- Dated futures are explicitly separated to avoid contaminating spot/perp runs; adjust ``value_traded_min`` downward if dated lists come back empty.
- Quote whitelist and dated/perp flags are enforced in post-filtering; widen quotes or disable exclusions if you need broader coverage.
