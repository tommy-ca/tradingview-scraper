# Offline-Only Alpha Architecture (v1)

## 1. Overview
The **Offline-Only Alpha** standard decouples the **DataOps Cycle** (Mutation) from the **Alpha Cycle** (Execution). This ensures that alpha generation is deterministic, reproducible, and safe from external network failures or side effects during optimization.

## 2. Core Principles
1.  **Read-Only Alpha**: The Alpha Pipeline (`flow-production`) MUST NOT perform any external network I/O (no `ccxt`, `TradingView`, `WebSocket`). It MUST only read from the immutable Lakehouse or Run Artifacts.
2.  **Workspace Isolation**: All run-specific artifacts (`candidates.json`, `returns_matrix.parquet`) MUST be stored in `data/artifacts/summaries/runs/<RUN_ID>/data/`. They MUST NOT overwrite global Lakehouse files.
3.  **Foundation Gate**: The Alpha Pipeline must validate the integrity of the input data (schema, density, toxicity) BEFORE attempting any logic. This prevents "garbage-in, garbage-out" waste of compute.
4.  **Point-in-Time (PIT) Features**: Alpha factors must be pre-computed and stored in `features_matrix.parquet` during DataOps. The Alpha pipeline simply *looks up* the values for the relevant timestamps.

## 3. Architecture

### 3.1 DataOps Cycle (`flow-data`)
**Goal**: Mutate the Lakehouse to prepare for Alpha.
- **Discovery**: Find candidates -> `data/export/<RUN_ID>/candidates.json`.
- **Ingestion**: Fetch OHLCV -> `data/lakehouse/EXCHANGE_SYMBOL_1d.parquet`.
- **Enrichment**: Fetch Metadata -> `data/lakehouse/symbols.parquet`.
- **Repair**: Fill gaps.
- **Feature Backfill**: Calculate Technicals -> `data/lakehouse/features_matrix.parquet`.
- **Audit**: Validate Lakehouse Health.

### 3.2 Alpha Cycle (`flow-production`)
**Goal**: Produce weights from a static snapshot.
- **Input**: `manifest.json`, `RUN_ID` (linking to DataOps export).
- **Step 1: Preparation**:
    - Load candidates from `data/export/<RUN_ID>/candidates_validated.json`.
    - Load OHLCV from Lakehouse.
    - Snapshot inputs to `run_dir/data/returns_matrix.parquet`.
- **Step 2: Foundation Gate**:
    - Verify `returns_matrix` has no NaNs (after trimming).
    - Verify max return < 500% (Toxic).
    - Verify Index is UTC.
- **Step 3: Selection**:
    - Load Features from `features_matrix.parquet` (PIT).
    - Run HTR Loop (Inference -> Clustering -> Policy -> Synthesis).
- **Step 4: Optimization**:
    - Run Convex Solvers on `returns_matrix` + `clusters`.
- **Step 5: Output**:
    - `portfolio_flattened.json` (Target Weights).

## 4. Implementation Details

### 4.1 Feature Engineering Stage
The `FeatureEngineeringStage` in the Alpha Pipeline has been refactored to:
- **Disable** local calculation of Technical Ratings (`compute_features=False`).
- **Enable** PIT Injection (`source=METADATA_OR_STORE`).
- **Require** `features_matrix` to be present.

### 4.2 Backfill Service
The `scripts/services/backfill_features.py` service:
- Accepts a **Scoped** candidate list.
- Calculates features using `ProcessPoolExecutor`.
- Performs an **Incremental Upsert** to the global `features_matrix.parquet`.

## 5. Benefits
- **Speed**: Alpha runs start immediately without waiting for calculations.
- **Safety**: No risk of API rate limits or connection errors breaking a production run.
- **Reproducibility**: Re-running an Alpha profile on an old `RUN_ID` yields exact same results (if Lakehouse snapshot is preserved).
