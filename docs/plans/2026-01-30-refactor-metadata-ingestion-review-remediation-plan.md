---
title: Metadata Ingestion Review Remediation
type: refactor
date: 2026-01-30
status: draft
---

# Metadata Ingestion Review Remediation

## Overview

Address critical performance bottlenecks, data integrity gaps, and code quality issues identified during the code review of the Run-Scoped Metadata Ingestion feature. This plan consolidates findings into a structured remediation workflow with explicit verification steps.

## Problem Statement

The recent metadata ingestion update introduced powerful scoping capabilities but also revealed:
1.  **Critical Performance Regression**: `backfill_features.py` computes technical ratings twice per symbol, effectively doubling execution time for the most expensive step in the pipeline.
2.  **Data Integrity Risk**: Feature backfills lack runtime schema validation, creating a risk where silent corruption (e.g., NaNs, infinity, or out-of-bound indicators) can persist into the Feature Store.
3.  **Legacy Debt**: Key components (`futures_universe_selector.py`) use outdated Python typing (`List`, `Dict`) and inefficient Pandas operations (`_safe_vote` uses `loc`/`reindex` loops).

## Proposed Solution

Execute a targeted refactoring sprint to:
1.  **Optimize**: Remove redundant calculations in `backfill_features.py` and vectorize `_safe_vote` using Numpy broadcasting.
2.  **Harden**: Enforce `FeatureStoreSchema` validation before persistence, expanding the schema to cover all persisted columns.
3.  **Modernize**: Upgrade type hints to Python 3.10+ standards (`list`, `dict`, `| None`) and simplify collection logic.

## Technical Approach

### Phase 1: Critical Performance Fixes (P1)

**Goal**: Restore backfill performance by eliminating redundant calculations.

- **Target**: `scripts/services/backfill_features.py`
- **Action**: 
    1.  Refactor the calculation loop to compute `ma` and `osc` once.
    2.  Compute `rating` as the vectorized arithmetic mean of `ma` and `osc`.
- **Logic**:
  ```python
  # Current (Redundant - 3x calc)
  # ma = TechnicalRatings.calculate_recommend_ma_series(df)
  # osc = TechnicalRatings.calculate_recommend_other_series(df)
  # rating = TechnicalRatings.calculate_recommend_all_series(df)  # <--- Recalculates MA & OSC internally
  
  # New (Vectorized - 1x calc)
  ma = TechnicalRatings.calculate_recommend_ma_series(df)
  osc = TechnicalRatings.calculate_recommend_other_series(df)
  rating = (ma + osc) / 2.0
  ```
- **Verification**: 
    - Verify `rating` values match exactly with the previous implementation for a sample symbol.
    - Measure execution time per symbol before and after.

### Phase 2: Core Optimization (P2)

**Goal**: Reduce memory allocation overhead in high-frequency technical analysis loops.

- **Target**: `tradingview_scraper/utils/technicals.py`
- **Action**: Refactor `_safe_vote` to use Numpy-level vectorized subtraction instead of Pandas `reindex`/`loc`.
- **Implementation**:
  ```python
  def _safe_vote(cond_buy: pd.Series, cond_sell: pd.Series, index: pd.Index) -> pd.Series:
      # Align series to index (fast path if already aligned)
      b = cond_buy.reindex(index, fill_value=False).to_numpy(dtype=bool)
      s = cond_sell.reindex(index, fill_value=False).to_numpy(dtype=bool)
      
      # Vectorized subtraction: True(1) - False(0) = 1, False(0) - True(1) = -1
      return pd.Series(b.astype(float) - s.astype(float), index=index)
  ```
- **Benchmark**: Compare execution time of `TechnicalRatings.calculate_recommend_ma_series` on a large dataframe (5000 rows).

### Phase 3: Data Integrity & Schema Enforcement (P2)

**Goal**: Prevent corrupted data from entering the Lakehouse.

- **Target**: `tradingview_scraper/pipelines/contracts.py` & `scripts/services/backfill_features.py`
- **Action 1 (Schema Expansion)**: Update `FeatureStoreSchema` in `contracts.py` to include checks for `recommend_ma` and `recommend_other` (range -1.0 to 1.0).
- **Action 2 (Validation)**: Import `FeatureStoreSchema` in `backfill_features.py` and validate the final consolidated dataframe before `to_parquet`.
  ```python
  # Validation Step
  try:
      FeatureStoreSchema.validate(features_df)
  except pa.errors.SchemaError as e:
      logger.error(f"Schema Validation Failed: {e}")
      # Decide: abort or filter invalid rows?
      # Decision: Abort to prevent silent corruption.
      raise
  ```
- **Constraint**: Ensure validation logic handles potential floating-point precision issues safely (e.g., `1.00000001` vs `1.0`).

### Phase 4: Code Modernization (P2)

**Goal**: Align codebase with modern Python standards.

- **Target**: `tradingview_scraper/futures_universe_selector.py`
- **Action**: 
  - Replace `List[...]` with `list[...]`.
  - Replace `Dict[...]` with `dict[...]`.
  - Replace `Optional[...]` with `... | None` (Union types).
  - Simplify `sorted(list(...))` to `sorted(...)`.
  - Remove `from typing import List, Dict, Optional`.
- **Validation**: Run `mypy .` to ensure no regression in type safety.

## Acceptance Criteria

### Performance
- [ ] `backfill_features.py` execution time reduced by ~40-50% per symbol (measured via tqdm rate).
- [ ] `_safe_vote` micro-benchmark shows >2x speedup or significant memory reduction.

### Integrity
- [ ] `FeatureStoreSchema` includes `recommend_ma` and `recommend_other`.
- [ ] Backfilled parquet files pass `FeatureStoreSchema.validate()` strictly.
- [ ] Invalid data triggers an explicit fatal error during backfill.

### Quality
- [ ] `futures_universe_selector.py` contains zero imports from `typing` for `List`, `Dict`, `Optional`.
- [ ] `mypy` check passes on all modified files.

## Dependencies & Risks

- **Risk**: Vectorized `_safe_vote` must handle index alignment correctly. If `cond_buy` is shorter than `index`, `reindex` handles it, but `to_numpy` assumes alignment. The proposed implementation uses `reindex` first, so safety is preserved.
- **Risk**: Schema validation might fail for existing "valid" data if the schema is too strict (e.g., strict bounds on unbounded indicators). **Mitigation**: Only enforce strict bounds (-1, 1) on the Rating columns. Use looser checks for oscillators if added.
