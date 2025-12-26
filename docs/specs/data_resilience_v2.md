# Data Integrity & Self-Healing Pipeline (v2)

This specification documents the multi-layered data resilience architecture implemented to ensure high-integrity market data for quantitative analysis.

## 1. Genesis Detection & Data Gaps

A critical challenge in historical data management is distinguishing between a **missing data gap** and the **genesis** (start of history) of an asset.

- **Genesis Heuristic**: If a backfill request for a specific depth returns 0 new candles, the system flags that point as the asset's "Genesis."
- **Persistence**: The pipeline respects the genesis point and stops attempting to fill data prior to that date, preventing infinite retry loops and artificial gap detection.
- **Reverse Iteration**: Gaps are filled from most recent to oldest. Deep historical fetches naturally fill younger gaps in a single call.

## 2. Market-Aware Gap Detection

The system uses the `DataProfile` (CRYPTO, EQUITY, FUTURES, FOREX) to apply different gap detection logic:

| Profile | Session Logic | Gap Logic |
| :--- | :--- | :--- |
| **CRYPTO** | 24/7 | Every missing minute/day is a gap. |
| **EQUITY** | 09:30-16:00 EST | Skips weekends and market holidays. |
| **FUTURES** | Exchange Specific | Skips specific session breaks (e.g., CME Sunday open). |
| **FOREX** | 24/5 | Skips Friday 5PM to Sunday 5PM EST. |

## 3. The Self-Healing Cycle

The production workflow implements an automated loop to ensure data health:

1.  **Orchestrated Backfill**: Batch-processed fetch of historical data (e.g., 200 days).
2.  **Audit (Validation)**: Runs `scripts/validate_portfolio_artifacts.py` to identify "DEGRADED" or "MISSING" assets.
3.  **Targeted Repair**: Automatically triggers `scripts/repair_portfolio_gaps.py` for symbols with identified internal holes.
4.  **Neutral Alignment**: Any remaining minor gaps (e.g., exchange maintenance) are filled with **0.0 (neutral returns)** during matrix alignment.

## 4. Operational Guardrails

- **WebSocket Resilience**:
    - **Total Execution Timeout**: Main collection loop exits if `total_timeout` is reached.
    - **Partial Data Recovery**: Returns any gathered candles upon timeout instead of failing.
    - **Idle Packet Detection**: Monitors consecutive "empty" messages to spot hangs.
- **Throttling**: The `BATCH` parameter ensures backfills do not trigger rate limits.
- **HTTP Retries**: Scrapers use exponential backoff and retries for status codes `[429, 500, 502, 503, 504]`.
