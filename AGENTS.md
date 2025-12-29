# AI Agent Guide: Quantitative Portfolio Platform

This document provides a comprehensive guide for AI agents working on the TradingView Scraper quantitative platform. It codifies the institutional workflows, risk engine logic, and implementation standards developed for multi-asset portfolio management.

## 1. Core Pipeline Workflow

The entire production lifecycle is unified under the `make clean-run` target. Agents should adhere to this sequence to ensure data integrity and de-risked allocation.

### The 13-Step Production Sequence
1.  **Cleanup**: Wipe previous artifacts (`data/lakehouse/portfolio_*`).
2.  **Discovery**: Run multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Aggregation**: Consolidate scans into a **Raw Pool** with canonical identity merging (Venue Neutrality).
4.  **Lightweight Prep**: Fetch **60-day** history for the raw pool to establish baseline correlations.
5.  **Natural Selection (Pruning)**: Hierarchical clustering on the raw pool; select **Top 3 Assets** per cluster using **Execution Intelligence**.
6.  **Enrichment**: Propagate sectors, industries, and descriptions to the filtered winners.
7.  **High-Integrity Prep**: Fetch **200-day** secular history for winners with automated gap-repair.
8.  **Health Audit**: Validate 100% gap-free alignment for the implementation universe.
9.  **Factor Analysis**: Build hierarchical risk buckets using **Ward Linkage** and **Adaptive Thresholds**.
10. **Regime Detection**: Multi-factor analysis (**Entropy + DWT Spectral Turbulence**).
11. **Optimization**: Cluster-Aware V2 allocation with **Fragility (CVaR) Penalties**, supported by a multi-engine benchmarking framework (`skfolio`, `Riskfolio`, `PyPortfolioOpt`, `cvxportfolio`).
12. **Validation**: Run `make tournament` to benchmark multiple optimization backends against the custom baseline.
13. **Reporting**: Generate Implementation Dashboard, Strategy Resume, and sync to private Gist.

---

## 2. Configuration & Reproducibility

The platform uses a schema-validated JSON manifest system to ensure every run is perfectly reproducible.

### Workflow Profiles (configs/manifest.json)
- **`production`**: Institutional high-integrity settings (200d history, 25% global caps, all optimizers enabled).
- **`repro_dev`**: Lightweight development profile for fast end-to-end testing (40d history, 50 symbol limit).

### Execution
Agents should prioritize profile-based execution via the CLI:
```bash
make daily-run PROFILE=production
```

---

## 2. Decision Logic & Specifications

### A. Canonical Asset Merging
Redundant venues (e.g., `BINANCE:ETHUSDT`, `OKX:ETHUSDT`) are merged into a single economic identity.
- **Winner**: Selected via **Discovery Alpha Score** (`Liquidity + Trend + Performance`).
- **Liquidity Factor**: Incorporation of **Execution Intelligence** (Value Traded + Spread Proxy) into the winner selection.
- **Persistence**: Alternatives are stored in metadata for future liquidity routing or statsarb research.

### B. Tiered Natural Selection
Pruning happens statistically *before* deep backfilling to optimize rate limits.
- **Pass 1 (60d)**: Captures tactical correlation and momentum.
- **Pass 2 (200d)**: Captures secular tail-risk and stable risk-parity weights.

### C. Advanced Risk Engine
The system moves beyond simple MPT by treating clusters as single units of risk.
- **Cluster Caps**: Strictly enforced **25% gross weight** per hierarchical bucket.
- **Fragility Penalty**: Mathematically penalizes weights in sectors with high **Expected Shortfall (CVaR)**.
- **Adaptive Bucketing**: Clustering distance threshold ($t$) tightens during `CRISIS` regimes (0.3) and loosens during `QUIET` regimes (0.5).
- **Factor Neutrality**: Every profile includes a **Beta to Market (SPY)** audit to monitor systemic exposure.

---

## 3. Reporting & implementation Tools

### Institutional Dashboards
- **CLI Dashboard (`make display`)**: Real-time terminal view for implementing oversight.
- **Strategy Dashboard (`artifacts/summaries/latest/portfolio_report.md`)**: Grouped by Asset Class with visual concentration bars.
- **Selection Audit (`artifacts/summaries/latest/selection_audit.md`)**: Full trace of every merging and selection decision.
- **Backtest Validator**: `scripts/backtest_engine.py` provides walk-forward validation of returns and volatility.

### Rebalancing & Health
- **Drift Monitor (`make drift-monitor`)**: Tracks "Last Implemented" vs. "Current Optimal" and provides BUY/SELL signals.
- **Data Health (`artifacts/summaries/latest/data_health_selected.md`)**: Verifies 100% alignment integrity.
- **Self-Healing**: `scripts/repair_portfolio_gaps.py` includes 429 exponential backoff and multi-pass repair.

---

## 4. Key Developer Commands

| Command | Purpose |
| :--- | :--- |
| `make clean-run` | Execute full production lifecycle. |
| `make audit` | Verify logic constraints (Caps, Insulation, Weights). |
| `make backtest` | Run walk-forward validator (optional). |
| `make validate` | Audit data integrity and freshness. |
| `make recover` | High-intensity repair for degraded assets. |
| `make tournament` | Run multi-engine benchmarking benchmark. |
| `make drift-monitor` | Analyze rebalancing requirements. |
| `make gist` | Synchronize artifacts to private GitHub Gist. |

---

## 5. Strategic Guiding Principles for Agents

1.  **Redundancy is Risk**: Always cluster before allocating. Ticker counting leads to systemic fragility.
2.  **Spectral Intelligence**: Prioritize spectral (DWT) and entropy metrics for regime detection over simple volatility ratios.
3.  **Self-Healing Data**: Never trust raw data alignment. Always run `make validate` before generating a final report.
4.  **Lead with Alpha**: Within clusters, always select the instrument with the highest composite rank of **Momentum, Stability, and Convexity**, while respecting **Execution Intelligence** (Liquidity).
5.  **Validation First**: Never recommend a profile for implementation if its realized Win Rate in the last 2 walk-forward windows is below 25%.
