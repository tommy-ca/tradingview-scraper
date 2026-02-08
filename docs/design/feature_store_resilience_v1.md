# Design: Feature Store Resilience & Consistency (v1)

**Phase**: 630 & 800
**Status**: Implemented
**Target**: `scripts/services/backfill_features.py`

## 1. Objective
To harden the Feature Store generation process against data quality degradation, ensuring Point-in-Time (PIT) correctness and strict schema compliance, while enabling scalable, run-scoped backfills.

## 2. Architecture Changes

### 2.1 Workspace-Isolated Backfill (Phase 890)
The backfill process is now strictly candidate-driven to ensure efficiency:
1.  **Isolation**: The process requires a `candidates.json` file (typically from a specific discovery run).
2.  **Hybrid Sourcing**: 
    - For "Current" features (last bar), it checks the candidate's `metadata` for values retrieved from the TradingView Screener API.
    - For historical backfilling (PIT), it uses the optimized local `TechnicalRatings` pipeline.
3.  **No Default Global Backfill**: The tool will fail if no candidates file is provided, preventing accidental re-calculation of the entire Lakehouse.

### 2.2 Incremental Merge Pattern
To maintain a master Feature Store while processing isolated runs:
1.  Load the master `features_matrix.parquet`.
2.  Compute/extract features for the *new* symbols.
3.  Upsert columns into the master matrix.
4.  Perform an atomic write-rename.

### 2.3 Backtest Engine Optimization (Phase 800)
- **Column Filtering**: `BacktestEngine` now filters the loaded features matrix to include only columns relevant to the active `returns_matrix`.
- **Impact**: Reduces memory usage significantly (e.g., from 3636 columns to ~200 columns for a 69-asset universe) and eliminates log noise about "missing features" for irrelevant assets.

### 2.4 Feature Logic Consolidation (Phase 640)
- Centralized logic in `TechnicalRatings`.
- Formula: $Rating_{All} = 0.574 \times Rating_{MA} + 0.3914 \times Rating_{Other}$ (Institutional Standard).
- **Ichimoku Tuning** (Phase 660): Changed `Recommend.MA` Ichimoku logic to compare Price vs Base Line (Kijun-sen) instead of Cloud, aligning with TradingView methodology.

### 2.5 Feature Ingest Resilience (Phase 950)
- `ingest_features.py` now performs bounded retries (default 3 attempts) with incremental backoff and per-attempt coverage logging to survive transient TradingView 429/handshake failures.
- Zero coverage after retries remains a hard failure to preserve pipeline fidelity.
- Concurrency defaults remain low (workers=3, Makefile fan-out=2) to reduce API pressure.
- Coverage metrics (fetched/failed symbols, failing symbol list) should be emitted to logs and persisted alongside run artifacts for auditability.
- Persist coverage artifacts (e.g., `feature_ingest_coverage.json` in the run dir) and link them in the run audit ledger for downstream validation.
- Coverage Artifact Schema (minimum): `{ run_id, profile, attempts: [{idx, fetched, failed, duration_s}], failed_symbols: [] }`; reject empty/malformed artifacts in strict mode.
- Promotion Gate: Manifest/meta promotion must reference the coverage artifact in the audit ledger and require 100% coverage (or an explicit, documented exception) before proceeding.

## 3. Implementation Details

### 3.1 Backfill Service
```python
def run(self, candidates_path=None, output_path=None, strict_scope=False):
    # 1. Resolve symbols (Scoped or Full)
    # 2. Load existing matrix (if strict_scope)
    # 3. Compute new features (TechnicalRatings)
    # 4. Merge new with existing
    # 5. Validate (FeatureConsistencyValidator)
    # 6. Atomic Save
```

### 3.2 Backtest Injection
```python
# In BacktestEngine
pit_features_slice = self.features_matrix.loc[current_date]
req = SelectionRequest(..., params={"pit_features": pit_features_slice})
```

## 4. Validation
- **Unit Tests**: `tests/test_feature_consistency.py` (passed).
- **Integration**: Full atomic runs for `binance_spot_rating_all_long` and `short` passed with correct feature matrix sizes.
