# Requirements v3: Quantitative Portfolio Platform

## 1. The 3-Pillar Architecture
The platform is organized into three orthogonal pillars to ensure logical purity and numerical stability.

### Pillar 1: Universe Selection (Filtering)
- **Standard**: HTR v3.4.2 (Hierarchical Threshold Relaxation).
- **Goal**: Recruit a high-hygiene subset of assets with validated secular history.
- **Clustering**: Performed on raw asset returns to ensure factor diversity in the candidate pool.
- **Filtering Logic**:
    - **Strict Health**: Assets must meet strict data availability requirements.
    - **Predictability Vetoes**: Optional strict alpha-predictability filters.

### Pillar 2: Strategy Synthesis (Alpha Generation)
- **The Strategy Atom**: Smallest unit of alpha, defined as `(Asset, Logic)`. Each atom MUST have exactly ONE logic.
- **Synthetic Long Normalization**: SHORT return streams are inverted ($R_{syn} = -1 \times R_{raw}$) to ensure positive-alpha bias for solvers.
- **Composition**: Atoms can be ensembled into complex strategies (e.g., Long/Short pairs).
- **Directional Purity**: Synthetic shorts are treated as distinct positive-alpha streams.

### Pillar 3: Portfolio Allocation (Risk Layer)
- **Decision-Naive Solvers**: Mathematical engines (`skfolio`, `riskfolio`) that optimize provided streams without "market views".
- **Synthetic Hierarchical Clustering**: Clustering is performed on *synthesized* return streams to identify logic-space correlations.
- **Constraint Delegation**: Targets like **Market Neutrality** are handled as native solver constraints ($|w^T\beta| \le 0.15$), ensuring global optimality.

## 2. Selection Standards (The Alpha Core)

### Selection v3.4 (Stabilized HTR Standard)
- **Hierarchical Threshold Relaxation**: 4-stage relaxation loop (Strict -> Spectral -> Cluster Floor -> Alpha Fallback).
- **Numerical Hardening**: **Dynamic Ridge Scaling** (Iterative shrinkage) to bound Kappa < 5000.
- **Adaptive Resilience**: Default fallback to **ERC (Equal Risk Contribution)** safety profile.
- **Constraints**: $N \ge 15$ candidates to ensure stable convex optimization.

### Selection v3.2 (Log-MPS Core)
- **Deep Audit Standard**: Uses additive log-probabilities.
- **Preferred for**: Maximum alpha and regime-aware robustness.

### Selection v2.1 (Stability Anchor)
- **Additive Rank-Sum (CARS 2.1)**.
- **Normalization**: Multi-Method (Logistic/Z-score/Rank).
- **Preferred for**: Conservative "Core" profiles where drawdown minimization is primary.

## 3. Strategic Principles
1.  **Alpha must survive friction**: Optimization engines must maintain Sharpe ratio stability in high-fidelity simulation (slippage/commission).
2.  **Spectral Intelligence**: Use spectral (DWT) and entropy metrics for regime detection.
3.  **HTR Resilience**: Always utilize the HTR loop to prevent winner sparsity.
4.  **Execution Integrity**: Use `feat_partial_rebalance` to avoid noisy small trades.
5.  **Audit Integrity**: Every production decision must be backed by an entry in the `audit.jsonl` ledger.
6.  **No Padding**: Ensure the returns matrix preserves real trading calendars.

## 4. Modular Pipeline Architecture (v3.5+)

### 4.1 Design Principles
1. **Extend, Don't Duplicate**: All new modules must extend existing patterns (`BasePipelineStage`, `SelectionContext`).
2. **Single Responsibility**: Each stage/filter/ranker performs exactly one transformation.
3. **Composability**: Pipelines are chains of stages; stages can be swapped/reordered.
4. **Fractal Design**: Meta-portfolios treat sleeves as assets (recursive application).
5. **Audit Trail**: Every stage logs to `context.audit_trail`.

### 4.2 Core Abstractions

