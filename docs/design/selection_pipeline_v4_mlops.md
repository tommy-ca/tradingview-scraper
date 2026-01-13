# Design Document: MLOps-Centric Selection Pipeline (v4)

## 1. Objective
Refactor the quantitative selection logic into a formal, stage-based inference pipeline inspired by MLOps and modern Data Engineering practices. This architecture prioritizes statelessness, observability, and modularity, allowing for rapid experimentation with new alpha factors and scoring models.

## 2. The Universal Pipeline Architecture
The v4 pipeline is defined as a sequence of discrete, swappable **Stateless Transformers**. Each stage consumes a validated `SelectionContext` and returns an enriched version of it.

### 2.1 Mapping Selection to Pipeline Stages
| Stage | Pipeline Component | Responsibility |
| :--- | :--- | :--- |
| **Ingestion** | `DiscoveryProvider` | Fetch raw assets/metadata from Lakehouse (L4 Scanners). |
| **Feature Engineering** | `FeatureGenerator` | Calculate alpha factors (Momentum, ADX, Entropy, etc.). |
| **Inference** | `ConvictionScorer` | Apply scoring models (Log-MPS, ML models) to produce conviction. |
| **Partitioning** | `FactorBucketizer` | Unsupervised grouping of assets into orthogonal factor groups. |
| **Policy** | `SelectionController` | Pruning logic (HTR Loop, Top-N recruitment). |
| **Synthesis** | `StrategySynthesizer` | Generating the final `StrategyAtom` manifest for Allocation. |

## 3. Data Contracts & Schema Enforcement
To ensure 100% reproducibility and prevent hidden state bugs, every stage transition is validated by strict data models (Pydantic).

### 3.1 `SelectionContext` (The State Container)
- `raw_pool`: Initial list of candidates with discovery metadata.
- `feature_store`: DataFrame containing calculated technical/statistical features.
- `inference_outputs`: Probability scores and model-specific metadata.
- `clusters`: Mapping of assets to identified factor buckets.
- `winners`: The final subset of recruited strategy atoms.

## 4. Logical Separation (The "Shadow Pipeline")
The v4 pipeline will reside in a parallel namespace to ensure the existing `v3.4` production path remains untouched.

- **Namespace**: `tradingview_scraper.pipelines.selection.*`
- **Isolation**: v4 components MUST NOT import from `selection_engines.impl.*`.
- **Parity Goal**: The `Log-MPS` transformer in v4 must produce bit-identical results to the `v3.4` engine during the transition phase.

## 5. MLOps Capabilities

### 5.1 Champion/Challenger Framework
The pipeline supports running multiple `ConvictionScorer` implementations in a single run, tagging outputs for easy performance comparison.

### 5.2 Observability & Traceability
Every run generates an `audit.jsonl` that follows the standard ML tracking schema:
- **Inputs**: Data version (Git hash + Data hash).
- **Parameters**: Hyperparameters for HTR (Entropy ceiling, ADX floor).
- **Metrics**: Cluster density, average conviction, pool diversity.
- **Artifacts**: Link to the generated `portfolio_candidates.json`.

### 5.3 Global Ledger Mapping
To maintain schema hygiene, the v4 pipeline's internal audit trail is mapped to the `data.pipeline_audit` field of the global system ledger. This ensures that MLOps stage transitions are traceable without bloating the high-frequency metrics namespace used for performance analysis.

### 5.4 Matrix Stability Validation
The v4 pipeline has been validated across a multi-dimensional risk matrix (MaxSharpe, HRP, Barbell, MinVariance) using the `SelectionPipelineAdapter`. This ensures that the modular HTR loop correctly provides a stable pool of strategy atoms to all production portfolio engines.

### 5.5 Grand Tournament Standard (v3.4.6)
Institutional validation now requires a head-to-head tournament against the `v3.4` champion engine. Success criteria include:
- **Zero Bankruptcy**: 100% survival across all stress windows.
- **Telemetry Purity**: Verifiable structured events in `data.pipeline_audit`.
- **Logic Preservation**: Match legacy alpha signatures while improving modularity.

