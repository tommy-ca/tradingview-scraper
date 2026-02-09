---
date: 2026-02-08
topic: full-strategy-specs
---

# Brainstorm: Full Strategy Specifications (Rating Strategies & MTF)

## What We're Building
We are upgrading the `rating_all`, `rating_ma`, and `rating_osc` strategies to support **Full Trade Specifications** (Entry, Stop Loss, Take Profit) and **Multi-Timeframe (MTF) Trend Following**.

## Why This Approach
The user requested support for both **Portfolio Rebalance** (Allocation-based) and **Discrete Trade** (Event-based) models, as well as both **Wide Feature Matrix** and **Ensemble Voting** for MTF. This implies a need for a flexible architecture that can handle hybrid execution styles.
The current `BacktestEngine` is allocation-centric. To support discrete trades (SL/TP), we need to introduce a "Signal Overlay" that can override the allocator's weights (e.g., forcing a 0% weight if a Stop Loss is hit intraday, or simulating a TP exit).

## Key Decisions
-   **Decision 1: Hybrid Execution Model**: We will maintain the core `Portfolio Rebalance` engine but add a **Signal Overlay Layer** (likely in `SimulationStage` or a new `TradeManagementStage`) that interprets SL/TP rules.
    -   *Portfolio Mode*: Standard weight optimization.
    -   *Discrete Mode*: The `VectorBTSimulator` (which supports SL/TP natively) will be configured to execute these "Full Specs" instead of just tracking weights.
-   **Decision 2: MTF via Wide Matrix**: We will implement MTF by ingesting multiple timeframes (e.g., 4h, 1d) and merging them into a "Wide" feature set (e.g., `RSI_4h`, `SMA_1d`). This allows the existing `InferenceStage` to learn cross-timeframe correlations.
-   **Decision 3: Strategy Config Schema**: We will expand the `manifest.json` strategy schema to include `exit_rules` (SL/TP percentages) and `timeframes` (list of intervals to fetch).

## Open Questions
-   **Data Ingestion**: Fetching multiple timeframes for 500+ assets will significantly increase API load. Should we prioritize specific "Core" assets for MTF? (Assumption: Yes, or use lower resolution for broad universe).
-   **VectorBT Integration**: Does the current `VectorBTSimulator` adapter support the advanced `from_signals` API required for SL/TP, or is it stuck on `from_orders`/`from_weights`? (Action: Check adapter).

## Next Steps
→ `/workflows:plan` to execute the upgrade:
1.  **Schema Upgrade**: Update `manifest.json` and `DiscoveryPipeline` to support multi-timeframe ingestion.
2.  **Ingestion Upgrade**: Modify `IngestionStage` to merge MTF data.
3.  **Simulation Upgrade**: Enhance `VectorBTSimulator` to accept SL/TP parameters and run in "Signal Mode" when requested.
4.  **Config Update**: Define full specs for `crypto_rating_*` profiles.