| Abstraction | Location | Contract |
| :--- | :--- | :--- |
| `BasePipelineStage` | `pipelines/selection/base.py` | `execute(context) -> context` |
| `SelectionContext` | `pipelines/selection/base.py` | Pydantic model with staged data slots |
| `BaseSelectionEngine` | `selection_engines/base.py` | `select(returns, candidates, stats, request) -> SelectionResponse` |
| `BaseRiskEngine` | `portfolio_engines/base.py` | `optimize(returns, clusters, meta, stats, request) -> EngineResponse` |
| `BaseFilter` | `pipelines/selection/filters/base.py` | `apply(context) -> context` (vetoes candidates) |
| `BaseRanker` | `pipelines/selection/rankers/base.py` | `rank(candidates, returns, strategy) -> ranked_candidates` |

### 4.3 Pipeline Modules

#### A. Discovery Pipeline (`pipelines/discovery/`)
- **Purpose**: Source candidate assets from external data providers.
- **Interface**: `BaseDiscoveryScanner.discover(params) -> List[CandidateMetadata]`.
- **Implementations**: `binance.py`, `tradingview.py`.

#### B. Selection Pipeline (`pipelines/selection/`)
- **Purpose**: Filter, score, and cluster candidates for portfolio construction.
- **Orchestrator**: `SelectionPipeline` with HTR loop.
- **Stages**: Ingestion → Feature Engineering → Inference → Clustering → Policy → Synthesis.
- **Sub-modules**:
    - `stages/`: Transformation stages.
    - `rankers/`: Scoring algorithms (MPS, Signal, Regime).
    - `filters/`: Veto policies (Darwinian, Spectral, Friction).

#### C. Meta-Portfolio Pipeline (`pipelines/meta/`)
- **Purpose**: Aggregate atomic sleeves into a unified portfolio.
- **Context**: `MetaContext` (extends `SelectionContext` with sleeve-level data).
- **Stages**: Sleeve Execution → Aggregation → Meta-Optimization → Flattening.
- **Key Classes**:
    - `SleeveAggregator`: Builds meta-returns matrix from sleeve performance.
    - `WeightFlattener`: Projects meta-weights to individual asset weights.

### 4.4 MLOps/Quant Vocabulary

| Term | Definition |
| :--- | :--- |
| **Strategy Atom** | `(Asset, Logic)` - Smallest unit of alpha. |
| **Sleeve** | An atomic portfolio (e.g., "Crypto Long", "US Equities Short"). |
| **Meta-Portfolio** | A portfolio of sleeves, optimized using Risk Parity. |
| **HTR Loop** | Hierarchical Threshold Relaxation - 4-stage filter relaxation. |
| **Synthetic Long** | SHORT returns inverted to positive-alpha streams. |
| **Regime** | Market environment classification (CRISIS, EXPANSION, STAGNATION, NORMAL). |
| **Quadrant** | Combination of Regime + Volatility (e.g., INFLATIONARY_TREND). |

## 5. Orchestration Layer (v3.6+)

### 5.1 Architecture Layers
The platform uses a layered orchestration architecture for scalability and observability:

```
┌────────────────────────────────────────────────────────────┐
│                   CLAUDE SKILL LAYER                       │
│  Addressable stage invocation via CLI/SDK                  │
│  URI: quant://pipeline/stage?run_id=abc&profile=crypto     │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│               WORKFLOW ENGINE (Prefect/DBOS)               │
│  DAG orchestration, automatic retries, task caching        │
│  State persistence, scheduling, observability              │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                  COMPUTE ENGINE (Ray)                      │
│  Parallel execution across workers                         │
│  Actor isolation for sleeves                               │
│  Distributed compute for large universes                   │
└────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────┐
│                   STAGE LOGIC LAYER                        │
│  BasePipelineStage, BaseRiskEngine, BaseFilter             │
│  Pure business logic, no orchestration concerns            │
└────────────────────────────────────────────────────────────┘
```

### 5.2 Callable/Addressable Stages

Every stage is registered with a unique identifier and can be invoked independently:

