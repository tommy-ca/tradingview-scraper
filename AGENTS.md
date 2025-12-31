# AI Agent Guide: Quantitative Portfolio Platform

This document provides a comprehensive guide for AI agents working on the TradingView Scraper quantitative platform. It codifies the institutional workflows, risk engine logic, and implementation standards developed for multi-asset portfolio management.

## 1. Core Pipeline Workflow

The entire production lifecycle is unified under the `make clean-run` target. Agents should adhere to this sequence to ensure data integrity and de-risked allocation.

### The 14-Step Production Sequence
1.  **Cleanup**: Wipe previous artifacts (`data/lakehouse/portfolio_*`).
2.  **Discovery**: Run multi-asset scanners. **Audit Gate**: Verifies scanner success.
3.  **Aggregation**: Consolidate scans into a **Raw Pool** with rich metadata.
4.  **Lightweight Prep**: Fetch **60-day** history for the raw pool.
5.  **Natural Selection (Pruning)**: Hierarchical clustering + Global XS Ranking. **Audit Gate**: Verifies leader survival.
6.  **Enrichment**: Propagate sectors, industries, and descriptions.
7.  **High-Integrity Prep**: Fetch **500-day** secular history for winners.
8.  **Health Audit**: Validate 100% gap-free alignment. **Self-Healing**: Automated recovery loop if gaps found.
9.  **Factor Analysis**: Build hierarchical risk buckets (Ward Linkage).
10. **Regime Detection**: Multi-factor analysis (Entropy + DWT).
11. **Optimization**: Cluster-Aware allocation with Turnover Control. **Audit Gate**: Verifies profile integrity.
12. **Validation**: Walk-Forward "Tournament" benchmarking (High-Fidelity).
13. **Reporting**: QuantStats Tear-sheets + Alpha Isolation Audit.
14. **Audit Verification**: Final cryptographic signature check of the run's decision ledger.

---

## 2. Configuration & Reproducibility

The platform uses a schema-validated JSON manifest system to ensure every run is perfectly reproducible.

### Workflow Profiles (configs/manifest.json)
- **`production`**: Institutional high-integrity settings (500d history, 252d train, 25% global caps, all optimizers enabled).
- **`production_v2_canary`**: Early-access profile with **Feature Flags** enabled (Turnover Penalty, XS Momentum, Spectral Regimes).
- **`repro_dev`**: Lightweight development profile for fast end-to-end testing (60d history, 50 symbol limit).

### Execution
Agents should prioritize profile-based execution via the CLI:
```bash
make daily-run PROFILE=production
```

---

## 3. Decision Logic & Specifications

### A. Immutable Market Baseline
The platform enforces an immutable **Market Baseline Engine**. This baseline loads raw data directly and forces LONG direction, providing an absolute yardstick regardless of scanner sentiment.

### B. Tiered Natural Selection
Pruning happens statistically *before* deep backfilling to optimize rate limits.
- **Pass 1 (60d)**: Captures tactical correlation and momentum.
- **Pass 2 (500d)**: Captures secular tail-risk and stable risk-parity weights over a full trading year (252d training window).

### C. Advanced Risk Engine
The system moves beyond simple MPT by treating clusters as single units of risk.
- **Cluster Caps**: Strictly enforced **25% gross weight** per hierarchical bucket.
- **Fragility Penalty**: Mathematically penalizes weights in sectors with high **Expected Shortfall (CVaR)**.
- **Adaptive Bucketing**: Clustering distance threshold tightens during `CRISIS` regimes (0.3) and loosens during `QUIET` regimes (0.5).

---

## 4. Reporting & Implementation Tools

### Institutional Dashboards
- **Strategy Resume (`backtest_comparison.md`)**: Unified dashboard derived from the 3D Tournament Matrix.
- **Selection Audit (`selection_audit.md`)**: Full trace of every merging and selection decision.
- **QuantStats Tear-sheets**: Automated Markdown teardowns for all tournament winners and the market baseline.

### Rebalancing & Health
- **Data Quality Gate**: `strict_health: true` ensures no portfolio is generated if data gaps persist.
- **Self-Healing**: Step 8 automatically triggers `make recover` for automated gap repair and matrix alignment.

---

## 5. Key Developer Commands

| Command | Purpose |
| :--- | :--- |
| `make daily-run` | Master entry point for production lifecycle. |
| `make reports` | Generate unified quantitative and analysis reports. |
| `make tournament` | Run 3D benchmarking matrix (Engine x Simulator x Profile). |
| `make recover` | High-intensity repair for degraded assets. |
| `make gist` | Synchronize essential artifacts to private implementation Gist. |

---

## 6. Strategic Guiding Principles for Agents

1.  **Alpha must survive friction**: Prioritize optimization engines that maintain Sharpe ratio stability in high-fidelity simulation. Use `feat_turnover_penalty` to minimize churn.
2.  **Spectral Intelligence**: Prioritize spectral (DWT) and entropy metrics for regime detection over simple volatility ratios. Use `feat_spectral_regimes` for adaptive scaling.
3.  **Execution Integrity**: Use `feat_partial_rebalance` to avoid noisy small trades. Generate implementation orders via `scripts/track_portfolio_state.py --orders`.
4.  **Provenance First**: Always verify that the `manifest.json` has been archived in the run directory.
5.  **Audit Integrity**: Every production decision must be backed by an entry in the `audit.jsonl` ledger. Never bypass the audit chain for manual weight overrides.
6.  **No Padding**: Ensure the returns matrix preserves real trading calendars; never zero-fill weekends for TradFi assets.
