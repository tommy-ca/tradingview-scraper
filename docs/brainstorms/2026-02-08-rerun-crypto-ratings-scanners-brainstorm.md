---
date: 2026-02-08
topic: rerun-crypto-ratings-scanners
---

# Brainstorm: Rerun Crypto Ratings Scanners & Optimization

## What We're Building
A plan to rerun the crypto scanner pipelines for the `ratings_all` and `ratings_ma` profiles (both Long/Short) across Binance Spot and Perps. We will stick to the **Sequential (Redundant Fetch)** architecture for now (per user preference) but identify specific low-hanging optimizations to improve stability and auditability without a full architectural rewrite.

## Why This Approach
The user explicitly chose to maintain the **Sequential** architecture. This prioritizes **Isolation** over **Speed**. If one strategy fetch fails (e.g. API timeout), it won't affect others. It also simplifies debugging as each strategy run is independent.
However, we must address the identified bottlenecks (Redundant Fetching, Heavy Post-Processing) through targeted optimizations rather than structural changes.

## Key Decisions
-   **Decision 1: Maintain Sequential Execution**: We will not implement the "Snapshot & Filter" pattern yet. Each strategy will continue to manage its own data fetching lifecycle.
-   **Decision 2: Focus on Ratings Profiles**: The scope is strictly `ratings_all` (Overall Rating) and `ratings_ma` (Moving Averages Rating) for both Spot and Perps.
-   **Decision 3: Targeted Optimization**: Instead of caching the fetch, we will optimize the *filtering logic* within the `FuturesUniverseSelector` to reduce the O(N) overhead per run.

## Open Questions
-   **API Rate Limits**: With sequential redundant fetching, will we hit TradingView/Binance rate limits if we run 4+ strategies in a row? (Mitigation: Add configurable delays).
-   **Data Consistency**: Since fetches happen at slightly different times, the "Spot Long" universe might differ slightly from "Spot Short" universe due to market movements during the run. Is this acceptable? (Assumption: Yes, for ratings strategies which are slower moving).

## Next Steps
→ `/workflows:plan` to execute the rerun:
1.  Verify configuration for `ratings_all` and `ratings_ma`.
2.  Optimize `FuturesUniverseSelector` filtering (vectorize where possible).
3.  Execute `make scan-run` for the target profiles.
4.  Audit the results in `data/discovery/`.
