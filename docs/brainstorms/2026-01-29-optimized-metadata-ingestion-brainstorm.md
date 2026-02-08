---
date: 2026-01-29
topic: optimized-metadata-ingestion
---

# Optimized Metadata Ingestion Strategy

## What We're Building
We are optimizing the `scripts/build_metadata_catalog.py` workflow to support **Run-Scoped Ingestion**. Instead of refreshing the entire 1130+ symbol universe by default, the script will accept a target list of candidates (from the current DataOps run) and only fetch/update metadata for those specific symbols. We will also introduce a `--workers` argument to strictly control concurrency, defaulting to a low value (e.g., 1-3) to ensure friendly behavior toward public endpoints.

## Why This Approach
The user explicitly requested "Run-Scoped Ingestion" to minimize the footprint on external APIs. This approach drastically reduces the number of requests per run (e.g., from 1130 to ~50), significantly speeding up the pipeline while adhering to rate limits. It aligns with the "Offline Alpha" philosophy where we only fetch what we need for the immediate task.

## Key Decisions
- **Targeted Input**: The script will accept a `--candidates-file` argument pointing to the run-specific `portfolio_candidates.json`.
- **Default Concurrency**: The default worker count will be reduced (e.g., to 1 or 3) to be "friendly" by default. Users can override this if needed.
- **Incremental Update**: The script will update the global `symbols.parquet` with the new data for the targeted symbols, preserving the existing data for others.
- **Makefile Integration**: The `make meta-ingest` (or similar) target will be updated to pass the current run's candidate file instead of running a full catalog refresh.

## Open Questions
- None. The scope is well-defined.

## Next Steps
→ `/workflows:plan` to implement the changes in `scripts/build_metadata_catalog.py` and the `Makefile`.
