# Brainstorm: Rerun Binance Spot Ratings Sleeves (End-to-End)

**Date:** 2026-02-03
**Topic:** Rerun Binance Spot Ratings All/MA Long/Short Sleeves

## What We're Building

A coordinated execution plan to refresh four specific atomic sleeve portfolios for Binance Spot ratings strategies:
1.  `binance_spot_rating_all_long`
2.  `binance_spot_rating_all_short`
3.  `binance_spot_rating_ma_long`
4.  `binance_spot_rating_ma_short`

This will involve running the **Full End-to-End Pipeline** for each profile, ensuring fresh data ingestion, feature engineering, selection, and backtesting.

## Why This Approach

The user explicitly requested an **Atomic Sleeve Refresh** with a focus on the **Full Data Pipeline**. This ensures:
1.  **Freshness**: Ingesting the latest market data guarantees the ratings are up-to-date.
2.  **Integrity**: Re-running the full stack verifies that no regressions have been introduced in the ingestion or feature engineering layers since the last run.
3.  **Isolation**: Running atomically allows for easier debugging of any specific failures in a single strategy type (e.g., Short vs Long).

## Key Decisions

1.  **Execution Mode**: `Full Pipeline (End-to-End)`. We will trigger `make flow-production` for each profile, which includes `data-fetch`, `features`, `alpha`, and `risk`.
2.  **Parallelism**: We will execute these sequentially or in parallel depending on resource availability, but treated as independent units of work.
3.  **Validation**: Post-run validation will check for successful `audit.jsonl` entries and valid `returns_matrix.parquet` artifacts.

## Open Questions

1.  Do we need to update any `yaml` configurations before running, or are the current settings in `configs/scanners/crypto/ratings/` sufficient? (Assuming current settings).
2.  Should we use a specific `run_id` pattern for tracking these (e.g., `20260203_refresh_...`) or auto-generated timestamps? (Will use auto-generated for simplicity unless specified).

## Recommended Next Steps

Run `/workflows:plan` to generate the execution script.
