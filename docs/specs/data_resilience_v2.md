# Data Resilience & Stabilization (v2)

This document specifies the guardrails and architectural patterns implemented to ensure high-quality, continuous market data collection across mixed asset universes.

## 1. WebSocket Guardrails (`Streamer`)

To prevent the streaming process from hanging on throttled symbols or network instability, the following mechanisms are active:

- **Total Execution Timeout**: `Streamer.stream()` accepts a `total_timeout` (seconds). The main collection loop exits immediately if this limit is reached.
- **Partial Data Recovery**: Upon timeout, the streamer returns any candles gathered so far instead of failing the entire request.
- **Idle Packet Detection**: Monitors consecutive "empty" WebSocket messages. Exits early if no new data is received for `idle_packet_limit` packets.
- **Auto-Reset Connection**: Every subscription request triggers a fresh connection state to prevent cross-symbol session pollution.

## 2. Optimized Repair Pattern (`PersistentDataLoader`)

The gap-filling process has been refactored for efficiency and "Genesis" detection:

- **Reverse Iteration (Newest to Oldest)**: Gaps are filled from most recent to oldest. Deep historical fetches naturally fill all younger gaps in a single call.
- **Fail-Fast Genesis Detection**: If an API call for a specific depth returns **0 new candles**, the system assumes it has hit the beginning of available history ("Genesis") and breaks the loop for that symbol.
- **Redundancy Check**: Before attempting to fill a gap, the system checks the local lakehouse via `contains_timestamp()` to see if a previous deeper fetch already covered the hole.
- **Strict Per-Symbol Caps**:
    - `max_time`: Limits total repair duration per symbol (prevents blocking the batch).
    - `max_fills`: Limits discrete gap-fill attempts per symbol.
    - `legacy_cutoff`: Hard floor at **2010-01-01**; older gaps are ignored.

## 3. HTTP Resilience (`RequestSession`)

All REST-based scrapers (`Overview`, `News`, `Ideas`) utilize a thread-safe `RequestSession` singleton:

- **Retries**: 3 attempts per request.
- **Backoff**: Exponential backoff factor (1.0s base) to handle `429 Too Many Requests`.
- **Global Timeout**: 10s default timeout for all HTTPS operations.
- **Status Forcelist**: Automatically retries on `[429, 500, 502, 503, 504]`.

## 4. Mixed-Universe Alignment

To merge assets with different trading sessions (e.g., 24/7 Crypto vs M-F Equities):

- **Zero-Fill Returns**: Missing returns during market closures (weekends/holidays) are filled with `0.0`.
- **Min-History Floor**: `PORTFOLIO_MIN_HISTORY_FRAC` ensures symbols with insufficient anchoring are excluded, while allowing newer listings through a lower threshold (e.g., 0.4).
- **Smart Gap Detection**: Weekend gaps for non-crypto symbols are automatically filtered out of the "Health" report.
