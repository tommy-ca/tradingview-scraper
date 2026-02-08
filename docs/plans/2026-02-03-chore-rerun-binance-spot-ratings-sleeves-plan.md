---
title: "chore: Execute coordinated refresh of Binance Spot Ratings sleeves"
type: chore
date: 2026-02-03
---

# chore: Execute coordinated refresh of Binance Spot Ratings sleeves

## Overview

This plan orchestrates a full end-to-end refresh of the four core Binance Spot "Ratings" strategies:
1. `binance_spot_rating_all_long`
2. `binance_spot_rating_all_short`
3. `binance_spot_rating_ma_long`
4. `binance_spot_rating_ma_short`

This operation ensures that the Alpha Layer is optimized against the latest market data in the Lakehouse.

## Problem Statement / Motivation

The user requires an update to the atomic sleeve portfolios to reflect the latest market conditions. These sleeves feed into higher-level meta-portfolios. Stale data in these atomic units leads to degradation in the aggregated signal quality.

## Proposed Solution

We will execute a robust, parallelized workflow that guarantees data integrity and run isolation.

1.  **Unified Data Ingestion (Blocking)**:
    -   Run `make flow-data` first. This refreshes the shared Lakehouse (prices, features) for *all* Binance Spot assets. This is a critical dependency; running production flows without this step would optimize on stale data.

2.  **Parallel Production Execution (Isolated)**:
    -   Launch 4 parallel `make flow-production` tasks.
    -   **CRITICAL**: Pass explicit, unique `TV_RUN_ID`s (e.g., `<timestamp>_all_long`) to prevent artifact collision in the `runs/` directory.

## Technical Considerations

-   **Concurrency**: The recently implemented `ContextVars` support in `BacktestEngine` allows safe parallel execution.
-   **Run Isolation**: By appending unique suffixes to `TV_RUN_ID`, we ensure that each pipeline writes to its own directory (`runs/<timestamp>_suffix/`), avoiding race conditions on `candidates.json` or `audit.jsonl`.
-   **Resource Usage**: Running 4 production flows (each using Ray) concurrently may saturate CPU/RAM. Monitoring is advised.

## Acceptance Criteria

- [ ] Successful completion of `make flow-data` (Lakehouse updated).
- [ ] Successful completion of all 4 `make flow-production` commands.
- [ ] Four distinct run directories exist in `data/artifacts/summaries/runs/`.
- [ ] Each run directory contains a valid `audit.jsonl` with "success" outcomes.

## Success Metrics

- **Freshness**: Features matrix timestamp matches current date.
- **Completeness**: All 4 profiles have generated new weights and equity curves.

## Dependencies & Risks

- **Risk**: High CPU load during parallel backtesting.
- **Mitigation**: If the system OOMs, we will fallback to sequential execution.

## References & Research

- **Brainstorm**: `docs/brainstorms/2026-02-03-rerun-binance-spot-ratings-sleeves-brainstorm.md`
- **SpecFlow Analysis**: Identified critical `RUN_ID` collision risk if running in parallel without explicit IDs.
- **Recent Fixes**: Relies on thread-safe configuration from PR #5.
