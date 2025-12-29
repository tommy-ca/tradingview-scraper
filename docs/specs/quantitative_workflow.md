# Specification: Quantitative Workflow Pipeline
**Status**: Formalized
**Date**: 2025-12-21

## 1. Overview
This document defines the standardized pipeline for transforming raw market data into an optimized, multi-asset portfolio.

## 2. Pipeline Stages

### Stage 1: Discovery & Scans
*   **Tools**: `tradingview_scraper.futures_universe_selector`, `tradingview_scraper.cfd_universe_selector`, `tradingview_scraper.bond_universe_selector`
*   **Entry point**: `make scan-all` (alias: `make scans`) (local + crypto scans, plus bonds + Forex MTF)
*   **Forex base universe audit (optional)**: `make forex-analyze` (runs `scan-forex-base`, filters to majors-only pairs, dedupes venues, excludes IG-only singleton pairs, and writes a tradable-pairs report + data health + hierarchical clusters under `artifacts/summaries/runs/<RUN_ID>/`).
*   **Config preflight**: `make scan-lint` (or `uv run scripts/lint_universe_configs.py --strict`) before running scans/CI.
*   **Input**: `configs/*.yaml` strategy configs (trend, mean reversion, MTF)
*   **Output**: `export/<run_id>/universe_selector_*.json` scan results (`{meta,data}` envelope; set `TV_EXPORT_RUN_ID` to scope a run)
*   **US equities note**: Avoid the TradingView screener field `index` (can return HTTP 400 "Unknown field"); constrain with `include_symbol_files` (e.g. `data/index/sp500_symbols.txt`).

### Stage 2: Strategy Filtering (Signal Generation)
*   **Process**: Applies technical strategy rules (Trend Momentum, Mean Reversion) to the Base Universe.
*   **Base universe principle**: keep strategy-neutral filters (liquidity, volatility, data completeness) separate from directional filters, so strategies can be layered on top of a stable tradable set.
*   **Parameters**: ADX thresholds, RSI levels, Performance horizons (1W, 1M, 3M).
*   *Note*: Short signals are identified for trend-reversal or defensive positioning.

### Stage 3: Natural Selection (Pruning)
*   **Tool**: `scripts/natural_selection.py`
*   **Process**: Performs hierarchical clustering on Pass 1 (60d) data. Selects the Top N assets per cluster based on **Execution Intelligence** (Liquidity + Momentum + Convexity).
*   **Health gate**: `make prune` runs `scripts/validate_portfolio_artifacts.py --mode raw --only-health` after the Pass 1 backfill; this is the first hard stop for STALE/MISSING assets.
*   **Identity Merging**: Canonical venue merging happens here to avoid redundant exchange risk (e.g., BTC across 5 exchanges).

### Stage 4: Risk Optimization (Clustered V2)
*   **Tool**: `scripts/optimize_clustered_v2.py`
*   **Process**: Optimizes weights across clusters using hierarchical risk buckets. Supports **Min Variance, Risk Parity, Max Sharpe, and Barbell** profiles.
*   **Insulation**: Strictly enforced 25% systemic cap per cluster.

### Stage 5: Validation & Backtesting
*   **Tool**: `scripts/backtest_engine.py`
*   **Process**: 13th Step of the production lifecycle. Performs a Walk-Forward validation to verify realized volatility and returns against the optimizer's goals.
*   **Target Achievement**: Automatically audits if `MIN_VARIANCE` actually delivered lower volatility than other profiles during the test period.

### Stage 6: Implementation & Reporting
*   **Output**: Implementation Dashboard (`make display`), Strategy Resume (`artifacts/summaries/latest/backtest_comparison.md`), and Audit Log (`artifacts/summaries/latest/selection_audit.md`).
*   **Publishing**: `make gist` syncs `artifacts/summaries/latest/` (a symlink to the last successful finalized run) to a private GitHub Gist (skips sync if missing/empty unless `GIST_ALLOW_EMPTY=1`).

## 3. Automation Commands
```bash
# Daily incremental run (recommended; preserves cache/state; includes gist preflight)
make run-daily   # alias: make daily-run

# Optional metadata gates (build + audit catalogs before portfolio run)
make run-daily META_REFRESH=1 META_AUDIT=1   # refresh + offline audits (PIT + timezone)
make run-daily META_REFRESH=1 META_AUDIT=2   # includes online TradingView parity sample

# Full reset run (blank slate)
make run-clean   # alias: make clean-run

# After implementing new target weights
make portfolio-accept-state   # alias: make accept-state

# Metadata-only workflows
make meta-validate            # refresh + offline audits
make meta-audit               # offline + online parity sample

# Or step-by-step (tiered selection + analysis + finalize)
make scan-lint                # validate configs first
make scan-all                 # alias: make scans
make prep-raw  # best-effort raw health check (may be stale before backfill)
make prune TOP_N=3 THRESHOLD=0.4
make align LOOKBACK=200
make analyze
make finalize
```

### Forex Base Universe Audit (Debugging)
```bash
# Fast: liquidity report only
make forex-analyze-fast

# Full: backfill + gap-fill + data health + clusters
BACKFILL=1 GAPFILL=1 FOREX_LOOKBACK_DAYS=365 make forex-analyze
```
- Produces run-scoped artifacts under `artifacts/summaries/runs/<RUN_ID>/` (report, data health CSV, cluster map + JSON).
- Default filter excludes IG-only singleton pairs (use `--include-excluded` to render them in the report).
- Clusters tend to separate into quote-currency blocks (e.g. JPY, CHF) plus cross themes (e.g. EUR/GBP vs AUD/NZD).

## 4. Universe Selectors (Scanners) — Current State

- **Core engine**: `FuturesUniverseSelector` is the generic selector used across Crypto, Equities, Forex, Futures, and CFDs.
- **Wrappers**: `BondUniverseSelector` and `cfd_universe_selector` are thin entrypoints that reuse the same selector plumbing.
- **Export contract**: scan artifacts are written to `export/<run_id>/universe_selector_*.json` using a `{meta,data}` envelope; consumers should prefer `meta` (with filename parsing as a fallback).
- **Forex dedup**: forex selectors dedupe by canonical pair identity (base+quote) across venues; aggregated `volume`/`Value.Traded` are preserved alongside representative `volume_rep`/`Value.Traded_rep` for execution-aware ranking.
- **Operational risks**:
  - configs are linted via `make scan-lint` (CI-safe), but TradingView fields can still change over time
  - scan orchestration still uses duplicated bash config lists (to be replaced with a manifest runner)

## 5. Universe Selector Roadmap (Non-Breaking)

1. **Inventory & dependency map**: document producer→consumer coupling for `export/<run_id>/universe_selector_*.json` (which scripts still parse filenames vs read embedded `meta`).
2. **Config lint + deterministic tests**: validate all `configs/**/*.yaml` (lint implemented via `make scan-lint`) and gate network tests behind markers/env vars.
3. **Stable export envelope + run scoping**: implemented (`{meta,data}` envelope + `export/<run_id>/...`) to prevent cross-run leakage; consumers fall back to legacy filename parsing when needed.
4. **Standardized scan runner**: replace bash scan lists with a manifest-driven runner (`--group local|crypto|base`, `--run-id`, `--max-concurrent`, `--export-format`).
5. **Selector refactor**: `build_payloads()` now matches real execution; remaining work is splitting selector internals into modules (config loader, payload builder, post-filters, normalization, export).
6. **Config DRY**: introduce layered presets and additive list merges (`filters_add`, `columns_add`, etc.) to reduce duplication without breaking existing configs.
