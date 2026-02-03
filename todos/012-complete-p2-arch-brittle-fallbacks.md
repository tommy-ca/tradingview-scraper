---
status: complete
priority: p2
issue_id: "012"
tags: [architecture, robustness]
dependencies: []
---

# Excessive File Fallbacks in BacktestEngine.load_data

The `BacktestEngine.load_data` method in `scripts/backtest_engine.py` implements 6+ levels of file fallbacks for loading the returns matrix, which is brittle and can lead to loading incorrect or outdated data.

## Problem Statement

- The current implementation of `load_data` attempts to find the returns matrix in multiple locations (run directory, latest run directory, lakehouse) and with multiple filenames (`returns_matrix.parquet`, `portfolio_returns.pkl`, `returns_matrix.pkl`, `BINANCE_BTCUSDT_1d.parquet`).
- This deep nesting of fallbacks makes the data loading logic hard to follow and debug.
- It introduces the risk of "silent failure" where the engine loads a stale file from a different directory because the intended file was missing.
- The "ultimate fallback" to a specific symbol file (`BINANCE_BTCUSDT_1d.parquet`) is particularly brittle and likely incorrect for a portfolio engine.

## Findings

- **File**: `scripts/backtest_engine.py:64`
- **Fallback sequence**:
    1. `run_dir` provided as argument.
    2. Latest run directory in `summaries_runs_dir`.
    3. `run_dir / "data"`.
    4. `self.settings.lakehouse_dir`.
    5. Filename fallbacks:
        - `returns_matrix.parquet`
        - `portfolio_returns.pkl`
        - `returns_matrix.pkl`
        - `BINANCE_BTCUSDT_1d.parquet` (ultimate fallback)
- **Code**: Lines 87-103 contain the nested fallback logic.

## Proposed Solutions

### Option 1: Unified Data Locator
**Approach:** Replace the nested fallbacks with a dedicated `DataLocator` service that implements a clear, prioritized search strategy. Fail explicitly if the data cannot be found in expected locations rather than falling back to arbitrary files.

**Pros:**
- Centralized data discovery logic.
- More predictable behavior.
- Easier to audit where data is coming from.

**Cons:**
- Requires refactoring how data paths are resolved across the project.

**Effort:** 2-3 hours
**Risk:** Low

---

### Option 2: Explicit Configuration
**Approach:** Require the caller or the settings to explicitly define the data source path. Remove the "automatic discovery" of latest runs unless explicitly requested via a flag.

**Pros:**
- Most robust approach.
- Prevents accidental loading of wrong data.

**Cons:**
- Less "magic" / convenience for quick CLI runs.

**Effort:** 1-2 hours
**Risk:** Low

## Recommended Action

**To be filled during triage.** Implement Option 1 with a focus on removing the most brittle fallbacks (like the single-symbol fallback).

## Technical Details

**Affected files:**
- `scripts/backtest_engine.py:64` - `load_data` method

## Acceptance Criteria

- [ ] Number of fallback levels in `load_data` reduced to < 3.
- [ ] Brittle symbol-specific fallback (`BINANCE_BTCUSDT_1d.parquet`) removed.
- [ ] Engine raises a clear `FileNotFoundError` with a list of searched paths if data is missing.
- [ ] Source of loaded data is logged clearly at INFO level.

## Work Log

### 2026-02-02 - Initial Discovery

**By:** Antigravity

**Actions:**
- Analyzed `load_data` in `scripts/backtest_engine.py`.
- Identified 6 levels of fallbacks and highlighted the risk of stale data loading.
- Created todo entry 012.

## Notes

- Ensuring data provenance is critical for quantitative research reproducibility.
- This refactor should align with the `PersistentDataLoader` patterns used elsewhere in the project.
