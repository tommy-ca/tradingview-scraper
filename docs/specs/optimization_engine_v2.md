# Optimization Engine V2: Profile-Centric Allocation

The Profile-Centric Optimization Engine (v2) is an institutional-grade framework designed to handle venue redundancy and benchmark library-specific solver variance across disparate asset classes.

## 1. Profile-Centric Architecture (New Jan 2026)

As of the 4D Tournament Meta-Analysis, the framework has transitioned from engine-driven logic to a **Profile-First** model. Universal fallbacks have been removed to ensure that every backend library (`skfolio`, `riskfolio`, etc.) utilizes its own native solvers for each risk paradigm.

### Layer 1: Across Clusters (Factor Level)
The total capital is first distributed across high-level hierarchical risk buckets.
- **Max Cluster Cap (25%)**: Strictly enforced via linear constraints ($w_{cluster} \le 0.25$) to prevent systemic over-concentration.
- **Numerical Stability**: Standardized on **Tikhonov Regularization** ($10^{-6} \cdot I$) for all covariance matrices to ensure strictly positive definite inputs for convex solvers.
- **Turnover Control**: Implements an **L1-norm penalty** on weight changes relative to the previously implemented state:
  $$Penalty_{Turnover} = \lambda \cdot \sum |w_{t} - w_{t-1}|$$

### Core Institutional Profiles

#### 1. Hierarchical Risk Parity (HRP)
- **Library Native**: Uses `HierarchicalRiskParity` (skfolio) and native recursive bisection backends.
- **Goal**: Maintain stable risk contributions across the correlation tree.

#### 2. Native Risk Parity
- **Implementation**: Convex log-barrier equal risk contribution.
- **Solvers**: `RiskBudgeting` (skfolio), `rp_optimization` (riskfolio).
- **Rationale**: Superior stability during **TURBULENT** and **CRISIS** regimes (2025 winner).

#### 3. Research Baselines (Standardized EW)
- **`market` Profile**: Force-allocation to a single asset (**SPY**). Used as the absolute market yardstick.
- **`benchmark` Profile**: Equal-Weighting of the **entire unpruned candidate pool**. Used to isolate the value added by selection/pruning logic.

#### 4. Antifragile Barbell
- **Aggressor Sleeve (5-15%)**: Allocates to clusters with the highest **Antifragility Scores** (convexity leaders).
- **Core Sleeve (85-95%)**: Allocates to the remaining universe using the **HRP** profile.

## 2. Intra-Cluster Allocation (Instrument Level)
Within each factor, weight is distributed using a **Momentum-Volatility Hybrid**:
- **Formula**: $Weight \propto 0.5 \cdot InverseVolatility + 0.5 \cdot AlphaRank$.
- **Rationale**: Ensures the portfolio is anchored by stable instruments while rewarding the highest-momentum members within a correlated group.

## 3. Simulator Parity & Fidelity
All tournament profiles are validated across four synchronized simulators:
- **`cvxportfolio`**: The High-Fidelity standard (Linear transaction costs + N+1 alignment).
- **`nautilus` / `custom`**: Synchronized with **Turnover-Aware Friction** to ensure research parity.
- **`vectorbt`**: Vectorized rapid prototyping.

## 4. Decision Support & Audit Trace
- **Audit Ledger**: Every decision is cryptographically logged in `audit.jsonl`.
- **Atomic Renaming**: Ensures audit logs remain uncorrupted during multi-threaded optimization runs.
- **Atomic selection**: Every run archives its specific selection state for 100% provenance.
