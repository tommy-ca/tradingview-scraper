Validation Snapshots
====================

Forex (trend preset)
--------------------
- Config: ``configs/forex_trend_momentum.yaml``
- Exchanges: FX_IDC, THINKMARKETS, BLACKBULL, ICMARKETS, ACTIVTRADES, FUSIONMARKETS, OANDA, TRADENATIONSB, TRADENATION, FXOPEN, FX, SKILLING, FPMARKETS, VELOCITY, CAPITALCOM, VANTAGE, PEPPERSTONE.
- Filters (daily long): Rec >= 0.2, ADX >= 15, Perf.W >= 0, Perf.1M >= 0.5%, Perf.3M >= 1.5%, Vol.D <= 6% (ATR/close <= 6% fallback), volume >= 1B.
- Latest run (status=success): 5 candidates (THINKMARKETS: CHFJPY, GBPJPY, EURJPY, EURNOK, USDBRL).

Crypto (Binance spot/perps)
---------------------------
- Configs: see ``configs/binance_*`` presets (trend, TS, XS, MR). Base sort market cap then volume; fields enriched via Overview.
- Long filters remain sparse in bearish regime (often 0–1 names). Short presets surface small/mid-cap alts.
- Latest runs: trend momentum (1: SHIBDOGE), TS momentum long (1: JSTUSDT.P), TS momentum short (2: BTTCUSDT, TUSDT), TS mean reversion short (5: XECUSDT, 1000CHEEMSUSDT variants, IQUSDT, DAMUSDT.P); XS/long MR often 0.

CFD (OANDA)
-----------
- Configs: ``configs/cfd_trend_momentum.yaml`` (OANDA) and ``configs/cfd_trend_multi.yaml`` (OANDA-only; other CFD venues sparse).
- Screener-only fields: Rec, change, volume; richer metrics require Overview enrichment.
- Latest run (OANDA): 2 candidates (XAUUSD, XCUUSD).

Notes
-----
- Screener limitations: FX/CFD/crypto screens expose minimal fields; Overview provides Perf.*, ADX, Volatility.*, ATR, oscillators, and Value.Traded.
- Adjust thresholds/exchanges per regime; majors may need lower Rec/Perf gates and higher liquidity floors.
