# DataOps Architecture v1: The Decoupled Lakehouse

## 1. MLOps/DataOps Principles
To scale the platform from a "Script Runner" to an "Institutional Platform", we adopt the following DataOps principles:

### 1.1 Separation of Concerns
- **Data Engineering (Data Cycle)**: Responsible for availability, freshness, and quality of the raw asset universe.
- **Quantitative Research (Alpha Cycle)**: Responsible for selecting assets and optimizing weights.
- **Contract**: The Data Cycle produces a certified "Golden Copy" in the Lakehouse. The Alpha Cycle consumes this copy as Read-Only input.

### 1.2 Reproducibility via Snapshotting
- **The Problem**: A mutable Lakehouse breaks backtest reproducibility.
- **The Solution**: Every Alpha Run (Production Pipeline) begins by **snapshotting** the necessary subset of the Lakehouse into its immutable `run_dir`.
- **Constraint**: No external API calls allowed inside the Alpha Cycle.

### 1.3 Quality Gates as a Service
- Toxic Data Filtering (e.g., ADA +157,000% spike) moves from "Reaction" (in backtest) to "Prevention" (in ingestion).
- The Lakehouse must never contain known-toxic data.

## 2. Architecture Diagram

```mermaid
graph TD
    subgraph "Data Cycle (flow-data)"
        A[Universe Definitions] -->|YAML| B[Ingestion Service]
        B -->|Fetch & Clean| C[Staging Area]
        C -->|Toxic Filter & Gap Check| D[Data Lakehouse (Parquet)]
        D -->|Update| E[Lakehouse Catalog (JSON)]
    end

    subgraph "Alpha Cycle (flow-alpha)"
        E -->|Read| F[Data Selector]
        D -->|Read| F
        F -->|Snapshot| G[Run Artifacts (Immutable)]
        G --> H[Selection Engine]
        G --> I[Synthesis Engine]
        G --> J[Optimization Engine]
    end
```

## 3. Technical Specifications

### 3.1 The Lakehouse Contract
- **Registry**: `docs/design/lakehouse_schema_registry.md`
- **Location**: `data/lakehouse/`
- **Format**: `EXCHANGE_SYMBOL_1d.parquet` (Snappy compression).
- **Schema**: `timestamp (int64), open, high, low, close, volume`.
- **Index**: `catalog.json` containing metadata (freshness, start_date, end_date, data_quality_score).

### 3.2 Ingestion Service (`scripts/services/ingest_data.py`)
A unified CLI tool replacing ad-hoc `data-fetch` calls.
- **Input**: List of Universe YAMLs.
- **Logic**:
    1.  **Diff**: Compare Lakehouse vs. API availability.
    2.  **Fetch**: Smart polling with rate-limit handling.
    3.  **Sanitize**: Apply `TOXIC_THRESHOLD` (>500% returns).
    4.  **Validate**: Check for gaps > 5 days.
    5.  **Commit**: Atomic write to Parquet.

### 3.3 Data Selector (`scripts/prepare_portfolio_data.py` Refactor)
- **Mode**: `source="lakehouse"` (Default).
- **Operation**:
    1.  Read `catalog.json`.
    2.  Filter assets based on Profile requirements (e.g., `min_history`).
    3.  **Copy** Parquet files from Lakehouse to `artifacts/runs/<ID>/data/`.
    4.  **Fail Fast**: If an asset is missing/stale in Lakehouse, do NOT fetch. Fail the run or drop the asset (configurable).

### 3.4 Feature Store
- **Service**: `scripts/services/ingest_features.py`
- **Contract**: Produces `data/lakehouse/features/tv_technicals_1d.parquet`.
- **Trigger**: Runs daily after Data/Meta ingestion.

## 4. Operational Workflow

### Daily Routine (Cron/Airflow)
1.  **Step 1: Discovery** (`make scan-run`)
    - Generates candidates.
2.  **Step 2: Ingestion** (`make flow-data-ingest`)
    - `data-ingest`: OHLCV Market Data.
    - `meta-ingest`: Symbol/Execution Metadata.
    - `feature-ingest`: TradingView Technicals (New).
3.  **Step 3: Alpha Production** (`make flow-production`)
    - Runs Strategies using Lakehouse data and features.

### Research Routine
1.  Dev updates `universe.yaml`.
2.  `make flow-data-dev` -> Fetches new assets to Lakehouse.
3.  `make flow-dev` -> Tests strategy.
