Market Discovery Notes
======================

Screener-supported markets
-------------------------
- The screener accepts the following markets (per Screener.SUPPORTED_MARKETS): ``america, australia, canada, germany, india, israel, italy, luxembourg, mexico, spain, turkey, uk, crypto, forex, cfd, futures, bonds, global``.

Safe probe pattern
------------------
- Use minimal columns to avoid 400 errors: ``name, close, change, change_abs, volume, Recommend.All``.
- Example (forex): ``Screener().screen(market='forex', columns=cols, sort_by='volume', sort_order='desc', limit=500)``.
- If you request fields unsupported by a market (e.g., ``market_cap_calc`` on CFD), the API returns HTTP 400.

Forex exchanges (discovered via screener, top counts)
----------------------------------------------------
- FX_IDC, THINKMARKETS, BLACKBULL, ICMARKETS, ACTIVTRADES, FUSIONMARKETS, OANDA, TRADENATIONSB, TRADENATION, FXOPEN, FX, SKILLING, FPMARKETS, VELOCITY, CAPITALCOM, VANTAGE, PEPPERSTONE (counts vary; FX_IDC and THINKMARKETS dominate).

CFD exchanges (discovered via screener)
---------------------------------------
- Dominated by CRYPTOCAP aggregates; practical CFDs come from OANDA (multi-instrument), with isolated single rows for other codes (SAXO/BLACKBULL/PEPPERSTONE/etc.). In practice, OANDA-only is the usable CFD source.

Field availability
------------------
- Screener fields (forex/cfd): ``name, close, change, change_abs, volume, Recommend.All`` (plus ``market_cap_calc`` for forex; CFD 400s on ``market_cap_calc``).
- Rich indicators (Perf.W/1M/3M/6M, ADX, Volatility.D/W/M, ATR, RSI, Stoch.K, Value.Traded) require per-symbol Overview calls.

Preset guidance
---------------
- Use forex presets with Overview enrichment for trend filters (Rec/ADX/momentum/volatility). Volume is tick-volume proxy; adjust floors per exchange universe.
- For CFDs, use OANDA-only presets; add Overview enrichment for production-quality trend filters.
