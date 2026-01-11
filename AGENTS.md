# AI Agent Guide: Quantitative Portfolio Platform

This document provides a comprehensive guide for AI agents working on the TradingView Scraper quantitative platform. It codifies the institutional workflows, risk engine logic, and implementation standards developed for multi-asset portfolio management.

## 1. Core Pipeline Workflow

The entire production lifecycle is unified under the `make flow-production` target. Agents should adhere to this sequence to ensure data integrity and de-risked allocation.

### The 15-Step Production Sequence
1.  **Cleanup**: Wipe incremental artifacts (`make clean-run`).
2.  **Composition & Discovery**: Execute layered scanners (`make scan-run`).
3.  **Aggregation**: Consolidate scans into Raw Pool (`make data-prep-raw`).
4.  **Metadata Enrichment**: Synchronize with institutional catalogs and apply defaults to prevent technical vetoes.
5.  **Natural Selection**: Darwinian filtering (Log-MPS 3.2) with **Benchmark Isolation** (Scanned Alpha only).
6.  **High-Integrity Prep**: Fetch 500-day secular history.
7.  **Health Audit**: Validate 100% gap-free alignment using Market-Day normalization (+4h shift).
8.  **Self-Healing**: Automated recovery loop if gaps found (`make data-repair`).
9.  **Persistence Analysis**: Research trend and mean-reversion persistent duration (`make research-persistence`).
10. **Factor Analysis**: Build hierarchical risk buckets (`make port-analyze`).
11. **Regime Detection**: Multi-factor state analysis.
12. **Optimization**: Cluster-Aware allocation (`make port-optimize`).
13. **Validation**: Walk-Forward Tournament benchmarking (`make port-test`).
14. **Reporting**: QuantStats Tear-sheets & Alpha Audit (`make port-report`).
15. **Audit Verification**: Final cryptographic signature check.

---

## 2. Configuration & Reproducibility

The platform uses a schema-validated JSON manifest system to ensure every run is perfectly reproducible.

### Workflow Profiles (configs/manifest.json)
- **`production`**: Institutional high-integrity settings (500d history, 252d train, 25% global caps, all optimizers enabled).
- **`canary`**: Early-access profile with **Feature Flags** enabled (Spectral Regimes, Decay Audit).
- **`development`**: Lightweight profile for fast iteration (60d history, 50 symbol limit).

### Feature Toggles (CLI Overrides)
For tactical runs, use environment variables or Makefile shortcuts instead of editing the manifest.

| Shortcut | Environment Variable | Purpose |
| :--- | :--- | :--- |
| `VETOES=1` | `TV_FEATURES__FEAT_PREDICTABILITY_VETOES=1` | Enable strict alpha-predictability filters. |
| `STRICT=1` | `TV_STRICT_HEALTH=1` | Veto any asset with even 1 missing bar. |
| `LOOKBACK=N` | `TV_LOOKBACK_DAYS=N` | Override secular history depth. |

### Execution
Agents should prioritize namespace-prefixed targets:
```bash
make flow-production PROFILE=production
```

### Logging & Visibility
Every step of the production sequence persists its full execution trace in the run directory:
- **Log Path**: `artifacts/summaries/runs/<RUN_ID>/logs/`
- **Real-time Progress**: The orchestrator parses log output to provide dynamic progress bars for long-running tasks.
- **Traceability**: All log paths are recorded in the `audit.jsonl` ledger for each step.

---

## 5. Key Developer Commands

| Command | Namespace | Purpose |
| :--- | :--- | :--- |
| `make flow-production` | **Flow** | Full institutional production lifecycle (Vectorized Simulators). |
| `make flow-prelive` | **Flow** | High-fidelity pre-live verification (includes Nautilus). |
| `make flow-dev` | **Flow** | Fast-path development execution. |
| `make scan-run` | **Scan** | Execute composed discovery scanners. |
| `make data-fetch` | **Data** | Ingest historical market data. |
| `make data-repair` | **Data** | High-intensity gap repair for degraded assets. |
| `make data-audit` | **Data** | Session-Aware health check. |
| `make research-persistence` | **Data** | Research trend and mean-reversion persistent duration. |
| `make port-optimize` | **Port** | Strategic asset allocation (Convex). |
| `make port-test` | **Port** | Execute 3D benchmarking tournament. |
| `make port-report` | **Port** | Generate unified quant reports. |
| `make report-sync` | **Report** | Synchronize artifacts to Gist. |
| `make clean-all` | **Clean** | Wipe all data, exports, and summaries. |
| `make clean-archive` | **Clean** | Archive old runs (keep 10) to `artifacts/archive`. |
| `make check-archive` | **Clean** | Dry-run archive to preview deletions. |


