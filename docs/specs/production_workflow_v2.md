# Production Workflow v2

## 1. Overview
The production workflow is divided into three distinct phases to ensure data integrity, alpha purity, and efficient execution.

### Phase 1: Data Operations (`flow-data`)
**Goal**: Identify candidates, ingest raw market data, and prepare the Lakehouse.
**Trigger**: Scheduled (e.g., Daily/Weekly) or Manual.

1.  **Discovery (`scan-run`)**:
    - Executes composable scanners defined in `configs/scanners/`.
    - Outputs candidate lists (JSON) to `data/export/<RUN_ID>/`.
    - **Parallelism**: Scanners run independently.

2.  **Ingestion (`data-ingest`)**:
    - **Parallel Execution**: Uses `xargs -P` to process candidate files concurrently.
    - **Idempotency**: Checks `freshness_hours` to skip recently updated assets.
    - **Toxic Guard**: Validates daily returns ($|r| < 500\%$) immediately after fetch.

3.  **Metadata (`meta-ingest`)**:
    - Refreshes symbol metadata (tick sizes, lot sizes) from exchanges.

4.  **Feature Ingestion (`feature-ingest`)**:
    - Fetches/Calculates technical indicators (TradingView technicals).

5.  **Feature Backfill (`feature-backfill`)**:
    - **Dynamic Backtesting**: Reconstructs historical technical ratings (Time x Symbol) from OHLCV data.
    - Produces `data/lakehouse/features_matrix.parquet` for point-in-time correct simulations.

### Phase 2: Alpha Production (`flow-production`)
**Goal**: Generate a single-sleeve portfolio (e.g., "Crypto Trend Following" or "US Equities").
**Orchestrator**: `scripts/run_production_pipeline.py`

**Optimization Flags**:
- `--skip-analysis`: Skips heavy visualizations (Clustermaps, Factor Maps).
- `--skip-validation`: Skips full backtesting (useful for rapid iteration).

1.  **Aggregation**:
    - Reads candidates from Lakehouse.
    - Applies "Strict Health" filters (no missing bars).

2.  **Natural Selection (`port-select`)**:
    - Applies HTR v3.4 (Hierarchical Threshold Relaxation).
    - Filters for secular history and momentum.

3.  **Strategy Synthesis**:
    - Inverts Short candidates ($R_{syn} = -1 \times R$).
    - Construct "Strategy Atoms".

4.  **Pre-Opt Analysis (`port-pre-opt`)**:
    - **Critical Path**: Calculates Correlation Clusters (HRP), Antifragility Stats, and Regime Caps.
    - Required for Optimization logic.

5.  **Optimization (`port-optimize`)**:
    - Runs Decision-Naive Solvers (HRP, MinVar, MaxSharpe).
    - Enforces **Stable Sum Gate** ($W_{sum} > 1e-6$).

6.  **Reporting (`port-report`)**:
    - Generates unified tearsheets and weight files immediately.

7.  **Validation (`port-test`)** *(Optional)*:
    - Runs backtests (VectorBT/Nautilus) on the optimized weights.
    - **Dynamic Filtering**: Uses `features_matrix.parquet` to filter eligible assets at each historical rebalance point.
    - Generates forensic reports.

8.  **Post-Analysis (`port-post-analysis`)** *(Optional)*:
    - Generates heavy visualizations (Cluster Maps, Factor Maps, Drift Monitors).

### Phase 3: Meta-Portfolio (`flow-meta-production`)
**Goal**: Combine multiple sleeves into a unified "Fractal" portfolio.
**Orchestrator**: `scripts/run_meta_pipeline.py`

1.  **Parallel Sleeve Execution**:
    - Uses **Ray** to execute child profiles (e.g., `crypto_long`, `crypto_short`) in parallel.
    - Each sleeve runs a full Phase 2 cycle.

2.  **Recursive Aggregation**:
    - Builds a "Meta-Returns" matrix (Sleeves become Assets).

3.  **Meta-Optimization**:
    - Allocates risk budget across sleeves (e.g., Risk Parity).

4.  **Flattening**:
    - Projects meta-weights down to individual assets.

## 2. Key Improvements (v2)
- **Parallel Data Ingestion**: Makefile updated to use `xargs -P` for faster `data-ingest`.
- **Fractal Isolation**: Meta-portfolios run in isolated workspaces (`data/runs/<RUN_ID>`) to prevent leakage.
- **Fail-Fast Health**: Pipeline aborts immediately if "Strict Health" audit fails.
