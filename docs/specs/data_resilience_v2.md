# Data Integrity & Self-Healing Pipeline (v2)

This specification documents the multi-layered data resilience architecture implemented to ensure high-integrity market data for quantitative analysis.

## 1. Genesis Detection & Data Gaps

A critical challenge in historical data management is distinguishing between a **missing data gap** and the **genesis** (start of history) of an asset.

- **Genesis Heuristic**: If a backfill request for a specific depth returns 0 new candles, the system flags that point as the asset's "Genesis."
- **Persistence**: The pipeline respects the genesis point and stops attempting to fill data prior to that date, preventing infinite retry loops and artificial gap detection.

## 2. Market-Aware Gap Detection

The system uses the `DataProfile` (CRYPTO, EQUITY, FUTURES, FOREX) to apply different gap detection logic:

| Profile | Session Logic | Gap Logic |
| :--- | :--- | :--- |
| **CRYPTO** | 24/7 | Every missing minute/day is a gap. |
| **EQUITY** | 09:30-16:00 EST | Skips weekends and US market holidays. |
| **FUTURES** | Exchange Specific | Skips specific session breaks (e.g., CME Sunday open). |
| **FOREX** | 24/5 | Skips Friday 5PM to Sunday 5PM EST and global bank holidays. |

**Institutional Alignment**: The holiday list includes full Thanksgiving and Christmas week closures to prevent false "DEGRADED" flags for TradFi assets.

## 3. The Self-Healing Cycle

The production workflow implements an automated loop to ensure data health:

1.  **Orchestrated Backfill**: Batch-processed fetch of historical data.
2.  **Selective Sync**: Performance optimization that skips backfilling for assets updated within the last 12 hours.
3.  **Audit (Validation)**: Runs `scripts/validate_portfolio_artifacts.py` to identify "DEGRADED" assets.
4.  **Targeted Repair**: Automatically triggers `scripts/repair_portfolio_gaps.py` for symbols with identified internal holes.
5.  **Neutral Alignment**: Any remaining minor gaps are filled with **0.0 (neutral returns)** during matrix alignment to preserve cross-asset synchronization.

## 4. Temporal Normalization (Timezone Stripping)

To ensure 100% reliability of time-series operations (slicing, alignment, reindexing), the pipeline enforces a **strictly timezone-naive DatetimeIndex**.

- **Contamination Handling**: If an index becomes "contaminated" with mixed tz-aware/naive objects (e.g., from `yfinance` or `quantstats`), standard `tz_localize` fails.
- **Ultra-Robust Remediation**: All loaders implement element-wise normalization:
  ```python
  new_idx = [pd.to_datetime(t).replace(tzinfo=None) for t in df.index]
  df.index = pd.DatetimeIndex(new_idx)
  ```
- **Fallback**: System-wide fallback to `pd.to_datetime(idx, utc=True).tz_convert(None)` ensures continuity if element-wise stripping fails.

## 5. Operational Guardrails

- **WebSocket Resilience**:
    - **Total Execution Timeout**: Main collection loop exits if `total_timeout` is reached.
    - **Partial Data Recovery**: Returns any gathered candles upon timeout instead of failing.
- **Throttling**: The `BATCH` Makefile param (mapped to `PORTFOLIO_BATCH_SIZE`) controls concurrency to avoid rate limits; `LOOKBACK` maps to `PORTFOLIO_LOOKBACK_DAYS`, and `PORTFOLIO_FORCE_SYNC=1` forces refresh even if locally "fresh".
- **HTTP Retries**: Scrapers use exponential backoff and retries for status codes `[429, 500, 502, 503, 504]`.