---

## 6. Strategic Guiding Principles for Agents

1.  **Alpha must survive friction**: Prioritize optimization engines that maintain Sharpe ratio stability in high-fidelity simulation. Use `feat_turnover_penalty` to minimize churn.
2.  **Spectral Intelligence**: Prioritize spectral (DWT) and entropy metrics for regime detection over simple volatility ratios. Use `feat_spectral_regimes` for adaptive scaling.
3.  **Execution Integrity**: Use `feat_partial_rebalance` to avoid noisy small trades. Generate implementation orders via `scripts/track_portfolio_state.py --orders`.
4.  **Provenance First**: Always verify that the `manifest.json` has been archived in the run directory.
5.  **Audit Integrity**: Every production decision must be backed by an entry in the `audit.jsonl` ledger. Never bypass the audit chain for manual weight overrides.
6.  **No Padding**: Ensure the returns matrix preserves real trading calendars; never zero-fill weekends for TradFi assets.

---

## 7. Selection Standards (The Alpha Core)

The platform supports multiple selection architectures, evaluated via head-to-head tournaments.

### Current Standards
- **Selection v3.2 (New Champion)**: **Log-Multiplicative Probability Scoring (Log-MPS)**.
    - Uses additive log-probabilities for numerical stability and HPO optimization.
    - **Global Robust**: Achieving the highest 2025 Annualized Return (29.2%) and Sharpe (2.35).
    - Features integrated spectral predictability filters (Entropy, Hurst, Efficiency).
- **Selection v2.1 (Stability Anchor)**: **Additive Rank-Sum (CARS 2.1)**. 
    - Uses **Multi-Method Normalization** (Logistic/Z-score/Rank).
    - Optimized for lower volatility and maximum drawdown protection.
- **Selection v3.1 (Legacy Alpha)**: Original Multiplicative Standard.

### Guiding Rule
Always prefer **Selection v3.2** for maximum alpha and regime-aware robustness. Use **Selection v2.1** for conservative "Core" profiles where drawdown minimization is the primary objective.

---

## 8. Crypto Sleeve Operations

The crypto sleeve operates as an orthogonal capital allocation within the multi-sleeve meta-portfolio architecture.

### Exchange Strategy
- **Production**: BINANCE-only for institutional crypto sleeve (highest liquidity, cleanest execution).
- **Research**: Multi-exchange (BINANCE/OKX/BYBIT/BITGET) configs available for experimentation.

### Key Commands
| Command | Purpose |
| :--- | :--- |
| `make flow-production PROFILE=crypto_production` | Full crypto-only production run |
| `make scan-run PROFILE=crypto_production` | Execute crypto discovery scanners |
| `make flow-meta-production` | Multi-sleeve run including crypto |

### Crypto-Specific Parameters
| Parameter | Crypto Value | TradFi Value | Rationale |
| :--- | :--- | :--- | :--- |
| `entropy_max_threshold` | 0.999 | 0.995 | Higher noise tolerance for microstructure |
| `backtest_slippage` | 0.001 | 0.0005 | Higher volatility and wider spreads |
| `backtest_commission` | 0.0004 | 0.0001 | Typical CEX maker/taker fees |
| `feat_dynamic_selection` | false | true | Stable universe benefits crypto |

### Calendar Handling
- Crypto uses XCRY calendar (24x7, no holidays).
- When joining with TradFi sleeves in meta-portfolio, use **inner join** on dates.
- **Never zero-fill weekends** for crypto-TradFi correlation calculations.

### Production Pillars (Forensic Standards)
Agents must ensure every production run adheres to the following three pillars:
1.  **Regime Alignment**: The `step_size` must be **20 days** for crypto production to match the structural optimum identified via forensic audit (Sharpe 2.36).
2.  **Tail-Risk Mitigation**: Forensic validation proves that 20-day alignment provides the best balance between momentum capture and drawdown protection (-15.9% MaxDD).
3.  **Alpha Capture**: High-resolution factor isolation (threshold=0.35) ensures winners are orthogonal and high-conviction.

### Blacklisted Assets
- `BINANCE:PAXGUSDT.P`: Detached from gold tracking (correlation 0.44). Use `OKX:XAUTUSDT.P` for gold exposure.
