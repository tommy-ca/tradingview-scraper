# Specification: Multi-Sleeve Meta-Portfolio (v1)

## 1. Objective
To build robust, diversified meta-portfolios by combining independent strategy sleeves (e.g. Instruments, ETF Proxies, FX) using Hierarchical Risk Parity (HRP) at the sleeve level. This prevents capital concentration and handles disparate market calendars elegantly.

## 2. Architecture: Two-Layer Optimization

### Layer 1: Intra-Sleeve Optimization
- **Definition**: Each sleeve is an independent "Atom" with its own discovery pipelines and selection logic.
- **Output**: A single return series $R_{sleeve, t}$ representing the performance of the sleeve's optimal portfolio (e.g., the `skfolio/barbell` result).
- **Providence**: Derived from the latest production run or tournament results.

### Layer 2: Inter-Sleeve Allocation (Meta)
- **Mechanism**: Hierarchical Risk Parity (HRP) or Equal Risk Contribution (ERC).
- **Input**: A Meta-Returns matrix $R_{meta}[t, sleeve\_id]$.
- **Constraint**: Sleeves must be aligned on a common calendar (TradFi-aligned preferred for macro sleeves).
- **Output**: Sleeve weights $\omega_{sleeve}$ such that $\sum \omega_{sleeve} = 1.0$.

## 3. Data Contracts

### 3.1 Sleeve Returns Path
Sleeve returns are extracted from tournament pickles:
- Path: `artifacts/summaries/runs/<RUN_ID>/data/returns/<simulator>_<engine>_<profile>.pkl`

### 3.2 Meta-Manifest (`manifest.json`)
The `meta_portfolio` profile defines the constituent sleeves:
```json
"meta_production": {
  "description": "Multi-Sleeve Meta-Portfolio",
  "sleeves": [
    {
      "id": "instruments",
      "profile": "production",
      "weight_limit": [0.2, 0.8]
    },
    {
      "id": "etf_proxies",
      "profile": "institutional_etf",
      "weight_limit": [0.2, 0.6]
    }
  ],
  "meta_allocation": "hrp"
}
```

## 4. Operational Workflow

1.  **Stage 1: Sleeve Execution**
    - Run `make flow-production PROFILE=production`
    - Run `make flow-production PROFILE=institutional_etf`
2.  **Stage 2: Meta-Returns Construction**
    - Script: `scripts/build_meta_returns.py`
    - **Intersection Policy**: The Meta-Returns matrix must only contain dates where ALL constituent sleeves have valid data.
    - Aggregates the `benchmark` or `barbell` returns from both runs.
3.  **Stage 3: Meta-Allocation**
    - Script: `scripts/optimize_meta_portfolio.py`
    - Computes sleeve weights using HRP.
4.  **Stage 4: Weight Flattening**
    - **Proportional Exposure**: Generates final asset weights: $w_{i, final} = \omega_{sleeve} \times w_{i, sleeve}$.
    - If a symbol exists in multiple sleeves, weights are additive.

## 5. Acceptance Criteria
- **Correlation Benefit**: The Meta-Portfolio must show lower volatility than the best individual sleeve.
- **Reproducibility**: The meta-allocation must be logged in the `audit.jsonl` of the meta-run.
- **Integrity**: Weekend padding must not be introduced; TradFi calendars must remain sparse.
