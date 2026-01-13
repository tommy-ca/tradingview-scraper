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

## 6. Implementation Strategy (The HTR Controller)
The **Hierarchical Threshold Relaxation (HTR)** logic is moved from recursion into a **Policy Controller**.
1. Initialize Pipeline with Stage 1 parameters.
2. Execute Pipeline.
3. Inspect `WinningUniverse`.
4. If $N < 15$ and Relaxation Limit not reached:
    - Update parameters for next stage.
    - Re-run from **Inference Stage** (preserving earlier features).
5. Output final manifest.
