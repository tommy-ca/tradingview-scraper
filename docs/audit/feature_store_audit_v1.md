# Audit Report: Feature Store Consistency

**Date**: 2026-01-23
**Scope**: Feature Store Ingestion & Backfill (`data/lakehouse/features_matrix.parquet`)

## 1. Current Architecture
The Feature Store is the "L1 Gate" for Alpha Generation. It transforms raw OHLCV data into a Point-in-Time (PIT) matrix of technical indicators.

### Data Flow
1.  **Ingestion**: `ingest_data.py` -> `data/lakehouse/<SYMBOL>_1d.parquet`
2.  **Backfill**: `backfill_features.py` -> `data/lakehouse/features_matrix.parquet`
3.  **Consumption**: `BacktestEngine` (Ranking), `NaturalSelection` (Filtering)

## 2. Findings (Code Review)

### 2.1 Schema Looseness
- **Issue**: `backfill_features.py` manually calculates indicators and stores them in a `dict` before DataFrame creation.
- **Risk**: No formal guarantee that `recommend_ma`, `recommend_other`, `recommend_all` exist for every symbol.
- **Impact**: Downstream `InferenceStage` (L2) might fail or default to 0.0 silently.

### 2.2 NaN Handling
- **Current**: `check_nan_density` checks for >10% NaNs after the first valid index.
- **Gap**: Does not check for *recent* gaps (e.g. data stopped updating 5 days ago).
- **Gap**: Does not enforce specific bounds (e.g. RSI must be 0-100).

### 2.3 Feature Parity
- **Issue**: Logic is duplicated between `backfill_features.py` (for Backtest) and `feature_engineering.py` (for Selection).
- **Status**: Phase 640 aims to consolidate this, but strict schema enforcement must come first.

### 2.4 Artifact Integrity
- **Observation**: `features_matrix.parquet` is overwritten in place.
- **Recommendation**: Write to `features_matrix_temp.parquet` -> Validate -> Atomic Rename.

## 3. Recommendations
1.  **Integrate Pandera**: Use `FeatureStoreSchema` (from Phase 740) inside `backfill_features.py`.
2.  **Atomic Write**: Implement atomic write pattern to prevent corruption during generation.
3.  **Lag Detection**: Add a check for "Last Valid Index" vs "Latest Price Date".
4.  **Strict Mode**: If `TV_STRICT_HEALTH=1`, fail backfill if *any* candidate is degraded.

## 4. Plan
Proceed with Phase 630 (Feature Store Consistency Audit) to implement `FeatureConsistencyValidator` upgrades and integrate them into the backfill process.