| Stage ID | Module | Purpose |
| :--- | :--- | :--- |
| `selection.ingestion` | `pipelines/selection/stages/ingestion.py` | Load candidates and returns |
| `selection.features` | `pipelines/selection/stages/feature_engineering.py` | Compute technical features |
| `selection.inference` | `pipelines/selection/stages/inference.py` | MPS/Signal scoring |
| `selection.clustering` | `pipelines/selection/stages/clustering.py` | Hierarchical clustering |
| `selection.policy` | `pipelines/selection/stages/policy.py` | Apply filter chain |
| `selection.synthesis` | `pipelines/selection/stages/synthesis.py` | Create strategy atoms |
| `meta.aggregation` | `pipelines/meta/aggregator.py` | Build meta-returns matrix |
| `meta.optimization` | `pipelines/meta/optimizer.py` | Meta-level risk parity |
| `meta.flattening` | `pipelines/meta/flattener.py` | Project to atom weights |

### 5.3 Invocation Methods

#### A. CLI Invocation
```bash
# Run single stage
quant stage run selection.ingestion --run-id abc --param profile=crypto_long

# List available stages
quant stage list --tag selection

# Get stage schema
quant stage schema selection.ingestion
```

#### B. SDK Invocation (Python)
```python
from tradingview_scraper.orchestration.sdk import QuantSDK

# Run single stage
context = QuantSDK.run_stage(
    "selection.ingestion",
    params={"profile": "crypto_long"},
    run_id="abc"
)

# Run full pipeline
context = QuantSDK.run_pipeline(
    "selection.full",
    params={"profile": "crypto_long"}
)
```

#### C. Prefect Flow (Scheduled/Observable)
```python
from tradingview_scraper.orchestration.flows.selection_flow import selection_flow

# Run as Prefect flow with retries and observability
result = selection_flow(run_id="abc", profile="crypto_long")
```

### 5.4 Ray Compute Patterns

| Pattern | Use Case | Module |
| :--- | :--- | :--- |
| `@ray.remote` task | Parallel stage execution | `orchestration/compute.py` |
| `@ray.remote` actor | Isolated sleeve execution | `orchestration/sleeve_executor.py` |
| `RayTaskRunner` | Prefect + Ray integration | `orchestration/flows/meta_flow.py` |

### 5.5 Workflow Engine Options

| Engine | Complexity | Features | Use Case |
| :--- | :--- | :--- | :--- |
| **Prefect** | Medium | DAG, Retry, UI, Scheduling | Production workflows |
| **DBOS** | Low | Transactional, Lightweight | Simple pipelines |
| **Manual** | None | None | Development/Testing |

### 5.6 Claude Skill Integration

Skills follow the [Agent Skills](https://agentskills.io) open standard, which is portable across Claude Code, OpenCode, and other compatible agents.

**Key Insight**: Skills are **SKILL.md files**, not Python functions. They are Markdown instructions that Claude reads and follows.

#### Skill Structure
```
.claude/skills/quant-select/
├── SKILL.md                    # Instructions + frontmatter (required)
└── scripts/
    └── run_pipeline.py         # Executable script (optional)
```

#### Available Skills

| Skill | Purpose | Invocation |
| :--- | :--- | :--- |
| `quant-select` | Run HTR selection pipeline | `/quant-select crypto_long` |
| `quant-backtest` | Run historical simulation | `/quant-backtest <run_id>` |
| `quant-discover` | Discover candidate assets | `/quant-discover binance_spot` |
| `quant-optimize` | Run portfolio optimization | `/quant-optimize <run_id>` |

#### SKILL.md Format (Agent Skills Standard)

```markdown
---
name: quant-select                    # 1-64 chars, lowercase, hyphens
description: Run the selection...     # 1-1024 chars, when to use
compatibility: Claude Code
allowed-tools: Bash(python:*) Read
---

# Instructions for Claude to follow...
```

#### Progressive Disclosure

Skills use progressive disclosure to minimize context usage:
1. **Discovery** (~100 tokens): Only `name` + `description` loaded at startup
2. **Activation** (<5000 tokens): Full SKILL.md loaded when invoked
3. **Execution** (on-demand): Referenced files loaded as needed

See: `docs/design/claude_skills_v1.md` for complete specification.