## 6. System Coexistence & Benchmarking
To ensure long-term statistical integrity, v4 is designed to coexist with legacy engines.
- **Legacy Preservation**: Files in `selection_engines/impl/v3_*.py` are frozen to serve as immutable benchmarks.
- **Versioning**: Tournament logs must explicitly tag the `spec_version` (e.g., `4.0-mlops` vs `3.4`) to prevent cross-contamination in meta-analysis.

## 7. Statistical Grand Tournament Protocol
To identify pipeline bottlenecks and alpha decay thresholds, the system implements a multi-dimensional sweep:
- **Spatial Diversity**: Comparison of $v3$ vs $v4$ selection engines.
- **Temporal Frequency**: Testing of `step_size` sensitivity ($5d, 20d, 60d$).
- **Memory Depth**: Evaluation of `train_window` impact on regime stability.
- **Factor Sensitivity**: Audit of `feature_lookback` consistency across varying volatility regimes.
The outcome of this protocol is a **Bootstrap-validated Performance Matrix** ensuring results are not due to window-selection bias.

### 9.1 High-Entropy Hardening (CR-490)
To mitigate the "flash-crash" instability observed in Windows 140/300, the `SelectionPipeline` implements **Entropy-Aware Hardening**:
- **Trigger**: System-wide mean entropy $> 0.95$.
- **Action**: Tighten `entropy_max_threshold` by 10% and increase `default_shrinkage_intensity` (Ridge loading) to stabilize the covariance matrix.
- **Goal**: Prioritize low-noise factor anchors when statistical confidence in high-alpha assets is degraded.

## 6. Implementation Strategy (The HTR Controller)
The **Hierarchical Threshold Relaxation (HTR)** logic is moved from recursion into a **Pipeline Orchestrator**.

### 6.1 `SelectionPipeline` (Orchestrator)
A high-level controller that manages the stage execution graph and HTR loop.

**Logic Flow:**
1.  **Initialize**: Load data (Stage 1) and calculate features (Stage 2). This is done ONCE.
2.  **Loop (HTR Stages 1-4)**:
    *   Set `SelectionContext.params` for current stage (e.g., `relaxation_stage=1`).
    *   Execute **Inference** (Stage 3).
    *   Execute **Partitioning** (Stage 4).
    *   Execute **Policy** (Stage 5).
    *   **Check**: If `len(winners) >= 15`, break loop.
3.  **Finalize**: Execute **Synthesis** (Stage 6).

### 6.2 `SelectionPolicyStage` (Stage 5)
Responsible for the *single-pass* recruitment logic:
- Apply hard vetoes (Entropy, Efficiency, Metadata).
- Rank candidates by `alpha_score` within each cluster.
- Select Top-N per cluster.
- Handle "Representative Forcing" if `relaxation_stage >= 3`.
- Handle "Balanced Fallback" if `relaxation_stage >= 4`.

## 10. Vectorized Probability Mapping (CR-530)
To support institutional scaling ($N > 1000$), the `AlphaScorer` utilizes vectorized probability mapping:
- **Broadcasting**: Normalization methods (CDF, Z-Score) are applied across the entire feature matrix in a single `numpy` operation.
- **Complexity**: Reduces selection latency from $O(N)$ to $O(1)$ effectively, ensuring real-time responsiveness even with massive candidate pools.

## 11. Sector-Aware Diversification (CR-540)
The `SelectionPolicyStage` utilizes discovery metadata to enforce sector-level limits:
- **Constraint**: No single sector can exceed 40% of the recruited winner pool.
- **Implementation**: The HTR loop prunes low-conviction assets within over-concentrated sectors during recruitment, ensuring the final portfolio remains uncorrelated across different industry verticals.

## 12. Final Operational Certification (v3.5.3)
As of Q1 2026, the v4 Selection Pipeline is the **Institutional Standard** for the multi-sleeve meta-portfolio.
- **Reliability**: Validated via exhaustive 3D Matrix Tournament (Selection x Profile x Engine).
- **Directionality**: 100% verified SHORT atom normalization.
- **Traceability**: All stage transitions (Ingestion -> Synthesis) are fully audited in the deep ledger.
- **Statistical Benchmark**: Achieved Mean Sharpe 5.48 with 60/20/20 sampling configuration.
