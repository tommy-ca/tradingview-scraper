# AI Agent Guide: Quantitative Portfolio Platform

This document provides a comprehensive guide for AI agents working on the TradingView Scraper quantitative platform. It codifies the institutional workflows, risk engine logic, and implementation standards developed for multi-asset portfolio management.

## 1. Core Pipeline Workflow

The entire production lifecycle is unified under the `make clean-run` target. Agents should adhere to this sequence to ensure data integrity and de-risked allocation.

### The 12-Step Production Sequence
1.  **Cleanup**: Wipe previous artifacts (`data/lakehouse/portfolio_*`).
2.  **Discovery**: Run multi-asset scanners (Equities, Crypto, Bonds, MTF Forex).
3.  **Aggregation**: Consolidate scans into a **Raw Pool** with canonical identity merging (Venue Neutrality).
4.  **Lightweight Prep**: Fetch **60-day** history for the raw pool to establish baseline correlations.
5.  **Natural Selection (Pruning)**: Hierarchical clustering on the raw pool; select **Top 3 Assets** per cluster.
6.  **Enrichment**: Propagate sectors, industries, and descriptions to the filtered winners.
7.  **High-Integrity Prep**: Fetch **200-day** secular history for winners with automated gap-repair.
8.  **Health Audit**: Validate 100% gap-free alignment for the implementation universe.
9.  **Factor Analysis**: Build hierarchical risk buckets using **Ward Linkage** and **Adaptive Thresholds**.
10. **Regime Detection**: multi-factor analysis (**Entropy + DWT Spectral Turbulence**).
11. **Optimization**: Cluster-Aware V2 allocation with **Fragility (CVaR) Penalties**.
12. **Reporting**: Generate Implementation Dashboard, Decision Audit, and sync to private Gist.

---

## 2. Decision Logic & Specifications

### A. Canonical Asset Merging
Redundant venues (e.g., `BINANCE:ETHUSDT`, `OKX:ETHUSDT`) are merged into a single economic identity.
- **Winner**: Selected via **Discovery Alpha Score** (`Liquidity + Trend + Performance`).
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

---

## 3. Reporting & implementation Tools

### Institutional Dashboards
- **CLI Dashboard (`make display`)**: Real-time terminal view for implementing oversight.
- **Strategy Dashboard (`summaries/portfolio_report.md`)**: Grouped by Asset Class with visual concentration bars.
- **Selection Audit (`summaries/selection_audit.md`)**: Full trace of every merging and selection decision.

### Rebalancing & Health
- **Drift Monitor (`make drift-monitor`)**: Tracks "Last Implemented" vs. "Current Optimal" and provides BUY/SELL signals.
- **Data Health (`summaries/data_health_selected.md`)**: Verifies 100% alignment integrity.

---

## 4. Key Developer Commands

| Command | Purpose |
| :--- | :--- |
| `make clean-run` | Execute full production lifecycle. |
| `make audit` | Verify logic constraints (Caps, Insulation, Weights). |
| `make validate` | Audit data integrity and freshness. |
| `make recover` | High-intensity repair for degraded assets. |
| `make drift-monitor` | Analyze rebalancing requirements. |
| `make gist` | Synchronize artifacts to private GitHub Gist. |

---

## 5. Strategic Guiding Principles for Agents

1.  **Redundancy is Risk**: Always cluster before allocating. Ticker counting leads to systemic fragility.
2.  **Spectral Intelligence**: Prioritize spectral (DWT) and entropy metrics for regime detection over simple volatility ratios.
3.  **Self-Healing Data**: Never trust raw data alignment. Always run `make validate` before generating a final report.
4.  **Lead with Alpha**: Within clusters, always select the instrument with the highest composite rank of **Momentum, Stability, and Convexity**.
